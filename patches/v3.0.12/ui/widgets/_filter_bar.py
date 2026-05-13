"""공용 검색 필터 — 인라인 필터 행 / 일자 빠른 버튼 / 포함·제외 검색"""
from datetime import date, timedelta
from calendar import monthrange

from PyQt6.QtCore import Qt, pyqtSignal, QDate, QTimer
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QDialog, QFormLayout, QDateEdit, QTableWidget,
    QMenu, QSizePolicy,
)


# ============================================================
# 1. 포함/제외 검색 (전체)
# ============================================================
class IncludeExcludeSearch(QWidget):
    changed = pyqtSignal()

    def __init__(self, placeholder: str = "검색"):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.returnPressed.connect(self.changed.emit)
        self.mode = QComboBox()
        self.mode.addItem("🔍 포함", "include")
        self.mode.addItem("🚫 제외", "exclude")
        self.mode.setMaximumWidth(78)
        self.mode.currentIndexChanged.connect(self.changed.emit)
        h.addWidget(self.input, stretch=1)
        h.addWidget(self.mode)

    def get_text(self) -> str:
        return self.input.text().strip()

    def get_mode(self) -> str:
        return self.mode.currentData()


# ============================================================
# 2. 컬럼 헤더 필터 — Excel 스타일 (헤더 우클릭)
# ============================================================
OPERATORS = [
    # (label, op_key, needs_value)
    ("필터 초기화",       "reset",         False),
    ("같은 (=)",          "eq",            True),
    ("같지 않은 (≠)",     "ne",            True),
    ("포함하는",          "contains",      True),
    ("포함하지 않는",     "not_contains",  True),
    ("~로 시작",          "starts",        True),
    ("~로 끝나는",        "ends",          True),
    ("큰 (>)",            "gt",            True),
    ("크거나 같은 (≥)",   "gte",           True),
    ("작은 (<)",          "lt",            True),
    ("작거나 같은 (≤)",   "lte",           True),
]


def _to_number(s: str):
    """문자열 → float (콤마 제거). 실패 시 None."""
    if s is None:
        return None
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def match_cell(cell_text: str, op: str, filter_value: str) -> bool:
    """셀 텍스트가 (op, filter_value) 조건을 만족하는지"""
    if not op or op == "reset":
        return True
    cell = (cell_text or "").lower().strip()
    fv = (filter_value or "").lower().strip()

    # 숫자 비교 (콤마 처리)
    if op in ("gt", "gte", "lt", "lte"):
        c = _to_number(cell)
        f = _to_number(fv)
        if c is None or f is None:
            return False
        return {"gt": c > f, "gte": c >= f, "lt": c < f, "lte": c <= f}[op]

    if op == "eq":           return cell == fv
    if op == "ne":           return cell != fv
    if op == "contains":     return fv in cell
    if op == "not_contains": return fv not in cell
    if op == "starts":       return cell.startswith(fv)
    if op == "ends":         return cell.endswith(fv)
    return True


