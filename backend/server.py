"""
Saree Photography — Flask Backend
Runs on http://127.0.0.1:5050
"""

import csv
import os
import sys
import uuid
import subprocess
from datetime import date, timedelta
from pathlib import Path
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

# ── CORS (no flask-cors needed) ────────────────────────────────────────────────
@app.after_request
def cors(r):
    r.headers['Access-Control-Allow-Origin']  = '*'
    r.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    r.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    return r

@app.route('/api/<path:p>', methods=['OPTIONS'])
def options(p): return '', 204

# ── Paths ──────────────────────────────────────────────────────────────────────
# Works in dev (script runs from SareePhotography/) and packaged (PyInstaller)
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    ROOT = Path(sys.executable).parent.parent.parent
else:
    ROOT = Path(__file__).parent.parent

DATA_FILE = ROOT / 'data'      / 'events.csv'
INVOICES  = ROOT / 'invoices'
CALENDARS = ROOT / 'calendars'

FIELDS = [
    'booking_id', 'client_name', 'contact_number', 'booking_date',
    'event_type', 'event_venue', 'event_time',
    'start_date', 'end_date', 'packages',
    'package_amount', 'advance1', 'advance2', 'balance_due', 'payment_status',
    'album_type', 'album_count', 'frame_12x18', 'frame_16x24', 'frame_20x30',
    'calendar_addon', 'package_tier', 'invoice_path',
]

PKG_LABELS = {
    'traditional_photo':  'Traditional Photo',
    'candid_photo':       'Candid Photo',
    'drone':              'Drone',
    'outdoor_photoshoot': 'Outdoor Photoshoot',
    'traditional_video':  'Traditional Video',
    'candid_video':       'Candid Video',
    'led_tv':             'LED TV',
    'outdoor_video':      'Outdoor Video Shoot',
}

# ── Helpers ────────────────────────────────────────────────────────────────────
def ensure():
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    INVOICES.mkdir(parents=True, exist_ok=True)
    CALENDARS.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        with open(DATA_FILE, 'w', newline='', encoding='utf-8') as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()

def read_all():
    ensure()
    with open(DATA_FILE, 'r', newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def write_all(rows):
    with open(DATA_FILE, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in FIELDS})

def calc_balance(b):
    try:
        amt  = float(b.get('package_amount') or 0)
        adv1 = float(b.get('advance1') or 0)
        adv2 = float(b.get('advance2') or 0)
        b['balance_due'] = str(round(amt - adv1 - adv2, 2))
    except Exception:
        b['balance_due'] = '0'

def date_set(s: date, e: date):
    return {s + timedelta(days=i) for i in range((e - s).days + 1)}

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route('/api/ping')
def ping(): return jsonify({'ok': True})

@app.route('/api/bookings')
def list_bookings():
    rows = read_all()
    rows.sort(key=lambda r: r.get('start_date', ''), reverse=True)
    return jsonify(rows)

@app.route('/api/bookings/<bid>')
def get_booking(bid):
    for r in read_all():
        if r['booking_id'] == bid: return jsonify(r)
    return jsonify({'error': 'not found'}), 404

@app.route('/api/bookings', methods=['POST'])
def create_booking():
    data = request.json
    data['booking_id']   = str(uuid.uuid4())[:8].upper()
    data['booking_date'] = date.today().isoformat()
    calc_balance(data)
    rows = read_all(); rows.append(data); write_all(rows)
    return jsonify(data), 201

@app.route('/api/bookings/<bid>', methods=['PUT'])
def update_booking(bid):
    data = request.json
    data['booking_id'] = bid
    calc_balance(data)
    rows = read_all()
    rows = [data if r['booking_id'] == bid else r for r in rows]
    write_all(rows)
    return jsonify(data)

@app.route('/api/bookings/<bid>', methods=['DELETE'])
def delete_booking(bid):
    write_all([r for r in read_all() if r['booking_id'] != bid])
    return jsonify({'ok': True})

