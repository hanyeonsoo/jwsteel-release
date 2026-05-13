"""거래처 검색/조회/등록/수정 + 미수금 통합 그리드 위젯"""
import sqlite3
from datetime import date, timedelta
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QGroupBox,
    QFormLayout, QSplitter, QCheckBox, QDialog, QDialogButtonBox,
    QTextEdit, QAbstractItemView, QTabWidget, QSpinBox, QDateEdit,
)
from PyQt6.QtCore import QDate

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

from ui.common import fmt_money, msg_info, msg_warning, msg_error, msg_confirm


DB_PATH = "accounting.db"


class CompaniesWidget(QWidget):
    """탭 구조: 거래처 목록 + 전체 미수금 그리드"""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("거래처 관리")
        title.setStyleSheet("font-size: 18pt; font-weight: bold; padding: 8px 0px;")
        layout.addWidget(title)

        tabs = QTabWidget()
        self.tab_list = CompanyListTab()
        self.tab_unpaid = UnpaidGridTab()
        tabs.addTab(self.tab_list, "👥 거래처 목록")
        tabs.addTab(self.tab_unpaid, "💰 전체 미수금 / 담당자별")
        tabs.currentChanged.connect(self._on_tab_change)
        layout.addWidget(tabs)
        self.tabs = tabs

    def _on_tab_change(self, idx):
        if idx == 1:
            self.tab_unpaid.refresh()