class ColumnFilterDialog(QDialog):
    """컬럼 헤더 클릭 시 표시되는 필터 + 정렬 팝업"""
    def __init__(self, parent, column_label: str, current=None, current_sort=None):
        super().__init__(parent)
        self.setWindowTitle(f"필터 — {column_label}")
        self.setMinimumWidth(340)
        self.result_filter = None         # (op, value) or ("reset","")
        self.result_sort   = None         # 'asc' | 'desc' | None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        layout.addWidget(QLabel(f"<b>{column_label}</b>"))

        form = QFormLayout()
        form.setVerticalSpacing(6)

        # 정렬
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("정렬 안 함", None)
        self.sort_combo.addItem("오름차순 (A→Z, 1→9)", "asc")
        self.sort_combo.addItem("내림차순 (Z→A, 9→1)", "desc")
        if current_sort:
            for i in range(self.sort_combo.count()):
                if self.sort_combo.itemData(i) == current_sort:
                    self.sort_combo.setCurrentIndex(i); break
        form.addRow("정렬:", self.sort_combo)

        # 필터 조건
        self.op_combo = QComboBox()
        for label, key, _need in OPERATORS:
            self.op_combo.addItem(label, key)
        form.addRow("조건:", self.op_combo)

        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("비교 값")
        form.addRow("값:", self.value_input)

        layout.addLayout(form)

        if current:
            op, val = current
            for i in range(self.op_combo.count()):
                if self.op_combo.itemData(i) == op:
                    self.op_combo.setCurrentIndex(i); break
            self.value_input.setText(val or "")

        self.op_combo.currentIndexChanged.connect(self._on_op_changed)
        self._on_op_changed()

        btn_row = QHBoxLayout()
        clear_btn = QPushButton("🗑 필터 제거")
        clear_btn.clicked.connect(self._clear)
        cancel_btn = QPushButton("취소")
        cancel_btn.setStyleSheet(
            "background:white; color:#374151; border:1px solid #d1d5db;")
        cancel_btn.clicked.connect(self.reject)
        apply_btn = QPushButton("✓ 적용")
        apply_btn.setStyleSheet(
            "background:#16a34a; color:white; font-weight:bold;")
        apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)

        self.value_input.returnPressed.connect(self._apply)
        self.value_input.setFocus()

    def _on_op_changed(self):
        op = self.op_combo.currentData()
        needs = next((nv for _, k, nv in OPERATORS if k == op), True)
        self.value_input.setEnabled(needs)
        if not needs:
            self.value_input.clear()

    def _clear(self):
        self.result_filter = ("reset", "")
        self.result_sort = self.sort_combo.currentData()
        self.accept()

    def _apply(self):
        op = self.op_combo.currentData()
        val = self.value_input.text().strip()
        if op == "reset":
            self.result_filter = ("reset", "")
        else:
            needs = next((nv for _, k, nv in OPERATORS if k == op), True)
            if needs and not val:
                self.result_filter = None  # 값 누락 시 필터 변경 안 함
            else:
                self.result_filter = (op, val)
        self.result_sort = self.sort_combo.currentData()
        self.accept()


# ============================================================
# 4. 인라인 필터 행 — 헤더 바로 아래 입력칸 (Excel 스타일)
# ============================================================
# 기본 연산자 시각 마커
OP_MARKER = {
    "contains":     "🔍",
    "not_contains": "🚫",
    "eq":           "=",
    "ne":           "≠",
    "starts":       "A~",
    "ends":         "~A",
    "gt":           ">",
    "gte":          "≥",
    "lt":           "<",
    "lte":          "≤",
}