@app.route('/api/conflict', methods=['POST'])
def conflict():
    body = request.json
    try:
        s = date.fromisoformat(body['start_date'])
        e = date.fromisoformat(body['end_date'])
    except Exception:
        return jsonify({'conflicts': []})

    proposed   = date_set(s, e)
    exclude_id = body.get('exclude_id', '')
    conflicts  = []

    for b in read_all():
        if b.get('payment_status', '').upper() == 'CANCELLED': continue
        if b.get('booking_id') == exclude_id: continue
        try:
            overlap = proposed & date_set(
                date.fromisoformat(b['start_date']),
                date.fromisoformat(b['end_date'])
            )
        except Exception: continue
        if overlap:
            conflicts.append({
                'booking_id':     b['booking_id'],
                'client_name':    b['client_name'],
                'event_type':     b['event_type'],
                'clashing_dates': sorted(d.isoformat() for d in overlap),
            })

    return jsonify({'conflicts': conflicts})

@app.route('/api/stats')
def stats():
    rows   = read_all()
    active = [r for r in rows if r.get('payment_status', '').upper() != 'CANCELLED']
    total_adv = sum(
        (float(r.get('advance1') or 0) + float(r.get('advance2') or 0))
        for r in active
    )
    return jsonify({
        'total':           len(rows),
        'confirmed':       sum(1 for r in rows if r.get('payment_status','').upper() == 'CONFIRMED'),
        'cancelled':       sum(1 for r in rows if r.get('payment_status','').upper() == 'CANCELLED'),
        'completed':       sum(1 for r in rows if r.get('payment_status','').upper() == 'COMPLETED'),
        'revenue':         sum(float(r.get('package_amount') or 0) for r in active),
        'total_advance':   total_adv,
        'pending_balance': sum(float(r.get('balance_due') or 0) for r in active
                               if r.get('payment_status','').upper() == 'CONFIRMED'),
    })

@app.route('/api/invoice/<bid>', methods=['POST'])
def gen_invoice(bid):
    rows    = read_all()
    booking = next((r for r in rows if r['booking_id'] == bid), None)
    if not booking: return jsonify({'error': 'not found'}), 404
    try:
        p = make_pdf(booking)
        booking['invoice_path'] = p
        write_all([booking if r['booking_id'] == bid else r for r in rows])
        return jsonify({'path': p})
    except Exception as ex:
        return jsonify({'error': str(ex)}), 500

@app.route('/api/calendar/<bid>', methods=['POST'])
def gen_calendar(bid):
    for r in read_all():
        if r['booking_id'] == bid:
            try:
                p = make_ics(r)
                return jsonify({'path': p})
            except Exception as ex:
                return jsonify({'error': str(ex)}), 500
    return jsonify({'error': 'not found'}), 404

@app.route('/api/paths')
def get_paths():
    """Return absolute paths so frontend can open folders."""
    return jsonify({
        'invoices':  str(INVOICES.resolve()),
        'calendars': str(CALENDARS.resolve()),
        'data':      str(DATA_FILE.parent.resolve()),
    })

