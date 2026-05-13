"""
매입 모듈 - 매입 등록/원장/지급예정/기타매입

매출 모듈과 거의 동일한 구조 (반대 방향)
- register_purchase()           매입 등록
- get_purchase()                매입 상세
- get_purchase_ledger()         거래처별 매입 원장
- get_payables()                지급해야 할 미지급금 현황
- register_other_purchase()     기타매입 등록 (공과금 등)
- get_other_purchases()         기타매입 조회
- get_purchase_summary()        매입 통계
"""
import sqlite3
from datetime import date, timedelta
from typing import Optional


DB_PATH = "accounting.db"
VAT_RATE = 0.10


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _gen_no(conn, prefix_letter: str, table: str, no_col: str, d: date) -> str:
    prefix = f"{prefix_letter}{d.strftime('%Y%m%d')}"
    cur = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {no_col} LIKE ?", (f"{prefix}%",)
    )
    return f"{prefix}-{cur.fetchone()[0] + 1:03d}"


# ============================================================
# 매입 (purchases)
# ============================================================
def register_purchase(
    company_code: str,
    items: list[dict],
    purchase_date: Optional[date] = None,
    due_date: Optional[date] = None,
    note: str = "",
    tax_invoice_no: str = "",
) -> str:
    """매입 등록 (헤더 + 상세 트랜잭션)"""
    if not items:
        raise ValueError("매입 상세가 1건 이상 필요합니다")

    purchase_date = purchase_date or date.today()
    if due_date is None:
        due_date = purchase_date + timedelta(days=30)

    conn = get_conn()
    try:
        comp = conn.execute(
            "SELECT company_name, can_purchase FROM companies WHERE company_code=?",
            (company_code,),
        ).fetchone()
        if not comp:
            raise ValueError(f"거래처 없음: {company_code}")
        if comp["can_purchase"] != 1:
            raise ValueError(f"매입 불가 거래처: {comp['company_name']}")

        p_no = _gen_no(conn, "P", "purchases", "purchase_no", purchase_date)
        cur = conn.execute(
            """INSERT INTO purchases
               (purchase_no, purchase_date, company_code, due_date, note, tax_invoice_no)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (p_no, purchase_date, company_code, due_date, note, tax_invoice_no or None),
        )
        pid = cur.lastrowid

        total_supply = total_vat = 0
        for seq, item in enumerate(items, start=1):
            qty = item["quantity"]
            price = item["unit_price"]
            supply = round(qty * price)
            vat = round(supply * VAT_RATE)
            conn.execute(
                """INSERT INTO purchase_items
                   (purchase_id, seq, item_name, spec, quantity, unit_price,
                    supply_amount, vat_amount, total_amount, note)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (pid, seq, item["item_name"], item.get("spec"),
                 qty, price, supply, vat, supply + vat, item.get("note")),
            )
            total_supply += supply
            total_vat += vat

        total = total_supply + total_vat
        conn.execute(
            """UPDATE purchases SET
                 supply_amount=?, vat_amount=?, total_amount=?, unpaid_amount=?
               WHERE purchase_id=?""",
            (total_supply, total_vat, total, total, pid),
        )
        conn.commit()
        return p_no
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cancel_purchase(purchase_no: str, reason: str = "") -> bool:
    """매입 취소 - 지급된 내역 있으면 취소 불가"""
    conn = get_conn()
    try:
        p = conn.execute(
            "SELECT * FROM purchases WHERE purchase_no=?", (purchase_no,)
        ).fetchone()
        if not p:
            raise ValueError(f"매입번호 없음: {purchase_no}")
        if p['status'] == '취소':
            raise ValueError("이미 취소된 매입입니다")
        if p['paid_amount'] > 0:
            raise ValueError(
                f"지급된 매입은 취소할 수 없습니다 (지급액: {p['paid_amount']:,}원)"
            )
        conn.execute(
            """UPDATE purchases SET status='취소', cancel_reason=?,
               cancelled_at=CURRENT_TIMESTAMP WHERE purchase_no=?""",
            (reason, purchase_no)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def cancel_other_purchase(other_no: str, reason: str = "") -> bool:
    """기타매입 취소 - 항상 가능"""
    conn = get_conn()
    try:
        o = conn.execute(
            "SELECT status FROM other_purchases WHERE other_no=?", (other_no,)
        ).fetchone()
        if not o:
            raise ValueError(f"기타매입 없음: {other_no}")
        if o['status'] == '취소':
            raise ValueError("이미 취소된 항목")
        conn.execute(
            "UPDATE other_purchases SET status='취소' WHERE other_no=?",
            (other_no,)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_purchase(purchase_no: str) -> Optional[dict]:
    conn = get_conn()
    try:
        h = conn.execute(
            """SELECT p.*, c.company_name FROM purchases p
               JOIN companies c ON p.company_code=c.company_code
               WHERE p.purchase_no=?""",
            (purchase_no,),
        ).fetchone()
        if not h:
            return None
        items = conn.execute(
            "SELECT * FROM purchase_items WHERE purchase_id=? ORDER BY seq",
            (h["purchase_id"],),
        ).fetchall()
        return {"header": dict(h), "items": [dict(i) for i in items]}
    finally:
        conn.close()


def get_purchase_ledger(company_code: str, start_date=None, end_date=None) -> list[dict]:
    """거래처별 매입 원장 (누적 미지급금)"""
    conn = get_conn()
    try:
        sql = """SELECT purchase_no, purchase_date, due_date, total_amount,
                        paid_amount, unpaid_amount, payment_status
                 FROM purchases WHERE company_code=? AND status='정상'"""
        params = [company_code]
        if start_date:
            sql += " AND purchase_date>=?"; params.append(start_date)
        if end_date:
            sql += " AND purchase_date<=?"; params.append(end_date)
        sql += " ORDER BY purchase_date, purchase_id"

        result, cum = [], 0
        for r in conn.execute(sql, params):
            d = dict(r)
            cum += d["unpaid_amount"]
            d["cumulative_unpaid"] = cum
            result.append(d)
        return result
    finally:
        conn.close()


def get_payables(only_overdue: bool = False, today: date = None) -> list[dict]:
    """지급해야 할 미지급금 현황 (큰 순)"""
    today = today or date.today()
    conn = get_conn()
    try:
        sql = """SELECT c.company_code, c.company_name, c.phone,
                        COUNT(p.purchase_id) AS unpaid_count,
                        SUM(p.unpaid_amount) AS total_unpaid,
                        MIN(p.due_date) AS earliest_due,
                        SUM(CASE WHEN p.due_date<? THEN p.unpaid_amount ELSE 0 END)
                            AS overdue_amount
                 FROM purchases p
                 JOIN companies c ON p.company_code=c.company_code
                 WHERE p.status='정상' AND p.unpaid_amount>0"""
        params = [today]
        if only_overdue:
            sql += " AND p.due_date<?"; params.append(today)
        sql += " GROUP BY c.company_code, c.company_name, c.phone"
        sql += " ORDER BY total_unpaid DESC"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def get_purchase_summary(start_date=None, end_date=None) -> dict:
    conn = get_conn()
    try:
        sql = """SELECT COUNT(*) AS count,
                        COALESCE(SUM(supply_amount),0) AS total_supply,
                        COALESCE(SUM(vat_amount),0)    AS total_vat,
                        COALESCE(SUM(total_amount),0)  AS total_amount,
                        COALESCE(SUM(paid_amount),0)   AS total_paid,
                        COALESCE(SUM(unpaid_amount),0) AS total_unpaid
                 FROM purchases WHERE status='정상'"""
        params = []
        if start_date:
            sql += " AND purchase_date>=?"; params.append(start_date)
        if end_date:
            sql += " AND purchase_date<=?"; params.append(end_date)
        return dict(conn.execute(sql, params).fetchone())
    finally:
        conn.close()


# ============================================================
# 기타 매입 (other_purchases)
# ============================================================

# 권장 비용항목 카테고리
EXPENSE_CATEGORIES = [
    '임대료', '관리비', '전기료', '수도료', '가스료', '통신비', '인터넷',
    '유류비', '주차료', '식대', '접대비', '복리후생', '소모품', '사무용품',
    '운반비', '수선비', '보험료', '세금공과', '교육훈련', '광고선전', '기타',
]


def register_other_purchase(
    description: str,
    total_amount: int,
    category: str = "기타",
    expense_date: Optional[date] = None,
    vendor_name: str = "",
    company_code: str = "",
    supply_amount: int = None,
    vat_amount: int = None,
    payment_method: str = "계좌이체",
    evidence_type: str = "영수증",
    evidence_no: str = "",
    note: str = "",
) -> str:
    """
    기타 매입 등록 (공과금, 소모품 등)

    공급가액/부가세를 따로 안 주면 합계에서 역산:
      - total/1.1 = supply, total - supply = vat
    """
    if total_amount <= 0:
        raise ValueError("금액은 0보다 커야 합니다")

    expense_date = expense_date or date.today()

    if supply_amount is None or vat_amount is None:
        # 부가세 포함 합계에서 역산 (영수증 보통 합계만 있음)
        supply_amount = round(total_amount / (1 + VAT_RATE))
        vat_amount = total_amount - supply_amount

    conn = get_conn()
    try:
        if company_code:
            comp = conn.execute(
                "SELECT 1 FROM companies WHERE company_code=?", (company_code,),
            ).fetchone()
            if not comp:
                raise ValueError(f"거래처 없음: {company_code}")

        o_no = _gen_no(conn, "O", "other_purchases", "other_no", expense_date)
        conn.execute(
            """INSERT INTO other_purchases
               (other_no, expense_date, category, description, vendor_name,
                company_code, supply_amount, vat_amount, total_amount,
                payment_method, evidence_type, evidence_no, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (o_no, expense_date, category, description,
             vendor_name or None, company_code or None,
             supply_amount, vat_amount, total_amount,
             payment_method, evidence_type,
             evidence_no or None, note or None),
        )
        conn.commit()
        return o_no
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_other_purchases(
    start_date=None, end_date=None, category: str = None,
) -> list[dict]:
    """기타매입 조회"""
    conn = get_conn()
    try:
        sql = "SELECT * FROM other_purchases WHERE status='정상'"
        params = []
        if start_date:
            sql += " AND expense_date>=?"; params.append(start_date)
        if end_date:
            sql += " AND expense_date<=?"; params.append(end_date)
        if category:
            sql += " AND category=?"; params.append(category)
        sql += " ORDER BY expense_date DESC, other_id DESC"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def get_other_purchase_summary(start_date=None, end_date=None) -> dict:
    """기타매입 요약 (카테고리별)"""
    conn = get_conn()
    try:
        sql = """SELECT category, COUNT(*) AS count,
                        SUM(supply_amount) AS supply,
                        SUM(vat_amount) AS vat,
                        SUM(total_amount) AS total
                 FROM other_purchases WHERE status='정상'"""
        params = []
        if start_date:
            sql += " AND expense_date>=?"; params.append(start_date)
        if end_date:
            sql += " AND expense_date<=?"; params.append(end_date)
        sql += " GROUP BY category ORDER BY total DESC"

        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        total_all = sum(r['total'] for r in rows) if rows else 0
        return {"by_category": rows, "total": total_all}
    finally:
        conn.close()
