"""거래명세서 PDF 출력"""
import sqlite3
import os
from datetime import date
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT


DB_PATH = "accounting.db"


def _register_korean_font():
    """한글 폰트 등록 - 시스템 폰트 자동 탐색"""
    candidates = [
        "C:/Windows/Fonts/malgun.ttf",   # Windows
        "C:/Windows/Fonts/gulim.ttc",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",  # macOS
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",  # Linux
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for f in candidates:
        if os.path.exists(f):
            try:
                pdfmetrics.registerFont(TTFont('Korean', f))
                return 'Korean'
            except Exception:
                continue
    return 'Helvetica'  # fallback


def export_invoice_pdf(sale_no: str, output_path: str,
                        company_self_info: dict = None) -> str:
    """거래명세서 PDF 출력

    company_self_info: 자사 정보 dict
        {name, business_no, ceo, address, phone}
    """
    font = _register_korean_font()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    sale = conn.execute(
        """SELECT s.*, c.* FROM sales s
           JOIN companies c ON s.company_code=c.company_code
           WHERE s.sale_no=?""",
        (sale_no,)
    ).fetchone()
    if not sale:
        raise ValueError(f"매출 없음: {sale_no}")

    items = conn.execute(
        "SELECT * FROM sale_items WHERE sale_id=? ORDER BY seq",
        (sale['sale_id'],)
    ).fetchall()
    conn.close()

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleK', parent=styles['Title'],
        fontName=font, fontSize=22, alignment=TA_CENTER,
        spaceAfter=10*mm,
    )
    normal = ParagraphStyle(
        'NormalK', fontName=font, fontSize=10, leading=14,
    )
    right = ParagraphStyle(
        'RightK', fontName=font, fontSize=10, alignment=TA_RIGHT,
    )

    elements = []
    elements.append(Paragraph("거래명세서", title_style))

    # 자사/거래처 정보
    self_info = company_self_info or {
        "name": "자사명을 설정하세요",
        "business_no": "000-00-00000",
        "ceo": "대표자명",
        "address": "주소",
        "phone": "연락처",
    }
    info_data = [
        [Paragraph("<b>공급자</b>", normal),
         Paragraph("<b>공급받는자</b>", normal)],
        [Paragraph(f"상호: {self_info['name']}", normal),
         Paragraph(f"상호: {sale['company_name']}", normal)],
        [Paragraph(f"사업자번호: {self_info['business_no']}", normal),
         Paragraph(f"사업자번호: {sale['business_no'] or '-'}", normal)],
        [Paragraph(f"대표자: {self_info['ceo']}", normal),
         Paragraph(f"대표자: {sale['ceo_name'] or '-'}", normal)],
        [Paragraph(f"주소: {self_info['address']}", normal),
         Paragraph(f"주소: {sale['address'] or '-'}", normal)],
        [Paragraph(f"전화: {self_info['phone']}", normal),
         Paragraph(f"전화: {sale['phone'] or '-'}", normal)],
    ]
    info_table = Table(info_data, colWidths=[90*mm, 90*mm])
    info_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#9ca3af')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f4f6')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 8*mm))

    # 매출 메타
    meta = [
        [f"매출번호: {sale['sale_no']}",
         f"발행일자: {sale['sale_date']}",
         f"결제예정: {sale['due_date'] or '-'}"],
    ]
    meta_table = Table(meta, colWidths=[60*mm, 60*mm, 60*mm])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), font),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#dbeafe')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 5*mm))

    # 품목 테이블
    item_header = ["#", "품목", "규격", "수량", "단가", "공급가", "부가세", "합계"]
    item_rows = [item_header]
    for i, it in enumerate(items, 1):
        qty_str = f"{it['quantity']:.2f}".rstrip('0').rstrip('.')
        item_rows.append([
            str(i),
            it['item_name'],
            it['spec'] or '',
            qty_str,
            f"{it['unit_price']:,}",
            f"{it['supply_amount']:,}",
            f"{it['vat_amount']:,}",
            f"{it['total_amount']:,}",
        ])
    # 합계 행
    item_rows.append([
        "", "합계", "", "", "",
        f"{sale['supply_amount']:,}",
        f"{sale['vat_amount']:,}",
        f"{sale['total_amount']:,}",
    ])

    item_table = Table(item_rows, colWidths=[
        10*mm, 40*mm, 20*mm, 15*mm, 25*mm, 25*mm, 22*mm, 25*mm
    ])
    item_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), font),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('ALIGN', (3,1), (-1,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#9ca3af')),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f3f4f6')),
        ('FONTNAME', (0,-1), (-1,-1), font),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(item_table)
    elements.append(Spacer(1, 8*mm))

    # 합계 박스
    total_box = Table([
        ["공급가액", f"{sale['supply_amount']:,} 원"],
        ["부가세액", f"{sale['vat_amount']:,} 원"],
        ["합계금액", f"{sale['total_amount']:,} 원"],
    ], colWidths=[60*mm, 80*mm])
    total_box.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), font),
        ('FONTSIZE', (0,0), (-1,-1), 11),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#9ca3af')),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#dbeafe')),
        ('FONTNAME', (0,-1), (-1,-1), font),
        ('FONTSIZE', (0,-1), (-1,-1), 14),
        ('TEXTCOLOR', (0,-1), (-1,-1), colors.HexColor('#1e3a8a')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(total_box)
    elements.append(Spacer(1, 10*mm))

    # 세금계산서 + 메모
    if sale['tax_invoice_no']:
        elements.append(Paragraph(
            f"세금계산서 번호: {sale['tax_invoice_no']}", normal))
    if sale['note']:
        elements.append(Paragraph(f"비고: {sale['note']}", normal))

    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph(
        f"<font color='#6b7280'>출력일: {date.today()}</font>",
        right
    ))

    doc.build(elements)
    return output_path


def get_self_info() -> dict:
    """자사 정보 - config.json에서 읽음"""
    import json
    try:
        with open("config.json", encoding="utf-8") as f:
            c = json.load(f)
        return c.get("company_self", {
            "name": "자사명을 설정하세요",
            "business_no": "000-00-00000",
            "ceo": "",
            "address": "",
            "phone": "",
        })
    except Exception:
        return {}


def save_self_info(info: dict):
    import json
    try:
        with open("config.json", encoding="utf-8") as f:
            c = json.load(f)
    except Exception:
        c = {}
    c["company_self"] = info
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(c, f, indent=2, ensure_ascii=False)
