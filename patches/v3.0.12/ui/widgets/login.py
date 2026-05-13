"""로그인 다이얼로그"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/..')

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QWidget,
)

from auth_module import authenticate, Session, log_action
from ui.common import msg_warning


def _center_on_primary_screen(widget):
    """현재 화면(주 모니터)의 가운데로 위젯을 옮긴다.
    이전 다중 모니터 환경의 좌표 기억으로 화면 밖에 그려지는 사고 방지."""
    try:
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        w = widget.frameGeometry().width() or widget.width()
        h = widget.frameGeometry().height() or widget.height()
        x = geo.x() + max(0, (geo.width() - w) // 2)
        y = geo.y() + max(0, (geo.height() - h) // 2)
        widget.move(x, y)
    except Exception:
        pass


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("(주)정원철강 로그인")
        # 입력칸 라벨이 위에 별도로 들어가므로 세로 약간 키움
        self.setFixedSize(440, 460)
        self.setStyleSheet(
            "QDialog { background-color: white; }"
            "QLabel { color: #111827; background: transparent; }"
        )
        self._init_ui()
        _center_on_primary_screen(self)

    def showEvent(self, ev):
        super().showEvent(ev)
        _center_on_primary_screen(self)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 28, 40, 24)
        layout.setSpacing(10)

        # 로고
        logo = QLabel("💼")
        logo.setStyleSheet("font-size: 44pt; color: #111827;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        # 타이틀
        title = QLabel("JWSteel 통합전산")
        title.setStyleSheet(
            "font-size: 18pt; font-weight: bold; color: #111827;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 서브타이틀
        sub = QLabel("로그인이 필요합니다")
        sub.setStyleSheet("color: #6b7280; font-size: 10pt;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        layout.addSpacing(14)

        # ── 사용자명 입력 ──
        layout.addWidget(self._make_field_label("사용자명"))
        self.username_input = self._make_input("아이디 입력")
        layout.addWidget(self.username_input)

        layout.addSpacing(4)

        # ── 비밀번호 입력 ──
        layout.addWidget(self._make_field_label("비밀번호"))
        self.password_input = self._make_input("비밀번호 입력")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self._login)
        layout.addWidget(self.password_input)

        layout.addSpacing(14)

        # 로그인 버튼
        login_btn = QPushButton("로그인")
        login_btn.setMinimumHeight(40)
        login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        login_btn.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: white; "
            "border: none; border-radius: 4px; "
            "font-size: 12pt; font-weight: bold; padding: 8px; }"
            "QPushButton:hover { background-color: #1d4ed8; }"
            "QPushButton:pressed { background-color: #1e40af; }"
        )
        login_btn.clicked.connect(self._login)
        layout.addWidget(login_btn)

        layout.addStretch()

        # 푸터
        company = QLabel("정원철강 · JWSteel")
        company.setStyleSheet("color: #9ca3af; font-size: 9pt;")
        company.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(company)

        self.username_input.setFocus()

    def _make_field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #374151; font-size: 10pt; font-weight: 600; "
            "padding: 2px 2px 0 2px; background: transparent;")
        return lbl

    def _make_input(self, placeholder: str) -> QLineEdit:
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setMinimumHeight(38)
        inp.setStyleSheet(
            "QLineEdit { padding: 8px 12px; "
            "border: 1px solid #d1d5db; border-radius: 4px; "
            "font-size: 11pt; background: white; color: #111827; }"
            "QLineEdit:focus { border: 2px solid #2563eb; "
            "padding: 7px 11px; }"
        )
        return inp

    def _login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            msg_warning(self, "입력 필요", "사용자명과 비밀번호를 입력하세요")
            return

        user = authenticate(username, password)
        if not user:
            msg_warning(self, "로그인 실패",
                        "사용자명 또는 비밀번호가 잘못되었습니다")
            self.password_input.clear()
            self.password_input.setFocus()
            return

        Session.login_set(user)
        log_action("로그인", "user", str(user['user_id']),
                   f"{user['full_name']}({user['role']}) 로그인")
        self.accept()
