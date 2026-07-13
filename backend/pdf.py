"""
backend/pdf.py
สร้างไฟล์ PDF จากข้อมูลเอกสาร (ฝั่ง server) ด้วย xhtml2pdf (เพียว Python ไม่มี native dep
จึงฝังเข้า PyInstaller onefile ได้ง่าย และทำงาน "ออฟไลน์" ได้เพราะฝังฟอนต์ไทยไว้ในตัว)

ทำไมไม่รียูสหน้า HTML บนจอ: เลย์เอาต์บนจอใช้ flexbox เยอะ ซึ่ง xhtml2pdf ไม่รองรับ
เทมเพลตในไฟล์นี้จึงจัดด้วย <table> ล้วน ๆ ให้ออกมาคมชัด สีไม่ซีด (เป็น PDF จริง ไม่ใช่ปริ้น)
"""
from __future__ import annotations

import io
import os
import re
import socket
from html import escape

from config import resource_path

# ---- ฟอนต์ที่ฝังมากับแอป (frontend/fonts ถูก bundle ด้วย --add-data frontend) ----
_FONT_DIR = resource_path(os.path.join("frontend", "fonts"))
_FONT_FILES = [
    "Sarabun-Regular.ttf", "Sarabun-Bold.ttf", "Sarabun-SemiBold.ttf",
    "KoHo-SemiBold.ttf", "KoHo-Bold.ttf",
]


def _font_face(family: str, filename: str, weight: str | None = None) -> str:
    # ใช้ "ชื่อไฟล์เปล่า" ใน url() แล้วให้ _link_callback แปลงเป็น path จริง
    # (กัน path แบบ C:\... บน Windows ถูก xhtml2pdf ตีความว่า "C:" เป็น scheme = ฟอนต์ไม่โหลด)
    w = f" font-weight:{weight};" if weight else ""
    return f"@font-face {{ font-family:'{family}'; src:url('{filename}');{w} }}"


_FONTS_CSS = "\n".join([
    _font_face("Sarabun", "Sarabun-Regular.ttf"),
    _font_face("Sarabun", "Sarabun-Bold.ttf", "bold"),
    _font_face("Sarabun", "Sarabun-SemiBold.ttf", "600"),
    _font_face("KoHo", "KoHo-SemiBold.ttf", "600"),
    _font_face("KoHo", "KoHo-Bold.ttf", "bold"),
])


def _link_callback(uri, rel):
    """แปลง url() ในเทมเพลตให้เป็น path จริง — อนุญาตเฉพาะฟอนต์ที่ฝังมาเท่านั้น
    อย่างอื่น (ลิงก์เน็ต ฯลฯ) คืนค่าว่าง เพื่อไม่ให้ xhtml2pdf ไปโหลดจากภายนอก"""
    name = os.path.basename(uri or "")
    if name in _FONT_FILES:
        return os.path.join(_FONT_DIR, name)
    return ""


# ลบทรัพยากรภายนอก (รูปจากเน็ต ฯลฯ) ที่อาจติดมากับข้อความที่ผู้ใช้ "วาง" ในช่อง contenteditable
# — ป้องกันทั้งการหลุดออกเน็ต (แอปนี้ต้องออฟไลน์ได้) และอาการค้างตอนดึงรูปที่โหลดไม่ได้
_IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.I)
_DATA_SRC_RE = re.compile(r"""src\s*=\s*["']\s*data:""", re.I)
_REMOTE_ATTR_RE = re.compile(
    r"""\s(?:src|href)\s*=\s*["'](?!\s*data:)[^"']*:[^"']*["']""", re.I)
_REMOTE_URL_RE = re.compile(
    r"""url\(\s*["']?(?!\s*data:)[^)"']*:[^)]*\)""", re.I)


def _sanitize_html(s: str) -> str:
    if not s:
        return ""
    # 1) เก็บ <img> เฉพาะที่ฝังภาพมาแบบ data: URI (เช่นลายเซ็น) — ที่เหลือทิ้ง
    s = _IMG_TAG_RE.sub(lambda m: m.group(0) if _DATA_SRC_RE.search(m.group(0)) else "", s)
    # 2) กัน src/href/background-url ที่ชี้ออกภายนอกทุกกรณีที่หลงเหลือ
    s = _REMOTE_ATTR_RE.sub("", s)
    s = _REMOTE_URL_RE.sub("none", s)
    return s