class InlineFilterBar(QWidget):
    """테이블 컬럼과 픽셀 단위로 정렬되는 인라인 필터 입력 바.

    - 각 컬럼 아래에 작은 QLineEdit 표시
    - 텍스트 입력 시 즉시 setRowHidden 으로 필터링
    - 입력 우클릭 → 연산자 변경 메뉴 (포함/제외/같은/큰/작은 등)
    """
    def __init__(self, table: QTableWidget, parent=None):
        super().__init__(parent)
        self.table = table
        self.inputs = {}     # col -> QLineEdit
        self.operators = {}  # col -> op key (default 'contains')
        self.setFixedHeight(24)
        self.setStyleSheet(
            "QWidget { background:#fffbe6; border-bottom:1px solid #fbbf24; }")
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

        # 디바운스 타이머 - 키 입력 후 200ms 안 누르면 한 번만 적용
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self.apply)

        for c in range(table.columnCount()):
            inp = QLineEdit(self)
            inp.setStyleSheet(
                "background:white; border:1px solid #fbbf24; "
                "padding:1px 4px; font-size:8pt; color:#374151;")
            inp.setPlaceholderText(OP_MARKER["contains"])
            inp.textChanged.connect(self._schedule_apply)
            inp.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            inp.customContextMenuRequested.connect(
                lambda pos, col=c: self._show_op_menu(col, pos))
            self.inputs[c] = inp
            self.operators[c] = "contains"

        hdr = table.horizontalHeader()
        hdr.sectionResized.connect(self._sync)
        hdr.sectionMoved.connect(self._sync)
        table.horizontalScrollBar().valueChanged.connect(self._sync)
        QTimer.singleShot(0, self._sync)
        QTimer.singleShot(100, self._sync)

    def _schedule_apply(self):
        """타이핑할 때마다 즉시 필터링 대신 200ms 디바운스 적용."""
        try:
            self._debounce.start()
        except RuntimeError:
            pass

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._sync()

    def _sync(self):
        """헤더 섹션 위치에 맞춰 각 입력 위치 갱신"""
        hdr = self.table.horizontalHeader()
        for c, inp in self.inputs.items():
            try:
                x = hdr.sectionViewportPosition(c)
                w = hdr.sectionSize(c)
            except Exception:
                continue
            if w <= 0:
                inp.hide(); continue
            if x + w < 0 or x > self.width():
                inp.hide(); continue
            inp.setGeometry(max(0, x) + 1, 1,
                            min(w, self.width() - x) - 2, self.height() - 2)
            inp.show()

    def _show_op_menu(self, col, pos):
        inp = self.inputs[col]
        menu = QMenu(inp)
        for label, key, needs in OPERATORS:
            if key == "reset":
                act = menu.addAction("🗑 모든 필터 초기화")
                act.triggered.connect(self.reset_all)
                continue
            mark = OP_MARKER.get(key, "")
            act = menu.addAction(f"{mark}  {label}")
            act.setCheckable(True)
            act.setChecked(self.operators.get(col) == key)
            act.triggered.connect(lambda _, k=key, c=col: self._set_op(c, k))
        menu.exec(inp.mapToGlobal(pos))

    def _set_op(self, col, op):
        self.operators[col] = op
        self.inputs[col].setPlaceholderText(OP_MARKER.get(op, ""))
        self.apply()

    def reset_all(self):
        for inp in self.inputs.values():
            inp.blockSignals(True); inp.clear(); inp.blockSignals(False)
        for c in self.operators:
            self.operators[c] = "contains"
            self.inputs[c].setPlaceholderText(OP_MARKER["contains"])
        self.apply()

    def apply(self):
        """모든 입력값에 맞춰 setRowHidden 갱신.

        같은 테이블에 팝업 컬럼 필터(column_filters)도 설치돼 있으면
        AND 결합된 통합 필터를 적용해 두 필터가 서로 덮어쓰지 않게 한다.

        성능 최적화: 활성 필터만 모아서 한 번만 비교, .lower() 호출도 최소화.
        예외 처리 보강: PyQt 객체 수명 이슈로 인한 크래시 방지.
        """
        try:
            self._apply_unsafe()
        except RuntimeError:
            # QObject 가 이미 삭제됨 (테이블 재구성 중 등)
            pass
        except Exception as e:
            try:
                print(f"[filter] apply error: {e}")
            except Exception:
                pass

    def _apply_unsafe(self):
        if not self.table or not self.inputs:
            return
        if hasattr(self.table, 'column_filters'):
            apply_all_filters(self.table)
            return

        # 활성 필터만 미리 추출 (값이 비어있지 않은 컬럼)
        active = []  # [(col, op, fv_lower, fv_number_or_None)]
        for col, inp in self.inputs.items():
            try:
                fv = inp.text().strip()
            except RuntimeError:
                continue
            if not fv:
                continue
            op = self.operators.get(col, "contains")
            fv_lower = fv.lower()
            fv_num = _to_number(fv) if op in ("gt", "gte", "lt", "lte") else None
            active.append((col, op, fv_lower, fv_num))

        row_count = self.table.rowCount()

        if not active:
            for r in range(row_count):
                self.table.setRowHidden(r, False)
            return

        for r in range(row_count):
            visible = True
            for col, op, fv_lower, fv_num in active:
                item = self.table.item(r, col)
                cell_l = (item.text() if item else "").lower().strip()
                if op == "contains":
                    ok = fv_lower in cell_l
                elif op == "not_contains":
                    ok = fv_lower not in cell_l
                elif op == "eq":
                    ok = cell_l == fv_lower
                elif op == "ne":
                    ok = cell_l != fv_lower
                elif op == "starts":
                    ok = cell_l.startswith(fv_lower)
                elif op == "ends":
                    ok = cell_l.endswith(fv_lower)
                elif op in ("gt", "gte", "lt", "lte") and fv_num is not None:
                    c = _to_number(cell_l)
                    if c is None:
                        ok = False
                    else:
                        ok = {"gt": c > fv_num, "gte": c >= fv_num,
                              "lt": c < fv_num, "lte": c <= fv_num}[op]
                else:
                    ok = True
                if not ok:
                    visible = False
                    break
            self.table.setRowHidden(r, not visible)