# ── PDF ────────────────────────────────────────────────────────────────────────
def make_pdf(b: dict) -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, HRFlowable
    )
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    INVOICES.mkdir(exist_ok=True)
    bid   = b.get('booking_id', 'XXXX')
    fname = f"Invoice_{bid}_{b.get('client_name','').replace(' ','_')}.pdf"
    path  = str(INVOICES / fname)

    GOLD  = colors.HexColor('#c9a84c')
    DARK  = colors.HexColor('#0f0f1a')
    LGREY = colors.HexColor('#eeeeee')
    GREEN = colors.HexColor('#27ae60')
    RED   = colors.HexColor('#e74c3c')
    WHITE = colors.white

    def ps(name, **kw): return ParagraphStyle(name, **kw)

    doc = SimpleDocTemplate(path, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm,  bottomMargin=15*mm)
    story = []

    status = b.get('payment_status', '').upper()
    sc     = '#27ae60' if status == 'CONFIRMED' else ('#e74c3c' if status == 'CANCELLED' else '#c9a84c')

    # Header
    story.append(Table([[
        Paragraph(
            '<font size="22" color="#c9a84c"><b>SAREE PHOTOGRAPHY</b></font><br/>'
            '<font size="9" color="#888">Professional Wedding &amp; Event Photography</font><br/>'
            '<font size="9" color="#888">contact@sareephotography.in</font>',
            ps('hl', leading=16)),
        Paragraph(
            f'<font size="9" color="#888">INVOICE</font><br/>'
            f'<font size="16" color="#c9a84c"><b>#{bid}</b></font><br/>'
            f'<font size="9" color="#888">Date: {b.get("booking_date","")}</font><br/>'
            f'<font size="10" color="{sc}"><b>{status}</b></font>',
            ps('hr', alignment=TA_RIGHT, leading=14)),
    ]], colWidths=[115*mm, 70*mm]))
    story[-1].setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    story.append(HRFlowable(width='100%', thickness=2, color=GOLD, spaceAfter=6))

    if status == 'CANCELLED':
        story.append(Paragraph(
            '<font size="28" color="#e74c3c"><b>CANCELLED</b></font>',
            ps('cx', alignment=TA_CENTER)))
        story.append(Spacer(1, 4*mm))

    def section(title):
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph(
            f'<font size="11" color="#ffffff"><b>  {title}</b></font>',
            ps('sh', backColor=DARK, leftPadding=8, topPadding=5, bottomPadding=5)))
        story.append(Spacer(1, 2*mm))

    def info_table(rows, cw=None):
        cw = cw or [40*mm, 65*mm, 40*mm, 40*mm]
        t  = Table(rows, colWidths=cw)
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(0,-1),LGREY), ('BACKGROUND',(2,0),(2,-1),LGREY),
            ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
            ('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),9),
            ('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#cccccc')),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('TOPPADDING',(0,0),(-1,-1),5),
            ('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LEFTPADDING',(0,0),(-1,-1),6),
        ]))
        story.append(t)

    # Client
    section('CLIENT DETAILS')
    info_table([
        ['Client Name', b.get('client_name',''),   'Contact',      b.get('contact_number','')],
        ['Event Type',  b.get('event_type',''),     'Event Time',   b.get('event_time','')],
        ['Venue',       b.get('event_venue',''),    'Package Tier', b.get('package_tier','').upper()],
        ['Start Date',  b.get('start_date',''),     'End Date',     b.get('end_date','')],
    ])

    # Services
    section('SERVICES SELECTED')
    sel   = {p.strip() for p in b.get('packages','').split(',') if p.strip()}
    srows = [['#', 'Service', 'Included']]
    for i, (k, lbl) in enumerate(PKG_LABELS.items(), 1):
        srows.append([str(i), lbl, '✔' if k in sel else '—'])
    st = Table(srows, colWidths=[12*mm, 145*mm, 28*mm])
    st.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),DARK), ('TEXTCOLOR',(0,0),(-1,0),WHITE),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('ALIGN',(0,0),(-1,-1),'CENTER'), ('ALIGN',(1,0),(1,-1),'LEFT'),
        ('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,colors.HexColor('#fafafa')]),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),5), ('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(1,0),(1,-1),8),
    ]))
    story.append(st)

    # Add-ons
    section('ADD-ONS & EXTRAS')
    info_table([
        ['Album Type',  b.get('album_type','—'),  'Album Count',     b.get('album_count','—')],
        ['Frame 12×18', b.get('frame_12x18','0'), 'Frame 16×24',     b.get('frame_16x24','0')],
        ['Frame 20×30', b.get('frame_20x30','0'), 'Calendar Add-on', b.get('calendar_addon','No')],
    ])

    # Payment — now shows advance1 + advance2
    section('PAYMENT SUMMARY')
    try:
        amt  = float(b.get('package_amount') or 0)
        adv1 = float(b.get('advance1') or 0)
        adv2 = float(b.get('advance2') or 0)
        bal  = float(b.get('balance_due') or 0)
    except Exception:
        amt = adv1 = adv2 = bal = 0

    sc2 = GREEN if status == 'CONFIRMED' else (RED if status == 'CANCELLED' else GOLD)
    pt  = Table([
        ['Package Amount',    f'Rs. {amt:,.2f}'],
        ['Advance 1 (Paid)',  f'Rs. {adv1:,.2f}'],
        ['Advance 2 (Paid)',  f'Rs. {adv2:,.2f}'],
        ['Total Advance',     f'Rs. {adv1+adv2:,.2f}'],
        ['Balance Due',       f'Rs. {bal:,.2f}'],
        ['Payment Status',    status],
    ], colWidths=[100*mm, 85*mm])
    pt.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,-1),LGREY),
        ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),10),
        ('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#cccccc')),
        ('ALIGN',(1,0),(1,-1),'RIGHT'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),6), ('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LEFTPADDING',(0,0),(-1,-1),8), ('RIGHTPADDING',(0,0),(-1,-1),8),
        # Highlight total advance row
        ('BACKGROUND',(0,3),(-1,3),colors.HexColor('#e8f4e8')),
        ('FONTNAME',(0,3),(-1,3),'Helvetica-Bold'),
        # Highlight balance row
        ('BACKGROUND',(0,4),(-1,4),colors.HexColor('#fff3cd')),
        ('FONTSIZE',(0,4),(-1,4),12),
        ('FONTNAME',(0,4),(-1,4),'Helvetica-Bold'),
        # Status colour
        ('TEXTCOLOR',(1,5),(1,5),sc2),
        ('FONTNAME',(1,5),(1,5),'Helvetica-Bold'),
    ]))
    story.append(pt)
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width='100%', thickness=1, color=GOLD, spaceAfter=4))
    story.append(Paragraph(
        '<font size="8" color="#888">Thank you for choosing Saree Photography. '
        'Computer-generated invoice.</font>',
        ps('ft', alignment=TA_CENTER)))
    doc.build(story)
    return path

