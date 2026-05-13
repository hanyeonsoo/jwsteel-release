"""
첫 실행 시 자동 셋업 마법사
- config.json 없으면 자동 생성
- Supabase 연결 정보 미리 입력되어 있음 (호스트, 사용자명)
- 직원은 비밀번호만 입력하면 됨
"""
import os
import sys
import json
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFormLayout, QMessageBox, QFrame, QCheckBox,
)


# 기본 Supabase 연결 정보 (회사 공통)
DEFAULT_CONFIG = {
    "db_type": "postgres",
    "host": "aws-1-ap-northeast-2.pooler.supabase.com",
    "port": 5432,
    "database": "postgres",
    "user": "postgres.nziqdobyuuhvkknyjusq",
    "password": "",  # 직원이 입력
    "sslmode": "require",
    "backup_dir": "backups",
    "backup_keep_days": 30,
}


def get_config_path() -> Path:
    """config.json 위치 - 실행 위치 자동 감지"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 환경
        exe_dir = Path(sys.executable).parent
        internal = exe_dir / "_internal"
        base = internal if internal.exists() else exe_dir
    else:
        # 개발 환경
        base = Path(__file__).resolve().parent
    return base / "config.json"


def config_exists() -> bool:
    """유효한 config.json 이 있는지"""
    path = get_config_path()
    if not path.exists():
        return False
    try:
        cfg = json.loads(path.read_text(encoding='utf-8'))
        return bool(cfg.get('password'))  # 비밀번호 있어야 유효
    except Exception:
        return False


class FirstRunSetupDialog(QDialog):
    """첫 실행 시 자동 셋업 마법사"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JWSteel 통합전산 - 초기 설정")
        self.setMinimumWidth(600)
        self.setStyleSheet("""
            QDialog { background: white; }
            QLabel { color: #1f2937; }
            QLineEdit {
                padding: 10px; border: 2px solid #e5e7eb;
                border-radius: 6px; font-size: 11pt;
            }
            QLineEdit:focus { border-color: #2563eb; }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(16)

        # 헤더
        title = QLabel("🏢 JWSteel 통합전산")
        title.setStyleSheet(
            "font-size: 22pt; font-weight: bold; color: #2563eb;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("처음 실행되었습니다. 클라우드 DB 연결 설정을 진행합니다.")
        subtitle.setStyleSheet("color: #6b7280; font-size: 11pt;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #e5e7eb;")
        layout.addWidget(line)

        # 안내 박스
        info = QLabel(
            "💡 회사 IT 담당자로부터 받은 <b>DB 비밀번호</b>를 입력하세요.<br/>"
            "<br/>"
            "  • DB 호스트, 사용자명은 자동으로 설정됩니다<br/>"
            "  • 첫 설정 후에는 자동으로 클라우드 DB에 연결됩니다<br/>"
            "  • 본사·지점 어디서든 같은 데이터를 사용합니다"
        )
        info.setStyleSheet(
            "background: #eff6ff; color: #1e3a8a; padding: 16px; "
            "border-radius: 8px; line-height: 1.6;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # 폼
        form = QFormLayout()
        form.setVerticalSpacing(12)

        # 호스트 (읽기 전용 표시)
        host_label = QLabel(DEFAULT_CONFIG['host'])
        host_label.setStyleSheet(
            "padding: 10px; background: #f9fafb; border: 1px solid #e5e7eb; "
            "border-radius: 6px; color: #6b7280; font-family: monospace;")
        form.addRow("🌐 DB 호스트:", host_label)

        # 사용자 (읽기 전용)
        user_label = QLabel(DEFAULT_CONFIG['user'])
        user_label.setStyleSheet(
            "padding: 10px; background: #f9fafb; border: 1px solid #e5e7eb; "
            "border-radius: 6px; color: #6b7280; font-family: monospace;")
        form.addRow("👤 사용자명:", user_label)

        # 비밀번호 (입력!)
        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.setPlaceholderText("회사 IT 담당자로부터 받은 비밀번호")
        form.addRow("🔑 DB 비밀번호:", self.pw_input)

        # 표시 토글
        self.show_pw = QCheckBox("비밀번호 표시")
        self.show_pw.stateChanged.connect(self._toggle_pw)
        form.addRow("", self.show_pw)

        layout.addLayout(form)

        # 안내
        warn = QLabel(
            "⚠ 비밀번호는 이 PC에만 저장되며, 외부로 전송되지 않습니다."
        )
        warn.setStyleSheet(
            "background: #fef3c7; color: #92400e; padding: 10px; "
            "border-radius: 6px; font-size: 9pt;")
        layout.addWidget(warn)

        # 버튼
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("취소")
        cancel_btn.setStyleSheet(
            "background: white; color: #374151; padding: 10px 24px; "
            "border: 1px solid #d1d5db; border-radius: 6px;")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("✅ 설정 완료")
        ok_btn.setStyleSheet(
            "background: #2563eb; color: white; padding: 10px 32px; "
            "font-weight: bold; border: none; border-radius: 6px;")
        ok_btn.clicked.connect(self._save)
        ok_btn.setDefault(True)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

        self.pw_input.setFocus()

    def _toggle_pw(self, state):
        if state == 2:  # Checked
            self.pw_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)

    def _save(self):
        pw = self.pw_input.text().strip()
        if not pw:
            QMessageBox.warning(self, "입력 필요", "비밀번호를 입력하세요.")
            return

        # config 저장
        cfg = dict(DEFAULT_CONFIG)
        cfg['password'] = pw

        try:
            path = get_config_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(cfg, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", str(e))
            return

        # 연결 테스트
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=cfg['host'], port=cfg['port'],
                database=cfg['database'], user=cfg['user'],
                password=cfg['password'],
                sslmode=cfg['sslmode'],
                connect_timeout=10,
            )
            conn.close()
        except ImportError:
            # psycopg2 없으면 자동 설치
            import subprocess
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install",
                     "psycopg2-binary", "--quiet"]
                )
            except Exception:
                QMessageBox.warning(
                    self, "라이브러리 누락",
                    "psycopg2-binary 가 설치되지 않았습니다.\n"
                    "관리자에게 문의하세요."
                )
                return
        except Exception as e:
            QMessageBox.critical(
                self, "연결 실패",
                f"DB 연결에 실패했습니다.\n\n오류: {e}\n\n"
                "비밀번호가 맞는지 확인하세요.\n"
                "회사 IT 담당자에게 문의해 주세요."
            )
            # config 삭제 (다시 입력하게)
            try:
                get_config_path().unlink()
            except Exception:
                pass
            return

        QMessageBox.information(
            self, "설정 완료",
            "✅ 클라우드 DB 연결 성공!\n\n"
            "이제 JWSteel 통합전산을 사용할 수 있습니다."
        )
        self.accept()


def run_first_setup_if_needed():
    """필요하면 셋업 마법사 실행"""
    if config_exists():
        return True  # 이미 설정됨

    # 셋업 마법사 실행
    dlg = FirstRunSetupDialog()
    result = dlg.exec()
    return result == QDialog.DialogCode.Accepted
