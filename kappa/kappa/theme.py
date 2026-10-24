"""Claude-like look: warm ivory / charcoal surfaces, terracotta accent, serif headings."""

LIGHT = dict(
    bg="#FAF9F5", sidebar="#F0EEE6", card="#FFFFFF", border="#E3DFD3", text="#141413",
    muted="#6F6E69", accent="#D97757", accent_hover="#C6613F", accent_text="#FFFFFF",
    selected="#E6E2D6", hover="#E9E6DC", groove="#E3DFD3", input="#FFFFFF", ok="#4E8A5A",
    warn="#B5642E", meter_bg="#ECE9E0",
)

DARK = dict(
    bg="#262624", sidebar="#1F1E1D", card="#30302E", border="#3E3D39", text="#F4F2EC",
    muted="#A6A39A", accent="#D97757", accent_hover="#E08A6D", accent_text="#FFFFFF",
    selected="#3A3936", hover="#34332F", groove="#4A4944", input="#262624", ok="#7BB487",
    warn="#E59866", meter_bg="#3A3936",
)

SERIF = '"Georgia", "Tiempos Text", "Times New Roman", serif'


def stylesheet(c):
    return f"""
* {{ color: {c['text']}; font-size: 13px; }}
QMainWindow, #Main {{ background: {c['bg']}; }}
QScrollArea, #MainInner {{ background: {c['bg']}; border: none; }}
#Sidebar {{ background: {c['sidebar']}; border-right: 1px solid {c['border']}; }}
#Logo {{ font-family: {SERIF}; font-size: 21px; }}
#Spark {{ color: {c['accent']}; font-size: 22px; }}
#Kappa {{ color: {c['accent']}; font-family: {SERIF}; font-style: italic; font-size: 30px; padding-bottom: 3px; }}
#Section {{ color: {c['muted']}; font-size: 11px; font-weight: 600; letter-spacing: 1px; }}
#Title {{ font-family: {SERIF}; font-size: 30px; }}
#CardTitle {{ font-family: {SERIF}; font-size: 18px; }}
#Muted, QLabel[muted="true"] {{ color: {c['muted']}; }}
#Status {{ color: {c['muted']}; }}
#StatusOk {{ color: {c['ok']}; }}
#StatusWarn {{ color: {c['warn']}; }}
#Card {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px; }}
#Card QLabel {{ background: transparent; }}

QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ border-radius: 9px; padding: 0px; margin: 1px 0px; }}
QListWidget::item:hover {{ background: {c['hover']}; }}
QListWidget::item:selected {{ background: {c['selected']}; }}
#ModelName {{ font-size: 14px; }}
#ModelInfo {{ color: {c['muted']}; font-size: 11px; }}

QPushButton {{
    background: {c['card']}; border: 1px solid {c['border']}; border-radius: 9px;
    padding: 7px 14px;
}}
QPushButton:hover {{ background: {c['hover']}; }}
QPushButton:disabled {{ color: {c['muted']}; }}
QPushButton#Primary {{
    background: {c['accent']}; color: {c['accent_text']}; border: none; font-weight: 600;
    border-radius: 12px; padding: 12px 26px; font-size: 15px;
}}
QPushButton#Primary:hover {{ background: {c['accent_hover']}; }}
QPushButton#Primary[active="true"] {{ background: {c['text']}; color: {c['bg']}; }}
QPushButton#Accent {{ background: {c['accent']}; color: {c['accent_text']}; border: none; font-weight: 600; }}
QPushButton#Accent:hover {{ background: {c['accent_hover']}; }}
QPushButton#Accent:disabled {{ background: {c['groove']}; }}
QPlainTextEdit {{
    background: {c['input']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 6px 8px;
}}
QPlainTextEdit:focus {{ border: 1px solid {c['accent']}; }}
QPushButton#Ghost {{ background: transparent; border: 1px dashed {c['border']}; color: {c['muted']}; }}
QPushButton#Ghost:hover {{ background: {c['hover']}; color: {c['text']}; }}
QPushButton#Link {{ background: transparent; border: none; color: {c['muted']}; padding: 4px 6px; }}
QPushButton#Link:hover {{ color: {c['accent']}; }}

QComboBox, QLineEdit, QDoubleSpinBox {{
    background: {c['input']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 6px 10px;
    min-height: 18px;
}}
QComboBox:focus, QLineEdit:focus, QDoubleSpinBox:focus {{ border: 1px solid {c['accent']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {c['card']}; border: 1px solid {c['border']}; selection-background-color: {c['selected']};
    selection-color: {c['text']}; outline: none;
}}

QSlider::groove:horizontal {{ height: 4px; background: {c['groove']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {c['accent']}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {c['card']}; border: 2px solid {c['accent']}; width: 12px; height: 12px;
    margin: -6px 0; border-radius: 8px;
}}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 5px; border: 1px solid {c['border']}; background: {c['input']};
}}
QCheckBox::indicator:checked {{ background: {c['accent']}; border: 1px solid {c['accent']}; }}

QProgressBar {{ background: {c['meter_bg']}; border: none; border-radius: 4px; height: 8px; text-align: center; }}
QProgressBar::chunk {{ background: {c['accent']}; border-radius: 4px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['groove']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; padding: 6px 14px; color: {c['muted']}; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {c['text']}; border-bottom: 2px solid {c['accent']}; }}
QDialog {{ background: {c['bg']}; }}
QToolTip {{ background: {c['card']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 4px; }}
"""
