"""
매출 모듈 - 등록/조회/원장/미수금 함수 모음

다른 스크립트에서 사용:
    from sales_module import register_sale, get_ledger, get_receivables
"""
import sqlite3
from datetime import date, timedelta
from typing import Optional


DB_PATH = "accounting.db"
VAT_RATE = 0.10  # 부가세율


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def generate_sale_no(conn, sale_date: date) -> str:
    """매출번호 자동 생성: S20260507-001 형식"""
    prefix = f"S{sale_date.strftime('%Y%m%d')}"
    cur = conn.execute(
        "SELECT COUNT(*) FROM sales WHERE sale_no LIKE ?", (f"{prefix}%",)
    )
    seq = cur.fetchone()[0] + 1
    return f"{prefix}-{seq:03d}"


def register_sale(
    company_code: str,
    items: list[dict],
    sale_date: Optional[date] = None,
    due_date: Optional[date] = None,
    note: str = "",
    tax_invoice_no: str = "",
) -> str:
    """
    매출 등록 (헤더 + 상세를 한 트랜잭션으로)

    items 예시:
        [
            {"item_name": "상품A", "quantity": 10, "unit_price": 50000},
            {"item_name": "상품B", "quantity": 2,  "unit_price": 100000, "spec": "1m"},
        ]

    반환: 생성된 매출번호
    """
    if not items:
        raise ValueError("매출 상세 품목이 1건 이상 필요합니다")

    sale_date = sale_date or date.today()
    if due_date is None:
        due_date = sale_date + timedelta(days=30)  # 기본 30일 후

    conn = get_conn()
    try:
        # 거래처 검증
        cur = conn.execute(
            "SELECT company_name, can_sell FROM companies WHERE company_code = ?",
            (company_code,),
        )
        comp = cur.fetchone()
        if not comp:
            raise ValueError(f"거래처 없음: {company_code}")
        if comp["can_sell"] != 1:
            raise ValueError(f"매출 불가 거래처: {comp['company_name']}")

        # 매출번호 생성
        sale_no = generate_sale_no(conn, sale_date)

        # 헤더 INSERT (총액은 나중에 계산)
        cur = conn.execute(
            """INSERT INTO sales
               (sale_no, sale_date, company_code, due_date, note, tax_invoice_no)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (sale_no, sale_date, company_code, due_date, note, tax_invoice_no or None),
        )
        sale_id = cur.lastrowid

        # 상세 INSERT + 합계 누적
        total_supply = total_vat = 0
        for seq, item in enumerate(items, start=1):
            qty = item["quantity"]
            price = item["unit_price"]
            supply = round(qty * price)
            vat = round(supply * VAT_RATE)
            total = supply + vat

            conn.execute(
                """INSERT INTO sale_items
                   (sale_id, seq, item_name, spec, quantity, unit_price,
                    supply_amount, vat_amount, total_amount, note)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sale_id, seq, item["item_name"], item.get("spec"),
                    qty, price, supply, vat, total, item.get("note"),
                ),
            )
            total_supply += supply
            total_vat += vat

        total_amount = total_supply + total_vat

        # 헤더 합계 UPDATE
        conn.execute(
            """UPDATE sales SET
                 supply_amount = ?, vat_amount = ?, total_amount = ?,
                 unpaid_amount = ?
               WHERE sale_id = ?""",
            (total_supply, total_vat, total_amount, total_amount, sale_id),
        )

        conn.commit()
        return sale_no

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cancel_sale(sale_no: str, reason: str = "") -> bool:
    """
    매출 취소 - 수금된 내역이 있으면 취소 불가
    수금 없으면 status='취소'로 변경
    """
    conn = get_conn()
    try:
        sale = conn.execute(
            "SELECT * FROM sales WHERE sale_no=?", (sale_no,)
        ).fetchone()
        if not sale:
            raise ValueError(f"매출번호 없음: {sale_no}")
        if sale['status'] == '취소':
            raise ValueError("이미 취소된 매출입니다")
        if sale['paid_amount'] > 0:
            raise ValueError(
                f"수금된 매출은 취소할 수 없습니다 (수금액: {sale['paid_amount']:,}원)\n"
                f"먼저 수금을 취소하세요"
            )
        conn.execute(
            """UPDATE sales SET status='취소', cancel_reason=?,
               cancelled_at=CURRENT_TIMESTAMP WHERE sale_no=?""",
            (reason, sale_no)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_sale(sale_no: str) -> dict:
    """매출 1건 상세 조회 (헤더 + 상세)"""
    conn = get_conn()
    try:
        header = conn.execute(
            """SELECT s.*, c.company_name
               FROM sales s
               JOIN companies c ON s.company_code = c.company_code
               WHERE s.sale_no = ?""",
            (sale_no,),
        ).fetchone()
        if not header:
            return None

        items = conn.execute(
            "SELECT * FROM sale_items WHERE sale_id = ? ORDER BY seq",
            (header["sale_id"],),
        ).fetchall()

        return {
            "header": dict(header),
            "items": [dict(i) for i in items],
        }
    finally:
        conn.close()


def get_ledger(company_code: str, start_date: date = None, end_date: date = None):
    """
    거래처 매출 원장 - 시간순 매출 내역 + 누적 잔액

    반환: [{매출번호, 일자, 합계, 수금, 미수금, 누적미수금}, ...]
    """
    conn = get_conn()
    try:
        sql = """SELECT sale_no, sale_date, due_date, total_amount,
                        paid_amount, unpaid_amount, payment_status, status
                 FROM sales
                 WHERE company_code = ? AND status = '정상'"""
        params = [company_code]
        if start_date:
            sql += " AND sale_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND sale_date <= ?"
            params.append(end_date)
        sql += " ORDER BY sale_date, sale_id"

        rows = conn.execute(sql, params).fetchall()

        result = []
        cumulative_unpaid = 0
        for r in rows:
            d = dict(r)
            cumulative_unpaid += d["unpaid_amount"]
            d["cumulative_unpaid"] = cumulative_unpaid
            result.append(d)
        return result
    finally:
        conn.close()


def get_receivables(only_overdue: bool = False, today: date = None):
    """
    미수금 현황 - 거래처별 잔여 미수금 큰 순서

    only_overdue=True: 결제예정일 지난 것만
    """
    today = today or date.today()
    conn = get_conn()
    try:
        sql = """SELECT
                     c.company_code,
                     c.company_name,
                     c.phone,
                     COUNT(s.sale_id) AS unpaid_count,
                     SUM(s.unpaid_amount) AS total_unpaid,
                     MIN(s.due_date) AS earliest_due,
                     SUM(CASE WHEN s.due_date < ? THEN s.unpaid_amount ELSE 0 END)
                         AS overdue_amount
                 FROM sales s
                 JOIN companies c ON s.company_code = c.company_code
                 WHERE s.status = '정상' AND s.unpaid_amount > 0"""
        params = [today]
        if only_overdue:
            sql += " AND s.due_date < ?"
            params.append(today)
        sql += " GROUP BY c.company_code, c.company_name, c.phone"
        sql += " ORDER BY total_unpaid DESC"

        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def get_sales_summary(start_date: date = None, end_date: date = None):
    """매출 통계 요약"""
    conn = get_conn()
    try:
        sql = """SELECT
                     COUNT(*) AS sale_count,
                     COALESCE(SUM(supply_amount), 0) AS total_supply,
                     COALESCE(SUM(vat_amount), 0)    AS total_vat,
                     COALESCE(SUM(total_amount), 0)  AS total_amount,
                     COALESCE(SUM(paid_amount), 0)   AS total_paid,
                     COALESCE(SUM(unpaid_amount), 0) AS total_unpaid
                 FROM sales WHERE status = '정상'"""
        params = []
        if start_date:
            sql += " AND sale_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND sale_date <= ?"
            params.append(end_date)

        return dict(conn.execute(sql, params).fetchone())
    finally:
        conn.close()
