"""
수금 모듈 - 등록/충당/조회/취소

핵심 함수:
    register_collection_auto()  - 자동 충당 (오래된 매출부터)
    register_collection()       - 수동 충당 (매출 지정)
    cancel_collection()         - 수금 취소 (매출 미수금 원복)
    get_collection_history()    - 거래처별 수금 이력
"""
import sqlite3
from datetime import date
from typing import Optional


DB_PATH = "accounting.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def generate_collection_no(conn, c_date: date) -> str:
    """수금번호 자동 생성: C20260507-001"""
    prefix = f"C{c_date.strftime('%Y%m%d')}"
    cur = conn.execute(
        "SELECT COUNT(*) FROM collections WHERE collection_no LIKE ?",
        (f"{prefix}%",),
    )
    seq = cur.fetchone()[0] + 1
    return f"{prefix}-{seq:03d}"


def _refresh_sale_status(conn, sale_id: int):
    """sales 테이블의 paid/unpaid/status 자동 갱신
    (취소된 수금은 제외)"""
    row = conn.execute(
        """SELECT s.total_amount,
                  COALESCE(SUM(
                      CASE WHEN c.status = '정상'
                           THEN a.allocated_amount
                           ELSE 0
                      END
                  ), 0) AS paid
           FROM sales s
           LEFT JOIN collection_allocations a ON a.sale_id = s.sale_id
           LEFT JOIN collections c ON c.collection_id = a.collection_id
           WHERE s.sale_id = ?
           GROUP BY s.sale_id""",
        (sale_id,),
    ).fetchone()

    total = row["total_amount"]
    paid = row["paid"]
    unpaid = total - paid

    if paid <= 0:
        status = "미수"
    elif paid >= total:
        status = "완료"
    else:
        status = "일부수금"

    conn.execute(
        """UPDATE sales
           SET paid_amount = ?, unpaid_amount = ?, payment_status = ?,
               updated_at = CURRENT_TIMESTAMP
           WHERE sale_id = ?""",
        (paid, unpaid, status, sale_id),
    )