def _clean_header_text(text: str) -> str:
    """헤더 텍스트에서 필터/정렬 마커 제거"""
    for marker in ("▼", "🔽", "▲", "▽"):
        text = text.replace(marker, "")
    return text.strip()


def install_inline_filter_row(table: QTableWidget):
    """테이블 위에 InlineFilterBar 추가. 부모 레이아웃 안에 자동 삽입."""
    if getattr(table, "_inline_filter_installed", False):
        return None
    parent = table.parentWidget()
    if not parent:
        return None
    layout = parent.layout()
    # QSplitter 같은 부모는 직접 위젯 추가 불가 → 스킵
    if not layout:
        return None
    idx = layout.indexOf(table)
    if idx < 0:
        return None
    bar = InlineFilterBar(table, parent)
    layout.insertWidget(idx, bar)
    table._inline_filter_installed = True
    table._inline_filter_bar = bar
    # 데이터 재로드 후에도 필터 다시 적용되도록 헬퍼 노출
    table.apply_inline_filters = bar.apply
    return bar


def install_column_header_filters(table: QTableWidget, on_filter_changed=None):
    """모든 컬럼 헤더에 필터 + 정렬 팝업 설치.

    - 헤더 좌클릭 또는 우클릭 → 필터/정렬 팝업
    - 헤더 텍스트 앞에 ▼ (활성 시 🔽) 표시
    - sortingEnabled 자동 끔 (정렬은 팝업에서 처리)
    - my_table.column_filters: {col: (op, value)}
    - my_table.column_sort: (col, 'asc'|'desc') or None
    """
    table.column_filters = {}
    table.column_sort = None
    table.setSortingEnabled(False)

    hdr = table.horizontalHeader()
    hdr.setSectionsClickable(True)
    hdr.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    # 헤더 텍스트에 ▼ 마커 prefix (시각적 affordance)
    def _decorate_headers():
        for c in range(table.columnCount()):
            hi = table.horizontalHeaderItem(c)
            if not hi:
                continue
            base = _clean_header_text(hi.text())
            active = c in table.column_filters
            sort_dir = (table.column_sort[1]
                        if table.column_sort and table.column_sort[0] == c
                        else None)
            sort_marker = "▲" if sort_dir == "asc" else ("▽" if sort_dir == "desc" else "")
            if active:
                hi.setText(f"🔽 {sort_marker}{base}".strip())
            else:
                hi.setText(f"▼ {sort_marker}{base}".strip())
            hi.setToolTip("클릭 또는 우클릭하여 필터 / 정렬")
    _decorate_headers()

    def _show_popup_at_col(col):
        if col < 0 or col >= table.columnCount():
            return
        hi = table.horizontalHeaderItem(col)
        clean = _clean_header_text(hi.text()) if hi else f"컬럼{col+1}"
        cur_sort_dir = (table.column_sort[1]
                        if table.column_sort and table.column_sort[0] == col
                        else None)
        dlg = ColumnFilterDialog(
            table, clean, table.column_filters.get(col), cur_sort_dir)
        # 위치를 헤더 아래
        try:
            rect = hdr.sectionViewportPosition(col)
            pt = hdr.mapToGlobal(hdr.rect().topLeft())
            dlg.move(pt.x() + rect, pt.y() + hdr.height() + 2)
        except Exception:
            pass
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        # 필터 적용
        if dlg.result_filter is not None:
            op, val = dlg.result_filter
            if op == "reset":
                table.column_filters.pop(col, None)
            else:
                table.column_filters[col] = (op, val)
        # 정렬 적용 (다른 컬럼 정렬은 해제)
        if dlg.result_sort:
            table.column_sort = (col, dlg.result_sort)
            _do_sort(col, dlg.result_sort)
        elif dlg.result_sort is None and table.column_sort and \
                table.column_sort[0] == col:
            table.column_sort = None  # 정렬 해제
        _decorate_headers()
        _apply_filters()
        if on_filter_changed:
            on_filter_changed()

    def _on_section_clicked(col):
        _show_popup_at_col(col)

    def _on_context(pos):
        col = hdr.logicalIndexAt(pos)
        _show_popup_at_col(col)

    def _do_sort(col, direction):
        # 데이터 추출 후 재배치
        rows_data = []
        for r in range(table.rowCount()):
            cells = []
            for c in range(table.columnCount()):
                it = table.item(r, c)
                txt = it.text() if it else ""
                cells.append((txt, it))
            # 표 위에 위젯도 보존하려면 cellWidget 챙겨야 함 — 일단 텍스트만
            rows_data.append(cells)
        # sort key: 숫자 가능하면 숫자로, 아니면 문자열
        def keyfn(row):
            t = row[col][0]
            try:
                return (0, float(t.replace(",", "")))
            except (ValueError, TypeError):
                return (1, t.lower() if t else "")
        rows_data.sort(key=keyfn, reverse=(direction == "desc"))
        # 다시 채우기
        for r, cells in enumerate(rows_data):
            for c, (txt, orig_item) in enumerate(cells):
                new_item = QTableWidgetItem(txt)
                if orig_item is not None:
                    new_item.setTextAlignment(orig_item.textAlignment())
                    new_item.setForeground(orig_item.foreground())
                    new_item.setFont(orig_item.font())
                    ud = orig_item.data(Qt.ItemDataRole.UserRole)
                    if ud is not None:
                        new_item.setData(Qt.ItemDataRole.UserRole, ud)
                table.setItem(r, c, new_item)

    def _apply_filters():
        # 인라인 필터도 함께 설치돼 있으면 AND 결합된 통합 필터로
        if getattr(table, '_inline_filter_bar', None) is not None:
            apply_all_filters(table)
            return
        for r in range(table.rowCount()):
            visible = True
            for col, (op, val) in table.column_filters.items():
                it = table.item(r, col)
                if not match_cell(it.text() if it else "", op, val):
                    visible = False; break
            table.setRowHidden(r, not visible)

    hdr.sectionClicked.connect(_on_section_clicked)
    hdr.customContextMenuRequested.connect(_on_context)
    table.apply_column_filters = _apply_filters
    table.redecorate_headers = _decorate_headers
    return table


