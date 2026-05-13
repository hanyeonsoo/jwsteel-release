"""재고 픽커 다이얼로그 — 재고 현황과 동일 구성 + 단가 입력"""
import sys
import os
from typing import Optional, Dict

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication, QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QDoubleSpinBox, QSpinBox, QFormLayout, QGroupBox,
    QComboBox, QWidget,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/..')
from inventory_module import (
    search_inventory, count_inventory, DISPLAY_COLS,
)
from ui.widgets._filter_bar import (
    IncludeExcludeSearch, install_column_header_filters,
    install_inline_filter_row, reset_column_filters, apply_all_filters,
)


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


class InventoryPickerDialog(QDialog):
    """재고에서 품목 1건을 골라 단위/수량/중량/단가와 함께 반환"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("재고에서 품목 선택")
        # 사용자 화면 거의 가득 차게
        try:
            geo = QGuiApplication.primaryScreen().availableGeometry()
            w = int(geo.width() * 0.92)
            h = int(geo.height() * 0.88)
            self.resize(w, h)
            self.move(geo.x() + (geo.width()-w)//2,
                      geo.y() + (geo.height()-h)//2)
        except Exception:
            self.resize(1500, 850)
        self.result_item: Optional[Dict] = None
        self._current_inv: Optional[Dict] = None
        self._build_ui()
        QTimer.singleShot(50, self._do_search)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(6)

        # 타이틀
        title_row = QHBoxLayout()
        title = QLabel("📦 재고에서 품목 선택")
        title.setStyleSheet("font-size: 13pt; font-weight: bold;")
        title_row.addWidget(title)
        title_row.addStretch()
        root.addLayout(title_row)

        # 검색 + 필터 초기화 버튼
        f1 = QHBoxLayout(); f1.setSpacing(6)
        f1.addWidget(QLabel("검색:"))
        self.search = IncludeExcludeSearch(
            "품목명/그룹/재질/Lot/창고/위치/소재번호 — 부분 검색")
        self.search.changed.connect(self._do_search)
        f1.addWidget(self.search, stretch=3)
        clear_btn = QPushButton("🧹 컬럼 필터 초기화")
        clear_btn.setStyleSheet(
            "background:white; color:#374151; border:1px solid #d1d5db; padding:3px 10px;")
        clear_btn.clicked.connect(self._clear_filters)
        f1.addWidget(clear_btn)
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color:#6b7280;")
        f1.addWidget(self.count_label)
        root.addLayout(f1)

        hint = QLabel(
            "💡 컬럼별 필터: <b>헤더 아래 노란 입력칸</b> 또는 "
            "<b>헤더 우클릭</b> 팝업 (둘 다 가능, AND 결합)")
        hint.setStyleSheet("color:#6b7280;")
        root.addWidget(hint)

        # 재고 테이블
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
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        self.table.doubleClicked.connect(self._on_double_click)
        # 헤더 필터 설치 (팝업 + 인라인 둘 다)
        install_column_header_filters(self.table)
        root.addWidget(self.table, stretch=1)
        # 픽커 다이얼로그는 main 의 auto_install 대상이 아니므로
        # 인라인 입력행을 명시적으로 설치
        install_inline_filter_row(self.table)

        # 선택 + 단위/수량/중량/단가
        bottom_box = QGroupBox("선택 품목 → 매출에 추가")
        bl = QFormLayout(bottom_box)
        bl.setContentsMargins(10, 8, 10, 8)
        bl.setVerticalSpacing(6)

        self.selected_label = QLabel("(아직 선택 안 됨)")
        self.selected_label.setStyleSheet(
            "padding:6px; background:#f9fafb; border:1px solid #e5e7eb; "
            "border-radius:3px;")
        bl.addRow("품목:", self.selected_label)

        self.unit_combo = QComboBox()
        self.unit_combo.addItem("수량 기준 (수량 × 단가)", "EA")
        self.unit_combo.addItem("중량 기준 (중량 × 단가/kg)", "KG")
        self.unit_combo.currentIndexChanged.connect(self._on_unit_changed)
        self.unit_combo.setMaximumWidth(260)
        bl.addRow("단가 기준:", self.unit_combo)

        qty_row = QHBoxLayout()
        qty_row.setSpacing(6)
        self.qty_input = QDoubleSpinBox()
        self.qty_input.setRange(0.01, 999999)
        self.qty_input.setDecimals(2)
        self.qty_input.setValue(1)
        self.qty_input.setMaximumWidth(110)
        self.qty_input.valueChanged.connect(self._update_amount_preview)

        self.weight_input = QDoubleSpinBox()
        self.weight_input.setRange(0.0, 9999999)
        self.weight_input.setDecimals(2)
        self.weight_input.setValue(0)
        self.weight_input.setMaximumWidth(130)
        self.weight_input.valueChanged.connect(self._update_amount_preview)

        self.price_input = QSpinBox()
        self.price_input.setRange(0, 2_000_000_000)
        self.price_input.setSingleStep(1000)
        self.price_input.setGroupSeparatorShown(True)
        self.price_input.setMaximumWidth(160)
        self.price_input.valueChanged.connect(self._update_amount_preview)

        qty_row.addWidget(QLabel("수량(EA):"))
        qty_row.addWidget(self.qty_input)
        qty_row.addSpacing(10)
        qty_row.addWidget(QLabel("중량(kg):"))
        qty_row.addWidget(self.weight_input)
        qty_row.addSpacing(10)
        qty_row.addWidget(QLabel("단가:"))
        qty_row.addWidget(self.price_input)
        self.unit_suffix_label = QLabel("원/EA")
        self.unit_suffix_label.setStyleSheet("color:#6b7280;")
        qty_row.addWidget(self.unit_suffix_label)
        qty_row.addSpacing(20)
        self.preview_label = QLabel("공급가: 0 원")
        self.preview_label.setStyleSheet(
            "font-size: 10pt; font-weight: bold; color: #16a34a;")
        qty_row.addWidget(self.preview_label)
        qty_row.addStretch()
        w = QWidget(); w.setLayout(qty_row)
        bl.addRow("입력:", w)
        root.addWidget(bottom_box)

        # 버튼
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("취소")
        cancel_btn.setStyleSheet(
            "background:white; color:#374151; border:1px solid #d1d5db; "
            "padding:6px 14px;")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self.ok_btn = QPushButton("✓ 매출에 추가")
        self.ok_btn.setStyleSheet(
            "background:#16a34a; color:white; padding:6px 18px; "
            "font-weight:bold;")
        self.ok_btn.clicked.connect(self._accept)
        self.ok_btn.setEnabled(False)
        btn_row.addWidget(self.ok_btn)
        root.addLayout(btn_row)

    def _clear_filters(self):
        reset_column_filters(self.table)

    def _do_search(self):
        rows = search_inventory(
            keyword=self.search.get_text(),
            mode=self.search.get_mode(),
            limit=2000,
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
            self.table.item(i, 0).setData(Qt.ItemDataRole.UserRole, r)
            self.table.setRowHidden(i, False)
        # 팝업 + 인라인 필터 통합 재적용
        apply_all_filters(self.table)
        self.count_label.setText(
            f"검색 결과 {len(rows):,}건 / 전체 재고 {count_inventory():,}건"
        )

    def _on_row_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.ok_btn.setEnabled(False)
            self.selected_label.setText("(아직 선택 안 됨)")
            self._current_inv = None
            return
        r = rows[0].row()
        inv = self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)
        if not inv:
            return
        spec_parts = []
        if inv.get("thickness"): spec_parts.append(f"T{_fmt(inv['thickness'])}")
        if inv.get("width"): spec_parts.append(f"W{_fmt(inv['width'])}")
        if inv.get("length_val"): spec_parts.append(f"L{_fmt(inv['length_val'])}")
        spec_str = " × ".join(spec_parts)
        avail_qty = inv.get("stock_qty") or 0
        avail_wt = inv.get("stock_weight") or 0
        self.selected_label.setText(
            f"<b>{inv.get('item_name','')}</b>  "
            f"<span style='color:#6b7280'>"
            f"{inv.get('item_group','')} / {inv.get('material','')} / "
            f"{inv.get('origin','')}</span>"
            f"<br/><span style='color:#6b7280'>창고 {inv.get('warehouse','')} "
            f"{inv.get('location','') or ''} · 규격 {spec_str} · "
            f"재고 {avail_qty}EA / {avail_wt}kg · Lot {inv.get('lot_no','')}</span>"
        )
        self.qty_input.setMaximum(max(avail_qty, 99999))
        self.qty_input.setValue(avail_qty if avail_qty else 1)
        self.weight_input.setMaximum(max(avail_wt, 9999999))
        self.weight_input.setValue(avail_wt if avail_wt else 0)
        upk = inv.get("unit_price_kg") or 0
        self.price_input.setValue(int(upk))
        if upk and avail_wt:
            self.unit_combo.setCurrentIndex(1)
        else:
            self.unit_combo.setCurrentIndex(0)
        self._current_inv = inv
        self.ok_btn.setEnabled(True)
        self._update_amount_preview()

    def _on_unit_changed(self):
        unit = self.unit_combo.currentData()
        self.unit_suffix_label.setText("원/kg" if unit == "KG" else "원/EA")
        self._update_amount_preview()

    def _update_amount_preview(self):
        unit = self.unit_combo.currentData()
        price = self.price_input.value()
        supply = int(round(
            self.weight_input.value() * price if unit == "KG"
            else self.qty_input.value() * price))
        vat = int(round(supply * 0.10))
        self.preview_label.setText(
            f"공급가 {supply:,}원 + 부가세 {vat:,} = 합계 {supply+vat:,}"
        )

    def _on_double_click(self, _):
        if self.ok_btn.isEnabled():
            self._accept()

    def _accept(self):
        inv = self._current_inv
        if not inv: return
        unit = self.unit_combo.currentData()
        qty = self.qty_input.value()
        weight = self.weight_input.value()
        price = self.price_input.value()
        if price <= 0:
            QMessageBox.warning(self, "입력 오류", "단가를 입력하세요"); return
        if unit == "EA" and qty <= 0:
            QMessageBox.warning(self, "입력 오류", "수량을 입력하세요"); return
        if unit == "KG" and weight <= 0:
            QMessageBox.warning(self, "입력 오류", "중량을 입력하세요"); return

        spec_parts = []
        if inv.get("thickness"): spec_parts.append(f"T{inv['thickness']}")
        if inv.get("width"): spec_parts.append(f"W{inv['width']}")
        if inv.get("length_val"): spec_parts.append(f"L{inv['length_val']}")
        spec_str = " × ".join(spec_parts) if spec_parts else None

        self.result_item = {
            "item_name":   inv.get("item_name") or "",
            "spec":        spec_str,
            "quantity":    qty,
            "weight":      weight,
            "unit_price":  price,
            "unit_type":   unit,
            "inv_id":      inv.get("inv_id"),
            "lot_no":      inv.get("lot_no"),
            "material_no": inv.get("material_no"),
            "warehouse":   inv.get("warehouse"),
            "location":    inv.get("location"),
            "item_group":  inv.get("item_group"),
            "material":    inv.get("material"),
            "thickness":   inv.get("thickness"),
            "width":       inv.get("width"),
            "length_val":  inv.get("length_val"),
        }
        self.accept()
