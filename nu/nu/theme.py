"""Claude-like look (shared with Каппа and Epsilon): ivory / charcoal, terracotta accent, serif headings."""

LIGHT = dict(
    name="light",
    bg="#FAF9F5", sidebar="#F0EEE6", activity="#E9E6DC", card="#FFFFFF", border="#E3DFD3", text="#141413",
    muted="#6F6E69", faint="#A8A59C", accent="#D97757", accent_hover="#C6613F", accent_text="#FFFFFF",
    selected="#E6E2D6", hover="#E9E6DC", input="#FFFFFF", ok="#4E8A5A", warn="#B5642E", error="#C2453E",
    editor="#FFFFFF", gutter="#FFFFFF", line_no="#B4B0A5", line_no_active="#141413", current_line="#F7F5EF",
    selection="#F6DED3", find="#F7D9A8", find_current="#F0B25E", bracket="#E9E1CC", guide="#ECE9E0",
    guide_active="#CFC9BA", panel="#FAF9F5", terminal="#FFFFFF", terminal_text="#141413", tab_inactive="#F0EEE6",
    git_modified="#B5862E", git_added="#3E8E63", git_deleted="#C2453E", git_untracked="#3E8E63",
)

DARK = dict(
    name="dark",
    bg="#262624", sidebar="#1F1E1D", activity="#1A1918", card="#30302E", border="#3E3D39", text="#F4F2EC",
    muted="#A6A39A", faint="#6E6C66", accent="#D97757", accent_hover="#E08A6D", accent_text="#FFFFFF",
    selected="#3A3936", hover="#34332F", input="#262624", ok="#7BB487", warn="#E59866", error="#E5736B",
    editor="#262624", gutter="#262624", line_no="#5E5C57", line_no_active="#F4F2EC", current_line="#2C2B29",
    selection="#4A362D", find="#5C4A2A", find_current="#8A6A2E", bracket="#45433E", guide="#33322F",
    guide_active="#55534D", panel="#1F1E1D", terminal="#1F1E1D", terminal_text="#F4F2EC", tab_inactive="#1F1E1D",
    git_modified="#E2C27A", git_added="#7BB487", git_deleted="#E5736B", git_untracked="#7BB487",
)

# syntax colours (Pygments token families), warm and quiet like the rest of the UI
SYNTAX = {
    "light": dict(
        keyword=("#A0461F", False, False), keyword_type=("#9A6B12", False, False), string=("#3E7C4F", False, False),
        string_escape=("#B5532F", False, False), number=("#8A4FC2", False, False), comment=("#8A8780", False, True),
        function=("#2E5E9E", False, False), class_=("#9A6B12", True, False), builtin=("#2B7C8C", False, False),
        operator=("#6F6E69", False, False), punctuation=("#5A5954", False, False), decorator=("#8A4FC2", False, False),
        tag=("#A0461F", False, False), attribute=("#9A6B12", False, False), constant=("#8A4FC2", False, False),
        variable=("#2B7C8C", False, False), heading=("#A0461F", True, False), emph=("#141413", False, True),
        strong=("#141413", True, False), inserted=("#3E8E63", False, False), deleted=("#C2453E", False, False),
        namespace=("#9A6B12", False, False), regex=("#B5532F", False, False), error=("#C2453E", False, False),
    ),
    "dark": dict(
        keyword=("#E8916F", False, False), keyword_type=("#E2C27A", False, False), string=("#9CC28A", False, False),
        string_escape=("#E8A487", False, False), number=("#C3A6F0", False, False), comment=("#8A877F", False, True),
        function=("#8FB5E8", False, False), class_=("#E2C27A", True, False), builtin=("#7EC4C9", False, False),
        operator=("#B5B2A8", False, False), punctuation=("#C9C6BD", False, False), decorator=("#C3A6F0", False, False),
        tag=("#E8916F", False, False), attribute=("#E2C27A", False, False), constant=("#C3A6F0", False, False),
        variable=("#7EC4C9", False, False), heading=("#E8916F", True, False), emph=("#F4F2EC", False, True),
        strong=("#F4F2EC", True, False), inserted=("#7BB487", False, False), deleted=("#E5736B", False, False),
        namespace=("#E2C27A", False, False), regex=("#E8A487", False, False), error=("#E5736B", False, False),
    ),
}

