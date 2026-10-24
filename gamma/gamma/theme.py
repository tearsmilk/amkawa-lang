"""Claude-like look (shared with Каппа, Epsilon, Ню, Дзета, Дельта, Лямбда and Мю): ivory / charcoal, terracotta accent,
serif headings. `rec` is the recording red."""

LIGHT = dict(
    name="light",
    bg="#FAF9F5", sidebar="#F0EEE6", panel="#F0EEE6", card="#FFFFFF", border="#E3DFD3", text="#141413",
    muted="#6F6E69", faint="#A8A59C", accent="#D97757", accent_hover="#C6613F", accent_text="#FFFFFF",
    selected="#E6E2D6", hover="#E9E6DC", input="#FFFFFF", ok="#4E8A5A", warn="#B5642E",
        rec="#D64545", dim="#99141413",
)

DARK = dict(
    name="dark",
    bg="#262624", sidebar="#1F1E1D", panel="#1F1E1D", card="#30302E", border="#3E3D39", text="#F4F2EC",
    muted="#A6A39A", faint="#6E6C66", accent="#D97757", accent_hover="#E08A6D", accent_text="#FFFFFF",
    selected="#3A3936", hover="#34332F", input="#262624", ok="#7BB487", warn="#E59866",
        rec="#E05A5A", dim="#99141413",
)

SERIF = '"Georgia", "Tiempos Text", "Times New Roman", serif'


def stylesheet(c):
    return f"""
* {{ color: {c['text']}; font-size: 12px; }}
QMainWindow, #Main {{ background: {c['bg']}; }}
QDialog {{ background: {c['bg']}; }}
QToolTip {{ background: {c['card']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 4px; }}
#Side {{ background: {c['sidebar']}; border-right: 1px solid {c['border']}; }}
#Side QPushButton {{ text-align: left; border: none; background: transparent; padding: 7px 10px; border-radius: 7px; }}
#Side QPushButton:hover {{ background: {c['hover']}; }}
#Side QPushButton:checked {{ background: {c['selected']}; }}
#Gamma {{ color: {c['accent']}; font-family: {SERIF}; font-style: italic; font-size: 30px; }}
#Logo {{ font-family: {SERIF}; font-size: 17px; }}
#Title {{ font-family: {SERIF}; font-size: 28px; }}
#H2 {{ font-family: {SERIF}; font-size: 18px; }}
#Section {{ color: {c['muted']}; font-size: 10px; font-weight: 600; letter-spacing: 1px; }}
#Muted {{ color: {c['muted']}; }}
#Hint {{ color: {c['muted']}; font-size: 11px; }}
#Warn {{ color: {c['warn']}; font-size: 11px; }}
#Ok {{ color: {c['ok']}; font-size: 11px; }}
#Sep {{ background: {c['border']}; }}
#Page {{ background: {c['bg']}; }}

QPushButton {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 7px; padding: 5px 12px; }}
QPushButton:hover {{ background: {c['hover']}; }}
QPushButton:disabled {{ color: {c['faint']}; }}
QPushButton#Accent {{ background: {c['accent']}; color: {c['accent_text']}; border: none; font-weight: 600; }}
QPushButton#Accent:hover {{ background: {c['accent_hover']}; }}
QPushButton#Accent:disabled {{ background: {c['selected']}; color: {c['faint']}; }}
QPushButton#Rec {{ background: {c['rec']}; color: #FFFFFF; border: none; font-weight: 600; }}
QPushButton#Link {{ background: transparent; border: none; color: {c['accent']}; padding: 3px 4px; text-align: left; }}
QPushButton#Seg {{ border-radius: 0; padding: 5px 12px; }}
QPushButton#Seg:checked {{ background: {c['selected']}; border: 1px solid {c['accent']}; }}
QToolButton {{ background: transparent; border: none; border-radius: 6px; padding: 3px 5px; }}
QToolButton:hover {{ background: {c['hover']}; }}
QToolButton:checked {{ background: {c['selected']}; }}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {c['input']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 3px 6px; min-height: 16px; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {c['accent']}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{ background: {c['card']}; border: 1px solid {c['border']};
    selection-background-color: {c['selected']}; selection-color: {c['text']}; outline: none; }}
QCheckBox {{ spacing: 6px; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border-radius: 4px; border: 1px solid {c['muted']}; background: {c['input']}; }}
QCheckBox::indicator:checked {{ background: {c['accent']}; border: 1px solid {c['accent']}; }}
QMenu {{ background: {c['card']}; border: 1px solid {c['border']}; padding: 6px; border-radius: 10px; }}
QMenu::item {{ padding: 5px 22px 5px 10px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c['selected']}; color: {c['text']}; }}
QMenu::item:disabled {{ color: {c['faint']}; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 4px 6px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 4px; min-height: 24px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {c['border']}; border-radius: 4px; min-width: 24px; margin: 2px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget#Page {{ background: transparent; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ padding: 4px; border-radius: 8px; }}
QListWidget::item:selected {{ background: {c['selected']}; color: {c['text']}; }}
QListWidget::item:hover {{ background: {c['hover']}; }}
#Card {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px; }}
#Card:hover {{ border: 1px solid {c['accent']}; }}
#CardTitle {{ font-family: {SERIF}; font-size: 16px; }}
#Box {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px; }}
#ReplayOn {{ background: {c['card']}; border: 1px solid {c['accent']}; border-radius: 14px; }}
#Hotkey {{ background: {c['input']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 3px 8px; min-width: 110px; }}
#Hotkey:focus {{ border: 1px solid {c['accent']}; }}
#Kbd {{ color: {c['muted']}; background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 5px; padding: 1px 6px;
    font-size: 11px; }}
#Badge {{ color: {c['accent_text']}; background: {c['accent']}; border-radius: 8px; padding: 1px 8px; font-size: 11px; }}
"""
