"""
회계 프로그램 메인 윈도우 v2 (로그인/권한/리포트/관리자 추가)
실행: python ui/main.py  (개발)
     JWSteel.exe         (PyInstaller 배포)
"""
import sys
import os
import sqlite3
from pathlib import Path


def _get_app_root() -> Path:
    """앱 루트 디렉토리 (개발 / PyInstaller 환경 자동 감지)"""
    if getattr(sys, 'frozen', False):
        # PyInstaller로 빌드된 경우 - JWSteel.exe 옆 _internal/
        exe_dir = Path(sys.executable).parent
        internal = exe_dir / "_internal"
        return internal if internal.exists() else exe_dir
    else:
        # 개발 환경 - ui/ 의 부모 폴더
        return Path(__file__).resolve().parent.parent


HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = _get_app_root()
PARENT = str(APP_ROOT)

# Python 모듈 경로
sys.path.insert(0, PARENT)
sys.path.insert(0, HERE)
sys.path.insert(0, str(APP_ROOT / "ui"))

# 작업 디렉토리를 앱 루트로 (accounting.db, config.json 등이 여기 있음)
os.chdir(PARENT)

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QKeySequence, QShortcut, QColor, QGuiApplication
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTreeWidget, QTreeWidgetItem, QStackedWidget, QStatusBar,
    QPushButton, QMessageBox,
)

from auth_module import Session, log_action
from ui.common import MAIN_STYLE
from ui.widgets.login import LoginDialog
from ui.widgets.dashboard import DashboardWidget
from ui.widgets.dashboard_integrated import IntegratedDashboardWidget
from ui.widgets.companies import CompaniesWidget
from ui.widgets.sales import SalesWidget
from ui.widgets.collections import CollectionsWidget
from ui.widgets.purchases import PurchasesWidget
from ui.widgets.bank import BankWidget
from ui.widgets.reports import ReportsWidget
from ui.widgets.admin import AdminWidget
from ui.widgets.vat import VatReportWidget
from ui.widgets.backup import BackupWidget
from ui.widgets.analysis import AnalysisWidget


# 메뉴 트리 — ERP 전산 표준 구성. 카테고리는 클릭 시 펼침/접힘.
# - dict 에 'children' 이 있으면 카테고리(접힘 가능), 없으면 단일 메뉴.
# - admin_only=True 는 권한 무관하게 관리자만.
# - key 가 'dashboard_web' 같이 권한 시스템(permissions.py)에 등록된 키여야 함.
MENU_TREE = [
    {"label": "📊  통합 대시보드", "key": "dashboard_web"},

    {"label": "🏢  기준정보", "key": "_cat_master", "children": [
        {"label": "🤝  거래처 관리",   "key": "companies"},
        {"label": "📦  품목/제품 관리", "key": "items"},
        {"label": "👤  직원 관리",      "key": "admin",  "admin_only": True},
    ]},

    {"label": "💼  영업관리", "key": "_cat_sales", "children": [
        {"label": "✏️  매출 등록",     "key": "sales_register"},
        {"label": "📈  매출 관리",     "key": "sales"},
        {"label": "💵  수금 / 미수금", "key": "collections"},
    ]},

    {"label": "📦  구매관리", "key": "_cat_purchases", "children": [
        {"label": "📉  매입 관리",   "key": "purchases"},
        {"label": "🏦  은행 / 지급", "key": "bank"},
        {"label": "📥  입고 (예정)", "key": "inbound"},
    ]},

    {"label": "🏭  생산 / 재고", "key": "_cat_prod", "children": [
        {"label": "📊  재고 현황",   "key": "inventory"},
        {"label": "🔧  생산 (예정)", "key": "production"},
        {"label": "📤  출고 관리",   "key": "outbound"},
        {"label": "🚚  운송 (예정)", "key": "shipping"},
    ]},

    {"label": "📊  회계 / 보고", "key": "_cat_acct", "children": [
        {"label": "📈  회계 요약",   "key": "dashboard"},
        {"label": "📋  부가세 신고", "key": "vat"},
        {"label": "📊  매출 분석",   "key": "analysis"},
        {"label": "📤  엑셀 출력",   "key": "reports"},
    ]},

    {"label": "⚙️  시스템", "key": "_cat_system", "children": [
        {"label": "💾  시스템 / 백업", "key": "backup", "admin_only": True},
        {"label": "❓  도움말",        "key": "help"},
    ]},
]