def reset_column_filters(table: QTableWidget):
    """모든 컬럼 필터 + 정렬 초기화 (팝업 + 인라인 둘 다)"""
    if hasattr(table, 'column_filters'):
        table.column_filters.clear()
        table.column_sort = None
        if hasattr(table, 'redecorate_headers'):
            table.redecorate_headers()
    bar = getattr(table, '_inline_filter_bar', None)
    if bar is not None:
        bar.reset_all()
    else:
        for r in range(table.rowCount()):
            table.setRowHidden(r, False)


def apply_all_filters(table: QTableWidget):
    """팝업 컬럼 필터 + 인라인 입력행 필터를 AND 로 결합 적용.

    두 필터가 setRowHidden 을 두고 다투지 않도록 단일 패스로 계산.
    inventory.py / inventory_picker.py 처럼 두 필터를 함께 쓰는 화면에서 사용.

    성능: 활성 필터만 미리 모으고 .lower() 1회만 호출하여 큰 테이블에서도 빠르게.
    안전: RuntimeError (QObject 수명 종료) 등 무시.
    """
    try:
        _apply_all_unsafe(table)
    except RuntimeError:
        pass
    except Exception as e:
        try:
            print(f"[filter] apply_all error: {e}")
        except Exception:
            pass


def _apply_all_unsafe(table: QTableWidget):
    column_filters = getattr(table, 'column_filters', None) or {}
    bar = getattr(table, '_inline_filter_bar', None)

    # 팝업/인라인 활성 필터를 동일 구조로 정규화
    active = []  # [(col, op, fv_lower, fv_num)]
    for col, (op, val) in column_filters.items():
        if op == "reset":
            continue
        fv = (val or "").lower().strip()
        fn = _to_number(fv) if op in ("gt", "gte", "lt", "lte") else None
        active.append((col, op, fv, fn))
    if bar is not None:
        for col, inp in bar.inputs.items():
            try:
                fv_raw = inp.text().strip()
            except RuntimeError:
                continue
            if not fv_raw:
                continue
            op = bar.operators.get(col, "contains")
            fv = fv_raw.lower()
            fn = _to_number(fv) if op in ("gt", "gte", "lt", "lte") else None
            active.append((col, op, fv, fn))

    row_count = table.rowCount()

    if not active:
        for r in range(row_count):
            table.setRowHidden(r, False)
        return

    for r in range(row_count):
        visible = True
        for col, op, fv, fn in active:
            it = table.item(r, col)
            cell = (it.text() if it else "").lower().strip()
            if op == "contains":
                ok = fv in cell
            elif op == "not_contains":
                ok = fv not in cell
            elif op == "eq":
                ok = cell == fv
            elif op == "ne":
                ok = cell != fv
            elif op == "starts":
                ok = cell.startswith(fv)
            elif op == "ends":
                ok = cell.endswith(fv)
            elif op in ("gt", "gte", "lt", "lte") and fn is not None:
                c = _to_number(cell)
                if c is None:
                    ok = False
                else:
                    ok = {"gt": c > fn, "gte": c >= fn,
                          "lt": c < fn, "lte": c <= fn}[op]
            else:
                ok = True
            if not ok:
                visible = False
                break
        table.setRowHidden(r, not visible)