# ── ICS ────────────────────────────────────────────────────────────────────────
def make_ics(b: dict) -> str:
    CALENDARS.mkdir(exist_ok=True)
    bid   = b.get('booking_id', 'XXXX')
    fname = f"Event_{bid}_{b.get('client_name','').replace(' ','_')}.ics"
    path  = str(CALENDARS / fname)

    s    = date.fromisoformat(b['start_date'])
    e    = date.fromisoformat(b['end_date'])
    dend = e + timedelta(days=1)

    sel  = [p.strip() for p in b.get('packages','').split(',') if p.strip()]
    svcs = ', '.join(PKG_LABELS.get(p, p) for p in sel) or 'Photography'

    def esc(t):
        return str(t or '').replace('\\','\\\\').replace(';','\\;') \
                           .replace(',','\\,').replace('\n','\\n')

    adv1 = b.get('advance1', '0'); adv2 = b.get('advance2', '0')
    desc = '\\n'.join([
        f"Booking ID: {bid}",
        f"Client: {b.get('client_name','')}",
        f"Contact: {b.get('contact_number','')}",
        f"Type: {b.get('event_type','')}",
        f"Venue: {b.get('event_venue','')}",
        f"Services: {svcs}",
        f"Package: {b.get('package_tier','').upper()}",
        f"Amount: Rs.{b.get('package_amount',0)} | Adv1: Rs.{adv1} | Adv2: Rs.{adv2} | Balance: Rs.{b.get('balance_due',0)}",
        f"Status: {b.get('payment_status','').upper()}",
    ])

    ical_status = 'CANCELLED' if b.get('payment_status','').upper() == 'CANCELLED' else 'CONFIRMED'

    lines = [
        'BEGIN:VCALENDAR', 'VERSION:2.0',
        'PRODID:-//Shree Photography//EN',
        'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        f'UID:{bid}-{uuid.uuid4()}@sareephotography',
        f'SUMMARY:{esc("Shree Photography - " + b.get("client_name","") + " (" + b.get("event_type","") + ")")}',
        f'DESCRIPTION:{esc(desc)}',
        f'LOCATION:{esc(b.get("event_venue",""))}',
        f'DTSTART;VALUE=DATE:{s.strftime("%Y%m%d")}',
        f'DTEND;VALUE=DATE:{dend.strftime("%Y%m%d")}',
        f'STATUS:{ical_status}',
        'BEGIN:VALARM', 'TRIGGER:-P1D', 'ACTION:DISPLAY',
        f'DESCRIPTION:Reminder: {esc(b.get("client_name",""))} event tomorrow',
        'END:VALARM',
        'END:VEVENT', 'END:VCALENDAR',
    ]
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\r\n'.join(lines))
    return path

# ── Open file/folder ───────────────────────────────────────────────────────────
def open_path(p: str):
    if sys.platform == 'win32':   os.startfile(p)
    elif sys.platform == 'darwin': subprocess.Popen(['open', p])
    else:                          subprocess.Popen(['xdg-open', p])

# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    ensure()
    print('Shree Photography backend running on http://127.0.0.1:5050', flush=True)
    app.run(host='127.0.0.1', port=5050, debug=False)
