"""
ZUGZWANG - Global Stylesheet
Raven design system:
light neutral canvases, restrained dark navigation, and one consistent tab language.
"""

from .icons import stylesheet_icon_url


_CHEVRON_DOWN = stylesheet_icon_url("chevron-down.svg")
_CHEVRON_UP = stylesheet_icon_url("chevron-up.svg")
_RAVEN_99 = "#FBFCFD"
_RAVEN_95 = "#F8F9FC"
_RAVEN_90 = "#F2F4F8"
_RAVEN_80 = "#E3E7ED"
_RAVEN_70 = "#CED3DE"
_RAVEN_60 = "#969FB0"
_RAVEN_50 = "#6C7689"
_RAVEN_40 = "#4D576A"
_RAVEN_30 = "#30394B"
_RAVEN_20 = "#212A3B"
_RAVEN_10 = "#141B2A"
_RAVEN_5 = "#0B111D"


APP_STYLESHEET = """
* {
    font-family: "PT Root UI", "Arial", sans-serif;
    color: #F3EFF4;
    outline: none;
}

QLabel,
BodyLabel,
CaptionLabel,
StrongBodyLabel,
SubtitleLabel,
TitleLabel {
    background: transparent;
    border: none;
}

QApplication,
QMainWindow {
    background: #0E0D0F;
}

QWidget {
    background: transparent;
}

#WindowCanvas {
    background: #0E0D0F;
}

#AppShell {
    background: #121113;
    border: 1px solid #211F24;
    border-radius: 22px;
}

#ContentArea {
    background: #121113;
    border-bottom-left-radius: 18px;
    border-bottom-right-radius: 18px;
}

#Sidebar {
    background: #151316;
    border: 1px solid #242126;
    min-width: 88px;
    max-width: 88px;
    border-radius: 18px;
}

#SidebarLogoMark {
    min-width: 34px;
    max-width: 34px;
    min-height: 34px;
    max-height: 34px;
    padding: 6px;
    background: #635BFF;
    border-radius: 10px;
}

#SidebarLogo {
    font-size: 15px;
    font-weight: 700;
    color: #F6F3F7;
    padding: 2px 4px 2px 4px;
    letter-spacing: -0.2px;
}

#SidebarTagline {
    font-size: 9px;
    font-weight: 600;
    color: #B1A8B8;
    padding: 0 4px 0 4px;
    letter-spacing: 1.2px;
}

#SidebarVersion {
    font-size: 10px;
    color: #7D7784;
    padding: 4px 4px 18px 46px;
    letter-spacing: 0.2px;
}

#SidebarGroupLabel {
    font-size: 10px;
    font-weight: 700;
    color: #7E7786;
    text-transform: uppercase;
    letter-spacing: 1.4px;
    padding-left: 4px;
}

#SectionDivider {
    background-color: #262227;
    max-height: 1px;
    min-height: 1px;
    margin: 0 8px;
}

QPushButton#NavBtn {
    background: transparent;
    border: none;
    text-align: left;
    padding: 9px 13px;
    font-size: 12px;
    font-weight: 500;
    color: #B7B0B9;
    border-radius: 8px;
    margin: 2px 0;
}

QPushButton#NavBtn:hover {
    background: #1E1B1F;
    color: #F6F2F7;
}

QPushButton#NavBtn[active="true"] {
    background: #1F1C20;
    color: #FAF7FB;
}

QPushButton#NavBtn:focus {
    background: #221F24;
    border: 1px solid #6B64FF;
    color: #FAF7FB;
}

QPushButton#SidebarPrimaryBtn {
    background: #635BFF;
    color: #F7F5FF;
    border: none;
    border-radius: 8px;
    min-width: 56px;
    max-width: 56px;
    min-height: 56px;
    max-height: 56px;
    padding: 0;
    text-align: center;
    font-size: 0px;
    font-weight: 700;
}

QPushButton#SidebarPrimaryBtn:hover {
    background: #716AFF;
}

QPushButton#SidebarPrimaryBtn:pressed {
    background: #564EEA;
}

QPushButton#SidebarUtilityBtn {
    background: transparent;
    color: #AEA7B1;
    border: none;
    border-radius: 8px;
    min-width: 56px;
    max-width: 56px;
    min-height: 44px;
    max-height: 44px;
    padding: 0;
    text-align: center;
    font-size: 0px;
    font-weight: 600;
}

QPushButton#SidebarUtilityBtn:hover {
    background: #1B181C;
    color: #F3EFF4;
}

#WorkspacePanel {
    background: #151316;
    border: 1px solid #242126;
    min-width: 318px;
    max-width: 318px;
    border-radius: 18px;
}

#PanelTitle {
    font-size: 13px;
    font-weight: 700;
    color: #F6F3F7;
}

#PanelMeta {
    font-size: 11px;
    color: #9A919E;
}

QLineEdit#PanelSearch {
    background: #1A171B;
    border: 1px solid #2A2630;
    border-radius: 12px;
    padding: 9px 12px;
    min-height: 18px;
}

#PanelSectionLabel {
    font-size: 10px;
    font-weight: 700;
    color: #748090;
    text-transform: uppercase;
    letter-spacing: 1.4px;
    padding: 4px 2px 2px 2px;
}

#PanelEmpty {
    font-size: 12px;
    color: #97A2AF;
    padding: 8px 4px 0 4px;
}

QFrame#WorkspaceItem {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 14px;
}

QFrame#WorkspaceItem:hover {
    background: #1A2027;
    border-color: #28313D;
}

QFrame#WorkspaceItem[active="true"] {
    background: #212932;
    border-color: #34404E;
}

QLabel#WorkspaceItemTitle {
    font-size: 13px;
    font-weight: 700;
    color: #F2F6FA;
}

QLabel#WorkspaceItemMeta {
    font-size: 11px;
    color: #9AA5B4;
}

QLabel#WorkspaceItemPreview {
    font-size: 12px;
    color: #A0AAB6;
}

QLabel#WorkspaceItemBadge {
    background: #1E2732;
    border: 1px solid #2F3B49;
    border-radius: 999px;
    padding: 3px 8px;
    font-size: 9px;
    font-weight: 700;
    color: #A8B8C8;
}

#ContentShell {
    background: #151316;
    border: 1px solid #242126;
    border-radius: 18px;
}

#ContentTopBar {
    background: #151316;
    border-bottom: 1px solid #242126;
    border-top-left-radius: 18px;
    border-top-right-radius: 18px;
}

#ContentEyebrow {
    font-size: 10px;
    font-weight: 700;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 1.6px;
}

#ContentTitle {
    font-size: 18px;
    font-weight: 800;
    color: #F8FAFC;
}

QPushButton#TopNavBtn {
    background: transparent;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 14px;
    min-height: 20px;
    color: #94A3B8;
    font-size: 11px;
    font-weight: 700;
    text-align: center;
}

QPushButton#TopNavBtn:hover {
    background: #1E293B;
    border-color: #475569;
    color: #F8FAFC;
}

QPushButton#TopNavBtn[active="true"] {
    background: rgba(59, 130, 246, 0.10);
    border: 1px solid #3B82F6;
    color: #F8FAFC;
}

QLineEdit#ShellSearchInput {
    background: #050506;
    border: none;
    border-radius: 16px;
    padding: 10px 16px;
    min-height: 20px;
    color: #F2EEF4;
    selection-background-color: #635BFF;
}

QLineEdit#ShellSearchInput::placeholder {
    color: #7E7781;
}

QPushButton#TopBarIconBtn {
    background: #1A171B;
    border: 1px solid #2A2630;
    border-radius: 8px;
    color: #F3EFF4;
    padding: 0;
}

QPushButton#TopBarIconBtn:hover {
    background: #211D23;
    border-color: #312B36;
}

QPushButton#TopBarAvatarBtn {
    background: #FFD6B0;
    border: 2px solid #3A343C;
    border-radius: 21px;
    color: #23191A;
    font-size: 14px;
    font-weight: 800;
}

QPushButton:focus,
QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QTextBrowser:focus,
QTableView:focus {
    border-color: #6B64FF;
}

QPushButton#ToolbarPill {
    background: #1F1B20;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-size: 12px;
    font-weight: 700;
    color: #F6F3F7;
}

QPushButton#ToolbarPill:hover,
QPushButton#ToolbarIconBtn:hover {
    background: #2A252B;
}

QPushButton#ToolbarIconBtn {
    background: #1F1B20;
    border: 1px solid #2A2630;
    border-radius: 8px;
    padding: 0;
    font-size: 16px;
    font-weight: 700;
    color: #F4F0F5;
}

QMenu {
    background: #181518;
    border: 1px solid #2B262D;
    border-radius: 14px;
    padding: 8px;
}

QMenu::item {
    padding: 8px 14px;
    border-radius: 9px;
    color: #F3EFF4;
}

QMenu::item:selected {
    background: #262128;
}

#PageHeader {
    font-size: 28px;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: -0.8px;
}

#PageSubtitle {
    font-size: 12px;
    font-weight: 500;
    color: #8E8E93;
    letter-spacing: -0.2px;
}

#Card {
    background: #1B181C;
    border: 1px solid #262227;
    border-radius: 18px;
}

#CardTitle {
    font-size: 11px;
    font-weight: 700;
    color: #B4ACB6;
    text-transform: uppercase;
    letter-spacing: 2px;
}

#CardValue {
    font-size: 28px;
    font-weight: 700;
    color: #F8F5F9;
}

#CardSub {
    font-size: 12px;
    color: #A69EA9;
}

QLabel#FieldLabel {
    font-size: 12px;
    font-weight: 600;
    color: #B0A8B2;
    margin-bottom: 4px;
}

QGroupBox#FormSection {
    font-size: 14px;
    font-weight: 700;
    color: #F5F1F6;
    border: 1px solid #262227;
    border-radius: 22px;
    margin-top: 0;
    padding: 34px 18px 18px 18px;
    background: #1A171B;
}

QGroupBox#FormSection::title {
    subcontrol-origin: padding;
    subcontrol-position: top left;
    left: 16px;
    top: 10px;
    padding: 0 10px;
    background: #171C22;
    color: #F2F6FA;
    border: none;
    border-radius: 10px;
}

QLabel#FormHint {
    font-size: 12px;
    color: #94A0AE;
    font-style: italic;
}

QLabel#InlineHint {
    font-size: 12px;
    color: #9CA6B4;
    font-weight: 600;
}

QLabel#FormError {
    font-size: 11px;
    color: #E38484;
    font-weight: 600;
}

QLineEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox {
    background: #12171D;
    border: 1px solid #242B34;
    border-radius: 16px;
    padding: 11px 14px;
    font-size: 13px;
    color: #F1F5F9;
    selection-background-color: #6B64FF;
    selection-color: #0F1115;
    min-height: 22px;
    combobox-popup: 0;
}

QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {
    border: 1px solid #384556;
    background: #141A21;
}

QLineEdit:disabled,
QComboBox:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled {
    background: #171C22;
    border-color: #242B34;
    color: #6F7884;
}

QLineEdit[readOnly="true"] {
    background: #171D24;
}

QComboBox {
    padding-right: 38px;
}

QComboBox::drop-down {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 28px;
    border: none;
    background: transparent;
    padding-right: 8px;
}

QComboBox::down-arrow {
    image: url("__CHEVRON_DOWN__");
    width: 12px;
    height: 12px;
}

QComboBox QAbstractItemView {
    background: #171C22;
    border: 1px solid #2D3540;
    selection-background-color: #242D39;
    selection-color: #F7FAFC;
    border-radius: 14px;
    padding: 6px;
    outline: 0;
}

QComboBox QAbstractItemView::item {
    min-height: 30px;
    padding: 6px 10px;
    border-radius: 9px;
}

QComboBox QAbstractItemView::item:selected {
    background: #242D39;
    color: #F8FAFC;
}

QSpinBox,
QDoubleSpinBox {
    padding-left: 14px;
    padding-right: 28px;
    qproperty-buttonSymbols: UpDownArrows;
}

QSpinBox::up-button,
QDoubleSpinBox::up-button,
QSpinBox::down-button,
QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    width: 18px;
    border-left: 1px solid #2D3540;
    background: #181E26;
    margin: 2px 3px 2px 0;
    padding: 0;
}

QSpinBox::up-button,
QDoubleSpinBox::up-button {
    subcontrol-position: top right;
    height: 12px;
    border-top-right-radius: 10px;
    border-bottom: 1px solid #2D3540;
}

QSpinBox::down-button,
QDoubleSpinBox::down-button {
    subcontrol-position: bottom right;
    height: 12px;
    border-bottom-right-radius: 10px;
}

QSpinBox::up-button:hover,
QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover,
QDoubleSpinBox::down-button:hover {
    background: #202833;
}

QSpinBox::up-button:pressed,
QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed,
QDoubleSpinBox::down-button:pressed {
    background: #273140;
}

QSpinBox::up-arrow,
QDoubleSpinBox::up-arrow,
QSpinBox::down-arrow,
QDoubleSpinBox::down-arrow {
    image: url("__CHEVRON_DOWN__");
    width: 9px;
    height: 9px;
}

QSpinBox::up-arrow,
QDoubleSpinBox::up-arrow {
    image: url("__CHEVRON_UP__");
}

QPushButton {
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    padding: 10px 18px;
    border: none;
}

QPushButton#PrimaryBtn {
    background: #635BFF;
    color: #F7F5FF;
}

QPushButton#PrimaryBtn:hover {
    background: #726AFF;
}

QPushButton#PrimaryBtn:pressed {
    background: #564EEA;
}

QPushButton#PrimaryBtn:disabled {
    background: #2D2833;
    color: #7E7682;
}

QPushButton#SecondaryBtn {
    background: #272328;
    color: #F3EEF4;
    border: none;
}

QPushButton#SecondaryBtn:hover,
QPushButton#GhostBtn:hover,
QPushButton#SuccessBtn:hover,
QPushButton#DangerBtn:hover {
    background: #28313A;
}

QPushButton#GhostBtn,
QPushButton#SuccessBtn,
QPushButton#DangerBtn {
    background: #1E1A1F;
    color: #F0EBF2;
    border: none;
}

QPushButton#SecondaryBtn:pressed,
QPushButton#GhostBtn:pressed,
QPushButton#SuccessBtn:pressed,
QPushButton#DangerBtn:pressed,
QPushButton#ToolbarPill:pressed,
QPushButton#ToolbarIconBtn:pressed {
    background: #332D35;
}

QCheckBox {
    font-size: 13px;
    color: #E4E9EF;
    spacing: 9px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 2px solid #465160;
    border-radius: 5px;
    background: #12171D;
}

QCheckBox::indicator:checked {
    background: #6B64FF;
    border-color: #6B64FF;
}

QProgressBar {
    background: rgba(255, 255, 255, 0.05);
    border: none;
    border-radius: 999px;
    height: 4px;
    text-align: center;
    color: transparent;
}

QProgressBar::chunk {
    background: #0A84FF;
    border-radius: 999px;
}

QTableWidget,
QTableView {
    background: #171417;
    border: 1px solid #252126;
    border-radius: 22px;
    gridline-color: #221F24;
    selection-background-color: #221F26;
    selection-color: #FBF7FD;
    alternate-background-color: #141115;
    font-size: 12px;
}

QTableWidget::item,
QTableView::item {
    padding: 10px 12px;
    border: none;
}

QTableWidget::item:selected,
QTableView::item:selected {
    background-color: #222A34;
    color: #F7FAFD;
}

QHeaderView::section {
    background: #161B21;
    color: #AAB4C0;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.3px;
    padding: 14px 12px;
    border: none;
    border-bottom: 1px solid #2A313B;
    border-right: 1px solid #242B34;
}

QHeaderView::section:hover {
    background: #1A2129;
    color: #F1F4F8;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 6px 0;
}

QScrollBar::handle:vertical {
    background: #3A4552;
    border-radius: 5px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background: #4A5666;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    height: 0;
    width: 0;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal,
QAbstractScrollArea::corner {
    background: transparent;
    border: none;
}

QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 0 6px;
}

QScrollBar::handle:horizontal {
    background: #3A4552;
    border-radius: 5px;
    min-width: 28px;
}

QScrollBar::handle:horizontal:hover {
    background: #4A5666;
}

QTabWidget::pane {
    border: 1px solid #222A33;
    border-radius: 20px;
    background: #171C22;
}

QTabBar::tab {
    background: transparent;
    color: #8F99A8;
    padding: 11px 18px;
    font-size: 12px;
    font-weight: 700;
    border-radius: 14px;
    margin-right: 4px;
}

QTabBar::tab:selected {
    background: #222A34;
    color: #FFFDF9;
}

QTextEdit,
QPlainTextEdit,
QTextBrowser {
    background: #171C22;
    border: 1px solid #222A33;
    border-radius: 20px;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 11px;
    color: #F1F4F8;
    padding: 12px;
}

QStatusBar {
    background: #12161B;
    border-top: 1px solid #252C35;
    color: #8F99A8;
    font-size: 11px;
    padding: 3px 14px;
}

QToolTip {
    background: #171D24;
    color: #F3F4F6;
    border: 1px solid #2A333E;
    border-radius: 10px;
    padding: 7px 10px;
    font-size: 12px;
}

QSplitter::handle {
    background: transparent;
    width: 12px;
    height: 12px;
}

QDialog,
QMessageBox {
    background: #171C22;
    border: 1px solid #2A313B;
    border-radius: 24px;
}

QLabel#BadgeSuccess,
QLabel#BadgeWarning,
QLabel#BadgeError,
QLabel#BadgeInfo {
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.5px;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

/* --- APPLE AESTHETIC 3.0 (Senior Grade) --- */

QFrame#StepBadge {
    background: #0A84FF;
    border-radius: 14px;
    border: none;
}

QLabel#StepBadgeLabel {
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 800;
}

.SectionLabel {
    color: #8E8E93;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    margin-bottom: 2px;
}

QLabel#BadgeInfo {
    background: rgba(10, 132, 255, 0.12);
    color: #40A4FF;
    border: 1px solid rgba(10, 132, 255, 0.18);
    padding: 3px 14px;
    border-radius: 11px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.3px;
}

QLabel#BadgeSuccess {
    background: rgba(48, 209, 88, 0.12);
    color: #32D74B;
    border: 1px solid rgba(48, 209, 88, 0.18);
    padding: 3px 14px;
    border-radius: 11px;
    font-size: 10px;
    font-weight: 700;
}

QLabel#BadgeWarning {
    background: rgba(255, 159, 10, 0.12);
    color: #FF9F0A;
    border: 1px solid rgba(255, 159, 10, 0.18);
    padding: 3px 14px;
    border-radius: 11px;
    font-size: 10px;
    font-weight: 700;
}

/* Advanced macOS Sonoma Triple-Border Glassmorphism */
ElevatedCardWidget,
SimpleCardWidget,
QFrame#GlassCard {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.06); 
    border-top: 1px solid rgba(255, 255, 255, 0.16); /* Intense top highlight */
    border-bottom: 1px solid rgba(0, 0, 0, 0.2);     /* Precise bottom shadow */
    border-radius: 20px;
}

#PageHeader {
    color: #FFFFFF;
    font-size: 38px;
    font-weight: 800;
    letter-spacing: -1.8px;
    background: transparent;
    padding: 10px 0;
}

#SubHeader {
    color: #8E8E93;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
}

/* Control Center Pill Buttons */
QPushButton#PrimaryAction, 
PrimaryPushButton,
QPushButton#btn_send_all {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #40A4FF, stop:1 #0A84FF);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 20px; /* Full pill */
    color: #FFFFFF;
    font-weight: 700;
    font-size: 13px;
    padding: 10px 24px;
}

QPushButton#PrimaryAction:hover,
PrimaryPushButton:hover,
QPushButton#btn_send_all:hover {
    background: #40A4FF;
}

QPushButton#SecondaryAction, 
PushButton,
QPushButton#btn_dedup,
QPushButton#btn_attach {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    color: #FFFFFF;
    font-weight: 600;
    font-size: 13px;
    min-height: 32px;
}

QPushButton#SecondaryAction:hover {
    background: rgba(255, 255, 255, 0.12);
}

QPushButton#IconAction {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    color: #FFFFFF;
    font-weight: 600;
    font-size: 13px;
    min-height: 32px;
    padding: 0 16px 0 38px;
}

QPushButton#IconAction:hover {
    background: rgba(255, 255, 255, 0.12);
}

/* Field Row Style (macOS System Settings) */
QFrame#FieldRow {
    background: transparent;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    padding: 8px 0;
}

QLineEdit#StandardInput {
    background: rgba(255, 255, 255, 0.04);
    border-radius: 8px;
    padding: 10px 14px;
    color: #FFFFFF;
    font-size: 13px;
    border: 1px solid rgba(255, 255, 255, 0.08);
}

QLineEdit#StandardInput:focus {
    border: 1px solid #0A84FF;
    background: rgba(255, 255, 255, 0.08);
}

.SectionLabel {
    color: #8E8E93;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}

QTextEdit#RichLog {
    background: rgba(0, 0, 0, 0.25);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 16px;
    padding: 16px;
    color: #F2F2F7;
    font-family: 'SF Mono', 'Input', monospace;
    font-size: 12px;
    line-height: 1.5;
}

QProgressBar {
    background: rgba(255, 255, 255, 0.06);
    border: none;
    border-radius: 3px;
    max-height: 4px;
}

QProgressBar::chunk {
    background: #0A84FF;
    border-radius: 3px;
}

/* Composition Editor */
QPlainTextEdit {
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    padding: 12px;
    color: #F2F2F7;
    font-size: 13px;
    selection-background-color: rgba(10, 132, 255, 0.3);
}

QPlainTextEdit:focus {
    border: 1px solid rgba(10, 132, 255, 0.4);
    background: rgba(0, 0, 0, 0.25);
}

/* macOS Style Scrollbars */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.15);
    min-height: 30px;
    border-radius: 3px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 0.25);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    background: none;
}

QScrollBar:horizontal {
    background: transparent;
    height: 6px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: rgba(255, 255, 255, 0.15);
    min-width: 30px;
    border-radius: 3px;
    margin: 2px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
    background: none;
}

QFrame#MonitorHero,
QFrame#MonitorSection,
QFrame#MonitorActivity,
QFrame#MonitorStatCard {
    background: #171C22;
    border: 1px solid #222A33;
    border-radius: 24px;
}

#MonitorHeroTitle {
    font-size: 22px;
    font-weight: 700;
    color: #F7FAFC;
}

#MonitorSectionLabel,
#MonitorControlsLabel {
    font-size: 16px;
    font-weight: 700;
    color: #EDF2F7;
    text-transform: lowercase;
}

#MonitorMeta,
#MonitorEta {
    font-size: 12px;
    color: #97A1AE;
}

#MonitorProgressText {
    font-size: 15px;
    font-weight: 600;
    color: #ECF1F6;
}

#MonitorPercent {
    font-size: 18px;
    font-weight: 800;
    color: #6B64FF;
    min-width: 56px;
}

QProgressBar#MonitorProgressBar {
    background: #10151A;
    border: 1px solid #1F2730;
    border-radius: 999px;
    height: 12px;
}

QProgressBar#MonitorProgressBar::chunk {
    background: #6B64FF;
    border-radius: 999px;
}

QTextBrowser#MonitorLog {
    background: #151A20;
    border: 1px solid #2A313B;
    border-radius: 22px;
    padding: 14px;
    color: #EEF3F8;
    selection-background-color: rgba(107, 100, 255, 0.22);
}

QCheckBox#MonitorAutoScroll {
    color: #A0AAB8;
}

QFrame#ResultsWorkspaceShell,
QFrame#ResultsFiltersCard,
QFrame#ResultsProgressCard,
QFrame#ResultsTableShell,
QWidget#ResultsDetailPanel,
QFrame#ResultsFieldCard {
    background: #171C22;
    border: 1px solid #222A33;
    border-radius: 22px;
}

QFrame#ResultsWorkspaceShell {
    border-radius: 26px;
}

QFrame#ResultsFiltersCard {
    min-height: 58px;
    max-height: 58px;
}

QFrame#SectionCard,
QWidget#SectionCard {
    background: #171C22;
    border: 1px solid #2A313B;
    border-radius: 24px;
}

QLabel#SectionCardTitle {
    font-size: 16px;
    font-weight: 700;
    color: #F3F6FA;
}

QLabel#SectionCardSubtitle {
    font-size: 12px;
    color: #97A1AE;
}

QFrame#EmptyState {
    background: #151A20;
    border: 1px dashed #2C3642;
    border-radius: 22px;
}

QLabel#EmptyStateIcon {
    font-size: 36px;
    color: #7B8795;
}

QLabel#EmptyStateTitle {
    font-size: 17px;
    font-weight: 700;
    color: #EFF4F9;
}

QLabel#EmptyStateBody {
    font-size: 13px;
    color: #97A1AE;
}

QLabel#DashboardEmptyLabel {
    font-size: 18px;
    font-weight: 700;
    color: #DCE4EC;
    padding: 10px 0;
}

QFrame#DashboardBrowserBanner {
    background: #1E293B;
    border: 1px solid #334155;
    border-radius: 18px;
}

QLabel#DashboardBannerIcon {
    background: rgba(59, 130, 246, 0.16);
    color: #60A5FA;
    border-radius: 15px;
    font-size: 15px;
    font-weight: 800;
}

QLabel#DashboardHeroTitle {
    font-size: 34px;
    font-weight: 800;
    color: #F8FAFC;
    letter-spacing: -1px;
}

QLabel#DashboardHeroSubtitle {
    font-size: 14px;
    color: #94A3B8;
}

QPushButton#DashboardPrimaryBtn,
QPushButton#DashboardGhostBtn,
QPushButton#DashboardTextBtn {
    border-radius: 16px;
    padding: 11px 20px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton#DashboardPrimaryBtn {
    background: #3B82F6;
    color: #F8FAFC;
}

QPushButton#DashboardPrimaryBtn:hover {
    background: #60A5FA;
}

QPushButton#DashboardGhostBtn {
    background: transparent;
    color: #F8FAFC;
    border: 1px solid #334155;
}

QPushButton#DashboardGhostBtn:hover,
QPushButton#DashboardTextBtn:hover {
    background: #1E293B;
}

QPushButton#DashboardTextBtn {
    background: transparent;
    color: #BDB8FF;
    padding: 4px 10px;
}

QFrame#DashboardMetricCard,
QFrame#DashboardTableCard,
QFrame#DashboardSideCard,
QFrame#DashboardHealthStatCard {
    background: #1E293B;
    border: 1px solid #334155;
    border-radius: 22px;
}

QLabel#DashboardMetricIconShell {
    border-radius: 14px;
    border: none;
}

QLabel#DashboardMetricBadge {
    border-radius: 10px;
    padding: 5px 10px;
    font-size: 11px;
    font-weight: 700;
}

QLabel#DashboardMetricLabel {
    font-size: 11px;
    font-weight: 700;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 2px;
}

QLabel#DashboardMetricValue {
    font-size: 28px;
    font-weight: 800;
    color: #F8FAFC;
    letter-spacing: -0.8px;
}

QLabel#DashboardSectionTitle {
    font-size: 18px;
    font-weight: 800;
    color: #F3F7FB;
}

QLabel#DashboardTableHeader {
    font-size: 10px;
    font-weight: 700;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 2px;
    padding-bottom: 2px;
}

QFrame#DashboardJobRow {
    background: transparent;
    border: none;
}

QLabel#DashboardSourceIcon {
    background: #0E0F12;
    border-radius: 12px;
}

QLabel#DashboardJobTitle {
    font-size: 14px;
    font-weight: 700;
    color: #F5F8FB;
}

QLabel#DashboardJobMeta,
QLabel#DashboardJobDate {
    font-size: 11px;
    color: #9AA4B0;
}

QLabel#DashboardJobLeads {
    font-size: 14px;
    font-weight: 700;
    color: #F1F5FA;
}

QLabel#DashboardRecentEmpty {
    font-size: 16px;
    font-weight: 700;
    color: #94A3B8;
    padding: 4px 0 0 0;
}

QLabel#DashboardRecentEmptyIcon {
    color: #94A3B8;
    padding-top: 8px;
}

QLabel#DashboardSideTitle {
    font-size: 12px;
    font-weight: 800;
    color: #A6AFBA;
    text-transform: uppercase;
    letter-spacing: 2px;
}

QLabel#DashboardHealthDot {
    background: #10B981;
    border-radius: 999px;
}

QLabel#DashboardHealthLabel,
QLabel#DashboardHealthValue {
    font-size: 12px;
    color: #F8FAFC;
}

QLabel#DashboardHealthValue {
    font-weight: 700;
}

QProgressBar#DashboardHealthBar,
QProgressBar#DashboardStorageBar {
    background: #0F172A;
    border: none;
    border-radius: 999px;
    min-height: 8px;
    max-height: 8px;
}

QProgressBar#DashboardStorageBar::chunk {
    background: #716BFF;
    border-radius: 999px;
}

QFrame#DashboardHealthStatCard {
    background: #0F172A;
}

QLabel#DashboardHealthStatLabel {
    font-size: 10px;
    font-weight: 700;
    color: #949EAA;
    text-transform: uppercase;
    letter-spacing: 1.2px;
}

QLabel#DashboardHealthStatValue {
    font-size: 18px;
    font-weight: 800;
    color: #F4F8FC;
}

QLabel#DashboardStorageValue {
    font-size: 26px;
    font-weight: 800;
    color: #F6F9FC;
}

QLabel#DashboardStorageTitle {
    font-size: 14px;
    font-weight: 700;
    color: #F2F5FA;
}

QLabel#DashboardStorageMeta {
    font-size: 12px;
    color: #97A1AE;
}

QLabel#SearchViewTitle {
    font-size: 26px;
    font-weight: 800;
    color: #F4F7FB;
    letter-spacing: -0.5px;
}

QLabel#SearchStepLabel {
    font-size: 10px;
    font-weight: 700;
    color: #8D98A5;
    text-transform: uppercase;
    letter-spacing: 1.8px;
}

QLabel#SearchSectionTitle {
    font-size: 18px;
    font-weight: 800;
    color: #F3F7FB;
}

QFrame#SearchSourceCard,
QFrame#SearchAdvancedCard,
QFrame#SearchToggleTile {
    background: #1D1A1C;
    border: 1px solid #262C35;
    border-radius: 22px;
}

QFrame#SearchSourceCard[active="true"] {
    background: #292627;
    border: 1px solid #6059C8;
}

QFrame#SearchSourceCard:hover,
QFrame#SearchSourceCard:focus {
    border: 1px solid #495467;
}

QFrame#SearchSourceCard[active="true"]:focus {
    border: 1px solid #8C86FF;
}

QLabel#SearchSourceIconBox {
    background: #090A0D;
    border-radius: 14px;
}

QLabel#SearchSourceIndicator {
    background: #111318;
    border: 2px solid #474C56;
    border-radius: 11px;
}

QFrame#SearchSourceCard[active="true"] QLabel#SearchSourceIndicator {
    background: #6059F1;
    border-color: #6059F1;
}

QLabel#SearchSourceTitle {
    font-size: 18px;
    font-weight: 800;
    color: #F4F7FB;
}

QLabel#SearchSourceBody {
    font-size: 13px;
    color: #B0BAC6;
}

QLabel#SearchModePill {
    background: rgba(96, 89, 241, 0.10);
    border: 1px solid rgba(96, 89, 241, 0.24);
    border-radius: 10px;
    padding: 7px 12px;
    font-size: 10px;
    font-weight: 700;
    color: #C9C3FF;
    text-transform: uppercase;
    letter-spacing: 1.4px;
}

QLineEdit#SearchInput,
QComboBox#SearchInput,
QSpinBox#SearchInput,
QDoubleSpinBox#SearchInput {
    background: #090A0D;
    border: 1px solid #1A1F27;
    border-radius: 16px;
    padding: 12px 16px;
    min-height: 22px;
}

QLineEdit#SearchInput:focus,
QComboBox#SearchInput:focus,
QSpinBox#SearchInput:focus,
QDoubleSpinBox#SearchInput:focus {
    background: #0B0D10;
    border: 1px solid #343C48;
}

QLabel#SearchError {
    font-size: 11px;
    color: #E38484;
    font-weight: 600;
}

QLabel#SearchControlTitle {
    font-size: 14px;
    font-weight: 700;
    color: #F1F5FA;
}

QLabel#SearchMetricValue {
    font-size: 14px;
    font-weight: 700;
    color: #C8C2FF;
}

QLabel#SearchTinyMeta,
QLabel#SearchInlineMeta {
    font-size: 11px;
    color: #98A3AF;
}

QSlider#SearchResultsSlider::groove:horizontal {
    height: 6px;
    border-radius: 999px;
    background: #06080B;
}

QSlider#SearchResultsSlider::sub-page:horizontal {
    height: 6px;
    border-radius: 999px;
    background: #06080B;
}

QSlider#SearchResultsSlider::add-page:horizontal {
    height: 6px;
    border-radius: 999px;
    background: #06080B;
}

QSlider#SearchResultsSlider::handle:horizontal {
    width: 18px;
    margin: -6px 0;
    border-radius: 9px;
    background: #C5C0FF;
    border: none;
}

QLabel#SearchToggleTitle {
    font-size: 13px;
    font-weight: 700;
    color: #F1F5FA;
}

QLabel#SearchToggleSubtitle {
    font-size: 11px;
    color: #959EAA;
}

QCheckBox#SearchToggleCheck::indicator {
    width: 34px;
    height: 20px;
    border-radius: 10px;
    background: #2A2F37;
    border: 1px solid #333945;
}

QCheckBox#SearchToggleCheck::indicator:checked {
    background: #7B73FF;
    border-color: #7B73FF;
}

QPushButton#SearchLaunchBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5E58F7, stop:1 #7672FD);
    color: #F5F7FF;
    font-size: 18px;
    font-weight: 800;
    border-radius: 18px;
    padding: 14px 28px;
}

QPushButton#SearchLaunchBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6863FF, stop:1 #817DFF);
}

QPushButton#SearchLaunchBtn:disabled {
    background: #2B3139;
    color: #8A929D;
}

QLabel#SearchEstimate {
    font-size: 12px;
    color: #7E8895;
}

QLabel#SettingsViewTitle {
    font-size: 40px;
    font-weight: 900;
    color: #F5F8FC;
    letter-spacing: -0.8px;
}

QLabel#SettingsViewSubtitle {
    font-size: 14px;
    color: #98A2AF;
}

QFrame#SettingsSubnav {
    background: transparent;
    border: none;
}

QPushButton#SettingsNavBtn {
    background: transparent;
    border: none;
    border-radius: 12px;
    padding: 13px 16px;
    text-align: left;
    color: #A5AFBB;
    font-size: 13px;
    font-weight: 600;
}

QPushButton#SettingsNavBtn:hover {
    background: #171C22;
    color: #EEF3F8;
}

QPushButton#SettingsNavBtn[active="true"] {
    background: #1D1A1C;
    color: #F4F7FB;
    border-left: 2px solid #6B64FF;
}

QPushButton#SettingsNavBtn:focus {
    background: #171C22;
    color: #F4F7FB;
    border: 1px solid #6B64FF;
}

QGroupBox#SettingsPanel {
    background: #1D1A1C;
    border: 1px solid #252B34;
    border-radius: 18px;
    margin-top: 0;
    padding: 42px 22px 22px 22px;
    font-size: 22px;
    font-weight: 800;
    color: #F4F7FB;
}

QGroupBox#SettingsPanel::title {
    subcontrol-origin: padding;
    subcontrol-position: top left;
    left: 20px;
    top: 10px;
    padding: 0 2px;
    background: transparent;
    color: #F4F7FB;
}

QLabel#SettingsMicroLabel {
    font-size: 11px;
    font-weight: 700;
    color: #A7B1BD;
    text-transform: uppercase;
    letter-spacing: 2px;
}

QLabel#SettingsTinyMeta {
    font-size: 10px;
    color: #818B97;
    text-transform: uppercase;
    letter-spacing: 1.4px;
}

QLabel#SettingsAccentMeta {
    font-size: 11px;
    color: #B8B0FF;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 1.4px;
}

QLabel#SettingsRangeDash {
    font-size: 20px;
    color: #909AA7;
    padding: 0 2px;
}

QSlider#SettingsMaxResultsSlider::groove:horizontal {
    height: 4px;
    border-radius: 999px;
    background: #090B0F;
}

QSlider#SettingsMaxResultsSlider::sub-page:horizontal,
QSlider#SettingsMaxResultsSlider::add-page:horizontal {
    height: 4px;
    border-radius: 999px;
    background: #090B0F;
}

QSlider#SettingsMaxResultsSlider::handle:horizontal {
    width: 16px;
    margin: -6px 0;
    border-radius: 8px;
    background: #C5C0FF;
    border: none;
}

QTextEdit#SettingsCodeArea,
QComboBox#SettingsLevelCombo {
    background: #090A0D;
    border: 1px solid #1A1F27;
    border-radius: 12px;
}

QTextEdit#SettingsCodeArea {
    padding: 14px;
    font-family: "Consolas", "Cascadia Code", monospace;
    font-size: 12px;
    color: #EAEFF5;
}

QFrame#SettingsToggleTile {
    background: #090A0D;
    border: 1px solid #1A1F27;
    border-radius: 14px;
}

QLabel#SettingsToggleTitle {
    font-size: 14px;
    font-weight: 700;
    color: #F1F5FA;
}

QLabel#SettingsToggleSubtitle {
    font-size: 12px;
    color: #8E98A5;
}

QCheckBox#SettingsSwitch::indicator {
    width: 34px;
    height: 20px;
    border-radius: 10px;
    background: #2A2F37;
    border: 1px solid #333945;
}

QCheckBox#SettingsSwitch::indicator:checked {
    background: #7B73FF;
    border-color: #7B73FF;
}

QFrame#SettingsDangerCard {
    background: rgba(135, 28, 52, 0.14);
    border: 1px solid rgba(196, 75, 95, 0.25);
    border-radius: 16px;
}

QLabel#SettingsDangerTitle {
    font-size: 14px;
    font-weight: 800;
    color: #FF97A3;
}

QLabel#SettingsDangerBody {
    font-size: 12px;
    color: #D1C8CD;
}

QPushButton#SettingsDangerBtn {
    background: transparent;
    border: 1px solid rgba(196, 75, 95, 0.45);
    border-radius: 12px;
    color: #FF97A3;
    padding: 10px 18px;
    font-size: 12px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

QPushButton#SettingsDangerBtn:hover {
    background: rgba(135, 28, 52, 0.18);
}

QPushButton#SettingsPrimaryBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5E58F7, stop:1 #7672FD);
    border: none;
    border-radius: 14px;
    color: #F5F7FF;
    padding: 12px 24px;
    font-size: 14px;
    font-weight: 800;
}

QPushButton#SettingsPrimaryBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6863FF, stop:1 #817DFF);
}

QPushButton#SettingsTextBtn {
    background: transparent;
    border: none;
    color: #B6C0CB;
    padding: 12px 12px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton#SettingsTextBtn:hover {
    color: #F4F7FB;
}

QLabel#SettingsStatus {
    font-size: 12px;
    color: #9DA7B4;
    font-weight: 600;
}

QLineEdit#LogsSearchInput {
    background: #090A0D;
    border: none;
    border-radius: 14px;
    padding: 12px 18px;
    min-height: 22px;
    color: #EFF4FA;
    font-size: 13px;
}

QLineEdit#LogsSearchInput:focus,
QComboBox#LogsLevelFilter:focus,
QPushButton#LogsGhostBtn:focus,
QPushButton#LogsDangerBtn:focus,
QPushButton#LogsHeaderIconBtn:focus {
    border: 1px solid #6B64FF;
}

QComboBox#LogsLevelFilter {
    background: #2B2A29;
    border: none;
    border-radius: 14px;
    padding: 10px 16px;
    padding-right: 34px;
    color: #F1F5FA;
    font-size: 12px;
    font-weight: 800;
}

QComboBox#LogsLevelFilter::drop-down {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 24px;
    border: none;
    background: transparent;
    padding-right: 8px;
}

QComboBox#LogsLevelFilter::down-arrow {
    image: url("__CHEVRON_DOWN__");
    width: 12px;
    height: 12px;
}

QPushButton#LogsGhostBtn,
QPushButton#LogsDangerBtn {
    border-radius: 14px;
    padding: 10px 16px;
    font-size: 12px;
    font-weight: 700;
}

QPushButton#LogsGhostBtn {
    background: transparent;
    border: 1px solid #2A313B;
    color: #D8E0E8;
}

QPushButton#LogsGhostBtn:hover {
    background: #1D232B;
}

QPushButton#LogsDangerBtn {
    background: transparent;
    border: 1px solid #33262A;
    color: #FF7E95;
}

QPushButton#LogsDangerBtn:hover {
    background: rgba(135, 28, 52, 0.14);
}

QFrame#LogsShell {
    background: #08090B;
    border: 1px solid #1C2128;
    border-radius: 24px;
}

QFrame#LogsShellHeader {
    background: #0E0F12;
    border-bottom: 1px solid #171C22;
    border-top-left-radius: 24px;
    border-top-right-radius: 24px;
}

QLabel#LogsLiveDot {
    color: #AFA8FF;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1.6px;
}

QLabel#LogsLiveLabel,
QLabel#LogsHeaderMeta,
QLabel#LogsFooterMeta,
QLabel#LogsFooterError,
QLabel#LogsFooterWarn,
QLabel#LogsHeaderDivider {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.8px;
}

QLabel#LogsLiveLabel,
QLabel#LogsHeaderMeta,
QLabel#LogsFooterMeta,
QLabel#LogsHeaderDivider {
    color: #A0AAB7;
}

QLabel#LogsFooterError {
    color: #FF8398;
}

QLabel#LogsFooterWarn {
    color: #E7C1FF;
}

QPushButton#LogsHeaderIconBtn {
    background: transparent;
    border: none;
    color: #A5AFBC;
    min-width: 24px;
    min-height: 24px;
    font-size: 16px;
}

QPushButton#LogsHeaderIconBtn:hover {
    color: #F1F5FA;
}

QTextBrowser#LogsConsole {
    background: #000000;
    border: none;
    border-radius: 0;
    padding: 20px 24px;
    font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    color: #E2E8F0;
}

QFrame#LogsShellFooter {
    background: #1D1A1C;
    border-top: 1px solid #1C2128;
    border-bottom-left-radius: 24px;
    border-bottom-right-radius: 24px;
}

QLabel#ResultsCount {
    background: #1D242C;
    border: none;
    border-radius: 10px;
    padding: 6px 12px;
    color: #D5DEE8;
    font-size: 12px;
    font-weight: 700;
    min-width: 0;
}

QLabel#ResultsProgressLabel {
    font-size: 11px;
    color: #A7B1BE;
}

QProgressBar#ResultsProgressBar {
    background: #10151A;
    border: 1px solid #1F2730;
    border-radius: 999px;
    min-height: 6px;
    max-height: 6px;
}

QProgressBar#ResultsProgressBar::chunk {
    background: #6B64FF;
    border-radius: 999px;
}

QTableView#ResultsTable {
    background: transparent;
    border: none;
    border-radius: 22px;
}

QSplitter#ResultsSplitter::handle {
    background: transparent;
}

QLabel#ResultsDetailTitle {
    font-size: 24px;
    font-weight: 700;
    color: #F7FAFC;
}

QLabel#ResultsDetailMeta {
    font-size: 11px;
    font-weight: 700;
    color: #AAB4C0;
    text-transform: uppercase;
    letter-spacing: 1.2px;
}

QLabel#ResultsDetailSummary {
    font-size: 14px;
    color: #97A1AE;
}

QLabel#ResultsFieldLabel {
    font-size: 10px;
    font-weight: 700;
    color: #9EABBA;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}

QLabel#ResultsFieldValue {
    font-size: 13px;
    color: #EEF4FB;
}

QFrame#DataWorkspaceShell {
    background: #0F172A;
    border: none;
    border-bottom-left-radius: 18px;
    border-bottom-right-radius: 18px;
}

QFrame#ResultsIntro {
    background: transparent;
    border: none;
}

QLabel#ResultsPageTitle {
    font-family: "Segoe UI Variable Display", "Segoe UI Variable Text", "PT Root UI", sans-serif;
    font-size: 28px;
    font-weight: 800;
    color: #F8FAFC;
    letter-spacing: -0.8px;
}

QLabel#ResultsPageSubtitle {
    font-size: 14px;
    color: #94A3B8;
}

QFrame#ResultsMetricCard {
    background: #1D1A1C;
    border: 1px solid #24282F;
    border-radius: 14px;
}

QLabel#ResultsMetricLabel {
    font-size: 10px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 2px;
}

QLabel#ResultsMetricValue {
    font-family: "Segoe UI Variable Display", "Segoe UI Variable Text", "PT Root UI", sans-serif;
    font-size: 24px;
    font-weight: 800;
    color: #F5F8FC;
}

QLabel#ResultsMetricMeta {
    font-size: 11px;
    color: #A5AFBA;
}

QFrame#ResultsTopFilters {
    background: transparent;
    border: none;
}

QLineEdit#ResultsSearchInput {
    background: #1E293B;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 11px 16px;
    min-height: 18px;
    font-size: 13px;
    color: #F8FAFC;
}

QLineEdit#ResultsSearchInput:focus {
    border: 1px solid #3B82F6;
    background: #1E293B;
}

QComboBox#ResultsFilterPill {
    background: #1E293B;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 10px 14px;
    padding-right: 34px;
    min-height: 18px;
    color: #F8FAFC;
    font-size: 13px;
    font-weight: 600;
}

QComboBox#ResultsFilterPill::drop-down {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 26px;
    border: none;
    background: transparent;
    padding-right: 8px;
}

QComboBox#ResultsFilterPill::down-arrow {
    image: url("__CHEVRON_DOWN__");
    width: 12px;
    height: 12px;
}

QPushButton#ResultsFilterGhost,
QPushButton#ResultsIconGhost {
    background: #232735;
    border: 1px solid #303744;
    border-radius: 12px;
    color: #D7DEE7;
    padding: 10px 14px;
}

QPushButton#ResultsFilterGhost:disabled,
QPushButton#ResultsIconGhost:disabled {
    color: #C8D0DA;
}

QFrame#ResultsInlineProgress {
    background: transparent;
    border: none;
}

QLabel#ResultsInlineProgressLabel {
    font-size: 12px;
    color: #98A2AF;
}

QProgressBar#ResultsInlineProgressBar {
    background: #0D1014;
    border: none;
    border-radius: 999px;
    min-height: 6px;
    max-height: 6px;
}

QProgressBar#ResultsInlineProgressBar::chunk {
    background: #8E87FF;
    border-radius: 999px;
}

QFrame#MonitorHeroV2,
QFrame#MonitorMetricTileAccent,
QFrame#MonitorMetricTilePlain,
QFrame#MonitorVelocityCard,
QFrame#MonitorActivityPanel {
    background: #1D1A1C;
    border: 1px solid #252B34;
    border-radius: 22px;
}

QFrame#MonitorMetricTileAccent {
    border-left: 4px solid #8E87FF;
}

QLabel#MonitorHeroJob {
    font-size: 18px;
    font-weight: 800;
    color: #F5F8FC;
}

QLabel#MonitorHeroStatus {
    font-size: 13px;
    color: #ADB6C0;
}

QLabel#MonitorHeroBigPct {
    font-size: 44px;
    font-weight: 900;
    color: #F4F7FB;
    letter-spacing: -1px;
}

QLabel#MonitorHeroMetaLabel {
    font-size: 10px;
    font-weight: 700;
    color: #8F99A6;
    text-transform: uppercase;
    letter-spacing: 1.8px;
}

QLabel#MonitorHeroMetaValue,
QLabel#MonitorHeroMetaValueAccent {
    font-size: 20px;
    font-weight: 800;
    color: #F3F7FB;
}

QLabel#MonitorHeroMetaValueAccent {
    color: #BEB7FF;
}

QProgressBar#MonitorHeroProgress {
    background: #0A0D11;
    border: none;
    border-radius: 999px;
    min-height: 8px;
    max-height: 8px;
}

QProgressBar#MonitorHeroProgress::chunk {
    background: #6E67FF;
    border-radius: 999px;
}

QLabel#MonitorHeroProgressText {
    font-size: 12px;
    color: #98A2AF;
}

QLabel#MonitorMetricTitle {
    font-size: 10px;
    font-weight: 700;
    color: #A4AEB9;
    text-transform: uppercase;
    letter-spacing: 2px;
}

QLabel#MonitorMetricValue {
    font-size: 38px;
    font-weight: 900;
    color: #F3F7FB;
    letter-spacing: -1px;
}

QLabel#MonitorMetricMeta {
    font-size: 12px;
    font-weight: 700;
    color: #C9C2FF;
}

QPushButton#MonitorControlBtn,
QPushButton#MonitorDangerBtn,
QPushButton#MonitorGhostBtn {
    border-radius: 12px;
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton#MonitorControlBtn {
    background: #2C2A2D;
    color: #F2F5F8;
}

QPushButton#MonitorControlBtn:hover {
    background: #353235;
}

QPushButton#MonitorControlBtn:disabled {
    background: #22262C;
    color: #7E8792;
}

QPushButton#MonitorDangerBtn {
    background: #3B1E26;
    color: #FF8CA1;
}

QPushButton#MonitorDangerBtn:hover {
    background: #49242E;
}

QPushButton#MonitorDangerBtn:disabled {
    background: #24272D;
    color: #7E8792;
}

QPushButton#MonitorGhostBtn {
    background: #14181E;
    color: #DCE3EB;
}

QPushButton#MonitorGhostBtn:hover {
    background: #1D232B;
}

QLabel#MonitorVelocityTitle,
QLabel#MonitorActivityTitle {
    font-size: 16px;
    font-weight: 800;
    color: #F4F7FB;
}

QLabel#MonitorVelocityMeta,
QLabel#MonitorFooterLabel {
    font-size: 11px;
    color: #98A2AF;
    text-transform: uppercase;
    letter-spacing: 1.4px;
}

QLabel#MonitorVelocityPeak {
    font-size: 24px;
    font-weight: 900;
    color: #726CFF;
}

QFrame#MonitorVelocityBar {
    background: qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 #4740D2, stop:1 #736DFF);
    border: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QFrame#MonitorActivityHeader {
    background: #1D1A1C;
    border: none;
    border-top-left-radius: 22px;
    border-top-right-radius: 22px;
    border-bottom: 1px solid #252B34;
}

QLabel#MonitorActivityBadge {
    background: rgba(94, 88, 247, 0.18);
    border: none;
    border-radius: 10px;
    padding: 6px 10px;
    color: #AFA8FF;
    font-size: 10px;
    font-weight: 800;
}

QTextBrowser#MonitorActivityLog {
    background: #171416;
    border: none;
    border-radius: 0;
    padding: 20px 22px;
    font-family: "Consolas", "Cascadia Code", monospace;
    font-size: 11px;
    color: #E1E6EC;
}

QFrame#MonitorActivityFooter {
    background: rgba(255, 255, 255, 0.02);
    border-top: 1px solid #252B34;
    border-bottom-left-radius: 22px;
    border-bottom-right-radius: 22px;
}

QLabel#MonitorActivityFooterText {
    font-size: 11px;
    font-weight: 700;
    color: #98A2AF;
    text-transform: uppercase;
    letter-spacing: 1.6px;
}

QCheckBox#MonitorAutoScroll {
    color: #AEB8C3;
    font-size: 12px;
}

QFrame#MonitorStatusFooter {
    background: transparent;
    border-top: 1px solid #212730;
}

QFrame#ResultsGridShell {
    background: transparent;
    border: none;
}

QSplitter#ResultsWorkspaceSplitter::handle {
    background: #334155;
    width: 1px;
}

QTableView#DataWorkspaceTable {
    background: #0F172A;
    border: 1px solid #334155;
    border-radius: 16px;
    gridline-color: transparent;
    selection-background-color: #1E293B;
    selection-color: #F8FAFC;
    alternate-background-color: transparent;
}

QTableView#DataWorkspaceTable::item {
    padding: 22px 16px;
    border-bottom: 1px solid #334155;
}

QTableView#DataWorkspaceTable::item:hover {
    background: #1E293B;
}

QHeaderView::section {
    background: #0F172A;
}

QTableView#DataWorkspaceTable QHeaderView::section {
    background: #0F172A;
    color: #94A3B8;
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 1.9px;
    padding: 20px 18px;
    border: none;
    border-bottom: 1px solid #334155;
}

QTableView#DataWorkspaceTable QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 4px 10px 8px 10px;
}

QTableView#DataWorkspaceTable QScrollBar::handle:horizontal {
    background: #3B82F6;
    border-radius: 5px;
    min-width: 34px;
}

QTableView#DataWorkspaceTable QScrollBar::add-line:horizontal,
QTableView#DataWorkspaceTable QScrollBar::sub-line:horizontal,
QTableView#DataWorkspaceTable QScrollBar::add-page:horizontal,
QTableView#DataWorkspaceTable QScrollBar::sub-page:horizontal {
    background: transparent;
    border: none;
}

QLabel#ResultsHeaderCount {
    background: rgba(59, 130, 246, 0.12);
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 10px 14px;
    color: #F8FAFC;
    font-size: 12px;
    font-weight: 700;
}

QPushButton#ResultsHeaderBtn {
    background: transparent;
    border: 1px solid #334155;
    border-radius: 12px;
    color: #F8FAFC;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton#ResultsHeaderBtn:focus,
QPushButton#ResultsHeaderPrimaryBtn:focus,
QPushButton#ResultsMinorActionBtn:focus,
QPushButton#ResultsMinorGhostBtn:focus {
    border: 1px solid #3B82F6;
}

QPushButton#ResultsHeaderBtn:hover {
    background: #1E293B;
}

QPushButton#ResultsHeaderPrimaryBtn {
    background: #3B82F6;
    border: none;
    border-radius: 12px;
    color: #F8FAFC;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 800;
}

QPushButton#ResultsHeaderPrimaryBtn:hover {
    background: #4A8DF7;
}

QWidget#ResultsDetailPanelV2 {
    background: #1E293B;
    border-left: 1px solid #334155;
}

QLabel#ResultsDetailSideTitle {
    font-size: 18px;
    font-weight: 800;
    color: #F8FAFC;
    letter-spacing: -0.2px;
}

QFrame#ResultsLeadHero {
    background: rgba(248, 250, 252, 0.03);
    border: 1px solid #334155;
    border-radius: 18px;
}

QLabel#ResultsLeadHeroMark {
    background: rgba(59, 130, 246, 0.08);
    border: 2px solid #3B82F6;
    border-radius: 20px;
    color: #60A5FA;
    font-size: 34px;
    font-weight: 800;
}

QLabel#ResultsLeadHeroName {
    font-size: 14px;
    font-weight: 800;
    color: #F8FAFC;
}

QLabel#ResultsLeadHeroLink {
    font-size: 13px;
    font-weight: 600;
    color: #94A3B8;
    letter-spacing: 0;
}

QLabel#ResultsDetailFieldLabel {
    font-size: 10px;
    font-weight: 700;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 2px;
}

QLabel#ResultsDetailFieldValue {
    font-size: 13px;
    font-weight: 600;
    color: #F8FAFC;
}

QFrame#ResultsInfoCard {
    background: #0F172A;
    border: 1px solid #334155;
    border-radius: 16px;
}

QLabel#ResultsSectionCardTitle {
    font-size: 10px;
    font-weight: 800;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 2px;
}

QLabel#ResultsMarkerChip {
    background: rgba(59, 130, 246, 0.12);
    border: 1px solid rgba(59, 130, 246, 0.24);
    border-radius: 10px;
    padding: 6px 10px;
    color: #BFDBFE;
    font-size: 11px;
    font-weight: 700;
}

QLabel#ResultsDescription {
    font-size: 13px;
    color: #94A3B8;
    line-height: 1.5;
}

QPushButton#ResultsMinorActionBtn,
QPushButton#ResultsMinorGhostBtn {
    min-height: 18px;
    padding: 10px 18px;
    border-radius: 10px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton#ResultsMinorActionBtn {
    background: #3B82F6;
    border: none;
    color: #F8FAFC;
}

QPushButton#ResultsMinorActionBtn:hover {
    background: #4A8DF7;
}

QPushButton#ResultsMinorGhostBtn {
    background: transparent;
    border: 1px solid #334155;
    color: #F8FAFC;
}

QPushButton#ResultsMinorGhostBtn:hover {
    background: #1E293B;
}

QPushButton#ResultsRoundIconBtn {
    background: #0F172A;
    border: 1px solid #334155;
    border-radius: 20px;
    color: #F8FAFC;
}

QPushButton#ResultsRoundIconBtn:hover {
    background: #1E293B;
}

QPushButton#ResultsRoundIconBtn:disabled {
    background: #0F172A;
    color: rgba(248, 250, 252, 0.35);
    border: 1px solid rgba(51, 65, 85, 0.6);
}

/* Strict Monochrome / Grayscale override layer */
* {
    font-family: "Inter", "Geist Sans", "PT Root UI", sans-serif;
    color: #F5F5F5;
}

QApplication,
QMainWindow,
#WindowCanvas {
    background: #050505;
}

#AppShell,
#ContentShell,
#ContentArea,
#ContentTopBar,
#Sidebar,
#WorkspacePanel,
#Card,
QFrame#DashboardMetricCard,
QFrame#DashboardTableCard,
QFrame#DashboardSideCard,
QFrame#DashboardHealthStatCard,
QFrame#SearchSourceCard,
QFrame#SearchAdvancedCard,
QFrame#SearchToggleTile,
QFrame#DataWorkspaceShell,
QFrame#MonitorHeroV2,
QFrame#MonitorMetricTileAccent,
QFrame#MonitorMetricTilePlain,
QFrame#MonitorActivityPanel,
QGroupBox#SettingsPanel,
QFrame#LogsShell,
QFrame#ResultsLeadHero,
QFrame#ResultsInfoCard {
    background: #121212;
    border: 1px solid #262626;
    border-radius: 12px;
}

#ContentTopBar,
QFrame#LogsShellHeader,
QFrame#MonitorActivityHeader {
    border-bottom: 1px solid #262626;
}

#SidebarLogoMark {
    background: #1A1A1A;
    border: 1px solid #262626;
    border-radius: 12px;
}

#SidebarLogo,
#ContentTitle,
#PageHeader,
QLabel#DashboardHeroTitle,
QLabel#ResultsPageTitle,
QLabel#SearchViewTitle,
QLabel#SettingsViewTitle,
QLabel#MonitorHeroJob {
    color: #F5F5F5;
    font-size: 24px;
    font-weight: 600;
    letter-spacing: 0px;
}

#SidebarTagline,
#SidebarVersion,
#PanelMeta,
#PageSubtitle,
QLabel#DashboardHeroSubtitle,
QLabel#ResultsPageSubtitle,
QLabel#SettingsViewSubtitle,
QLabel#SearchSourceBody,
QLabel#SearchToggleSubtitle,
QLabel#DashboardJobMeta,
QLabel#DashboardJobDate,
QLabel#ResultsDescription,
QLabel#MonitorHeroStatus,
QLabel#MonitorHeroProgressText,
QLabel#MonitorMetricMeta,
QLabel#FormHint,
QLabel#InlineHint {
    color: #737373;
}

#ContentEyebrow,
#PanelSectionLabel,
#CardTitle,
QLabel#DashboardMetricLabel,
QLabel#DashboardTableHeader,
QLabel#DashboardSideTitle,
QLabel#SearchStepLabel,
QLabel#SearchControlTitle,
QLabel#SearchTinyMeta,
QLabel#SearchInlineMeta,
QLabel#ResultsSectionCardTitle,
QLabel#MonitorMetricTitle,
QLabel#MonitorHeroMetaLabel,
QLabel#DashboardHealthStatLabel,
QHeaderView::section {
    color: #737373;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.4px;
}

QPushButton#TopNavBtn {
    background: transparent;
    border: 1px solid #333333;
    border-radius: 12px;
    color: #F5F5F5;
}

QPushButton#TopNavBtn:hover {
    background: #1A1A1A;
    border-color: #333333;
    color: #F5F5F5;
}

QPushButton#TopNavBtn[active="true"] {
    background: #121212;
    border: 1px solid #F5F5F5;
    color: #FFFFFF;
}

QPushButton,
QPushButton#ToolbarPill,
QPushButton#ToolbarIconBtn,
QPushButton#DashboardGhostBtn,
QPushButton#ResultsHeaderBtn,
QPushButton#ResultsMinorGhostBtn,
QPushButton#LogsGhostBtn,
QPushButton#LogsDangerBtn,
QPushButton#MonitorControlBtn {
    background: transparent;
    border: 1px solid #333333;
    border-radius: 12px;
    color: #FFFFFF;
    padding: 10px 18px;
    font-weight: 600;
}

QPushButton:hover,
QPushButton#ToolbarPill:hover,
QPushButton#ToolbarIconBtn:hover,
QPushButton#DashboardGhostBtn:hover,
QPushButton#ResultsHeaderBtn:hover,
QPushButton#ResultsMinorGhostBtn:hover,
QPushButton#LogsGhostBtn:hover,
QPushButton#LogsDangerBtn:hover,
QPushButton#MonitorControlBtn:hover {
    background: #1A1A1A;
    border-color: #333333;
}

QPushButton#PrimaryBtn,
QPushButton#SidebarPrimaryBtn,
QPushButton#DashboardPrimaryBtn,
QPushButton#SearchLaunchBtn,
QPushButton#ResultsHeaderPrimaryBtn,
QPushButton#ResultsMinorActionBtn,
QPushButton#SettingsPrimaryBtn {
    background: #FFFFFF;
    color: #000000;
    border: 1px solid #FFFFFF;
    border-radius: 12px;
}

QPushButton#PrimaryBtn:hover,
QPushButton#SidebarPrimaryBtn:hover,
QPushButton#DashboardPrimaryBtn:hover,
QPushButton#SearchLaunchBtn:hover,
QPushButton#ResultsHeaderPrimaryBtn:hover,
QPushButton#ResultsMinorActionBtn:hover,
QPushButton#SettingsPrimaryBtn:hover {
    background: #EDEDED;
    color: #000000;
    border: 1px solid #EDEDED;
}

QPushButton#DangerBtn,
QPushButton#SettingsDangerBtn,
QPushButton#MonitorDangerBtn {
    background: transparent;
    color: #F5F5F5;
    border: 1px solid #333333;
}

QLineEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox,
QTextEdit,
QPlainTextEdit,
QTextBrowser,
QLineEdit#ShellSearchInput,
QLineEdit#SearchInput,
QLineEdit#ResultsSearchInput,
QLineEdit#LogsSearchInput,
QComboBox#SearchInput,
QComboBox#ResultsFilterPill,
QComboBox#LogsLevelFilter,
QSpinBox#SearchInput,
QDoubleSpinBox#SearchInput,
QTextEdit#SettingsCodeArea,
QTextBrowser#LogsConsole,
QTextBrowser#MonitorActivityLog {
    background: #1A1A1A;
    border: 1px solid #262626;
    border-radius: 12px;
    color: #F5F5F5;
    selection-background-color: #FFFFFF;
    selection-color: #000000;
}

QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QTextBrowser:focus,
QTableView:focus {
    border: 1px solid #F5F5F5;
}

QLineEdit::placeholder,
QTextEdit[placeholderText="true"],
QTextBrowser,
QLabel#FormHint,
QLabel#ResultsPageSubtitle,
QLabel#DashboardHeroSubtitle {
    color: #737373;
}

QCheckBox#SearchToggleCheck::indicator,
QCheckBox#SettingsSwitch::indicator,
QCheckBox::indicator {
    background: #1A1A1A;
    border: 1px solid #333333;
    border-radius: 10px;
}

QCheckBox#SearchToggleCheck::indicator:checked,
QCheckBox#SettingsSwitch::indicator:checked,
QCheckBox::indicator:checked {
    background: #FFFFFF;
    border-color: #FFFFFF;
}

QFrame#SearchSourceCard[active="true"] {
    background: #121212;
    border: 2px solid #FFFFFF;
}

QFrame#SearchSourceCard:hover,
QFrame#SearchSourceCard:focus {
    border: 1px solid #333333;
}

QFrame#SearchSourceCard[active="true"] QLabel#SearchSourceIndicator {
    background: #FFFFFF;
    border-color: #FFFFFF;
}

QSlider#SearchResultsSlider::groove:horizontal,
QProgressBar,
QProgressBar#DashboardHealthBar,
QProgressBar#DashboardStorageBar,
QProgressBar#MonitorHeroProgress {
    background: #1A1A1A;
    border: 1px solid #262626;
    border-radius: 999px;
}

QSlider#SearchResultsSlider::sub-page:horizontal,
QSlider#SearchResultsSlider::handle:horizontal,
QProgressBar::chunk,
QProgressBar#DashboardHealthBar::chunk,
QProgressBar#DashboardStorageBar::chunk,
QProgressBar#MonitorHeroProgress::chunk {
    background: #FFFFFF;
    border-radius: 999px;
}

QTableWidget,
QTableView,
QTableView#DataWorkspaceTable {
    background: #121212;
    border: 1px solid #262626;
    border-radius: 12px;
    gridline-color: #262626;
    selection-background-color: #1A1A1A;
    selection-color: #F5F5F5;
}

QTableWidget::item,
QTableView::item {
    padding: 14px 12px;
}

QTableWidget::item:selected,
QTableView::item:selected {
    background: #1A1A1A;
    color: #F5F5F5;
}

QHeaderView::section {
    background: #121212;
    border-bottom: 1px solid #262626;
    border-right: 1px solid #262626;
    color: #737373;
    padding: 16px 12px;
}

QWidget#ResultsDetailPanelV2 {
    background: #121212;
    border-left: 1px solid #262626;
}

QFrame#ResultsLeadHero {
    background: #1A1A1A;
    border: 1px solid #262626;
}

QLabel#ResultsLeadHeroMark {
    background: transparent;
    color: #F5F5F5;
    border: 2px solid #FFFFFF;
    border-radius: 22px;
}

QPushButton#ResultsRoundIconBtn {
    background: #1A1A1A;
    border: 1px solid #333333;
    border-radius: 18px;
    color: #F5F5F5;
}

QPushButton#ResultsRoundIconBtn:disabled {
    background: #1A1A1A;
    border: 1px solid #262626;
    color: #737373;
}

QFrame#MonitorMetricTileAccent,
QFrame#MonitorMetricTilePlain,
QFrame#MonitorActivityPanel,
QFrame#MonitorHeroV2 {
    background: #121212;
    border: 1px solid #262626;
}

QLabel#MonitorMetricValue,
QLabel#MonitorHeroMetaValueAccent,
QLabel#MonitorHeroBigPct {
    color: #F5F5F5;
}

QTextBrowser#LogsConsole,
QTextBrowser#MonitorActivityLog,
QTextEdit#SettingsCodeArea {
    font-family: "Geist Mono", "Cascadia Code", "Consolas", monospace;
}

QScrollBar:vertical,
QScrollBar:horizontal {
    background: transparent;
    border: none;
}

QScrollBar::handle:vertical,
QScrollBar::handle:horizontal {
    background: #333333;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover,
QScrollBar::handle:horizontal:hover {
    background: #4A4A4A;
}

QTableView#DataWorkspaceTable QScrollBar::handle:horizontal {
    background: #FFFFFF;
}

QLabel,
BodyLabel,
CaptionLabel,
StrongBodyLabel,
SubtitleLabel,
TitleLabel {
    background: transparent;
    border: none;
}

QPushButton#btn_reset {
    background-color: #2C2C2E;
    border: 1px solid #3A3A3C;
    border-radius: 8px;
    color: #636366;
    height: 36px;
    padding: 0px 18px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1.6px;
    text-transform: uppercase;
}
QPushButton#btn_reset:hover {
    background-color: #333333;
    color: #FFFFFF;
}

QPushButton#btn_save {
    background-color: #0A84FF;
    border: none;
    border-radius: 8px;
    color: #FFFFFF;
    height: 36px;
    padding: 0px 18px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1.6px;
    text-transform: uppercase;
}
QPushButton#btn_save:hover {
    background-color: #409CFF;
}

QPushButton#btn_wipe_data {
    background-color: #2C1A1A;
    border: 1px solid #3A2020;
    border-radius: 8px;
    color: #FF453A;
    height: 36px;
    padding: 0px 18px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1.6px;
    text-transform: uppercase;
}
QPushButton#btn_wipe_data:hover {
    background-color: #3A1F1F;
    color: #FF6259;
}
""".replace("__CHEVRON_DOWN__", _CHEVRON_DOWN).replace("__CHEVRON_UP__", _CHEVRON_UP)