def auto_install_filters(widget):
    """주어진 위젯 트리 안의 모든 QTableWidget 에:
    - 헤더 바로 아래 인라인 필터 행 설치
    """
    for t in widget.findChildren(QTableWidget):
        try:
            install_inline_filter_row(t)
        except Exception as e:
            print(f"[filter] inline install skipped: {e}")


# ============================================================
# 5. 일자 빠른 버튼 자동 설치
# ============================================================
# 날짜로 해석할 컬럼 라벨 키워드 (소문자 비교)
_DATE_KEYWORDS = [
    "일자", "날짜", "입고일", "출고일", "결제예정",
    "매출일", "매입일", "지급일", "수금일", "거래일",
    "출고완료", "출고요청",
]


def _is_date_column_label(label: str) -> bool:
    low = (label or "").lower()
    return any(k in low for k in _DATE_KEYWORDS)


def _filter_tables_by_date(widget, start: date, end: date):
    """위젯의 모든 테이블에서 '일자' 컬럼을 찾아 기간 필터링.

    - 기존 인라인 필터와 별도로 setRowHidden 적용 (AND 조합)
    - 일자 컬럼은 헤더 라벨 키워드로 자동 감지
    """
    s = start.isoformat()
    e = end.isoformat()
    for t in widget.findChildren(QTableWidget):
        # 일자 컬럼 인덱스 찾기
        date_col = -1
        for c in range(t.columnCount()):
            hi = t.horizontalHeaderItem(c)
            if not hi:
                continue
            if _is_date_column_label(_clean_header_text(hi.text())):
                date_col = c; break
        if date_col < 0:
            continue
        # 기존 인라인 필터 통과 여부 + 날짜 범위 체크
        bar = getattr(t, "_inline_filter_bar", None)
        for r in range(t.rowCount()):
            # 인라인 필터 결과를 보존
            base_visible = True
            if bar is not None:
                # bar 가 같은 logic 으로 재계산
                for col, inp in bar.inputs.items():
                    fv = inp.text().strip()
                    if not fv: continue
                    op = bar.operators.get(col, "contains")
                    it = t.item(r, col)
                    cell = it.text() if it else ""
                    if not match_cell(cell, op, fv):
                        base_visible = False; break
            # 날짜 범위
            if base_visible:
                it = t.item(r, date_col)
                if it:
                    cell = (it.text() or "").strip()[:10]
                    if cell and not (s <= cell <= e):
                        base_visible = False
                else:
                    base_visible = False
            t.setRowHidden(r, not base_visible)


def auto_install_date_bar(widget, default_days_back: int = 30):
    """위젯 최상단에 DateRangeBar 추가 + 일자 컬럼 자동 필터 연결.
    위젯에 일자 컬럼이 1개도 없으면 추가하지 않음.
    """
    if getattr(widget, "_date_bar_installed", False):
        return None
    # 일자 컬럼이 있는지 검사
    has_date = False
    for t in widget.findChildren(QTableWidget):
        for c in range(t.columnCount()):
            hi = t.horizontalHeaderItem(c)
            if hi and _is_date_column_label(_clean_header_text(hi.text())):
                has_date = True; break
        if has_date: break
    if not has_date:
        return None

    layout = widget.layout()
    if layout is None:
        return None

    bar_container = QWidget()
    bar_layout = QHBoxLayout(bar_container)
    bar_layout.setContentsMargins(8, 4, 8, 4)
    bar_layout.setSpacing(4)
    bar = DateRangeBar(default_days_back=default_days_back)
    bar_layout.addWidget(bar)
    bar_layout.addStretch()
    bar_container.setStyleSheet(
        "QWidget { background:#eff6ff; border-bottom:1px solid #bfdbfe; }")

    bar.range_changed.connect(
        lambda s, e: _filter_tables_by_date(widget, s, e))

    layout.insertWidget(0, bar_container)
    widget._date_bar_installed = True
    widget._date_bar = bar
    return bar


