from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractButton

APP_STYLESHEET = """
QMainWindow, QDialog, QMessageBox {
    background: #f5f7fa;
}

QWidget {
    color: #1d2733;
    font-family: "Segoe UI", "Arial", "Tahoma", sans-serif;
    font-size: 10pt;
}

QFrame#SurfaceBar,
QFrame#PathBar,
QFrame#SearchPanel,
QFrame#TableCard {
    background: #ffffff;
    border: 1px solid #d8e0ea;
    border-radius: 10px;
}

QToolButton,
QPushButton {
    background: #ffffff;
    border: 1px solid #cfd8e3;
    border-radius: 7px;
    min-height: 32px;
    padding: 2px 8px;
    outline: 0;
}

QToolButton:focus,
QPushButton:focus {
    border-color: #cfd8e3;
}

QToolButton:hover,
QPushButton:hover {
    background: #f3f7fb;
    border-color: #aab8c8;
}

QToolButton:pressed,
QPushButton:pressed {
    background: #e8eef6;
    border-color: #94a3b8;
}

QToolButton::menu-indicator {
    image: none;
    width: 0;
}

QToolButton#PathButton {
    min-height: 26px;
    max-height: 28px;
    padding: 2px 7px;
    border-radius: 6px;
    font-size: 9pt;
}

QLineEdit {
    background: #ffffff;
    border: 1px solid #cfd8e3;
    border-radius: 7px;
    min-height: 34px;
    padding: 0 11px;
    selection-background-color: #2f6fbd;
    selection-color: #ffffff;
}

QLineEdit:focus {
    border-color: #6e97c7;
}

QCheckBox {
    spacing: 8px;
}

QTableWidget {
    background: #ffffff;
    alternate-background-color: #fafbfc;
    border: 0;
    border-radius: 9px;
    gridline-color: transparent;
    outline: 0;
    selection-background-color: #e6f0ff;
    selection-color: #152033;
}

QTableWidget::viewport {
    background: #ffffff;
    border: 0;
}

QTableWidget::corner {
    background: #f8fafc;
    border: 0;
}

QScrollBar:vertical {
    background: transparent;
    border: 0;
    margin: 4px 3px 4px 0;
    width: 12px;
}

QScrollBar::handle:vertical {
    background: #b8c4d3;
    border-radius: 5px;
    min-height: 34px;
}

QScrollBar::handle:vertical:hover {
    background: #8fa0b4;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
    border: 0;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    background: transparent;
    border: 0;
    height: 12px;
    margin: 0 4px 3px 4px;
}

QScrollBar::handle:horizontal {
    background: #b8c4d3;
    border-radius: 5px;
    min-width: 34px;
}

QScrollBar::handle:horizontal:hover {
    background: #8fa0b4;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
    border: 0;
}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: transparent;
}

QTableWidget::item {
    border: 0;
    outline: 0;
    padding: 0 10px;
}

QTableWidget::item:focus {
    border: 0;
    outline: 0;
}

QTableWidget::item:selected {
    background: #e6f0ff;
    color: #152033;
}

QHeaderView::section {
    background: #f8fafc;
    border: 0;
    border-bottom: 1px solid #d8e0ea;
    color: #273548;
    font-weight: 600;
    padding: 9px 10px;
    text-align: left;
}

QMenu {
    background: #ffffff;
    border: 1px solid #d8e0ea;
    border-radius: 8px;
    padding: 4px;
    margin: 8px;
}

QMenu::icon {
    padding-left: 16px;
}

QMenu::item {
    border-radius: 6px;
    padding: 8px 24px 8px 14px;
}

QMenu::item:selected {
    background: #edf4ff;
    color: #172033;
}

QMenu::separator {
    height: 1px;
    background: #e7edf4;
    margin: 6px 8px;
}

QStatusBar {
    background: transparent;
    border-top: 1px solid #d8e0ea;
    color: #667385;
    min-height: 24px;
    padding: 0 8px;
}

QToolTip {
    background: #1f2937;
    color: #ffffff;
    border: 0;
    border-radius: 6px;
    padding: 6px 8px;
}
"""


def make_interactive(button: QAbstractButton, tooltip: str | None = None) -> None:
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    if tooltip:
        button.setToolTip(tooltip)
        button.setStatusTip(tooltip)
