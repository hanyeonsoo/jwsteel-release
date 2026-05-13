"""재고 현황 위젯 — 헤더 인라인 입력행 + 우클릭 팝업 필터"""
import sys
import os
import sqlite3

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFileDialog, QMessageBox,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/..')
from ui.common import msg_info, msg_warning, msg_error
from ui.widgets._filter_bar import (
    IncludeExcludeSearch, install_column_header_filters,
    install_inline_filter_row, reset_column_filters, apply_all_filters,
)
from inventory_module import (
    DISPLAY_COLS, search_inventory,
)

DB_PATH = "accounting.db"


def _fmt(v, decimals=None):
    if v is None or v == "":
        return ""
    try:
        f = float(v)
        if decimals is None:
            return str(int(f)) if f == int(f) else str(f)
        return f"{f:,.{decimals}f}"
    except (ValueError, TypeError):
        return str(v)


class InventoryWidget(QWidget):
    """재고 현황 — 포함/제외 + 헤더 인라인 입력행 + 우클릭 팝업 컬럼 필터"""

    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        # 타이틀
        title_row = QHBoxLayout()
        title = QLabel("📊 재고 현황")
        title.setStyleSheet("font-size: 15pt; font-weight: bold;")
        title_row.addWidget(title)
        title_row.addStretch()
        import_btn = QPushButton("📥 재고현황.xls 재임포트")
        import_btn.setStyleSheet(
            "background:#f59e0b; color:white; padding:5px 10px; font-weight:bold;")
        import_btn.clicked.connect(self._reimport)
        title_row.addWidget(import_btn)
        clear_btn = QPushButton("🧹 컬럼 필터 모두 초기화")
        clear_btn.setStyleSheet(
            "background:white; color:#374151; border:1px solid #d1d5db; padding:5px 10px;")
        clear_btn.clicked.connect(self._clear_filters)
        title_row.addWidget(clear_btn)
        refresh_btn = QPushButton("🔄 새로고침")
        refresh_btn.clicked.connect(self.refresh)
        title_row.addWidget(refresh_btn)
        layout.addLayout(title_row)

        # 검색 (포함/제외) + 빈 재고 토글
        f1 = QHBoxLayout(); f1.setSpacing(6)
        f1.addWidget(QLabel("검색:"))
        self.search = IncludeExcludeSearch(
            "품목명/그룹/재질/Lot/창고/위치/소재번호/거래처 — 부분 검색")
        self.search.changed.connect(self.refresh)
        f1.addWidget(self.search, stretch=3)

        self.show_empty = QPushButton("재고 0 포함")
        self.show_empty.setCheckable(True)
        self.show_empty.setStyleSheet(
            "QPushButton { background:white; color:#374151; "
            "border:1px solid #d1d5db; padding:3px 10px; }"
            "QPushButton:checked { background:#2563eb; color:white; }")
        self.show_empty.toggled.connect(self.refresh)
        f1.addWidget(self.show_empty)
        layout.addLayout(f1)

        # 안내 + 통계
        hint = QLabel(
            "💡 컬럼별 필터: <b>헤더 아래 노란 입력칸</b>에 바로 입력 "
            "(입력칸 우클릭 → 포함/제외/같음/시작/끝/크다/작다 11조건). "
            "또는 <b>헤더 우클릭</b> → 팝업으로도 가능. 두 필터는 AND 결합.")
        hint.setStyleSheet("color:#6b7280; font-size: 9pt; padding: 2px 0;")
        layout.addWidget(hint)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color:#1f2937; padding: 2px 0;")
        layout.addWidget(self.stats_label)

        # 테이블
        self.table = QTableWidget()
        self.table.setColumnCount(len(DISPLAY_COLS))
        self.table.setHorizontalHeaderLabels([c[0] for c in DISPLAY_COLS])
        hdr = self.table.horizontalHeader()
        for i, (_l, _k, w, _a) in enumerate(DISPLAY_COLS):
            if w == 0:
                hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                self.table.setColumnWidth(i, w)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        # (정렬은 헤더 필터 팝업에서 처리)
        self.table.verticalHeader().setVisible(False)
        # 헤더 필터 설치 (팝업 + 인라인 둘 다)
        install_column_header_filters(self.table, self._update_stats)
        layout.addWidget(self.table, stretch=1)
        # 인라인 입력행 (헤더 바로 아래 노란 띠) — main 의 auto_install 과 별개로
        # 명시 설치하여 picker 등에서도 동일 UX 제공
        bar = install_inline_filter_row(self.table)
        if bar is not None:
            bar.applied = True  # marker
            # 입력 변경 시 통계도 갱신
            for inp in bar.inputs.values():
                inp.textChanged.connect(self._update_stats)

    def refresh(self):
        rows = search_inventory(
            keyword=self.search.get_text(),
            mode=self.search.get_mode(),
            include_empty=self.show_empty.isChecked(),
            limit=10000,
        )
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for c, (_l, key, _w, align) in enumerate(DISPLAY_COLS):
                v = r.get(key)
                if key in ("thickness", "width", "length_val"):
                    text = _fmt(v)
                elif key == "stock_qty":
                    text = _fmt(v, 2)
                elif key == "stock_weight":
                    text = _fmt(v, 1)
                elif key in ("unit_price_kg", "stock_amount"):
                    text = _fmt(v, 0)
                elif key == "stock_days":
                    text = _fmt(v, 0)
                else:
                    text = "" if v is None else str(v)
                it = QTableWidgetItem(text)
                if align == "R":
                    it.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if key == "stock_type":
                    if v == "보관품":
                        it.setForeground(QColor("#f59e0b"))
                        f = it.font(); f.setBold(True); it.setFont(f)
                    elif v == "자사":
                        it.setForeground(QColor("#16a34a"))
                self.table.setItem(i, c, it)
            self.table.setRowHidden(i, False)
        # (정렬은 헤더 필터 팝업에서 처리)
        # 새로 로드 후 기존 컬럼필터 + 인라인필터 통합 재적용
        apply_all_filters(self.table)
        self._update_stats()

    def _update_stats(self):
        """현재 보이는 행 기준 통계"""
        qty_sum = wt_sum = amt_sum = 0.0
        visible_count = 0
        for r in range(self.table.rowCount()):
            if self.table.isRowHidden(r):
                continue
            visible_count += 1
            # 수량/중량/금액 컬럼 인덱스 찾아 합산
            for c, (_l, key, _w, _a) in enumerate(DISPLAY_COLS):
                if key == "stock_qty":
                    qty_sum += self._num(self.table.item(r, c))
                elif key == "stock_weight":
                    wt_sum += self._num(self.table.item(r, c))
                elif key == "stock_amount":
                    amt_sum += self._num(self.table.item(r, c))
        self.stats_label.setText(
            f"📦 표시 <b>{visible_count:,}</b>건 · 수량 {qty_sum:,.2f}EA · "
            f"중량 {wt_sum:,.1f}kg · 금액 {amt_sum:,.0f}원"
        )

    def _num(self, item):
        if not item:
            return 0.0
        try:
            return float(item.text().replace(",", ""))
        except (ValueError, TypeError):
            return 0.0

    def _clear_filters(self):
        reset_column_filters(self.table)
        self._update_stats()

    def _reimport(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "재고현황 파일 선택", "C:/dashboard", "Excel (*.xls *.xlsx)")
        if not path:
            return
        conn = sqlite3.connect(DB_PATH)
        try:
            held = conn.execute(
                "SELECT COUNT(*) FROM inventory WHERE stock_type='보관품'"
            ).fetchone()[0]
        finally:
            conn.close()
        if held > 0:
            reply = QMessageBox.question(
                self, "보관품 경고",
                f"현재 보관품 {held}건이 있습니다.\n"
                f"재임포트 시 파일 내용으로 덮어써집니다. 진행할까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        try:
            from inventory_module import import_from_xls
            result = import_from_xls(path)
            try:
                from auth_module import log_action
                log_action("재고임포트", "inventory",
                           f"{result['inserted']}건/{result['skipped']}스킵")
            except Exception:
                pass
            msg_info(self, "임포트 완료",
                     f"적재 {result['inserted']:,}건 / 스킵 {result['skipped']:,}건")
            self.refresh()
        except Exception as e:
            msg_error(self, "임포트 실패", str(e))