def auto_install_all(widget):
    """인라인 필터 + DateRangeBar 한 번에 설치"""
    auto_install_date_bar(widget)
    auto_install_filters(widget)


# ============================================================
# 3. 일자 빠른 버튼 — [당일][전일][명일][금월][전월][30일]
# ============================================================
class DateQuickFilter(QWidget):
    """일자 빠른 선택 버튼. period_selected(start_date, end_date) emit"""
    period_selected = pyqtSignal(object, object)  # date, date

    def __init__(self):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(2)
        presets = [
            ("당일",  "today"),
            ("전일",  "yesterday"),
            ("명일",  "tomorrow"),
            ("금월",  "this_month"),
            ("전월",  "last_month"),
            ("30일",  "last_30"),
        ]
        for label, key in presets:
            btn = QPushButton(label)
            btn.setMaximumWidth(52)
            btn.setStyleSheet(
                "background:white; color:#374151; "
                "border:1px solid #d1d5db; padding:3px 6px;"
                "QPushButton:hover { background:#f3f4f6; }")
            btn.clicked.connect(lambda _, k=key: self._emit(k))
            h.addWidget(btn)

    def _emit(self, period: str):
        today = date.today()
        if period == "today":
            s = e = today
        elif period == "yesterday":
            s = e = today - timedelta(days=1)
        elif period == "tomorrow":
            s = e = today + timedelta(days=1)
        elif period == "this_month":
            s = today.replace(day=1)
            last_day = monthrange(today.year, today.month)[1]
            e = today.replace(day=last_day)
        elif period == "last_month":
            if today.month == 1:
                y, m = today.year - 1, 12
            else:
                y, m = today.year, today.month - 1
            last_day = monthrange(y, m)[1]
            s = date(y, m, 1)
            e = date(y, m, last_day)
        elif period == "last_30":
            s = today - timedelta(days=30)
            e = today
        else:
            s = e = today
        self.period_selected.emit(s, e)


class DateRangeBar(QWidget):
    """기간 선택 바: [시작일] ~ [종료일] + 빠른 버튼"""
    range_changed = pyqtSignal(object, object)  # start_date, end_date

    def __init__(self, default_days_back: int = 30):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        h.addWidget(QLabel("기간:"))

        today = date.today()
        self.start = QDateEdit()
        self.start.setDate(QDate(
            today.year if today.day >= default_days_back else today.year,
            today.month, max(1, today.day - 0)
        ))
        self.start.setDate(QDate.currentDate().addDays(-default_days_back))
        self.start.setCalendarPopup(True)
        self.start.setDisplayFormat("yyyy-MM-dd")
        self.start.setMaximumWidth(120)
        self.start.dateChanged.connect(self._emit_range)
        h.addWidget(self.start)

        h.addWidget(QLabel("~"))

        self.end = QDateEdit()
        self.end.setDate(QDate.currentDate())
        self.end.setCalendarPopup(True)
        self.end.setDisplayFormat("yyyy-MM-dd")
        self.end.setMaximumWidth(120)
        self.end.dateChanged.connect(self._emit_range)
        h.addWidget(self.end)

        self.quick = DateQuickFilter()
        self.quick.period_selected.connect(self._on_quick)
        h.addWidget(self.quick)

    def _on_quick(self, s, e):
        self.start.setDate(QDate(s.year, s.month, s.day))
        self.end.setDate(QDate(e.year, e.month, e.day))

    def _emit_range(self):
        s = self.start.date().toPyDate()
        e = self.end.date().toPyDate()
        self.range_changed.emit(s, e)

    def get_range(self):
        return self.start.date().toPyDate(), self.end.date().toPyDate()
