"""Claude-like look (shared with Каппа, Epsilon, Ню, Дзета, Дельта and Лямбда): ivory / charcoal, terracotta accent, serif headings."""

LIGHT = dict(
    name="light",
    bg="#FAF9F5", sidebar="#F0EEE6", panel="#F0EEE6", card="#FFFFFF", border="#E3DFD3", text="#141413",
    muted="#6F6E69", faint="#A8A59C", accent="#D97757", accent_hover="#C6613F", accent_text="#FFFFFF",
    selected="#E6E2D6", hover="#E9E6DC", input="#FFFFFF", ok="#4E8A5A", warn="#B5642E",
    canvas="#E9E6DC", checker_a="#FFFFFF", checker_b="#E8E5DD", pixel_grid="#33141413",
    cel="#D97757", cel_empty="#C9C4B6", frame_current="#F6DED3", tag_text="#FFFFFF", key="#D97757", track="#E3DFD3",
    layer_bar="#E8E2D2", board="#F7F5EF", dot="#D3CEC1", handle="#FFFFFF", guide="#D97757", component="#9B59B6",
)

DARK = dict(
    name="dark",
    bg="#262624", sidebar="#1F1E1D", panel="#1F1E1D", card="#30302E", border="#3E3D39", text="#F4F2EC",
    muted="#A6A39A", faint="#6E6C66", accent="#D97757", accent_hover="#E08A6D", accent_text="#FFFFFF",
    selected="#3A3936", hover="#34332F", input="#262624", ok="#7BB487", warn="#E59866",
    canvas="#191918", checker_a="#3A3936", checker_b="#2E2D2B", pixel_grid="#40F4F2EC",
    cel="#D97757", cel_empty="#55534D", frame_current="#4A362D", tag_text="#FFFFFF", key="#D97757", track="#3E3D39",
    layer_bar="#34332F", board="#232322", dot="#3F3E3A", handle="#FFFFFF", guide="#E08A6D", component="#C39BD3",
)

SERIF = '"Georgia", "Tiempos Text", "Times New Roman", serif'