# ============================================================
# 탭 1: 거래처 목록 (기존)
# ============================================================
class CompanyListTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 액션 버튼
        title_row = QHBoxLayout()
        add_btn = QPushButton("+ 새 거래처")
        add_btn.setStyleSheet(
            "background-color: #16a34a; color: white; padding: 8px 16px;")
        add_btn.clicked.connect(self._add_company)
        title_row.addWidget(add_btn)

        edit_btn = QPushButton("✏ 수정")
        edit_btn.setStyleSheet(
            "background-color: #2563eb; color: white; padding: 8px 16px;")
        edit_btn.clicked.connect(self._edit_company)
        title_row.addWidget(edit_btn)

        del_btn = QPushButton("🗑 비활성화")
        del_btn.setStyleSheet(
            "background-color: #dc2626; color: white; padding: 8px 16px;")
        del_btn.clicked.connect(self._deactivate_company)
        title_row.addWidget(del_btn)
        title_row.addStretch()
        layout.addLayout(title_row)

        # 검색 영역
        search_box = QGroupBox("검색")
        search_layout = QHBoxLayout(search_box)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("거래처명/사업자번호/대표자/거래처코드로 검색...")
        self.search_input.returnPressed.connect(self.refresh)
        search_layout.addWidget(self.search_input, stretch=3)

        self.trade_filter = QComboBox()
        self.trade_filter.addItems(["전체", "소매", "실수요", "유통", "기타"])
        self.trade_filter.currentIndexChanged.connect(self.refresh)
        search_layout.addWidget(QLabel("유형:"))
        search_layout.addWidget(self.trade_filter, stretch=1)

        self.entity_filter = QComboBox()
        self.entity_filter.addItems(["전체", "법인", "개인"])
        self.entity_filter.currentIndexChanged.connect(self.refresh)
        search_layout.addWidget(QLabel("구분:"))
        search_layout.addWidget(self.entity_filter, stretch=1)

        self.sales_only = QCheckBox("매출가능만")
        self.sales_only.stateChanged.connect(self.refresh)
        search_layout.addWidget(self.sales_only)

        search_btn = QPushButton("검색")
        search_btn.clicked.connect(self.refresh)
        search_layout.addWidget(search_btn)

        layout.addWidget(search_box)

        # 메인 영역 (좌: 목록 / 우: 상세)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 좌측 - 거래처 목록
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.count_label = QLabel("0건")
        self.count_label.setStyleSheet("color: #6b7280;")
        left_layout.addWidget(self.count_label)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["코드", "거래처명", "담당자", "사업자번호", "대표자", "전화번호", "유형"])
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_selection)
        self.table.setAlternatingRowColors(True)
        left_layout.addWidget(self.table)

        splitter.addWidget(left_panel)

        # 우측 - 상세 정보
        self.detail_panel = self._create_detail_panel()
        splitter.addWidget(self.detail_panel)

        splitter.setSizes([700, 400])
        layout.addWidget(splitter, stretch=1)

    def _create_detail_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 0, 0, 0)

        title = QLabel("상세 정보")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; padding: 8px 0px;")
        layout.addWidget(title)

        group = QGroupBox()
        form = QFormLayout(group)
        form.setVerticalSpacing(10)

        self.detail_code = QLabel("-")
        self.detail_name = QLabel("-")
        self.detail_name.setWordWrap(True)
        self.detail_name.setStyleSheet("font-weight: bold; font-size: 12pt;")
        self.detail_business = QLabel("-")
        self.detail_ceo = QLabel("-")
        self.detail_entity = QLabel("-")
        self.detail_biz = QLabel("-")
        self.detail_item = QLabel("-")
        self.detail_phone = QLabel("-")
        self.detail_email = QLabel("-")
        self.detail_address = QLabel("-")
        self.detail_address.setWordWrap(True)
        self.detail_address.setMinimumWidth(300)
        self.detail_trade = QLabel("-")
        self.detail_flags = QLabel("-")
        self.detail_salesperson = QLabel("-")
        self.detail_salesperson.setStyleSheet("color: #2563eb; font-weight: bold;")

        form.addRow("거래처코드:", self.detail_code)
        form.addRow("거래처명:", self.detail_name)
        form.addRow("영업담당자:", self.detail_salesperson)
        form.addRow("사업자번호:", self.detail_business)
        form.addRow("대표자:", self.detail_ceo)
        form.addRow("법인구분:", self.detail_entity)
        form.addRow("업태:", self.detail_biz)
        form.addRow("종목:", self.detail_item)
        form.addRow("전화번호:", self.detail_phone)
        form.addRow("이메일:", self.detail_email)
        form.addRow("주소:", self.detail_address)
        form.addRow("거래유형:", self.detail_trade)
        form.addRow("매출/매입:", self.detail_flags)

        layout.addWidget(group)

        # 거래 요약 (매출/미수금)
        stat_group = QGroupBox("거래 요약")
        stat_layout = QFormLayout(stat_group)
        self.stat_sales = QLabel("0원")
        self.stat_unpaid = QLabel("0원")
        self.stat_purchase = QLabel("0원")
        self.stat_payable = QLabel("0원")
        self.stat_unpaid.setStyleSheet("color: #dc2626; font-weight: bold;")
        self.stat_payable.setStyleSheet("color: #f59e0b; font-weight: bold;")
        stat_layout.addRow("총 매출:", self.stat_sales)
        stat_layout.addRow("미수금:", self.stat_unpaid)
        stat_layout.addRow("총 매입:", self.stat_purchase)
        stat_layout.addRow("미지급:", self.stat_payable)
        layout.addWidget(stat_group)

        layout.addStretch()
        return panel

    def refresh(self):
        """검색 조건으로 거래처 목록 재조회"""
        keyword = self.search_input.text().strip()
        trade = self.trade_filter.currentText()
        entity = self.entity_filter.currentText()

        sql = "SELECT * FROM companies WHERE is_active = 1"
        params = []

        if keyword:
            sql += """ AND (company_name LIKE ? OR business_no LIKE ?
                          OR ceo_name LIKE ? OR company_code LIKE ?)"""
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw, kw])

        if trade != "전체":
            sql += " AND trade_type = ?"
            params.append(trade)

        if entity != "전체":
            sql += " AND entity_type = ?"
            params.append(entity)

        if self.sales_only.isChecked():
            sql += " AND can_sell = 1"

        sql += " ORDER BY company_code"

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
        # 전체 건수
        total = conn.execute(
            "SELECT COUNT(*) FROM companies WHERE is_active=1"
        ).fetchone()[0]
        conn.close()

        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(r['company_code']))
            self.table.setItem(i, 1, QTableWidgetItem(r['company_name']))
            # 담당자
            sp = r['salesperson'] if 'salesperson' in r.keys() else None
            sp_item = QTableWidgetItem(sp or '')
            if sp:
                sp_item.setForeground(QColor('#2563eb'))
            self.table.setItem(i, 2, sp_item)
            self.table.setItem(i, 3, QTableWidgetItem(r['business_no'] or ''))
            self.table.setItem(i, 4, QTableWidgetItem(r['ceo_name'] or ''))
            self.table.setItem(i, 5, QTableWidgetItem(r['phone'] or ''))
            self.table.setItem(i, 6, QTableWidgetItem(r['trade_type'] or ''))

        self.count_label.setText(
            f"검색 결과: {len(rows):,}건 / 전체 활성 거래처: {total:,}건"
        )

    def _on_selection(self):
        items = self.table.selectedItems()
        if not items:
            return
        row = items[0].row()
        code = self.table.item(row, 0).text()
        self._load_detail(code)

    def _load_detail(self, code):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        c = conn.execute(
            "SELECT * FROM companies WHERE company_code = ?", (code,)
        ).fetchone()

        if c:
            self.detail_code.setText(c['company_code'])
            self.detail_name.setText(c['company_name'])
            self.detail_business.setText(c['business_no'] or '-')
            self.detail_ceo.setText(c['ceo_name'] or '-')
            self.detail_entity.setText(c['entity_type'] or '-')
            self.detail_biz.setText(c['biz_type'] or '-')
            self.detail_item.setText(c['biz_item'] or '-')
            self.detail_phone.setText(c['phone'] or '-')
            self.detail_email.setText(c['email'] or '-')
            self.detail_address.setText(c['address'] or '-')
            self.detail_trade.setText(c['trade_type'] or '-')
            sp = c['salesperson'] if 'salesperson' in c.keys() else None
            self.detail_salesperson.setText(sp or '-')
            flags = []
            if c['can_sell']: flags.append("매출")
            if c['can_purchase']: flags.append("매입")
            self.detail_flags.setText(" / ".join(flags) or "-")

            # 거래 요약
            s = conn.execute(
                """SELECT COALESCE(SUM(total_amount),0) AS s,
                          COALESCE(SUM(unpaid_amount),0) AS u
                   FROM sales WHERE company_code=? AND status='정상'""", (code,)
            ).fetchone()
            p = conn.execute(
                """SELECT COALESCE(SUM(total_amount),0) AS s,
                          COALESCE(SUM(unpaid_amount),0) AS u
                   FROM purchases WHERE company_code=? AND status='정상'""", (code,)
            ).fetchone()
            self.stat_sales.setText(f"{s['s']:,}원")
            self.stat_unpaid.setText(f"{s['u']:,}원")
            self.stat_purchase.setText(f"{p['s']:,}원")
            self.stat_payable.setText(f"{p['u']:,}원")

        conn.close()

    def _selected_code(self):
        items = self.table.selectedItems()
        if not items:
            return None
        return self.table.item(items[0].row(), 0).text()

    def _add_company(self):
        dlg = CompanyEditDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                from auth_module import log_action
                log_action("거래처등록", "company", dlg.company_code)
            except Exception:
                pass
            self.refresh()

    def _edit_company(self):
        code = self._selected_code()
        if not code:
            msg_warning(self, "선택 필요", "수정할 거래처를 선택하세요")
            return
        dlg = CompanyEditDialog(self, edit_code=code)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                from auth_module import log_action
                log_action("거래처수정", "company", code)
            except Exception:
                pass
            self.refresh()
            self._load_detail(code)

    def _deactivate_company(self):
        from auth_module import Session, log_action
        if not Session.is_admin():
            msg_warning(self, "권한 없음", "비활성화는 관리자만 가능합니다")
            return
        code = self._selected_code()
        if not code:
            msg_warning(self, "선택 필요", "비활성화할 거래처를 선택하세요")
            return
        conn = sqlite3.connect(DB_PATH)
        unpaid = conn.execute(
            "SELECT COALESCE(SUM(unpaid_amount),0) FROM sales "
            "WHERE company_code=? AND status='정상'", (code,)
        ).fetchone()[0]
        payable = conn.execute(
            "SELECT COALESCE(SUM(unpaid_amount),0) FROM purchases "
            "WHERE company_code=? AND status='정상'", (code,)
        ).fetchone()[0]
        conn.close()
        if unpaid > 0 or payable > 0:
            if not msg_confirm(
                self, "미정산 잔액 존재",
                f"미수금 {unpaid:,}원 / 미지급 {payable:,}원이 있습니다.\n"
                f"정말 비활성화하시겠습니까?"
            ):
                return
        elif not msg_confirm(self, "비활성화", f"거래처 {code} 를 비활성화합니다"):
            return
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "UPDATE companies SET is_active=0 WHERE company_code=?", (code,)
            )
            conn.commit()
            conn.close()
            log_action("거래처비활성", "company", code)
            msg_info(self, "완료", "비활성화되었습니다")
            self.refresh()
        except Exception as e:
            msg_error(self, "실패", str(e))