# 16 ANSI colours for the terminal
ANSI = {
    "light": ["#141413", "#C2453E", "#3E8E63", "#9A6B12", "#2E5E9E", "#8A4FC2", "#2B7C8C", "#D7D3C8",
              "#6F6E69", "#D9574F", "#4FA275", "#B5862E", "#4A7BD0", "#A06AD6", "#3A97A8", "#FAF9F5"],
    "dark": ["#262624", "#E5736B", "#9CC28A", "#E2C27A", "#8FB5E8", "#C3A6F0", "#7EC4C9", "#D7D3C8",
             "#6E6C66", "#F08C84", "#B6D9A6", "#F0D594", "#ABC9F0", "#D6C0F5", "#9FD8DC", "#FFFFFF"],
}

SERIF = '"Georgia", "Tiempos Text", "Times New Roman", serif'
MONO_FAMILIES = ["SF Mono", "Menlo", "Monaco", "JetBrains Mono", "Fira Code", "DejaVu Sans Mono", "Courier New"]


def stylesheet(c, assets=""):
    a = assets.replace("\\", "/")
    return f"""
QTabBar::close-button {{ image: url({a}/close.svg); subcontrol-position: right; margin: 2px; }}
QTabBar::close-button:hover {{ image: url({a}/close-hover.svg); background: {c['hover']}; border-radius: 4px; }}
QTreeView::branch:has-children:closed {{ image: url({a}/chevron-right.svg); }}
QTreeView::branch:has-children:open {{ image: url({a}/chevron-down.svg); }}
QTreeView::branch:selected {{ background: transparent; }}
* {{ color: {c['text']}; font-size: 13px; }}
QMainWindow, #Main {{ background: {c['bg']}; }}
QDialog {{ background: {c['bg']}; }}
QToolTip {{ background: {c['card']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 4px; }}

#ActivityBar {{ background: {c['activity']}; border-right: 1px solid {c['border']}; }}
#ActivityBar QToolButton {{ background: transparent; border: none; border-left: 2px solid transparent; padding: 10px 0; }}
#ActivityBar QToolButton:hover {{ background: {c['hover']}; }}
#ActivityBar QToolButton:checked {{ border-left: 2px solid {c['accent']}; background: {c['sidebar']}; }}
#SideBar {{ background: {c['sidebar']}; border-right: 1px solid {c['border']}; }}
#SideTitle {{ color: {c['muted']}; font-size: 11px; font-weight: 600; letter-spacing: 1px; }}
#Logo {{ font-family: {SERIF}; font-size: 19px; }}
#Nu {{ color: {c['accent']}; font-family: {SERIF}; font-style: italic; font-size: 26px; }}
#Title {{ font-family: {SERIF}; font-size: 30px; }}
#BigLogo {{ color: {c['accent']}; font-family: {SERIF}; font-style: italic; font-size: 110px; }}
#CardTitle {{ font-family: {SERIF}; font-size: 18px; }}
#Muted {{ color: {c['muted']}; }}
#Section {{ color: {c['muted']}; font-size: 11px; font-weight: 600; letter-spacing: 1px; }}
#Breadcrumbs {{ color: {c['muted']}; font-size: 12px; padding: 4px 14px; background: {c['editor']};
    border-bottom: 1px solid {c['border']}; }}

QTreeView, QListWidget, QTreeWidget {{ background: transparent; border: none; outline: none; }}
QTreeView::item, QTreeWidget::item {{ padding: 3px 2px; border-radius: 5px; }}
QTreeView::item:hover, QTreeWidget::item:hover, QListWidget::item:hover {{ background: {c['hover']}; }}
QTreeView::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {c['selected']}; color: {c['text']}; }}
QTreeView::branch {{ background: transparent; }}
QListWidget::item {{ padding: 5px 8px; border-radius: 6px; }}
QHeaderView::section {{ background: {c['bg']}; color: {c['muted']}; border: none; padding: 4px; }}

QPushButton {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 6px 14px; }}
QPushButton:hover {{ background: {c['hover']}; }}
QPushButton:disabled {{ color: {c['muted']}; }}
QPushButton#Accent {{ background: {c['accent']}; color: {c['accent_text']}; border: none; font-weight: 600; }}
QPushButton#Accent:hover {{ background: {c['accent_hover']}; }}
QPushButton#Link {{ background: transparent; border: none; color: {c['accent']}; padding: 3px 4px; text-align: left; }}
QPushButton#Link:hover {{ color: {c['accent_hover']}; }}
QToolButton {{ background: transparent; border: none; border-radius: 6px; padding: 3px 5px; color: {c['muted']}; }}
QToolButton:hover {{ background: {c['hover']}; color: {c['text']}; }}
QToolButton:checked {{ background: {c['selected']}; color: {c['text']}; }}

QLineEdit, QComboBox, QSpinBox, QPlainTextEdit#Input {{
    background: {c['input']}; border: 1px solid {c['border']}; border-radius: 7px; padding: 5px 8px;
    selection-background-color: {c['selection']}; selection-color: {c['text']}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit#Input:focus {{ border: 1px solid {c['accent']}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{ background: {c['card']}; border: 1px solid {c['border']};
    selection-background-color: {c['selected']}; selection-color: {c['text']}; outline: none; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 15px; height: 15px; border-radius: 4px; border: 1px solid {c['muted']}; background: {c['input']}; }}
QCheckBox::indicator:checked {{ background: {c['accent']}; border: 1px solid {c['accent']}; }}

#CodeEditor {{ background: {c['editor']}; border: none; selection-background-color: {c['selection']};
    selection-color: {c['text']}; }}
#EditorTabs QTabBar {{ background: {c['tab_inactive']}; }}
#EditorTabs QTabBar::tab {{ background: {c['tab_inactive']}; color: {c['muted']}; padding: 7px 10px 7px 14px;
    border: none; border-right: 1px solid {c['border']}; border-top: 2px solid transparent; }}
#EditorTabs QTabBar::tab:selected {{ background: {c['editor']}; color: {c['text']}; border-top: 2px solid {c['accent']}; }}
#EditorTabs QTabBar::tab:hover {{ color: {c['text']}; }}
#EditorTabs::pane {{ border: none; }}
#EditorTabs[active="false"] QTabBar::tab:selected {{ border-top: 2px solid {c['faint']}; }}

#Panel {{ background: {c['panel']}; border-top: 1px solid {c['border']}; }}
#PanelTabs QTabBar::tab {{ background: transparent; color: {c['muted']}; padding: 6px 12px; border: none;
    border-bottom: 2px solid transparent; font-size: 11px; font-weight: 600; letter-spacing: 1px; }}
#PanelTabs QTabBar::tab:selected {{ color: {c['text']}; border-bottom: 2px solid {c['accent']}; }}
#PanelTabs::pane {{ border: none; }}
#Terminal {{ background: {c['terminal']}; }}

#FindBar {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 9px; }}
#FindBar QLineEdit {{ padding: 4px 6px; }}
#FindCount {{ color: {c['muted']}; font-size: 12px; min-width: 70px; }}

#Palette {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; }}
#Palette QLineEdit {{ border: none; border-bottom: 1px solid {c['border']}; border-radius: 0; padding: 10px 12px;
    font-size: 14px; background: transparent; }}
#Palette QListWidget::item {{ padding: 6px 10px; }}

QStatusBar {{ background: {c['activity']}; border-top: 1px solid {c['border']}; }}
QStatusBar QLabel, QStatusBar QPushButton {{ color: {c['muted']}; font-size: 12px; }}
QStatusBar QPushButton {{ background: transparent; border: none; padding: 1px 8px; border-radius: 4px; }}
QStatusBar QPushButton:hover {{ background: {c['hover']}; color: {c['text']}; }}
#Branch {{ color: {c['text']}; }}

QMenu {{ background: {c['card']}; border: 1px solid {c['border']}; padding: 6px; border-radius: 10px; }}
QMenu::item {{ padding: 5px 22px 5px 10px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c['selected']}; color: {c['text']}; }}
QMenu::item:disabled {{ color: {c['faint']}; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 4px 6px; }}
QSplitter::handle {{ background: {c['border']}; }}
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {c['guide_active']}; border-radius: 4px; min-height: 30px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {c['guide_active']}; border-radius: 4px; min-width: 30px; margin: 2px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
"""
