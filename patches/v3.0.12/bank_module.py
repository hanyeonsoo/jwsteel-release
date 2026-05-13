"""
은행 거래내역 모듈 - 자동매칭 엔진

흐름:
  엑셀 임포트 → 자동매칭 시도 → 자동/후보/실패로 분류
  → 자동매칭은 일괄 수금등록, 후보는 사용자 선택, 실패는 별칭 추가 후 재시도
"""
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from collections_module import register_collection_auto


DB_PATH = "accounting.db"

# 한국 은행 엑셀 컬럼명 자동인식 패턴
COLUMN_PATTERNS = {
    'date':        ['거래일자', '거래일', '일자', '날짜', '거래일시'],
    'time':        ['거래시간', '시간'],
    'description': ['적요', '거래내역', '거래종류', '구분', '거래내용', '상대계좌예금주명'],
    'depositor':   ['상대계좌예금주명', '보낸분', '받는분', '의뢰인', '수취인', '입금자',
                    '거래자', '거래처', '내용', '거래자명', '보낸이', '거래내용'],
    'withdraw':    ['출금액', '출금', '지급액', '출금금액'],
    'deposit':     ['입금액', '입금', '수입액', '입금금액'],
    'balance':     ['거래후잔액', '잔액', '거래후 잔액'],
    'memo':        ['메모', '비고', '적요메모'],
}


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _normalize(s) -> str:
    """이름 비교용 정규화: (주)/공백/특수문자 제거 + 소문자"""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = str(s).strip().lower()
    for token in ['(주)', '㈜', '(유)', '(사)', '(재)', '(합)', '주식회사', '유한회사']:
        s = s.replace(token, '')
    s = re.sub(r'[\s\-_·.,/()]', '', s)
    return s


def _detect_columns(df: pd.DataFrame) -> dict:
    col_map = {}
    for key, patterns in COLUMN_PATTERNS.items():
        for col in df.columns:
            col_clean = re.sub(r'\s', '', str(col))
            for pat in patterns:
                if pat in col_clean:
                    col_map[key] = col
                    break
            if key in col_map:
                break
    return col_map


def _to_int(v):
    if pd.isna(v) or v == '':
        return 0
    if isinstance(v, str):
        v = v.replace(',', '').replace(' ', '')
        if not v or v == '-':
            return 0
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return 0