def register_collection(
    company_code: str,
    amount: int,
    allocations: list[dict],
    collection_date: Optional[date] = None,
    payment_method: str = "계좌이체",
    bank_account: str = "",
    depositor_name: str = "",
    note: str = "",
) -> str:
    """
    수금 등록 - 수동 충당 (매출 지정)

    allocations 예시:
        [
            {"sale_no": "S20260417-001", "amount": 500000},
            {"sale_no": "S20260423-002", "amount": 300000},
        ]

    반환: 수금번호
    """
    if amount <= 0:
        raise ValueError("입금액은 0보다 커야 합니다")

    collection_date = collection_date or date.today()
    conn = get_conn()
    try:
        # 거래처 검증
        comp = conn.execute(
            "SELECT company_name FROM companies WHERE company_code = ?",
            (company_code,),
        ).fetchone()
        if not comp:
            raise ValueError(f"거래처 없음: {company_code}")

        # 충당 금액 합계 검증
        total_alloc = sum(a["amount"] for a in allocations)
        if total_alloc > amount:
            raise ValueError(
                f"충당 합계({total_alloc:,})가 입금액({amount:,})보다 큽니다"
            )

        # 수금 헤더 INSERT
        c_no = generate_collection_no(conn, collection_date)
        cur = conn.execute(
            """INSERT INTO collections
               (collection_no, collection_date, company_code, amount,
                allocated_amount, unallocated, payment_method,
                bank_account, depositor_name, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (c_no, collection_date, company_code, amount,
             total_alloc, amount - total_alloc,
             payment_method, bank_account or None,
             depositor_name or None, note or None),
        )
        coll_id = cur.lastrowid

        # 충당 INSERT + 매출 갱신
        for alloc in allocations:
            sale = conn.execute(
                """SELECT sale_id, unpaid_amount, company_code
                   FROM sales WHERE sale_no = ? AND status = '정상'""",
                (alloc["sale_no"],),
            ).fetchone()
            if not sale:
                raise ValueError(f"매출 없음: {alloc['sale_no']}")
            if sale["company_code"] != company_code:
                raise ValueError(
                    f"매출 {alloc['sale_no']}는 거래처 {company_code}의 것이 아님"
                )
            if alloc["amount"] > sale["unpaid_amount"]:
                raise ValueError(
                    f"매출 {alloc['sale_no']} 미수금({sale['unpaid_amount']:,}) 보다 "
                    f"많은 충당({alloc['amount']:,}) 시도"
                )

            conn.execute(
                """INSERT INTO collection_allocations
                   (collection_id, sale_id, allocated_amount)
                   VALUES (?, ?, ?)""",
                (coll_id, sale["sale_id"], alloc["amount"]),
            )
            _refresh_sale_status(conn, sale["sale_id"])

        conn.commit()
        return c_no
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def register_collection_auto(
    company_code: str,
    amount: int,
    collection_date: Optional[date] = None,
    payment_method: str = "계좌이체",
    bank_account: str = "",
    depositor_name: str = "",
    note: str = "",
) -> dict:
    """
    수금 등록 - 자동 충당 (가장 오래된 미수 매출부터)

    반환: {collection_no, allocations: [...], unallocated: int}
    """
    conn = get_conn()
    try:
        # 미수 매출 (오래된 순) 조회
        unpaid_sales = conn.execute(
            """SELECT sale_id, sale_no, unpaid_amount
               FROM sales
               WHERE company_code = ? AND status = '정상' AND unpaid_amount > 0
               ORDER BY sale_date, sale_id""",
            (company_code,),
        ).fetchall()
    finally:
        conn.close()

    # 자동 충당 계획 수립
    allocations = []
    remaining = amount
    for s in unpaid_sales:
        if remaining <= 0:
            break
        alloc = min(remaining, s["unpaid_amount"])
        allocations.append({"sale_no": s["sale_no"], "amount": alloc})
        remaining -= alloc

    # 일반 등록 함수에 위임
    c_no = register_collection(
        company_code=company_code,
        amount=amount,
        allocations=allocations,
        collection_date=collection_date,
        payment_method=payment_method,
        bank_account=bank_account,
        depositor_name=depositor_name,
        note=note,
    )

    return {
        "collection_no": c_no,
        "allocations": allocations,
        "unallocated": remaining,  # 선수금 (충당 못한 금액)
    }


def cancel_collection(collection_no: str, reason: str = ""):
    """
    수금 취소 - 충당된 매출의 미수금 원복
    """
    conn = get_conn()
    try:
        coll = conn.execute(
            "SELECT collection_id, status FROM collections WHERE collection_no = ?",
            (collection_no,),
        ).fetchone()
        if not coll:
            raise ValueError(f"수금 없음: {collection_no}")
        if coll["status"] == "취소":
            raise ValueError("이미 취소된 수금입니다")

        # 충당된 sale_id 목록 확보 (취소 처리 전에)
        affected_sales = [
            r["sale_id"] for r in conn.execute(
                "SELECT sale_id FROM collection_allocations WHERE collection_id = ?",
                (coll["collection_id"],),
            ).fetchall()
        ]

        # 수금 상태를 '취소'로 변경 (충당 레코드는 살려서 이력 보존)
        conn.execute(
            """UPDATE collections
               SET status = '취소',
                   note = COALESCE(note || ' | ', '') || ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE collection_id = ?""",
            (f"[취소] {reason}", coll["collection_id"]),
        )

        # 영향받은 매출 미수금 재계산 (status='취소'면 _refresh_sale_status에서 제외됨)
        for sale_id in affected_sales:
            _refresh_sale_status(conn, sale_id)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_collection(collection_no: str) -> Optional[dict]:
    """수금 상세 (헤더 + 충당 내역)"""
    conn = get_conn()
    try:
        header = conn.execute(
            """SELECT c.*, co.company_name
               FROM collections c
               JOIN companies co ON c.company_code = co.company_code
               WHERE c.collection_no = ?""",
            (collection_no,),
        ).fetchone()
        if not header:
            return None

        allocs = conn.execute(
            """SELECT a.allocated_amount, s.sale_no, s.sale_date, s.total_amount
               FROM collection_allocations a
               JOIN sales s ON a.sale_id = s.sale_id
               WHERE a.collection_id = ?
               ORDER BY s.sale_date""",
            (header["collection_id"],),
        ).fetchall()

        return {
            "header": dict(header),
            "allocations": [dict(a) for a in allocs],
        }
    finally:
        conn.close()


def get_collection_history(
    company_code: str,
    start_date: date = None,
    end_date: date = None,
    include_cancelled: bool = False,
) -> list[dict]:
    """거래처별 수금 이력"""
    conn = get_conn()
    try:
        sql = """SELECT collection_no, collection_date, amount, allocated_amount,
                        unallocated, payment_method, depositor_name, status, note
                 FROM collections
                 WHERE company_code = ?"""
        params = [company_code]
        if not include_cancelled:
            sql += " AND status = '정상'"
        if start_date:
            sql += " AND collection_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND collection_date <= ?"
            params.append(end_date)
        sql += " ORDER BY collection_date, collection_id"

        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def get_collection_summary(start_date: date = None, end_date: date = None) -> dict:
    """수금 통계"""
    conn = get_conn()
    try:
        sql = """SELECT
                     COUNT(*) AS count,
                     COALESCE(SUM(amount), 0) AS total_amount,
                     COALESCE(SUM(allocated_amount), 0) AS total_allocated,
                     COALESCE(SUM(unallocated), 0) AS total_unallocated
                 FROM collections WHERE status = '정상'"""
        params = []
        if start_date:
            sql += " AND collection_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND collection_date <= ?"
            params.append(end_date)
        return dict(conn.execute(sql, params).fetchone())
    finally:
        conn.close()


# ============================================================
# 수금 계획 (예정 입금 약속)
# ============================================================
def register_plan(
    company_code: str,
    plan_date: date,
    amount: int,
    note: str = "",
) -> int:
    """수금 계획 등록"""
    conn = get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO collection_plans
               (company_code, plan_date, amount, note, status)
               VALUES (?, ?, ?, ?, '예정')""",
            (company_code, plan_date, amount, note),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_plan(
    plan_id: int,
    plan_date: date = None,
    amount: int = None,
    note: str = None,
    status: str = None,
):
    sets, params = [], []
    if plan_date is not None:
        sets.append("plan_date=?"); params.append(plan_date)
    if amount is not None:
        sets.append("amount=?"); params.append(amount)
    if note is not None:
        sets.append("note=?"); params.append(note)
    if status is not None:
        sets.append("status=?"); params.append(status)
        if status == '완료':
            sets.append("completed_at=CURRENT_TIMESTAMP")
    if not sets:
        return
    params.append(plan_id)
    conn = get_conn()
    try:
        conn.execute(
            f"UPDATE collection_plans SET {', '.join(sets)} WHERE plan_id=?",
            params,
        )
        conn.commit()
    finally:
        conn.close()


def delete_plan(plan_id: int):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM collection_plans WHERE plan_id=?", (plan_id,))
        conn.commit()
    finally:
        conn.close()


def get_plans(
    only_pending: bool = True,
    company_code: str = None,
) -> list[dict]:
    """수금 계획 목록"""
    conn = get_conn()
    try:
        sql = """SELECT p.*, c.company_name, c.phone
                 FROM collection_plans p
                 JOIN companies c ON p.company_code = c.company_code
                 WHERE 1=1"""
        params = []
        if only_pending:
            sql += " AND p.status IN ('예정', '연체')"
        if company_code:
            sql += " AND p.company_code = ?"
            params.append(company_code)
        sql += " ORDER BY p.plan_date ASC, p.plan_id ASC"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def update_plan_overdue_status():
    """연체 처리 - 약속일 지났는데 예정 상태인 것"""
    conn = get_conn()
    try:
        today = date.today()
        conn.execute(
            """UPDATE collection_plans SET status='연체'
               WHERE status='예정' AND plan_date < ?""",
            (today,)
        )
        conn.commit()
    finally:
        conn.close()