class CompanyEditDialog(QDialog):
    """거래처 등록/수정 다이얼로그"""
    def __init__(self, parent=None, edit_code: str = None):
        super().__init__(parent)
        self.edit_code = edit_code
        self.company_code = None
        self.setWindowTitle("거래처 수정" if edit_code else "새 거래처 등록")
        self.setMinimumWidth(500)
        self._init_ui()
        if edit_code:
            self._load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.code = QLineEdit()
        self.code.setPlaceholderText("자동 생성하려면 비워두세요")
        if self.edit_code:
            self.code.setText(self.edit_code)
            self.code.setReadOnly(True)
            self.code.setStyleSheet("background-color: #f3f4f6;")
        form.addRow("거래처코드:", self.code)

        self.name = QLineEdit()
        self.name.setPlaceholderText("거래처명 *")
        form.addRow("거래처명 *:", self.name)

        self.business_no = QLineEdit()
        self.business_no.setPlaceholderText("123-45-67890")
        form.addRow("사업자번호:", self.business_no)

        self.entity = QComboBox()
        self.entity.addItems(['', '법인', '개인'])
        form.addRow("법인구분:", self.entity)

        self.ceo = QLineEdit()
        form.addRow("대표자:", self.ceo)

        self.biz_type = QLineEdit()
        form.addRow("업태:", self.biz_type)

        self.biz_item = QLineEdit()
        form.addRow("종목:", self.biz_item)

        self.salesperson = QLineEdit()
        self.salesperson.setPlaceholderText("(선택) 영업담당자 이름")
        form.addRow("영업담당자:", self.salesperson)

        self.phone = QLineEdit()
        self.phone.setPlaceholderText("02-1234-5678")
        form.addRow("전화번호:", self.phone)

        self.email = QLineEdit()
        form.addRow("이메일:", self.email)

        self.address = QTextEdit()
        self.address.setMaximumHeight(60)
        form.addRow("주소:", self.address)

        self.trade_type = QComboBox()
        self.trade_type.addItems(['소매', '실수요', '유통', '기타'])
        form.addRow("거래유형:", self.trade_type)

        flags = QHBoxLayout()
        self.can_sell = QCheckBox("매출 가능")
        self.can_sell.setChecked(True)
        self.can_purchase = QCheckBox("매입 가능")
        self.can_purchase.setChecked(True)
        flags.addWidget(self.can_sell)
        flags.addWidget(self.can_purchase)
        flags.addStretch()
        form.addRow("거래 구분:", flags)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("저장")
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load_data(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.execute(
            "SELECT * FROM companies WHERE company_code=?", (self.edit_code,)
        ).fetchone()
        conn.close()
        if not c:
            return
        self.name.setText(c['company_name'] or '')
        self.business_no.setText(c['business_no'] or '')
        self.entity.setCurrentText(c['entity_type'] or '')
        self.ceo.setText(c['ceo_name'] or '')
        self.biz_type.setText(c['biz_type'] or '')
        self.biz_item.setText(c['biz_item'] or '')
        sp = c['salesperson'] if 'salesperson' in c.keys() else None
        self.salesperson.setText(sp or '')
        self.phone.setText(c['phone'] or '')
        self.email.setText(c['email'] or '')
        self.address.setPlainText(c['address'] or '')
        if c['trade_type']:
            self.trade_type.setCurrentText(c['trade_type'])
        self.can_sell.setChecked(bool(c['can_sell']))
        self.can_purchase.setChecked(bool(c['can_purchase']))

    def _save(self):
        name = self.name.text().strip()
        if not name:
            msg_warning(self, "입력 오류", "거래처명을 입력하세요")
            return

        code = self.code.text().strip()
        trade_code_map = {'실수요': 10, '유통': 20, '소매': 30, '기타': 90}

        conn = sqlite3.connect(DB_PATH)
        try:
            if not self.edit_code:
                if not code:
                    last = conn.execute(
                        "SELECT MAX(CAST(company_code AS INTEGER)) FROM companies"
                    ).fetchone()[0]
                    code = str((last or 100000) + 1)

                conn.execute(
                    """INSERT INTO companies
                       (company_code, company_name, business_no, entity_type,
                        ceo_name, biz_type, biz_item, salesperson, phone, email,
                        address, trade_type, trade_type_code,
                        can_sell, can_purchase, is_active)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                    (code, name,
                     self.business_no.text().strip() or None,
                     self.entity.currentText() or None,
                     self.ceo.text().strip() or None,
                     self.biz_type.text().strip() or None,
                     self.biz_item.text().strip() or None,
                     self.salesperson.text().strip() or None,
                     self.phone.text().strip() or None,
                     self.email.text().strip() or None,
                     self.address.toPlainText().strip() or None,
                     self.trade_type.currentText(),
                     trade_code_map.get(self.trade_type.currentText(), 30),
                     1 if self.can_sell.isChecked() else 0,
                     1 if self.can_purchase.isChecked() else 0,
                     ),
                )
                self.company_code = code
            else:
                conn.execute(
                    """UPDATE companies SET
                       company_name=?, business_no=?, entity_type=?,
                       ceo_name=?, biz_type=?, biz_item=?, salesperson=?,
                       phone=?, email=?,
                       address=?, trade_type=?, trade_type_code=?,
                       can_sell=?, can_purchase=?, updated_at=CURRENT_TIMESTAMP
                       WHERE company_code=?""",
                    (name,
                     self.business_no.text().strip() or None,
                     self.entity.currentText() or None,
                     self.ceo.text().strip() or None,
                     self.biz_type.text().strip() or None,
                     self.biz_item.text().strip() or None,
                     self.salesperson.text().strip() or None,
                     self.phone.text().strip() or None,
                     self.email.text().strip() or None,
                     self.address.toPlainText().strip() or None,
                     self.trade_type.currentText(),
                     trade_code_map.get(self.trade_type.currentText(), 30),
                     1 if self.can_sell.isChecked() else 0,
                     1 if self.can_purchase.isChecked() else 0,
                     self.edit_code,
                     ),
                )
                self.company_code = self.edit_code
            conn.commit()
            self.accept()
        except sqlite3.IntegrityError:
            msg_error(self, "저장 실패", f"코드 {code} 가 이미 존재합니다")
        except Exception as e:
            msg_error(self, "저장 실패", str(e))
        finally:
            conn.close()

# ============================================================
# 탭 2: 전체 미수금 통합 그리드
# 모든 미수금 거래처를 한 화면에서 보고 인라인으로 약속 등록
# ============================================================
class UnpaidGridTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # 상단 요약 + 필터
        top_box = QGroupBox("🔍 필터")
        tl = QVBoxLayout(top_box)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("검색:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("거래처명/담당자/대표자로 검색...")
        self.search_input.textChanged.connect(self._refresh)
        row1.addWidget(self.search_input, stretch=2)

        row1.addWidget(QLabel("담당자:"))
        self.salesperson_filter = QComboBox()
        self.salesperson_filter.setMinimumWidth(120)
        self.salesperson_filter.currentIndexChanged.connect(self._refresh)
        row1.addWidget(self.salesperson_filter, stretch=1)

        row1.addWidget(QLabel("필터:"))
        self.unpaid_filter = QComboBox()
        self.unpaid_filter.addItems([
            "미수금 있는 곳만",
            "연체만 (지급 예정일 지남)",
            "7일 내 결제예정",
            "30일 내 결제예정",
            "전체 거래처",
        ])
        self.unpaid_filter.currentIndexChanged.connect(self._refresh)
        row1.addWidget(self.unpaid_filter, stretch=1)

        refresh_btn = QPushButton("🔄 새로고침")
        refresh_btn.setStyleSheet(
            "background-color: white; color: #374151; "
            "border: 1px solid #e5e7eb; padding: 6px 12px;")
        refresh_btn.clicked.connect(self.refresh)
        row1.addWidget(refresh_btn)
        tl.addLayout(row1)

        layout.addWidget(top_box)

        # 요약 카드 4개
        cards_row = QHBoxLayout()
        self.card_total = self._make_card("총 미수금", "0원", "#dc2626")
        self.card_overdue = self._make_card("연체 미수금", "0원", "#dc2626")
        self.card_companies = self._make_card("거래처 수", "0곳", "#2563eb")
        self.card_plans = self._make_card("등록된 약속", "0건", "#16a34a")
        cards_row.addWidget(self.card_total)
        cards_row.addWidget(self.card_overdue)
        cards_row.addWidget(self.card_companies)
        cards_row.addWidget(self.card_plans)
        layout.addLayout(cards_row)

        # 메인 그리드
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "코드", "거래처명", "담당자", "전화번호",
            "미수금", "연체", "최근 결제예정", "수금약속"
        ])
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(4, 130)
        self.table.setColumnWidth(5, 130)
        self.table.setColumnWidth(6, 190)
        self.table.setColumnWidth(7, 250)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemDoubleClicked.connect(self._on_row_dblclick)
        layout.addWidget(self.table)

        # 안내
        hint = QLabel(
            "💡 행을 더블클릭하여 수금 약속 등록 / 수정"
        )
        hint.setStyleSheet("color: #6b7280; padding: 8px;")
        layout.addWidget(hint)

        self._load_salespersons()

    def _make_card(self, label, value, color):
        from PyQt6.QtWidgets import QFrame
        card = QFrame()
        card.setStyleSheet(
            "background-color: white; border: 1px solid #e5e7eb; "
            "border-radius: 8px; padding: 12px;")
        v = QVBoxLayout(card)
        l1 = QLabel(label)
        l1.setStyleSheet("color: #6b7280; font-size: 10pt;")
        l2 = QLabel(value)
        l2.setStyleSheet(f"color: {color}; font-size: 18pt; font-weight: bold;")
        l2.setObjectName("value")
        v.addWidget(l1)
        v.addWidget(l2)
        return card

    def _set_card(self, card, value):
        for w in card.findChildren(QLabel):
            if w.objectName() == "value":
                w.setText(value)
                break

    def _load_salespersons(self):
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            """SELECT DISTINCT salesperson FROM companies
               WHERE salesperson IS NOT NULL AND salesperson != ''
               ORDER BY salesperson"""
        ).fetchall()
        conn.close()
        self.salesperson_filter.clear()
        self.salesperson_filter.addItem("전체 담당자")
        self.salesperson_filter.addItem("(담당자 없음)")
        for (sp,) in rows:
            self.salesperson_filter.addItem(sp)

    def refresh(self):
        self._load_salespersons()
        self._refresh()

    def _refresh(self):
        # 연체 처리
        try:
            from collections_module import update_plan_overdue_status
            update_plan_overdue_status()
        except Exception:
            pass

        today = date.today()
        keyword = self.search_input.text().strip()
        sp_filter = self.salesperson_filter.currentText()
        type_filter = self.unpaid_filter.currentText()

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        # 거래처 + 미수금 집계 + 담당자
        sql = """SELECT c.company_code, c.company_name, c.salesperson,
                        c.phone, c.ceo_name,
                        COALESCE(SUM(s.unpaid_amount), 0) AS total_unpaid,
                        COALESCE(SUM(CASE WHEN s.due_date < ?
                                          THEN s.unpaid_amount ELSE 0 END), 0) AS overdue,
                        MIN(s.due_date) AS earliest_due
                 FROM companies c
                 LEFT JOIN sales s ON s.company_code = c.company_code
                                   AND s.status = '정상' AND s.unpaid_amount > 0
                 WHERE c.is_active = 1"""
        params = [today]

        if keyword:
            sql += """ AND (c.company_name LIKE ? OR c.salesperson LIKE ?
                            OR c.ceo_name LIKE ?)"""
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])

        if sp_filter == "(담당자 없음)":
            sql += " AND (c.salesperson IS NULL OR c.salesperson = '')"
        elif sp_filter != "전체 담당자":
            sql += " AND c.salesperson = ?"
            params.append(sp_filter)

        sql += " GROUP BY c.company_code"

        # 필터
        if type_filter == "미수금 있는 곳만":
            sql = f"SELECT * FROM ({sql}) WHERE total_unpaid > 0"
        elif type_filter == "연체만 (지급 예정일 지남)":
            sql = f"SELECT * FROM ({sql}) WHERE overdue > 0"
        elif type_filter == "7일 내 결제예정":
            sql = f"""SELECT * FROM ({sql}) WHERE total_unpaid > 0
                     AND earliest_due BETWEEN ? AND ?"""
            params.extend([today, today + timedelta(days=7)])
        elif type_filter == "30일 내 결제예정":
            sql = f"""SELECT * FROM ({sql}) WHERE total_unpaid > 0
                     AND earliest_due BETWEEN ? AND ?"""
            params.extend([today, today + timedelta(days=30)])

        sql += " ORDER BY total_unpaid DESC, company_name LIMIT 500"

        rows = conn.execute(sql, params).fetchall()

        # 거래처별 기존 약속 조회 (한번에)
        plans_rows = conn.execute(
            """SELECT company_code, plan_date, amount FROM collection_plans
               WHERE status IN ('예정', '연체') ORDER BY plan_date ASC"""
        ).fetchall()
        plans_by_company = {}
        for pr in plans_rows:
            existing = plans_by_company.get(pr['company_code'], '')
            label = f"📌 {pr['plan_date']} / {pr['amount']:,}원"
            if existing:
                plans_by_company[pr['company_code']] = existing + "  " + label
            else:
                plans_by_company[pr['company_code']] = label

        # 약속 카운트
        plan_count = conn.execute(
            "SELECT COUNT(*) FROM collection_plans WHERE status IN ('예정', '연체')"
        ).fetchone()[0]
        conn.close()

        # 카드 업데이트
        total_unpaid = sum(r['total_unpaid'] for r in rows)
        total_overdue = sum(r['overdue'] for r in rows)
        self._set_card(self.card_total, f"{total_unpaid:,}원")
        self._set_card(self.card_overdue, f"{total_overdue:,}원")
        self._set_card(self.card_companies, f"{len(rows):,}곳")
        self._set_card(self.card_plans, f"{plan_count}건")

        # 테이블 채우기
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            # 0: 코드
            code_item = QTableWidgetItem(r['company_code'])
            code_item.setFlags(code_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, code_item)

            # 1: 거래처명
            name_item = QTableWidgetItem(r['company_name'])
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 1, name_item)

            # 2: 담당자
            sp_item = QTableWidgetItem(r['salesperson'] or '')
            sp_item.setFlags(sp_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if r['salesperson']:
                sp_item.setForeground(QColor('#2563eb'))
            self.table.setItem(i, 2, sp_item)

            # 3: 전화번호
            phone_item = QTableWidgetItem(r['phone'] or '')
            phone_item.setFlags(phone_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 3, phone_item)

            # 4: 미수금
            unpaid_item = QTableWidgetItem(f"{r['total_unpaid']:,}")
            unpaid_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            unpaid_item.setFlags(unpaid_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if r['total_unpaid'] > 0:
                unpaid_item.setForeground(QColor('#dc2626'))
                unpaid_item.setFont(self._bold_font())
            self.table.setItem(i, 4, unpaid_item)

            # 5: 연체
            overdue_item = QTableWidgetItem(f"{r['overdue']:,}" if r['overdue'] > 0 else "-")
            overdue_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            overdue_item.setFlags(overdue_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if r['overdue'] > 0:
                overdue_item.setForeground(QColor('#dc2626'))
                overdue_item.setFont(self._bold_font())
            self.table.setItem(i, 5, overdue_item)

            # 6: 최근 결제예정 (+ D-Day)
            if r['earliest_due']:
                due = date.fromisoformat(str(r['earliest_due']))
                diff = (due - today).days
                if diff < 0:
                    due_text = f"{r['earliest_due']} (D+{-diff} 연체)"
                    due_color = '#dc2626'
                elif diff == 0:
                    due_text = f"{r['earliest_due']} (D-Day)"
                    due_color = '#f59e0b'
                else:
                    due_text = f"{r['earliest_due']} (D-{diff})"
                    due_color = '#2563eb' if diff <= 7 else '#6b7280'
                due_item = QTableWidgetItem(due_text)
                due_item.setForeground(QColor(due_color))
            else:
                due_item = QTableWidgetItem('-')
            due_item.setFlags(due_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 6, due_item)

            # 7: 수금약속 (기존 약속 있으면 표시 / 없으면 안내)
            plan_text = plans_by_company.get(r['company_code'], '')
            if not plan_text:
                plan_text = '➕ 더블클릭하여 약속 등록'
            plan_item = QTableWidgetItem(plan_text)
            if '➕' in plan_text:
                plan_item.setForeground(QColor('#9ca3af'))
            else:
                plan_item.setForeground(QColor('#16a34a'))
            plan_item.setFlags(plan_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 7, plan_item)

    def _bold_font(self):
        from PyQt6.QtGui import QFont
        f = QFont()
        f.setBold(True)
        return f

    def _on_row_dblclick(self, item):
        """행 더블클릭 → 약속 등록/수정 다이얼로그"""
        row = item.row()
        company_code = self.table.item(row, 0).text()
        company_name = self.table.item(row, 1).text()
        unpaid_text = self.table.item(row, 4).text().replace(',', '')
        try:
            unpaid_amount = int(unpaid_text)
        except ValueError:
            unpaid_amount = 0

        from ui.widgets.collections import PlanEditDialog
        dlg = PlanEditDialog(self, company_code=company_code,
                            default_amount=unpaid_amount)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh()

