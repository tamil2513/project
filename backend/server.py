"""
Shree Photography — Flask Backend
Runs on http://127.0.0.1:5050
"""

import csv
import json as _json
import os
import sys
import uuid
import subprocess
from datetime import date, timedelta
from pathlib import Path
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

# ── CORS ──────────────────────────────────────────────────────────────────────
@app.after_request
def cors(r):
    r.headers['Access-Control-Allow-Origin']  = '*'
    r.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    r.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    return r

@app.route('/api/<path:p>', methods=['OPTIONS'])
def options(p): return '', 204

# ── Paths ──────────────────────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    ROOT = Path(sys.executable).parent.parent.parent
else:
    ROOT = Path(__file__).parent.parent

DATA_FILE = ROOT / 'data'      / 'events.csv'
INVOICES      = ROOT / 'invoices'
CALENDARS     = ROOT / 'calendars'
SETTINGS_FILE = ROOT / 'data' / 'settings.json'

def load_settings():
    try:
        if SETTINGS_FILE.exists():
            return _json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}

def save_settings_data(d):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(_json.dumps(d, indent=2), encoding='utf-8')

def get_invoices_dir():
    """Returns the configured invoice folder (custom path or default)."""
    custom = load_settings().get('invoices_dir', '').strip()
    if custom:
        p = Path(custom)
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            pass
    INVOICES.mkdir(parents=True, exist_ok=True)
    return INVOICES

