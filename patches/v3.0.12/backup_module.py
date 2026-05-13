"""
자동 백업 + 복원 모듈

- DB 자동 백업 (실행 시마다 1일 1회 + 매뉴얼 백업)
- 보관기간 지난 백업 자동 삭제 (30일)
- 백업 파일명: accounting_YYYYMMDD_HHMMSS.db
"""
import os
import shutil
import sqlite3
import json
from datetime import datetime, date, timedelta
from pathlib import Path

from db_adapter import CONFIG, is_postgres


BACKUP_DIR = CONFIG.get("backup_dir", "backups")
KEEP_DAYS = CONFIG.get("backup_keep_days", 30)


def ensure_backup_dir() -> Path:
    p = Path(BACKUP_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


def manual_backup() -> str:
    """매뉴얼 백업 - 즉시 실행"""
    if is_postgres():
        return _backup_postgres()
    return _backup_sqlite()


def _backup_sqlite() -> str:
    src = CONFIG.get("db_path", "accounting.db")
    if not Path(src).exists():
        raise FileNotFoundError(f"DB 파일 없음: {src}")

    backup_dir = ensure_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"accounting_{timestamp}.db"

    # SQLite 백업 API 사용 (락 안전)
    src_conn = sqlite3.connect(src)
    dest_conn = sqlite3.connect(str(dest))
    src_conn.backup(dest_conn)
    src_conn.close()
    dest_conn.close()

    return str(dest)


def _backup_postgres() -> str:
    """PostgreSQL은 pg_dump 사용"""
    import subprocess
    backup_dir = ensure_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"accounting_{timestamp}.sql"

    env = os.environ.copy()
    env['PGPASSWORD'] = CONFIG['password']
    cmd = [
        "pg_dump",
        "-h", str(CONFIG['host']),
        "-p", str(CONFIG.get('port', 5432)),
        "-U", CONFIG['user'],
        "-d", CONFIG['database'],
        "-f", str(dest),
    ]
    try:
        subprocess.run(cmd, env=env, check=True)
    except FileNotFoundError:
        raise RuntimeError(
            "pg_dump 명령을 찾을 수 없습니다. PostgreSQL 클라이언트를 설치하세요"
        )
    return str(dest)


def auto_backup_if_needed() -> str | None:
    """오늘 백업이 없으면 자동 백업"""
    backup_dir = ensure_backup_dir()
    today = date.today().strftime("%Y%m%d")
    existing = list(backup_dir.glob(f"accounting_{today}_*"))
    if existing:
        return None
    path = manual_backup()
    cleanup_old_backups()
    return path


def cleanup_old_backups() -> int:
    """KEEP_DAYS 이전의 백업 삭제"""
    backup_dir = ensure_backup_dir()
    cutoff = datetime.now() - timedelta(days=KEEP_DAYS)
    deleted = 0
    for f in backup_dir.glob("accounting_*.*"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                deleted += 1
        except Exception:
            pass
    return deleted


def list_backups() -> list[dict]:
    """백업 파일 목록 (최신순)"""
    backup_dir = ensure_backup_dir()
    files = []
    for f in backup_dir.glob("accounting_*.*"):
        st = f.stat()
        files.append({
            "filename": f.name,
            "path": str(f),
            "size": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime),
        })
    return sorted(files, key=lambda x: x['mtime'], reverse=True)


def restore_backup(backup_path: str):
    """백업 복원 - 현재 DB를 백업으로 덮어쓰기"""
    if is_postgres():
        raise NotImplementedError(
            "PostgreSQL 복원은 psql 명령으로 직접 수행하세요:\n"
            f"  psql -h {CONFIG['host']} -U {CONFIG['user']} "
            f"-d {CONFIG['database']} < {backup_path}"
        )

    src = Path(backup_path)
    if not src.exists():
        raise FileNotFoundError(f"백업 파일 없음: {backup_path}")

    # 현재 DB 자동 백업 (안전)
    current_db = CONFIG.get("db_path", "accounting.db")
    if Path(current_db).exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safety_backup = ensure_backup_dir() / f"before_restore_{timestamp}.db"
        shutil.copy2(current_db, safety_backup)
        print(f"  안전 백업: {safety_backup}")

    # 복원
    shutil.copy2(src, current_db)
    return current_db


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("사용법:")
        print("  python backup_module.py backup        # 즉시 백업")
        print("  python backup_module.py auto          # 1일 1회 자동 백업")
        print("  python backup_module.py list          # 백업 목록")
        print("  python backup_module.py cleanup       # 오래된 백업 삭제")
        print("  python backup_module.py restore <백업파일>")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "backup":
        path = manual_backup()
        size = Path(path).stat().st_size
        print(f"✓ 백업 완료: {path} ({size:,} bytes)")
    elif cmd == "auto":
        path = auto_backup_if_needed()
        if path:
            print(f"✓ 자동 백업: {path}")
        else:
            print("오늘 이미 백업됨")
    elif cmd == "list":
        backups = list_backups()
        print(f"백업 파일 {len(backups)}개:")
        for b in backups[:20]:
            print(f"  {b['mtime'].strftime('%Y-%m-%d %H:%M')}  "
                  f"{b['size']:>12,} bytes  {b['filename']}")
    elif cmd == "cleanup":
        n = cleanup_old_backups()
        print(f"✓ {n}개 삭제됨 ({KEEP_DAYS}일 이전)")
    elif cmd == "restore":
        if len(sys.argv) < 3:
            print("사용법: python backup_module.py restore <백업파일>")
            sys.exit(1)
        path = sys.argv[2]
        restored = restore_backup(path)
        print(f"✓ 복원 완료: {restored}")
