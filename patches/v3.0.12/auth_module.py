"""사용자/권한/감사로그 모듈"""
import sqlite3
import hashlib
import os
from datetime import datetime
from typing import Optional


DB_PATH = "accounting.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_pw(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


# ============================================================
# 현재 로그인한 사용자 (전역)
# ============================================================
class Session:
    user_id: int = None
    username: str = None
    full_name: str = None
    role: str = None        # '관리자' / '일반'

    @classmethod
    def is_admin(cls) -> bool:
        return cls.role == '관리자'

    @classmethod
    def is_executive(cls) -> bool:
        return cls.role == '임원'

    @classmethod
    def is_staff(cls) -> bool:
        return cls.role == '일반'

    @classmethod
    def can_access(cls, menu_key: str) -> bool:
        """현재 사용자가 메뉴 접근 가능?"""
        if cls.user_id is None:
            return False
        from permissions import can_access as _can_access
        return _can_access(cls.user_id, menu_key)

    @classmethod
    def is_logged_in(cls) -> bool:
        return cls.user_id is not None

    @classmethod
    def login_set(cls, user: dict):
        cls.user_id = user['user_id']
        cls.username = user['username']
        cls.full_name = user['full_name']
        cls.role = user['role']

    @classmethod
    def logout(cls):
        cls.user_id = cls.username = cls.full_name = cls.role = None


# ============================================================
# 인증
# ============================================================
def authenticate(username: str, password: str) -> Optional[dict]:
    """로그인 시도. 성공 시 user dict, 실패 시 None"""
    conn = get_conn()
    try:
        u = conn.execute(
            "SELECT * FROM users WHERE username=? AND is_active=1",
            (username,),
        ).fetchone()
        if not u:
            return None
        if hash_pw(password, u['salt']) != u['password_hash']:
            return None
        # 마지막 로그인 갱신
        conn.execute(
            "UPDATE users SET last_login=CURRENT_TIMESTAMP WHERE user_id=?",
            (u['user_id'],),
        )
        conn.commit()
        return dict(u)
    finally:
        conn.close()


def change_password(user_id: int, new_password: str):
    conn = get_conn()
    try:
        salt = os.urandom(16).hex()
        pw_hash = hash_pw(new_password, salt)
        conn.execute(
            """UPDATE users SET password_hash=?, salt=?,
                                updated_at=CURRENT_TIMESTAMP
               WHERE user_id=?""",
            (pw_hash, salt, user_id),
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================
# 사용자 관리 (관리자 전용)
# ============================================================
def list_users(include_inactive: bool = False) -> list[dict]:
    conn = get_conn()
    try:
        sql = """SELECT user_id, username, full_name, role, department,
                        is_active, last_login, created_at
                 FROM users"""
        if not include_inactive:
            sql += " WHERE is_active=1"
        sql += " ORDER BY user_id"
        return [dict(r) for r in conn.execute(sql).fetchall()]
    finally:
        conn.close()


def create_user(
    username: str, password: str, full_name: str,
    role: str = '일반', department: str = '',
) -> int:
    if role not in ('관리자', '일반'):
        raise ValueError("권한은 '관리자' 또는 '일반'")
    if len(password) < 6:
        raise ValueError("비밀번호는 6자 이상")

    conn = get_conn()
    try:
        salt = os.urandom(16).hex()
        pw_hash = hash_pw(password, salt)
        cur = conn.execute(
            """INSERT INTO users
               (username, password_hash, salt, full_name, role, department)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (username, pw_hash, salt, full_name, role, department or None),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError(f"이미 존재하는 사용자명: {username}")
    finally:
        conn.close()


def update_user(
    user_id: int, full_name: str = None, role: str = None,
    department: str = None, is_active: int = None,
):
    sets = []
    params = []
    if full_name is not None:
        sets.append("full_name=?"); params.append(full_name)
    if role is not None:
        if role not in ('관리자', '일반'):
            raise ValueError("권한은 '관리자' 또는 '일반'")
        sets.append("role=?"); params.append(role)
    if department is not None:
        sets.append("department=?"); params.append(department or None)
    if is_active is not None:
        sets.append("is_active=?"); params.append(is_active)
    if not sets:
        return
    sets.append("updated_at=CURRENT_TIMESTAMP")
    params.append(user_id)

    conn = get_conn()
    try:
        conn.execute(
            f"UPDATE users SET {', '.join(sets)} WHERE user_id=?", params
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================
# 감사 로그
# ============================================================
def log_action(action: str, target_type: str = None,
               target_id: str = None, detail: str = None):
    """현재 로그인한 사용자의 작업 기록"""
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO audit_logs
               (user_id, username, action, target_type, target_id, detail)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (Session.user_id, Session.username, action,
             target_type, target_id, detail),
        )
        conn.commit()
    finally:
        conn.close()


def get_audit_logs(
    limit: int = 100, user_id: int = None, action: str = None,
) -> list[dict]:
    conn = get_conn()
    try:
        sql = "SELECT * FROM audit_logs WHERE 1=1"
        params = []
        if user_id is not None:
            sql += " AND user_id=?"; params.append(user_id)
        if action:
            sql += " AND action LIKE ?"; params.append(f"%{action}%")
        sql += " ORDER BY log_id DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


# ============================================================
# 권한 체크 데코레이터
# ============================================================
def require_admin(func):
    """관리자 전용 함수에 사용"""
    def wrapper(*args, **kwargs):
        if not Session.is_admin():
            raise PermissionError("관리자 권한이 필요합니다")
        return func(*args, **kwargs)
    return wrapper