_DOCTYPES = {
    "quotation": {"title": "ใบเสนอราคา", "paid": False,
                  "sL": "ผู้เสนอราคา / วันที่", "sR": "ผู้สั่งซื้อ / วันที่"},
    "invoice":   {"title": "ใบแจ้งหนี้", "paid": False,
                  "sL": "ผู้วางบิล / วันที่", "sR": "ผู้รับวางบิล / วันที่"},
    "receipt":   {"title": "ใบเสร็จรับเงิน", "paid": True,
                  "sL": "ผู้รับเงิน / วันที่", "sR": "ผู้จ่ายเงิน / วันที่"},
}

# อักขระที่ตั้งชื่อไฟล์ไม่ได้บน Windows/macOS (+ control chars) — แทนด้วย '-' กันคำติดกัน
_ILLEGAL_FS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_MAX_NAME_BYTES = 230  # กันชื่อยาวเกินลิมิตไฟล์ (ext4/APFS = 255 ไบต์; ไทย 3 ไบต์/ตัว) เผื่อ ".pdf"


def suggest_filename(doc: dict) -> str:
    """ชื่อไฟล์ PDF แนะนำ = "{หัวข้อบิล}-{ชื่อบริษัทลูกค้า}" โดยแทนช่องว่างด้วย '-'
    เช่น ใบเสนอราคา + "บริษัท น้ำตาล สหมิตร จำกัด" -> "ใบเสนอราคา-บริษัท-น้ำตาล-สหมิตร-จำกัด"
    (คืนค่า "ยังไม่ใส่ .pdf" — ให้ผู้เรียกเติมนามสกุลเอง). กันอักขระต้องห้ามให้ผู้รับเปิดไฟล์ได้ชัวร์"""
    from backend.store import _client_name_from_html  # แหล่งเดียวกับลิสต์เอกสาร กันตรรกะลอกซ้ำ

    dtype = str(doc.get("doc_type") or "quotation")
    title = (_DOCTYPES.get(dtype) or _DOCTYPES["quotation"])["title"]
    client = _client_name_from_html(doc.get("client_html") or "")
    # ถ้าไม่มีชื่อลูกค้า ใช้เลขที่เอกสารต่อท้ายแทน จะได้ไม่ชนกันหลายไฟล์
    tail = client or str(doc.get("doc_no") or "")
    raw = "-".join(p for p in (title, tail) if p)

    name = re.sub(r"\s+", "-", raw.strip())          # ช่องว่าง/แท็บ/ขึ้นบรรทัด -> '-' ก่อน
    name = _ILLEGAL_FS.sub("-", name)                # อักขระต้องห้าม -> '-' (ไม่ลบทิ้ง)
    name = re.sub(r"-{2,}", "-", name).strip("-. ")  # ยุบ '--' ซ้ำ + ตัดขอบ
    # ตัดความยาวแบบนับ "ไบต์" (ไม่ใช่ตัวอักษร) — errors="ignore" กันตัดกลางตัวไทยแล้ว decode พัง
    name = name.encode("utf-8")[:_MAX_NAME_BYTES].decode("utf-8", "ignore").strip("-. ")
    return name or "document"


# ---------- ตัวเลข ----------
def _num(v) -> float:
    try:
        if isinstance(v, str):
            v = v.replace(",", "").strip()
        n = float(v)
        return 0.0 if n != n else n  # กัน NaN
    except (TypeError, ValueError):
        return 0.0


def _fmt(n: float) -> str:
    n = _num(n)
    if float(n).is_integer():
        return f"{int(n):,}"
    return f"{n:,.2f}"