def stylesheet(c):
    return f"""
* {{ color: {c['text']}; font-size: 12px; }}
QMainWindow, #Main {{ background: {c['bg']}; }}
QDialog {{ background: {c['bg']}; }}
QToolTip {{ background: {c['card']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 4px; }}

#ToolBox {{ background: {c['sidebar']}; border-right: 1px solid {c['border']}; }}
#ToolBox QToolButton {{ background: transparent; border: none; border-radius: 7px; padding: 4px; }}
#ToolBox QToolButton:hover {{ background: {c['hover']}; }}
#ToolBox QToolButton:checked {{ background: {c['selected']}; border: 1px solid {c['accent']}; }}
#ContextBar {{ background: {c['bg']}; border-bottom: 1px solid {c['border']}; }}
#SidePanel {{ background: {c['panel']}; border-left: 1px solid {c['border']}; }}
#Timeline {{ background: {c['panel']}; border-top: 1px solid {c['border']}; }}
#Logo {{ font-family: {SERIF}; font-size: 17px; }}
#Mu {{ color: {c['accent']}; font-family: {SERIF}; font-style: italic; font-size: 26px; }}
#BigLogo {{ color: {c['accent']}; font-family: {SERIF}; font-style: italic; font-size: 110px; }}
#Title {{ font-family: {SERIF}; font-size: 28px; }}
#Section {{ color: {c['muted']}; font-size: 10px; font-weight: 600; letter-spacing: 1px; }}
#Muted {{ color: {c['muted']}; }}
#Sep {{ background: {c['border']}; }}

QPushButton {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 7px; padding: 5px 12px; }}
QPushButton:hover {{ background: {c['hover']}; }}
QPushButton:disabled {{ color: {c['faint']}; }}
QPushButton#Accent {{ background: {c['accent']}; color: {c['accent_text']}; border: none; font-weight: 600; }}
QPushButton#Accent:hover {{ background: {c['accent_hover']}; }}
QPushButton#Link {{ background: transparent; border: none; color: {c['accent']}; padding: 3px 4px; text-align: left; }}
QToolButton {{ background: transparent; border: none; border-radius: 6px; padding: 3px 5px; }}
QToolButton:hover {{ background: {c['hover']}; }}
QToolButton:checked {{ background: {c['selected']}; }}
QToolButton:disabled {{ color: {c['faint']}; }}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {c['input']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 3px 6px; min-height: 16px; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {c['accent']}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{ background: {c['card']}; border: 1px solid {c['border']};
    selection-background-color: {c['selected']}; selection-color: {c['text']}; outline: none; }}
QCheckBox {{ spacing: 6px; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border-radius: 4px; border: 1px solid {c['muted']}; background: {c['input']}; }}
QCheckBox::indicator:checked {{ background: {c['accent']}; border: 1px solid {c['accent']}; }}
QSlider::groove:horizontal {{ height: 4px; background: {c['border']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {c['accent']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {c['card']}; border: 2px solid {c['accent']}; width: 10px; height: 10px;
    margin: -5px 0; border-radius: 7px; }}

QTabWidget::pane {{ border: none; }}
#DocTabs QTabBar::tab {{ background: transparent; color: {c['muted']}; padding: 6px 12px; border: none;
    border-bottom: 2px solid transparent; }}
#DocTabs QTabBar::tab:selected {{ color: {c['text']}; border-bottom: 2px solid {c['accent']}; }}
QStatusBar {{ background: {c['sidebar']}; border-top: 1px solid {c['border']}; }}
QStatusBar QLabel {{ color: {c['muted']}; font-size: 11px; padding: 0 6px; }}
QMenu {{ background: {c['card']}; border: 1px solid {c['border']}; padding: 6px; border-radius: 10px; }}
QMenu::item {{ padding: 5px 22px 5px 10px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c['selected']}; color: {c['text']}; }}
QMenu::item:disabled {{ color: {c['faint']}; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 4px 6px; }}
QSplitter::handle {{ background: {c['border']}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 4px; min-height: 24px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {c['border']}; border-radius: 4px; min-width: 24px; margin: 2px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ padding: 4px 6px; border-radius: 5px; }}
QListWidget::item:selected {{ background: {c['selected']}; color: {c['text']}; }}
QDockWidget {{ color: {c['muted']}; font-size: 10px; font-weight: 600; }}
QDockWidget::title {{ background: {c['panel']}; padding: 6px 10px; border-bottom: 1px solid {c['border']};
    text-align: left; }}
QDockWidget > QWidget {{ background: {c['panel']}; }}
QMainWindow::separator {{ background: {c['border']}; width: 1px; height: 1px; }}
#LayerList::item {{ padding: 2px; border-radius: 6px; }}
#LayerList::item:selected {{ background: {c['selected']}; }}
#Inspector, #InspectorBody {{ background: {c['panel']}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget#InspectorBody, QScrollArea > QWidget > QWidget#Home {{ background: transparent; }}
QTabBar#DocTabs::tab {{ background: transparent; color: {c['muted']}; padding: 6px 12px; border: none;
    border-bottom: 2px solid transparent; }}
QTabBar#DocTabs::tab:selected {{ color: {c['text']}; border-bottom: 2px solid {c['accent']}; }}
QTabBar::close-button {{ subcontrol-position: right; }}
#Inspector QLabel#Section {{ padding-top: 4px; }}
#TopBar {{ background: {c['sidebar']}; border-bottom: 1px solid {c['border']}; }}
#TopBar QToolButton {{ padding: 5px; border-radius: 7px; }}
#TopBar QToolButton:checked {{ background: {c['accent']}; }}
#FloatBar {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px; }}
#FloatBar QToolButton {{ padding: 6px; border-radius: 9px; }}
#FloatBar QToolButton:checked {{ background: {c['selected']}; border: 1px solid {c['accent']}; }}
#LeftPanel, #RightPanel {{ background: {c['panel']}; }}
#LeftPanel {{ border-right: 1px solid {c['border']}; }}
#RightPanel {{ border-left: 1px solid {c['border']}; }}
#Notes {{ background: {c['card']}; border: none; border-top: 1px solid {c['border']}; padding: 8px; }}
#FileName {{ font-family: {SERIF}; font-size: 14px; }}
#Scrub {{ color: {c['muted']}; font-size: 11px; min-width: 12px; }}
#Field {{ background: {c['input']}; border: 1px solid transparent; border-radius: 6px; padding: 2px 4px; }}
#Field:hover {{ border: 1px solid {c['border']}; }}
#Field:focus {{ border: 1px solid {c['accent']}; }}
#Swatch {{ border: 1px solid {c['border']}; border-radius: 4px; }}
#Card {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px; }}
#Card:hover {{ border: 1px solid {c['accent']}; }}
#CardTitle {{ font-family: {SERIF}; font-size: 17px; }}
#Home {{ background: {c['bg']}; }}
#HomeSide {{ background: {c['sidebar']}; border-right: 1px solid {c['border']}; }}
#HomeSide QPushButton {{ text-align: left; border: none; background: transparent; padding: 7px 10px; }}
#HomeSide QPushButton:checked {{ background: {c['selected']}; }}
#AppTabs {{ background: {c['sidebar']}; }}
#AppTabs QTabBar::tab {{ background: transparent; color: {c['muted']}; padding: 7px 14px; border: none;
    border-right: 1px solid {c['border']}; }}
#AppTabs QTabBar::tab:selected {{ color: {c['text']}; background: {c['bg']}; }}
QTreeWidget {{ background: transparent; border: none; outline: none; }}
QTreeWidget::item {{ padding: 3px 2px; border-radius: 5px; }}
QTreeWidget::item:selected {{ background: {c['selected']}; color: {c['text']}; }}
QTreeWidget::item:hover {{ background: {c['hover']}; }}
QTreeView::indicator {{ width: 13px; height: 13px; border-radius: 4px; border: 1px solid {c['muted']};
    background: {c['input']}; }}
QTreeView::indicator:checked {{ background: {c['accent']}; border: 1px solid {c['accent']}; }}
QPlainTextEdit, QTextEdit {{ background: {c['input']}; border: 1px solid {c['border']}; border-radius: 6px; }}
"""