def import_bank_excel(
    file_path: str,
    bank_account: str = "",
    skip_rows: int = 0,
) -> dict:
    """은행 엑셀/CSV 임포트 - 컬럼명 자동 인식 + 기업은행 특수 포맷"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(file_path)

    # 1차: 기업은행 xlsx 시도 (inlineStr 형식)
    if path.suffix.lower() == '.xlsx':
        df = _try_read_ibk(file_path)
        if df is not None:
            return _import_dataframe(df, bank_account)

    # 2차: pandas 일반 읽기
    if path.suffix.lower() in ['.xlsx', '.xls', '.xlsm']:
        engine = 'xlrd' if path.suffix.lower() == '.xls' else None
        df = pd.read_excel(file_path, skiprows=skip_rows, engine=engine)
    elif path.suffix.lower() == '.csv':
        df = pd.read_csv(file_path, skiprows=skip_rows, encoding='utf-8-sig')
    else:
        raise ValueError(f"지원하지 않는 형식: {path.suffix}")

    return _import_dataframe(df, bank_account)


def _try_read_ibk(file_path: str):
    """기업은행 엑셀 포맷 시도 (xml inlineStr 직접 파싱)"""
    import zipfile, xml.etree.ElementTree as ET
    try:
        with zipfile.ZipFile(file_path) as z:
            if 'xl/worksheets/sheet1.xml' not in z.namelist():
                return None
            with z.open('xl/worksheets/sheet1.xml') as f:
                xml = f.read().decode('utf-8')

        ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        root = ET.fromstring(xml)
        sheet_data = root.find('main:sheetData', ns)
        if sheet_data is None:
            return None

        rows = []
        for row in sheet_data.findall('main:row', ns):
            cells = []
            for c in row.findall('main:c', ns):
                t = c.get('t', 'n')
                if t == 'inlineStr':
                    is_elem = c.find('main:is', ns)
                    if is_elem is not None:
                        t_elem = is_elem.find('main:t', ns)
                        cells.append(t_elem.text if t_elem is not None else '')
                    else:
                        cells.append('')
                else:
                    v = c.find('main:v', ns)
                    cells.append(v.text if v is not None else '')
            rows.append(cells)

        # 헤더 찾기 - "거래일시" 포함된 행
        header_idx = None
        for i, r in enumerate(rows):
            if any('거래일시' in str(c) or '거래일자' in str(c) for c in r):
                header_idx = i
                break

        if header_idx is None:
            return None

        # 헤더 정규화
        headers = [str(c).strip() for c in rows[header_idx]]
        # 데이터 행
        data_rows = []
        for r in rows[header_idx + 1:]:
            # '합계' 행 스킵
            if r and ('합계' in str(r[0]) or '계' == str(r[0]).strip()):
                continue
            # 빈 행 스킵
            if not any(str(c).strip() for c in r):
                continue
            # 헤더 길이에 맞춰 padding
            while len(r) < len(headers):
                r.append('')
            data_rows.append(r[:len(headers)])

        if not data_rows:
            return None

        df = pd.DataFrame(data_rows, columns=headers)
        return df
    except Exception:
        return None


def _import_dataframe(df: pd.DataFrame, bank_account: str = "") -> dict:
    """DataFrame 임포트 처리"""
    col_map = _detect_columns(df)
    if 'date' not in col_map or ('deposit' not in col_map and 'withdraw' not in col_map):
        raise ValueError(
            f"필수 컬럼 인식 실패. 인식된: {col_map}\n원본: {list(df.columns)}"
        )

    conn = get_conn()
    imported = skipped_dup = 0
    try:
        for _, row in df.iterrows():
            d_raw = row[col_map['date']]
            if pd.isna(d_raw) or (isinstance(d_raw, str) and not d_raw.strip()):
                continue
            if isinstance(d_raw, str):
                d_str = re.sub(r'[^\d\-/.: ]', '', d_raw).strip()
                # "2026-05-08 13:15:52" 같은 형식
                d_str = d_str.replace('.', '-').replace('/', '-')
                d_str = d_str.split(' ')[0]  # 시간 떼기
                try:
                    txn_date = datetime.strptime(d_str[:10], '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    continue
            else:
                try:
                    txn_date = pd.Timestamp(d_raw).date()
                except Exception:
                    continue

            withdraw = _to_int(row.get(col_map.get('withdraw'))) if 'withdraw' in col_map else 0
            deposit = _to_int(row.get(col_map.get('deposit'))) if 'deposit' in col_map else 0
            if deposit == 0 and withdraw == 0:
                continue

            def safe_str(key):
                if key not in col_map:
                    return ''
                v = row.get(col_map[key])
                if pd.isna(v):
                    return ''
                return str(v).strip()

            depositor = safe_str('depositor')
            time_val = safe_str('time')
            desc = safe_str('description')
            memo = safe_str('memo')
            balance = _to_int(row.get(col_map.get('balance'))) if 'balance' in col_map else None

            # 기업은행: 거래내용에 보낸사람 들어있음, depositor 비어있을 수 있음
            if not depositor:
                depositor = desc

            initial_status = '무시(출금)' if withdraw > 0 else '미처리'

            try:
                conn.execute(
                    """INSERT INTO bank_transactions
                       (txn_date, txn_time, description, depositor_name,
                        withdraw_amount, deposit_amount, balance, memo,
                        bank_account, match_status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (txn_date, time_val or None, desc or None, depositor or None,
                     withdraw, deposit, balance, memo or None,
                     bank_account or None, initial_status),
                )
                imported += 1
            except sqlite3.IntegrityError:
                skipped_dup += 1

        conn.commit()
        return {
            'imported': imported,
            'skipped_dup': skipped_dup,
            'total_rows': len(df),
            'columns_detected': col_map,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# 매칭 엔진 (핵심)
# ============================================================

def _longest_common_substr(a: str, b: str) -> str:
    if not a or not b:
        return ""
    m, n = len(a), len(b)
    best, end = 0, 0
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i-1] == b[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
                if dp[i][j] > best:
                    best = dp[i][j]
                    end = i
    return a[end - best:end]


def _find_company_candidates(conn, depositor_name: str) -> list[dict]:
    """입금자명 → 거래처 후보 + 이름 매칭 점수 (0~60)"""
    if not depositor_name:
        return []
    norm_dep = _normalize(depositor_name)
    if not norm_dep:
        return []

    rows = conn.execute(
        """SELECT c.company_code, c.company_name,
                  GROUP_CONCAT(a.alias, '||') AS aliases
           FROM companies c
           LEFT JOIN company_aliases a ON c.company_code = a.company_code
           WHERE c.is_active = 1 AND c.can_sell = 1
           GROUP BY c.company_code, c.company_name"""
    ).fetchall()

    candidates = {}
    for r in rows:
        code = r['company_code']
        name = r['company_name']
        norm_name = _normalize(name)
        norm_aliases = []
        if r['aliases']:
            norm_aliases = [_normalize(a) for a in r['aliases'].split('||')]

        score = 0
        # 정확 일치 (정규화 후)
        if norm_dep == norm_name or norm_dep in norm_aliases:
            score = 60
        # 포함 관계
        elif norm_dep in norm_name or (len(norm_name) >= 4 and norm_name in norm_dep):
            score = 45
        elif any(norm_dep == a for a in norm_aliases if a):
            score = 60
        elif any(norm_dep in a or (len(a) >= 4 and a in norm_dep)
                 for a in norm_aliases if a):
            score = 45
        # 부분 일치 (3글자 이상)
        elif len(norm_dep) >= 3 and len(norm_name) >= 3:
            common = _longest_common_substr(norm_dep, norm_name)
            if len(common) >= 3:
                score = 25 + min((len(common) - 3) * 5, 15)

        if score > 0:
            candidates[code] = {
                'company_code': code,
                'company_name': name,
                'name_match_score': score,
            }

    return sorted(candidates.values(), key=lambda x: -x['name_match_score'])


def _calc_amount_score(conn, company_code: str, deposit_amount: int) -> int:
    """미수금과 입금액 매칭 점수 (0~40)"""
    rows = conn.execute(
        """SELECT unpaid_amount FROM sales
           WHERE company_code=? AND status='정상' AND unpaid_amount > 0""",
        (company_code,),
    ).fetchall()
    unpaid_list = [r['unpaid_amount'] for r in rows]
    total_unpaid = sum(unpaid_list)

    if total_unpaid == 0:
        return 5  # 미수 없어도 선수금 가능성
    if deposit_amount in unpaid_list:
        return 40   # 단일 매출 정확 일치
    if deposit_amount == total_unpaid:
        return 40   # 합계 정확 일치
    if deposit_amount <= total_unpaid:
        return 25   # 자동충당 가능
    return 15      # 미수보다 큼 (선수금)


def auto_match_all() -> dict:
    """
    미처리 거래에 대해 일괄 매칭 시도
    실제 수금은 등록하지 않고 매칭 결과만 기록
    """
    conn = get_conn()
    try:
        pending = conn.execute(
            """SELECT bank_tx_id, txn_date, depositor_name, deposit_amount
               FROM bank_transactions
               WHERE match_status='미처리' AND deposit_amount > 0"""
        ).fetchall()

        auto = candidates = nomatch = 0

        for tx in pending:
            cands = _find_company_candidates(conn, tx['depositor_name'])
            if not cands:
                conn.execute(
                    """UPDATE bank_transactions
                       SET match_status='매칭실패', match_score=0
                       WHERE bank_tx_id=?""",
                    (tx['bank_tx_id'],),
                )
                nomatch += 1
                continue

            best = None
            for c in cands:
                amt_score = _calc_amount_score(
                    conn, c['company_code'], tx['deposit_amount']
                )
                total = c['name_match_score'] + amt_score
                if best is None or total > best['score']:
                    best = {
                        'code': c['company_code'],
                        'name': c['company_name'],
                        'score': total,
                    }

            if best['score'] >= 90:
                status = '자동매칭'; auto += 1
            elif best['score'] >= 60:
                status = '후보제시'; candidates += 1
            else:
                status = '매칭실패'; nomatch += 1

            conn.execute(
                """UPDATE bank_transactions
                   SET match_status=?, match_score=?, matched_company_code=?
                   WHERE bank_tx_id=?""",
                (status, best['score'],
                 best['code'] if best['score'] >= 60 else None,
                 tx['bank_tx_id']),
            )

        conn.commit()
        return {'auto_matched': auto, 'candidates': candidates,
                'no_match': nomatch}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def confirm_auto_matches() -> int:
    """'자동매칭' 상태 → 실제 수금 등록"""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT bank_tx_id, txn_date, depositor_name, deposit_amount,
                      matched_company_code, bank_account
               FROM bank_transactions
               WHERE match_status='자동매칭' AND collection_id IS NULL"""
        ).fetchall()
    finally:
        conn.close()

    registered = 0
    for tx in rows:
        try:
            result = register_collection_auto(
                company_code=tx['matched_company_code'],
                amount=tx['deposit_amount'],
                collection_date=date.fromisoformat(tx['txn_date']),
                payment_method='계좌이체',
                bank_account=tx['bank_account'] or '',
                depositor_name=tx['depositor_name'] or '',
                note='[은행자동매칭]',
            )
            conn = get_conn()
            try:
                cid = conn.execute(
                    "SELECT collection_id FROM collections WHERE collection_no=?",
                    (result['collection_no'],),
                ).fetchone()['collection_id']
                conn.execute(
                    """UPDATE bank_transactions
                       SET collection_id=?, matched_at=CURRENT_TIMESTAMP
                       WHERE bank_tx_id=?""",
                    (cid, tx['bank_tx_id']),
                )
                conn.commit()
                registered += 1
            finally:
                conn.close()
        except Exception as e:
            print(f"   ⚠ 등록 실패 (bank_tx_id={tx['bank_tx_id']}): {e}")

    return registered


def apply_match(bank_tx_id: int, company_code: str, learn_alias: bool = True) -> str:
    """사용자 확정 매칭 + 별칭 학습"""
    conn = get_conn()
    try:
        tx = conn.execute(
            "SELECT * FROM bank_transactions WHERE bank_tx_id=?", (bank_tx_id,),
        ).fetchone()
        if not tx:
            raise ValueError(f"거래 없음: {bank_tx_id}")
        if tx['collection_id']:
            raise ValueError("이미 매칭된 거래입니다")
        tx = dict(tx)
    finally:
        conn.close()

    if learn_alias and tx['depositor_name']:
        add_alias(company_code, tx['depositor_name'], auto_learned=True)

    result = register_collection_auto(
        company_code=company_code,
        amount=tx['deposit_amount'],
        collection_date=date.fromisoformat(tx['txn_date']),
        payment_method='계좌이체',
        bank_account=tx['bank_account'] or '',
        depositor_name=tx['depositor_name'] or '',
        note='[은행수동매칭]',
    )

    conn = get_conn()
    try:
        cid = conn.execute(
            "SELECT collection_id FROM collections WHERE collection_no=?",
            (result['collection_no'],),
        ).fetchone()['collection_id']
        conn.execute(
            """UPDATE bank_transactions
               SET match_status='수동매칭', matched_company_code=?,
                   collection_id=?, matched_at=CURRENT_TIMESTAMP
               WHERE bank_tx_id=?""",
            (company_code, cid, bank_tx_id),
        )
        conn.commit()
    finally:
        conn.close()

    return result['collection_no']


def add_alias(company_code: str, alias: str, auto_learned: bool = False):
    """거래처 별칭 등록"""
    if not alias or not str(alias).strip():
        return
    conn = get_conn()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO company_aliases
               (company_code, alias, auto_learned) VALUES (?, ?, ?)""",
            (company_code, str(alias).strip(), 1 if auto_learned else 0),
        )
        conn.commit()
    finally:
        conn.close()


def get_pending(status: str = None) -> list[dict]:
    conn = get_conn()
    try:
        sql = """SELECT b.*, c.company_name AS matched_name
                 FROM bank_transactions b
                 LEFT JOIN companies c ON b.matched_company_code=c.company_code"""
        params = []
        if status:
            sql += " WHERE b.match_status=?"; params.append(status)
        sql += " ORDER BY b.txn_date, b.bank_tx_id"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def get_match_summary() -> dict:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT match_status, COUNT(*) AS cnt,
                      SUM(deposit_amount) AS deposit_total
               FROM bank_transactions GROUP BY match_status"""
        ).fetchall()
        return {r['match_status']: dict(r) for r in rows}
    finally:
        conn.close()