FIELDS = [
    'booking_id', 'client_name', 'contact_number', 'booking_date',
    'event_type', 'event_venue', 'event_time',
    'start_date', 'end_date',
    'event_slots',                          # JSON: [{event_type,date,date_iso,time}]
    'packages',
    'package_amount', 'advance1', 'advance2', 'advances', 'total_advance',
    'balance_due', 'payment_status',
    'album_type', 'album_count',
    'frame_12x18', 'frame_16x24', 'frame_20x30',
    'frames',                               # JSON: [{w,h,qty}]
    'calendar_addon', 'package_tier', 'event_colour',
    'notes', 'invoice_path',
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
def iso_to_display(iso):
    """yyyy-mm-dd to dd/mm/yyyy"""
    if not iso: return ''
    try:
        y, m, d = iso.split('-')
        return f"{d}/{m}/{y}"
    except Exception:
        return iso

def display_to_iso(disp):
    """dd/mm/yyyy  ->  yyyy-mm-dd"""
    if not disp: return ''
    try:
        parts = disp.split('/')
        if len(parts) == 3:
            d, m, y = parts
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    except Exception:
        pass
    return disp

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
        amt = float(b.get('package_amount') or 0)
        advances_json = b.get('advances', '')
        if advances_json:
            try:
                advs = _json.loads(advances_json)
                total_adv = sum(float(a) for a in advs if a)
            except Exception:
                total_adv = float(b.get('advance1') or 0) + float(b.get('advance2') or 0)
        else:
            total_adv = float(b.get('advance1') or 0) + float(b.get('advance2') or 0)
        b['total_advance'] = str(round(total_adv, 2))
        b['balance_due']   = str(round(amt - total_adv, 2))
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
    # ── Permanent sequential ID: find max existing numeric ID and add 1 ────────
    rows = read_all()
    max_id = 0
    for r in rows:
        try:
            n = int(r.get('booking_id', '0'))
            if n > max_id: max_id = n
        except (ValueError, TypeError):
            pass
    data['booking_id']   = str(max_id + 1)   # permanent — never changes
    data['booking_date'] = date.today().isoformat()
    calc_balance(data)
    rows.append(data)
    write_all(rows)
    return jsonify(data), 201

@app.route('/api/bookings/<bid>', methods=['PUT'])
def update_booking(bid):
    data = request.json
    data['booking_id'] = bid     # preserve original ID
    calc_balance(data)
    rows = read_all()
    rows = [data if r['booking_id'] == bid else r for r in rows]
    write_all(rows)
    return jsonify(data)

@app.route('/api/bookings/<bid>', methods=['DELETE'])
def delete_booking(bid):
    # Find the booking first so we can get client name for .ics filename
    all_rows = read_all()
    booking  = next((r for r in all_rows if r['booking_id'] == bid), None)
    write_all([r for r in all_rows if r['booking_id'] != bid])
    # Delete matching .ics calendar file if it exists
    if booking:
        import glob
        # Match by booking_id prefix so name changes don't matter
        for ics in glob.glob(str(CALENDARS / f'Event_{bid}_*.ics')):
            try:
                Path(ics).unlink()
            except Exception:
                pass
    return jsonify({'ok': True})

@app.route('/api/conflict', methods=['POST'])
def conflict():
    body       = request.json
    exclude_id = body.get('exclude_id', '')

    # Accept either slot_dates list (new) or legacy start_date/end_date range
    slot_dates_raw = body.get('slot_dates')
    if slot_dates_raw:
        try:
            proposed = {date.fromisoformat(d) for d in slot_dates_raw if d}
        except Exception:
            return jsonify({'conflicts': []})
    else:
        try:
            s = date.fromisoformat(body['start_date'])
            e = date.fromisoformat(body['end_date'])
            proposed = date_set(s, e)
        except Exception:
            return jsonify({'conflicts': []})

    if not proposed:
        return jsonify({'conflicts': []})

    conflicts = []
    for b in read_all():
        if b.get('payment_status', '').upper() == 'CANCELLED': continue
        if b.get('booking_id') == exclude_id: continue
        # Build this booking's date set from its event_slots (exact dates) or range
        try:
            import json as _json
            b_dates = set()
            if b.get('event_slots'):
                for sl in _json.loads(b['event_slots']):
                    d = sl.get('date_iso','')
                    if d: b_dates.add(date.fromisoformat(d))
            if not b_dates:
                b_dates = date_set(
                    date.fromisoformat(b['start_date']),
                    date.fromisoformat(b['end_date'])
                )
        except Exception: continue
        overlap = proposed & b_dates
        if overlap:
            conflicts.append({
                'booking_id':     b['booking_id'],
                'client_name':    b['client_name'],
                'event_type':     b['event_type'],
                'clashing_dates': sorted(d.isoformat() for d in overlap),
            })
    return jsonify({'conflicts': conflicts})

@app.route('/api/paths')
def get_paths():
    return jsonify({
        'invoices':  str(get_invoices_dir().resolve()),
        'calendars': str(CALENDARS.resolve()),
        'data':      str(DATA_FILE.parent.resolve()),
    })

@app.route('/api/settings', methods=['GET'])
def get_settings():
    s = load_settings()
    s.setdefault('invoices_dir', '')
    return jsonify(s)

@app.route('/api/settings', methods=['POST'])
def post_settings():
    data = request.json or {}
    s = load_settings()
    if 'invoices_dir' in data:
        s['invoices_dir'] = data['invoices_dir']
    save_settings_data(s)
    return jsonify({'ok': True, 'invoices_dir': s.get('invoices_dir','')})

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

# ── PDF ────────────────────────────────────────────────────────────────────────
def make_pdf(b: dict) -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, HRFlowable, KeepTogether
    )
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

    inv_dir = get_invoices_dir()
    bid   = b.get('booking_id', 'XXXX')
    fname = f"Invoice_{bid}_{b.get('client_name','').replace(' ','_')}.pdf"
    path  = str(inv_dir / fname)

    GOLD   = colors.HexColor('#c9a84c')
    DARK   = colors.HexColor('#0f0f1a')
    LGREY  = colors.HexColor('#f0f0f0')
    LGOLD  = colors.HexColor('#fdf8ed')
    GREEN  = colors.HexColor('#27ae60')
    RED    = colors.HexColor('#e74c3c')
    WHITE  = colors.white
    DKGOLD = colors.HexColor('#8a6b1e')

    def ps(name, **kw): return ParagraphStyle(name, **kw)

    doc = SimpleDocTemplate(path, pagesize=A4,
        leftMargin=14*mm, rightMargin=14*mm,
        topMargin=12*mm,  bottomMargin=14*mm)
    story = []

    status = b.get('payment_status', '').upper()
    bal    = float(b.get('balance_due') or 0)

    # ── STATUS colour ──────────────────────────────────────────────────────────
    sc_hex = '#27ae60' if status in ('CONFIRMED','COMPLETED') else ('#e74c3c' if status == 'CANCELLED' else '#c9a84c')
    sc_col = GREEN if status in ('CONFIRMED','COMPLETED') else (RED if status == 'CANCELLED' else GOLD)

    # ══ HEADER ════════════════════════════════════════════════════════════════
    booking_date_disp = iso_to_display(b.get('booking_date', ''))
    header_tbl = Table([[
        Paragraph(
            '<font size="20" color="#c9a84c"><b>SHREE PHOTOGRAPHY</b></font><br/>'
            '<font size="8.5" color="#888888">Professional Wedding &amp; Event Photography</font><br/>'
            '<font size="8.5" color="#888888">Email : shreephotographycreativestudio@gmail.com</font><br/>'
            '<font size="8.5" color="#888888"> contact : 9894380867</font>',
            ps('hl', leading=15, fontName='Helvetica')),
        Paragraph(
            f'<font size="8" color="#aaaaaa">BOOKING INVOICE</font><br/>'
            f'<font size="18" color="#c9a84c"><b>  #{str(bid).zfill(3)}</b></font><br/>'
            f'<font size="8" color="#aaaaaa">Date: {booking_date_disp}</font><br/>'
            f'<font size="9.5" color="{sc_hex}"><b>{status}</b></font>',
            ps('hr', alignment=TA_RIGHT, leading=13, fontName='Helvetica')),
    ]], colWidths=[120*mm, 62*mm])
    header_tbl.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    story.append(header_tbl)
    story.append(HRFlowable(width='100%', thickness=2.5, color=GOLD, spaceBefore=4, spaceAfter=8))

    if status == 'CANCELLED':
        story.append(Paragraph(
            '<font size="26" color="#e74c3c"><b>— CANCELLED —</b></font>',
            ps('cx', alignment=TA_CENTER, fontName='Helvetica-Bold')))
        story.append(Spacer(1, 4*mm))

    # ── section header helper ──────────────────────────────────────────────────
    def section(title):
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(
            f'<font size="9.5" color="#ffffff"><b>  {title}</b></font>',
            ps('sh', backColor=DARK, leftPadding=8, topPadding=4, bottomPadding=4,
               fontName='Helvetica-Bold')))
        story.append(Spacer(1, 1.5*mm))

    # ── 2-column info table ────────────────────────────────────────────────────
    def info_table(rows, cw=None):
        cw = cw or [38*mm, 60*mm, 38*mm, 46*mm]
        t  = Table(rows, colWidths=cw)
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(0,-1),LGREY), ('BACKGROUND',(2,0),(2,-1),LGREY),
            ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
            ('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),8.5),
            ('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#cccccc')),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('TOPPADDING',(0,0),(-1,-1),5),
            ('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LEFTPADDING',(0,0),(-1,-1),6),
        ]))
        story.append(t)

    # ══ CLIENT DETAILS ═════════════════════════════════════════════════════════
    section('CLIENT DETAILS')
    info_table([
        ['Client Name', b.get('client_name',''),  'Contact',      b.get('contact_number','')],
        ['Venue',       b.get('event_venue',''),  'Package Tier', b.get('package_tier','').upper()],
    ])

    # ══ EVENT SCHEDULE ═════════════════════════════════════════════════════════
    section('EVENT SCHEDULE')
    # Try to use event_slots JSON, else fall back to single event
    slots_json = b.get('event_slots','')
    slots = []
    if slots_json:
        try:
            slots = _json.loads(slots_json)
        except Exception:
            pass
    if slots:
        erows = [['#', 'Event Type', 'Date', 'Time']]
        for i, s in enumerate(slots, 1):
            d_disp = s.get('date','') or iso_to_display(s.get('date_iso',''))
            t_disp = s.get('time','') or '—'
            erows.append([str(i), s.get('event_type','—'), d_disp, t_disp])
        et = Table(erows, colWidths=[10*mm, 70*mm, 50*mm, 52*mm])
        et.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),DARK), ('TEXTCOLOR',(0,0),(-1,0),WHITE),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),8.5),
            ('ALIGN',(0,0),(-1,-1),'CENTER'), ('ALIGN',(1,0),(1,-1),'LEFT'),
            ('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE, LGREY]),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('TOPPADDING',(0,0),(-1,-1),5), ('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LEFTPADDING',(1,0),(1,-1),8),
        ]))
        story.append(et)
    else:
        # Legacy fallback
        start_disp = iso_to_display(b.get('start_date',''))
        end_disp   = iso_to_display(b.get('end_date',''))
        info_table([
            ['Event Type',  b.get('event_type',''),  'Event Time',  b.get('event_time','') or '—'],
            ['Start Date',  start_disp,               'End Date',    end_disp],
        ])

    # ══ SERVICES SELECTED ══════════════════════════════════════════════════════
    section('SERVICES SELECTED')
    # Parse packages with quantities
    pkg_raw = b.get('packages','')
    pkg_counts = {}
    for p in pkg_raw.split(','):
        p = p.strip()
        if p: pkg_counts[p] = pkg_counts.get(p, 0) + 1

    srows = [['#', 'Service', 'Qty']]
    row_n = 0
    selected_rows = []
    for k, lbl in PKG_LABELS.items():
        qty = pkg_counts.get(k, 0)
        if qty > 0:
            row_n += 1
            selected_rows.append(row_n)
            srows.append([str(row_n), lbl, str(qty)])
    if not selected_rows:
        srows.append(['—', 'No services selected', '—'])

    st = Table(srows, colWidths=[12*mm, 148*mm, 22*mm])
    style_cmds = [
        ('BACKGROUND',(0,0),(-1,0),DARK), ('TEXTCOLOR',(0,0),(-1,0),WHITE),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),8.5),
        ('ALIGN',(0,0),(-1,-1),'CENTER'), ('ALIGN',(1,0),(1,-1),'LEFT'),
        ('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE, LGREY]),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),5), ('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(1,0),(1,-1),8),
    ]
    # Highlight selected service rows green
    for rn in selected_rows:
        style_cmds.append(('TEXTCOLOR',(1,rn),(1,rn),GREEN))
        style_cmds.append(('FONTNAME',(1,rn),(2,rn),'Helvetica-Bold'))
    st.setStyle(TableStyle(style_cmds))
    story.append(st)

    # ══ ADD-ONS ════════════════════════════════════════════════════════════════
    album_type  = b.get('album_type','') or '—'
    album_count = b.get('album_count','') or '—'
    cal_addon   = b.get('calendar_addon','No')
    frames_json = b.get('frames','')
    notes       = b.get('notes','') or ''

    addon_rows = [['Album Type', album_type, 'Album Count', album_count],
                  ['Calendar Add-on', cal_addon, 'Package Tier', b.get('package_tier','').upper()]]
    if notes:
        addon_rows.append(['Notes', notes, '', ''])
    if addon_rows:
        section('ADD-ONS & EXTRAS')
        info_table(addon_rows)

    # ══ FRAMES ════════════════════════════════════════════════════════════════
    if frames_json:
        try:
            frames = _json.loads(frames_json)
            if frames:
                section('FRAMES ORDERED')
                frows = [['#', 'Size (inches)', 'Quantity']]
                for i, fr in enumerate(frames, 1):
                    frows.append([str(i), f"{fr.get('w','?')} × {fr.get('h','?')}", str(fr.get('qty','1'))])
                ft = Table(frows, colWidths=[15*mm, 130*mm, 37*mm])
                ft.setStyle(TableStyle([
                    ('BACKGROUND',(0,0),(-1,0),DARK), ('TEXTCOLOR',(0,0),(-1,0),WHITE),
                    ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
                    ('FONTSIZE',(0,0),(-1,-1),8.5),
                    ('ALIGN',(0,0),(-1,-1),'CENTER'),
                    ('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#cccccc')),
                    ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE, LGREY]),
                    ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                    ('TOPPADDING',(0,0),(-1,-1),5), ('BOTTOMPADDING',(0,0),(-1,-1),5),
                ]))
                story.append(ft)
        except Exception:
            pass

    # ══ PAYMENT SUMMARY ════════════════════════════════════════════════════════
    section('PAYMENT SUMMARY')
    try:
        amt = float(b.get('package_amount') or 0)
        adv_list = []
        adv_json = b.get('advances','')
        if adv_json:
            try:
                adv_list = [float(a) for a in _json.loads(adv_json) if a]
            except Exception:
                pass
        if not adv_list:
            a1 = float(b.get('advance1') or 0)
            a2 = float(b.get('advance2') or 0)
            if a1: adv_list.append(a1)
            if a2: adv_list.append(a2)
        total_adv = sum(adv_list)
        bal_val   = float(b.get('balance_due') or 0)
    except Exception:
        amt = total_adv = bal_val = 0; adv_list = []

    pay_rows = [['Package Amount', f'Rs. {amt:,.2f}']]
    for i, a in enumerate(adv_list, 1):
        pay_rows.append([f'Advance {i} Received', f'Rs. {a:,.2f}'])
    pay_rows.append(['Total Advance Paid', f'Rs. {total_adv:,.2f}'])
    pay_rows.append(['Balance Due', f'Rs. {bal_val:,.2f}'])
    pay_rows.append(['Payment Status', status])

    tot_row = len(pay_rows) - 3
    bal_row = len(pay_rows) - 2
    sts_row = len(pay_rows) - 1

    pt = Table(pay_rows, colWidths=[100*mm, 82*mm])
    pt.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,-1),LGREY),
        ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#cccccc')),
        ('ALIGN',(1,0),(1,-1),'RIGHT'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),6), ('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LEFTPADDING',(0,0),(-1,-1),8), ('RIGHTPADDING',(0,0),(-1,-1),8),
        # Total advance row
        ('BACKGROUND',(0,tot_row),(-1,tot_row),colors.HexColor('#e8f5e9')),
        ('FONTNAME',(0,tot_row),(-1,tot_row),'Helvetica-Bold'),
        # Balance row — highlight
        ('BACKGROUND',(0,bal_row),(-1,bal_row),LGOLD),
        ('FONTSIZE',(0,bal_row),(-1,bal_row),11),
        ('FONTNAME',(0,bal_row),(-1,bal_row),'Helvetica-Bold'),
        ('TEXTCOLOR',(1,bal_row),(1,bal_row), GREEN if bal_val <= 0 else RED),
        # Status
        ('TEXTCOLOR',(1,sts_row),(1,sts_row), sc_col),
        ('FONTNAME',(1,sts_row),(1,sts_row),'Helvetica-Bold'),
    ]))
    story.append(pt)

    # ══ FOOTER ════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width='100%', thickness=1.5, color=GOLD, spaceAfter=5))

    # Non-refundable notice box
    notice = Table([[
        Paragraph(
            '<font size="8.5" color="#7a5f20"><b>⚠ IMPORTANT NOTICE</b></font><br/>'
            '<font size="8" color="#5a4010">'
            'All advance payments made to Shree Photography are <b>strictly non-refundable</b>. '
            'By confirming this booking, the client agrees that advance amounts cannot be returned '
            'under any circumstances including cancellation or rescheduling. '
            'The balance amount is due on or before the event date.'
            '</font>',
            ps('nt', leading=11, fontName='Helvetica', leftPadding=4))
    ]], colWidths=[182*mm])
    notice.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),LGOLD),
        ('BOX',(0,0),(-1,-1),1,GOLD),
        ('TOPPADDING',(0,0),(-1,-1),7),
        ('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('LEFTPADDING',(0,0),(-1,-1),10),
        ('RIGHTPADDING',(0,0),(-1,-1),10),
    ]))
    story.append(notice)
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        '<font size="7.5" color="#aaaaaa">Thank you for choosing Shree Photography. '
        'This is a computer-generated invoice and does not require a signature.</font>',
        ps('ft', alignment=TA_CENTER, fontName='Helvetica')))

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

    desc = '\\n'.join([
        f"Booking ID: #{bid}",
        f"Client: {b.get('client_name','')}",
        f"Contact: {b.get('contact_number','')}",
        f"Type: {b.get('event_type','')}",
        f"Venue: {b.get('event_venue','')}",
        f"Services: {svcs}",
        f"Package: {b.get('package_tier','').upper()}",
        f"Amount: Rs.{b.get('package_amount',0)} | Balance: Rs.{b.get('balance_due',0)}",
        f"Status: {b.get('payment_status','').upper()}",
    ])

    ical_status = 'CANCELLED' if b.get('payment_status','').upper() == 'CANCELLED' else 'CONFIRMED'

    lines = [
        'BEGIN:VCALENDAR', 'VERSION:2.0',
        'PRODID:-//Shree Photography//EN',
        'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        f'UID:{bid}-{uuid.uuid4()}@shreephotography',
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

# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    ensure()
    print('Shree Photography backend running on http://127.0.0.1:5050', flush=True)
    app.run(host='127.0.0.1', port=5050, debug=False)