# 시작 시 펼쳐둘 카테고리 (열어둘 카테고리 키). 비워두면 전부 접힘.
DEFAULT_EXPANDED = {"_cat_master", "_cat_sales"}


def _all_menu_keys():
    """MENU_TREE 안의 leaf 키 전체 (placeholder 매핑 검증용)"""
    out = []
    for e in MENU_TREE:
        if "children" in e:
            for c in e["children"]:
                out.append(c["key"])
        else:
            out.append(e["key"])
    return out


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            f"(주)정원철강 - {Session.full_name} ({Session.role})")
        self.resize(1400, 900)
        self._init_ui()
        self._update_status()
        self._center_or_clamp_to_screen()

    def _center_or_clamp_to_screen(self):
        """주 모니터 범위 안에 들어오도록 위치 보정.
        이전 다중 모니터/DPI 변경으로 윈도우가 화면 밖에 그려지는 사고 방지."""
        try:
            screen = QGuiApplication.primaryScreen()
            if not screen:
                return
            geo = screen.availableGeometry()
            fr = self.frameGeometry()
            w = fr.width() or 1400
            h = fr.height() or 900
            # 너무 크면 화면에 맞게 줄임
            w = min(w, geo.width())
            h = min(h, geo.height())
            x = geo.x() + max(0, (geo.width() - w) // 2)
            y = geo.y() + max(0, (geo.height() - h) // 2)
            self.setGeometry(x, y, w, h)
        except Exception:
            pass

    def showEvent(self, ev):
        super().showEvent(ev)
        # 보여진 다음에도 다시 한 번 — Qt 가 이전 저장 좌표 적용한 뒤
        fr = self.frameGeometry()
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            # 윈도우의 어떤 부분이라도 화면 밖에 있으면 가운데로 끌어옴
            if (fr.right() < geo.left() + 100 or fr.left() > geo.right() - 100
                or fr.bottom() < geo.top() + 100 or fr.top() > geo.bottom() - 100):
                self._center_or_clamp_to_screen()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 좌측 메뉴
        left = QWidget()
        left.setFixedWidth(220)
        left.setStyleSheet("background-color: #1f2937;")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        logo = QLabel("🏢 (주)정원철강")
        logo.setStyleSheet(
            "color: white; font-size: 14pt; font-weight: bold; "
            "padding: 20px; background-color: #111827;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(logo)

        # 사용자 정보 + 내 정보 버튼
        user_box = QLabel(
            f"👤 {Session.full_name}\n"
            f"{Session.role} · {Session.username}"
        )
        user_box.setStyleSheet(
            "color: white; padding: 12px 20px; "
            "background-color: #374151; font-size: 10pt;")
        left_layout.addWidget(user_box)

        my_btn = QPushButton("🔑 내 정보 / 비밀번호 변경")
        my_btn.setStyleSheet(
            "background-color: #4b5563; color: white; padding: 8px; "
            "border: none; text-align: center; font-size: 9pt;")
        my_btn.clicked.connect(self._open_my_account)
        left_layout.addWidget(my_btn)

        search_btn = QPushButton("🔍  전역 검색  (Ctrl+F)")
        search_btn.setStyleSheet(
            "background-color: #2563eb; color: white; padding: 8px; "
            "border: none; text-align: center; font-size: 9pt;")
        search_btn.clicked.connect(self._open_global_search)
        left_layout.addWidget(search_btn)

        # 메뉴 (계단식 트리)
        self.menu_tree = QTreeWidget()
        self.menu_tree.setHeaderHidden(True)
        self.menu_tree.setRootIsDecorated(True)
        self.menu_tree.setIndentation(16)
        self.menu_tree.setAnimated(True)
        self.menu_tree.setUniformRowHeights(True)
        self.menu_tree.setExpandsOnDoubleClick(False)
        self.menu_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1f2937;
                color: #d1d5db;
                border: none;
                padding: 4px 0;
                font-size: 10pt;
                outline: 0;
            }
            QTreeWidget::item {
                padding: 8px 6px;
                border: none;
            }
            QTreeWidget::item:hover {
                background-color: #374151;
                color: white;
            }
            QTreeWidget::item:selected {
                background-color: #2563eb;
                color: white;
            }
            QTreeWidget::branch {
                background: #1f2937;
            }
            QTreeWidget::branch:has-children:closed {
                image: none;
                border-image: none;
            }
            QTreeWidget::branch:has-children:open {
                image: none;
                border-image: none;
            }
        """)

        # 현재 사용자의 접근 가능 메뉴 (권한 체크)
        from permissions import get_user_permissions
        user_perms = get_user_permissions(Session.user_id) if Session.user_id else set()

        self.visible_keys = []        # 단축키용 (leaf 만, 순서대로)
        self.key_to_item = {}         # 메뉴 키 → QTreeWidgetItem

        def _is_accessible(entry):
            """leaf entry 가 현재 사용자에게 보여야 하는지"""
            if entry.get("admin_only") and not Session.is_admin():
                return False
            return entry["key"] in user_perms

        for entry in MENU_TREE:
            if "children" in entry:
                accessible_children = [c for c in entry["children"] if _is_accessible(c)]
                if not accessible_children:
                    continue  # 권한 있는 자식 없음 → 카테고리 자체 숨김

                cat_item = QTreeWidgetItem([entry["label"]])
                cat_item.setData(0, Qt.ItemDataRole.UserRole, entry["key"])
                f = cat_item.font(0); f.setBold(True); cat_item.setFont(0, f)
                cat_item.setForeground(0, QColor("#fbbf24"))
                cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                self.menu_tree.addTopLevelItem(cat_item)

                for c in accessible_children:
                    leaf = QTreeWidgetItem([c["label"]])
                    leaf.setData(0, Qt.ItemDataRole.UserRole, c["key"])
                    cat_item.addChild(leaf)
                    self.key_to_item[c["key"]] = leaf
                    self.visible_keys.append(c["key"])

                cat_item.setExpanded(entry["key"] in DEFAULT_EXPANDED)
            else:
                if not _is_accessible(entry):
                    continue
                leaf = QTreeWidgetItem([entry["label"]])
                leaf.setData(0, Qt.ItemDataRole.UserRole, entry["key"])
                self.menu_tree.addTopLevelItem(leaf)
                self.key_to_item[entry["key"]] = leaf
                self.visible_keys.append(entry["key"])

        self.menu_tree.itemClicked.connect(self._on_tree_item_clicked)
        left_layout.addWidget(self.menu_tree, stretch=1)

        logout_btn = QPushButton("🚪 로그아웃")
        logout_btn.setStyleSheet(
            "background-color: #374151; color: white; padding: 12px; "
            "border: none; text-align: center;")
        logout_btn.clicked.connect(self._logout)
        left_layout.addWidget(logout_btn)

        info = QLabel("v3.0 통합")
        info.setStyleSheet("color: #6b7280; padding: 8px;")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(info)

        main_layout.addWidget(left)

        # 우측 화면
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: #f9fafb;")

        # 핵심 위젯들 (구현됨)
        from ui.widgets.help import HelpWidget
        from ui.widgets.outbound import OutboundWidget
        from ui.widgets.inventory import InventoryWidget
        from ui.widgets.sales import SalesRegisterTab
        from ui.widgets._filter_bar import auto_install_all
        self.widgets = {
            "dashboard_web":    IntegratedDashboardWidget(),
            "help":             HelpWidget(),
            "dashboard":        DashboardWidget(),
            "companies":        CompaniesWidget(),
            "sales_register":   SalesRegisterTab(),
            "sales":            SalesWidget(),
            "collections":      CollectionsWidget(),
            "purchases":        PurchasesWidget(),
            "bank":             BankWidget(),
            "vat":              VatReportWidget(),
            "analysis":         AnalysisWidget(),
            "reports":          ReportsWidget(),
            "outbound":         OutboundWidget(),
            "inventory":        InventoryWidget(),
        }
        # 통합 대시보드 제외 — 모든 위젯에:
        # 1) 헤더 바로 아래 인라인 필터 행
        # 2) 일자 컬럼 있으면 상단에 DateRangeBar (당일/전일/명일/금월/전월/30일)
        for key, w in self.widgets.items():
            if key == "dashboard_web":
                continue
            try:
                auto_install_all(w)
            except Exception as e:
                print(f"[main] filter install failed for {key}: {e}")
        if Session.is_admin():
            self.widgets["backup"] = BackupWidget()
            self.widgets["admin"] = AdminWidget()

        # 미구현 메뉴 placeholder (outbound/inventory 는 이제 구현됨)
        placeholder_labels = {
            "items":      "📦 품목/제품 관리",
            "inbound":    "📥 입고 관리",
            "production": "🔧 생산 관리",
            "shipping":   "🚚 운송 관리",
        }
        for key, name in placeholder_labels.items():
            if key in self.visible_keys and key not in self.widgets:
                pw = QWidget()
                pl = QVBoxLayout(pw)
                pl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl = QLabel(f"{name}\n\n🚧 개발 예정")
                lbl.setStyleSheet(
                    "font-size: 24pt; color: #9ca3af; font-weight: bold;")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                pl.addWidget(lbl)
                hint = QLabel("이 모듈은 통합 프로그램 확장 단계에서 추가됩니다.")
                hint.setStyleSheet("color: #6b7280; font-size: 11pt;")
                hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
                pl.addWidget(hint)
                self.widgets[key] = pw

        # 모든 visible_keys 의 위젯을 stack 에 한 번씩 등록
        for key in self.visible_keys:
            if key in self.widgets:
                self.stack.addWidget(self.widgets[key])

        main_layout.addWidget(self.stack, stretch=1)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # 첫 leaf 항목 자동 선택 + 표시
        if self.visible_keys:
            first_key = self.visible_keys[0]
            self._select_key(first_key)

        # 단축키
        self._setup_shortcuts()

        # 시작 후 3초 뒤 백그라운드로 업데이트 체크
        QTimer.singleShot(3000, self._check_for_updates_silent)

    def _check_for_updates_silent(self):
        """시작 시 자동 업데이트 체크 (조용히)"""
        try:
            from updater import check_for_updates
            check_for_updates(self, silent=True)
        except Exception:
            pass  # 업데이트 체크 실패는 무시

    def _setup_shortcuts(self):
        # 메뉴 단축키 (Ctrl+1 ~ Ctrl+9) → 보이는 leaf 순서로
        for i, key in enumerate(self.visible_keys[:9]):
            sc = QShortcut(QKeySequence(f"Ctrl+{i+1}"), self)
            sc.activated.connect(lambda k=key: self._select_key(k))

        # F5: 새로고침
        sc_refresh = QShortcut(QKeySequence("F5"), self)
        sc_refresh.activated.connect(self._refresh_current)

        # Ctrl+Q: 종료
        sc_quit = QShortcut(QKeySequence("Ctrl+Q"), self)
        sc_quit.activated.connect(self.close)

        # Ctrl+L: 로그아웃
        sc_logout = QShortcut(QKeySequence("Ctrl+L"), self)
        sc_logout.activated.connect(self._logout)

        # Ctrl+F: 전역 검색
        sc_search = QShortcut(QKeySequence("Ctrl+F"), self)
        sc_search.activated.connect(self._open_global_search)

    def _open_global_search(self):
        from ui.widgets.global_search import GlobalSearchDialog
        dlg = GlobalSearchDialog(self)
        dlg.exec()

    def _refresh_current(self):
        widget = self.stack.currentWidget()
        if hasattr(widget, 'refresh'):
            widget.refresh()
        elif hasattr(widget, 'tabs'):
            current_tab = widget.tabs.currentWidget()
            if hasattr(current_tab, 'refresh'):
                current_tab.refresh()
            elif hasattr(current_tab, '_refresh'):
                current_tab._refresh()
        self._update_status()
        self.status.showMessage(f"🔄 새로고침 완료  |  {Session.full_name}", 2000)

    def _on_tree_item_clicked(self, item, column):
        """트리 항목 클릭 핸들러
        - 카테고리(자식 있음, key='_cat_*'): expand/collapse 토글
        - leaf : 해당 위젯으로 stack 전환
        """
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if not key:
            return
        if key.startswith("_cat_"):
            item.setExpanded(not item.isExpanded())
            return
        self._select_key(key)

    def _select_key(self, key: str):
        """key 에 해당하는 메뉴를 선택 + 화면 전환"""
        if key not in self.widgets:
            return
        # 부모 카테고리가 접혀있으면 펼치기
        item = self.key_to_item.get(key)
        if item:
            parent = item.parent()
            if parent and not parent.isExpanded():
                parent.setExpanded(True)
            self.menu_tree.setCurrentItem(item)
        # 화면 전환
        self.stack.setCurrentWidget(self.widgets[key])
        widget = self.stack.currentWidget()
        if hasattr(widget, 'refresh'):
            widget.refresh()
        elif hasattr(widget, 'tabs'):
            current_tab = widget.tabs.currentWidget()
            if hasattr(current_tab, 'refresh'):
                current_tab.refresh()
            elif hasattr(current_tab, '_refresh'):
                current_tab._refresh()
        self._update_status()

    def _update_status(self):
        try:
            conn = sqlite3.connect("accounting.db")
            companies = conn.execute(
                "SELECT COUNT(*) FROM companies WHERE is_active=1"
            ).fetchone()[0]
            sales_count = conn.execute(
                "SELECT COUNT(*) FROM sales WHERE status='정상'"
            ).fetchone()[0]
            unpaid = conn.execute(
                "SELECT COALESCE(SUM(unpaid_amount),0) FROM sales WHERE status='정상'"
            ).fetchone()[0]
            conn.close()
            self.status.showMessage(
                f"📁 거래처 {companies:,}건  |  "
                f"📋 매출 {sales_count:,}건  |  "
                f"💰 미수금 {unpaid:,}원  |  "
                f"👤 {Session.full_name}"
            )
        except Exception as e:
            self.status.showMessage(f"DB 오류: {e}")

    def _logout(self):
        reply = QMessageBox.question(
            self, "로그아웃", "로그아웃 하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            log_action("로그아웃", "user", str(Session.user_id))
            Session.logout()
            QApplication.exit(99)

    def _open_my_account(self):
        from ui.widgets.my_account import MyAccountDialog
        dlg = MyAccountDialog(self)
        dlg.exec()


def main():
    # ── 0. QApplication 먼저 (다이얼로그 띄울 수 있게) ──
    app = QApplication(sys.argv)
    app.setStyleSheet(MAIN_STYLE)
    app.setFont(QFont("Malgun Gothic", 10))
    # placeholder/텍스트 색상은 QSS 가 아니라 QPalette 로만 적용됨
    from PyQt6.QtGui import QPalette, QColor
    pal = app.palette()
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor("#9ca3af"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#111827"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#111827"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#111827"))
    app.setPalette(pal)

    # ── 1. 첫 실행 셋업 (config.json 자동 생성) ──
    try:
        from first_run_setup import run_first_setup_if_needed, config_exists
        if not config_exists():
            if not run_first_setup_if_needed():
                sys.exit(0)
    except ImportError:
        pass

    # ── 2. accounting.db 체크 ──
    if not Path("accounting.db").exists():
        QMessageBox.critical(None, "오류",
            "accounting.db 파일을 찾을 수 없습니다.\n프로그램을 재설치하세요.")
        sys.exit(1)

    conn = sqlite3.connect("accounting.db")
    has_users = conn.execute(
        "SELECT name FROM sqlite_master WHERE name='users'"
    ).fetchone()
    conn.close()
    if not has_users:
        QMessageBox.critical(None, "초기화 필요",
            "DB 초기화가 필요합니다.\n관리자에게 문의하세요.")
        sys.exit(1)

    # ── 3. 1일 1회 자동 백업 ──
    try:
        from backup_module import auto_backup_if_needed
        bp = auto_backup_if_needed()
        if bp:
            print(f"자동 백업: {bp}")
    except Exception as e:
        print(f"자동 백업 실패: {e}")

    # ── 4. 로그인 + 메인 윈도우 (재로그인 루프) ──
    while True:
        login = LoginDialog()
        if login.exec() != LoginDialog.DialogCode.Accepted:
            sys.exit(0)

        win = MainWindow()
        win.show()
        ret = app.exec()
        if ret == 99:
            Session.logout()
            continue  # 로그아웃 → 다시 로그인
        sys.exit(ret)


if __name__ == "__main__":
    main()
