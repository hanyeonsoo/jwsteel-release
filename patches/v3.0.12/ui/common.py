"""공통 스타일, 유틸리티 함수"""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QMessageBox


# ============================================================
# 색상 / 스타일
# ============================================================
COLORS = {
    'primary':    '#2563eb',      # 파랑 (주 액션)
    'success':    '#16a34a',      # 녹색 (수금/완료)
    'warning':    '#f59e0b',      # 주황 (연체/주의)
    'danger':     '#dc2626',      # 빨강 (취소/삭제)
    'gray':       '#6b7280',
    'bg_light':   '#f9fafb',
    'border':     '#e5e7eb',
}

# 메인 스타일시트 — 컴팩트 (더 많은 데이터를 한 화면에)
MAIN_STYLE = f"""
QMainWindow, QDialog {{
    background-color: {COLORS['bg_light']};
    font-size: 9pt;
}}
QWidget {{
    font-size: 9pt;
    color: #111827;
}}
QLabel {{
    color: #111827;
    background: transparent;
}}
QPushButton {{
    background-color: {COLORS['primary']};
    color: white;
    border: none;
    padding: 5px 12px;
    border-radius: 3px;
    font-weight: 500;
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: #1d4ed8;
}}
QPushButton:disabled {{
    background-color: #cbd5e1;
}}
QPushButton.secondary {{
    background-color: white;
    color: #374151;
    border: 1px solid {COLORS['border']};
}}
QPushButton.secondary:hover {{
    background-color: #f3f4f6;
}}
QPushButton.success {{
    background-color: {COLORS['success']};
}}
QPushButton.success:hover {{
    background-color: #15803d;
}}
QPushButton.danger {{
    background-color: {COLORS['danger']};
}}
QPushButton.danger:hover {{
    background-color: #b91c1c;
}}

QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QTextEdit {{
    border: 1px solid {COLORS['border']};
    border-radius: 3px;
    padding: 4px 8px;
    background-color: white;
    color: #111827;
    min-height: 22px;
    selection-background-color: #bfdbfe;
    selection-color: #111827;
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QTextEdit:focus {{
    border: 2px solid {COLORS['primary']};
}}
/* placeholder 색상은 main.py 의 QPalette.PlaceholderText 로 설정 */

QTableWidget {{
    background-color: white;
    border: 1px solid {COLORS['border']};
    border-radius: 3px;
    gridline-color: #f3f4f6;
    font-size: 9pt;
}}
QTableWidget::item {{
    padding: 3px 6px;
}}
QTableWidget::item:selected {{
    background-color: #dbeafe;
    color: black;
}}
QHeaderView::section {{
    background-color: #f3f4f6;
    padding: 4px 6px;
    border: none;
    border-bottom: 2px solid {COLORS['border']};
    font-weight: 600;
    font-size: 9pt;
}}
QTabBar::tab {{
    padding: 6px 14px;
    font-size: 9pt;
}}
QGroupBox {{
    font-size: 9pt;
}}

/* QFormLayout 라벨 (자동 생성) 가시성 보장 */
QFormLayout > QLabel {{
    color: #111827;
    padding-right: 8px;
}}

QLabel.title {{
    font-size: 18pt;
    font-weight: bold;
    color: #111827;
    padding: 8px 0px;
}}
QLabel.subtitle {{
    font-size: 12pt;
    color: {COLORS['gray']};
}}
QLabel.stat-value {{
    font-size: 22pt;
    font-weight: bold;
    color: {COLORS['primary']};
}}
QLabel.stat-label {{
    font-size: 10pt;
    color: {COLORS['gray']};
}}

QListWidget {{
    background-color: #1f2937;
    color: #d1d5db;
    border: none;
    padding: 8px 0px;
    font-size: 11pt;
}}
QListWidget::item {{
    padding: 12px 20px;
    border: none;
}}
QListWidget::item:hover {{
    background-color: #374151;
    color: white;
}}
QListWidget::item:selected {{
    background-color: {COLORS['primary']};
    color: white;
}}

QStatusBar {{
    background-color: white;
    border-top: 1px solid {COLORS['border']};
    padding: 4px;
}}
QGroupBox {{
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    left: 10px;
    padding: 0 4px;
    color: #374151;
}}
"""


# ============================================================
# 유틸 함수
# ============================================================
def fmt_money(amount, with_sign=False):
    """금액 포맷팅"""
    if amount is None:
        return "-"
    if with_sign and amount > 0:
        return f"+{amount:,}"
    return f"{amount:,}"


def msg_info(parent, title, text):
    QMessageBox.information(parent, title, text)


def msg_warning(parent, title, text):
    QMessageBox.warning(parent, title, text)


def msg_error(parent, title, text):
    QMessageBox.critical(parent, title, text)


def msg_confirm(parent, title, text) -> bool:
    """확인 다이얼로그 - True/False 반환"""
    reply = QMessageBox.question(
        parent, title, text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return reply == QMessageBox.StandardButton.Yes


# ============================================================
# 상태 색상
# ============================================================
def status_color(status: str) -> QColor:
    """매출/수금/매칭 상태 → 색"""
    mapping = {
        '완료':       COLORS['success'],
        '미수':       COLORS['danger'],
        '일부수금':   COLORS['warning'],
        '미지급':     COLORS['danger'],
        '일부지급':   COLORS['warning'],
        '정상':       COLORS['gray'],
        '취소':       COLORS['danger'],
        '자동매칭':   COLORS['success'],
        '후보제시':   COLORS['warning'],
        '매칭실패':   COLORS['danger'],
        '수동매칭':   COLORS['primary'],
        '미처리':     COLORS['gray'],
        '무시(출금)': '#9ca3af',
    }
    return QColor(mapping.get(status, COLORS['gray']))