# ---------- ตัวอักษรบาท (port มาจาก bahtText ฝั่ง client ให้ผลตรงกัน) ----------
_TH_DIGIT = ["ศูนย์", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
_TH_POS = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน"]


def _read_group(s: str) -> str:
    r = ""
    L = len(s)
    for i, ch in enumerate(s):
        d = int(ch)
        pos = L - 1 - i
        if d == 0:
            continue
        if pos == 0 and d == 1 and L > 1:
            r += "เอ็ด"
        elif pos == 1 and d == 1:
            r += "สิบ"
        elif pos == 1 and d == 2:
            r += "ยี่สิบ"
        else:
            r += _TH_DIGIT[d] + _TH_POS[pos]
    return r


def baht_text(num) -> str:
    from decimal import ROUND_HALF_UP, Decimal
    # ปัดทศนิยม 2 ตำแหน่งแบบ half-up ให้ตรงกับที่แสดงบนจอ (JS toFixed) กันข้อความบาทเพี้ยน
    q = Decimal(str(_num(num))).copy_abs().quantize(Decimal("0.01"), ROUND_HALF_UP)
    fixed = f"{q:.2f}"
    ip, dp = fixed.split(".")
    ip = ip.lstrip("0") or "0"
    if ip == "0":
        baht = "ศูนย์"
    else:
        groups = []
        while len(ip) > 6:
            groups.insert(0, ip[-6:])
            ip = ip[:-6]
        groups.insert(0, ip)
        baht = "ล้าน".join(_read_group(g) for g in groups)
    baht += "บาท"
    baht += "ถ้วน" if dp == "00" else _read_group(dp) + "สตางค์"
    return baht


# ---------- ประกอบ HTML ----------
# PNG โปร่งใส 1x1 — ใช้ค้ำความสูงช่องลายเซ็นที่ยังว่าง ให้เส้นเซ็นสองฝั่งตรงระดับกัน
_SPACER_PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1"
               "HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


def _sig_cell(url: str, caption: str) -> str:
    # กรอบสูงคงที่ทั้งสองฝั่ง (ภาพลายเซ็นสูงไม่เกินกรอบ) เส้นเซ็นจะได้ตรงระดับกัน
    src = url if url else _SPACER_PNG
    img = f'<img src="{escape(src, quote=True)}" style="height:48px" />'
    return (f'<td width="50%" align="center" style="padding:0 12px">'
            f'<div style="height:52px">{img}</div>'
            f'<div class="sigln"></div>'
            f'<div class="muted">{escape(caption)}</div></td>')


def _build_html(payload: dict) -> str:
    doc = payload.get("document", {}) or {}
    items = payload.get("items", []) or []
    dtype = doc.get("doc_type") or "quotation"
    meta = _DOCTYPES.get(dtype, _DOCTYPES["quotation"])

    subtotal = _num(doc.get("subtotal"))
    wht_rate = _num(doc.get("wht_rate"))
    wht_amount = _num(doc.get("wht_amount"))
    grand = _num(doc.get("grand_total"))
    # baht_text จะคำนวณสด ๆ ไม่พึ่งค่าจาก client (server เป็นเจ้าของความถูกต้อง)
    baht = baht_text(grand)

    # แถวรายการ
    rows = []
    for i, it in enumerate(items):
        name = escape((it.get("item_name") or "").strip())
        desc = _sanitize_html((it.get("item_desc") or "").strip())  # HTML จาก contenteditable
        desc_html = f'<div class="desc">{desc}</div>' if desc else ""
        rows.append(
            f'<tr>'
            f'<td class="c">{i + 1}</td>'
            f'<td><b>{name}</b>{desc_html}</td>'
            f'<td class="r">{_fmt(it.get("price"))}</td>'
            f'<td class="c">{_fmt(it.get("qty"))}</td>'
            f'<td class="r">{_fmt(it.get("amount"))}</td>'
            f'</tr>'
        )
    if not rows:
        rows.append('<tr><td class="c">1</td><td>-</td><td class="r">0</td>'
                    '<td class="c">0</td><td class="r">0</td></tr>')

    paid_html = (f'<div class="paid">&#10003; ชำระเงินแล้ว</div>'
                 if meta["paid"] else '')

    # ราคาที่เสนอ / ข้อตกลง (2 คอลัมน์) + บรรทัดรับรอง — ให้ตรงกับหน้าจอ (เป็น text ล้วน)
    # escape ก่อน แล้วค่อยแปลง \n -> <br> กันข้อความหลายบรรทัดหดเหลือบรรทัดเดียวใน PDF
    def _txt(v):
        return escape((v or "").strip()).replace("\n", "<br>")
    pt = _txt(doc.get("price_terms"))
    ag = _txt(doc.get("agreement"))
    terms_html = (
        f'<table class="terms"><tr>'
        f'<td width="50%"><div class="k">ราคาที่เสนอ</div><div>{pt}</div></td>'
        f'<td width="50%"><div class="k">ข้อตกลง</div><div>{ag}</div></td>'
        f'</tr></table>'
    ) if (pt or ag) else ''
    assurance = _txt(doc.get("assurance"))
    assure_html = f'<div class="assure">{assurance}</div>' if assurance else ''

    # ช่องทางชำระเงิน / ลายเซ็น จะโชว์เมื่อมีข้อมูลเท่านั้น (เอกสารบางแบบอาจไม่ต้องมี)
    pay = _sanitize_html((doc.get("payment_info") or "").strip())
    pay_html = (
        f'<div class="box" style="margin-top:12px">'
        f'<div class="k">ช่องทางการชำระเงิน</div>{pay}</div>'
    ) if pay else ''

    return f"""<html><head><meta charset="utf-8"><style>
    {_FONTS_CSS}
    @page {{ size:a4; margin:15mm 15mm 14mm; }}
    body {{ font-family:'Sarabun'; font-size:9.5pt; color:#33302B; line-height:1.5; }}
    .head {{ font-family:'KoHo'; }}
    .muted {{ color:#8A7E73; font-size:8.5pt; }}
    .issuer-name {{ font-family:'KoHo'; font-size:15pt; font-weight:bold; color:#8B6A52; }}
    .title {{ font-family:'KoHo'; font-size:17pt; font-weight:bold; }}
    .paid {{ font-family:'KoHo'; color:#2f7d4f; font-weight:bold; font-size:12.5pt;
             padding-top:6px; }}
    .rule {{ border-bottom:2px solid #8B6A52; height:1px; margin:10px 0 12px; }}
    .box {{ background:#FBF8F3; border:1px solid #E2DACF; padding:10px 13px; }}
    .k {{ font-family:'KoHo'; font-weight:600; color:#8B6A52; font-size:8.5pt; }}
    .sub {{ color:#8A7E73; font-size:8.5pt; }}
    .b {{ font-size:9pt; }}
    .lead {{ color:#8A7E73; font-size:8.7pt; margin:12px 0 4px; }}
    table.items {{ width:100%; border-collapse:collapse; }}
    table.items thead td {{ background:#FBF8F3; font-family:'KoHo'; font-weight:600;
        font-size:8.3pt; border-bottom:1.5px solid #C2A18C; padding:7px 9px; }}
    table.items tbody td {{ padding:8px 9px; border-bottom:1px solid #E2DACF;
        font-size:9.3pt; vertical-align:top; }}
    .desc {{ color:#8A7E73; font-size:8.2pt; }}
    .r {{ text-align:right; }} .c {{ text-align:center; }}
    table.tot {{ width:55%; margin-left:45%; border-collapse:collapse; }}
    table.tot td {{ padding:6px 10px; font-size:9.3pt; }}
    table.tot tr.sub td {{ border-bottom:1px solid #E2DACF; }}
    table.tot tr.wht td {{ color:#8B6A52; }}
    .grand td {{ background:#8B6A52; color:#ffffff; font-family:'KoHo'; font-weight:bold;
        font-size:11.5pt; padding:10px 12px; }}
    .baht {{ background:#FBF8F3; border-left:3px solid #C2A18C; padding:8px 12px;
        font-size:9pt; margin:12px 0; }}
    .baht b {{ font-family:'KoHo'; color:#8B6A52; }}
    table.terms {{ width:100%; border-collapse:collapse; margin:6px 0 4px; }}
    table.terms td {{ vertical-align:top; padding-right:16px; font-size:9pt; }}
    /* ไม่ใส่ italic: ฟอนต์ไทยที่ฝังมีแต่ตัวตรง italic จะทำให้ไทยกลายเป็นกล่องว่าง — ใช้สีจางแยกแทน */
    .assure {{ color:#8A7E73; font-size:8.7pt; margin:4px 0 12px; }}
    .sigln {{ border-top:1px solid #33302B; margin:4px 20px 4px; }}
    </style></head><body>

    <table width="100%"><tr>
      <td width="60%" valign="top">
        <div class="issuer-name">{escape(doc.get("issuer_name") or "")}</div>
        <div class="muted">{_sanitize_html(doc.get("issuer_address") or "")}</div>
        <div class="muted">{_sanitize_html(doc.get("issuer_tax") or "")}</div>
        <div class="muted">{_sanitize_html(doc.get("issuer_contact") or "")}</div>
      </td>
      <td width="40%" valign="top" align="right">
        <div class="title">{meta["title"]}</div>
        <div class="muted">เลขที่ / No.: {escape(doc.get("doc_no") or "")}</div>
        <div class="muted">วันที่ / Date: {escape(doc.get("doc_date") or "")}</div>
        {paid_html}
      </td>
    </tr></table>
    <div class="rule"></div>

    <div class="box">
      <div class="k">เรียน (ลูกค้า)</div>
      {_sanitize_html(doc.get("client_html") or "")}
    </div>

    <div class="lead">ขอเสนอราคาและเงื่อนไขสำหรับท่านดังนี้</div>
    <table class="items">
      <thead><tr>
        <td class="c" width="7%">ลำดับ</td>
        <td width="45%">รายการ</td>
        <td class="r" width="18%">ราคาต่อหน่วย</td>
        <td class="c" width="12%">จำนวน</td>
        <td class="r" width="18%">จำนวนเงิน</td>
      </tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>

    <table class="tot">
      <tr class="sub"><td>รวมเงิน</td><td class="r">{_fmt(subtotal)}</td></tr>
      <tr class="wht"><td>ภาษีหัก ณ ที่จ่าย {_fmt(wht_rate)}%</td>
          <td class="r">{_fmt(wht_amount)}</td></tr>
    </table>
    <table class="tot"><tr class="grand">
      <td>จำนวนเงินทั้งสิ้น</td><td class="r">{_fmt(grand)}</td>
    </tr></table>

    <div class="baht">จำนวนเงิน (ตัวอักษร): <b>{escape(baht)}</b></div>

    {terms_html}
    {assure_html}

    {pay_html}

    <table width="100%" style="margin-top:22px"><tr>
      {_sig_cell(doc.get("sign_left") or "", meta["sL"])}
      {_sig_cell(doc.get("sign_right") or "", meta["sR"])}
    </tr></table>
    </body></html>"""


def render_pdf(payload: dict) -> bytes:
    """คืน bytes ของไฟล์ PDF จาก payload (โครงเดียวกับ collectDocument() ฝั่ง client)"""
    from xhtml2pdf import pisa

    # ฟอนต์ต้องมีจริง ไม่งั้น xhtml2pdf จะ fallback เงียบ ๆ = ภาษาไทยกลายเป็นช่องว่าง
    missing = [f for f in _FONT_FILES if not os.path.exists(os.path.join(_FONT_DIR, f))]
    if missing:
        raise RuntimeError("ไม่พบไฟล์ฟอนต์: " + ", ".join(missing))

    html = _build_html(payload)
    buf = io.BytesIO()
    # กันค้าง: เผื่อมีทรัพยากรภายนอกหลุด _sanitize_html ไปได้ ให้ล้มเร็วแทนที่จะค้างยาว
    prev_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(4)
    try:
        result = pisa.CreatePDF(
            html, dest=buf, encoding="utf-8", link_callback=_link_callback)
    finally:
        socket.setdefaulttimeout(prev_timeout)
    if result.err:
        raise RuntimeError(f"สร้าง PDF ไม่สำเร็จ ({result.err} error)")
    return buf.getvalue()
