from dotenv import load_dotenv
load_dotenv()

from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QFileDialog, QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QSpinBox, QSlider, QDialog, QGridLayout, QSizePolicy, QInputDialog, QTextEdit, QComboBox, QListWidget, QListWidgetItem, QFrame, QSplitter, QToolButton, QLineEdit, QMenu, QAbstractSpinBox, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt, QRect, QPoint, QEvent, QSize, QTimer, QByteArray, QSignalBlocker
from PySide6.QtGui import QPixmap, QImage, QKeySequence, QShortcut, QMouseEvent, QPainter, QPen, QColor, QBrush, QIcon, QFont, QFontDatabase, QFontMetrics, QGuiApplication, QPainterPath
from PySide6.QtSvg import QSvgRenderer
import re
import sys
import fitz
import os
import sqlite3
import json
import uuid
import traceback
import faulthandler
from datetime import datetime

RUNTIME_CRASH_LOG = None


def runtime_trace(message: str):
    timestamp = datetime.now().isoformat(timespec="seconds")
    line = f"[trace {timestamp}] {message}\n"
    try:
        if RUNTIME_CRASH_LOG is not None:
            RUNTIME_CRASH_LOG.write(line)
            RUNTIME_CRASH_LOG.flush()
    except Exception:
        pass


class SelectableLabel(QLabel):
    def __init__(self, parent=None, page_index=0):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.selecting = False
        self.page_index = page_index

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if hasattr(self.window(), 'handle_page_annotation_marker_click'):
                if self.window().handle_page_annotation_marker_click(self.page_index, self, event.position().toPoint()):
                    event.accept()
                    return
            if hasattr(self.window(), '_hide_focus_annotation_panel_on_page_click'):
                self.window()._hide_focus_annotation_panel_on_page_click()
            self.selecting = True
            add = bool(event.modifiers() & Qt.ControlModifier)
            if hasattr(self.window(), 'begin_selection'):
                self.window().begin_selection(self.page_index, self, event.position().toPoint(), add)
            event.accept()
            return
        if event.button() == Qt.RightButton:
            if hasattr(self.window(), 'goto_next'):
                self.window().goto_next()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.selecting and hasattr(self.window(), 'update_selection'):
            self.window().update_selection(self.page_index, self, event.position().toPoint())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self.selecting:
            self.selecting = False
            add = bool(event.modifiers() & Qt.ControlModifier)
            if hasattr(self.window(), 'finalize_selection'):
                self.window().finalize_selection(self.page_index, self, event.position().toPoint(), add)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class PanelResizeGrip(QLabel):
    def __init__(self, side: str, parent=None):
        super().__init__(parent)
        self.side = side
        self.setCursor(Qt.SizeHorCursor)
        self._dragging = False

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and hasattr(self.window(), "_begin_side_panel_resize"):
            self._dragging = True
            self.window()._begin_side_panel_resize(self.side, event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging and hasattr(self.window(), "_update_side_panel_resize"):
            self.window()._update_side_panel_resize(self.side, event.globalPosition().toPoint())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            if hasattr(self.window(), "_end_side_panel_resize"):
                self.window()._end_side_panel_resize()
            event.accept()
            return
        super().mouseReleaseEvent(event)

class PDFViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        try:
            from .db_init import init_db
            init_db()
        except Exception:
            print("DB initialization failed:")
            print(traceback.format_exc())
        self.setWindowTitle("Scholar - Prototype PDF Viewer")
        self.resize(1000, 800)
        self.setFont(self._ui_font())
        self.doc = None
        self.current_page = 0
        self.total_pages = 0
        self.continuous = False
        self.fit_to_width = False
        self.zoom_factor = 2.0
        self.db_path = os.path.join(os.path.dirname(__file__), '..', 'scholar.db')
        self.current_document_id = None
        self.current_project_source_id = None
        self.current_document_path = ""
        self._document_load_in_progress = False
        self._pending_document_load_key = None
        self._active_panel_resize_side = None
        self.focus_mode = False
        self._focus_restore_state = {}
        self.current_session_id = None
        self.current_session_intention = ""
        self.current_annotation_id = None
        self.current_annotation_tags = []
        self.system_annotation_tags = []
        self.annotation_saved_panel_has_results = False
        self.search_results = []
        self.search_result_index = -1
        self.search_query = ""
        self.annotation_draft_mode = "idle"
        self.current_library_doc_id = None
        self.current_library_project_source_id = None
        self.current_library_source_id = None
        self.current_project_id = None
        self.current_annotation_writing_project_id = None
        self.theme_mode = "light"
        self.reader_mode = "full"
        self.triage_inclusion_record_id = None
        self.triage_metadata_dirty = False
        self.updating_triage_panel = False
        self.updating_doc_organizer = False
        self.current_pixmap = None
        self.page_labels = {}
        self.page_pixmaps = {}
        self.page_annotation_markers = {}
        self.current_char_index = []
        self.selection_start_index = None
        self.selection_end_index = None
        self.selection_char_start = None
        self.selection_char_end = None
        self.selection_finalized = False
        self.focus_multi_select_pending = False
        self.selected_rect = None
        self.selected_page = None
        self.selected_label = None
        self.selection_regions = []  # list of (start_idx, end_idx) for committed regions

        # keyboard shortcuts
        self.shortcut_prev = QShortcut(QKeySequence("Left"), self)
        self.shortcut_prev.activated.connect(self.goto_previous)
        self.shortcut_next = QShortcut(QKeySequence("Right"), self)
        self.shortcut_next.activated.connect(self.goto_next)
        QShortcut(QKeySequence("Home"), self).activated.connect(lambda: self.render_page(0))
        QShortcut(QKeySequence("End"), self).activated.connect(lambda: self.render_page(self.total_pages-1 if self.total_pages>0 else 0))
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self._toggle_library)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.focus_pdf_search)
        QShortcut(QKeySequence("F3"), self).activated.connect(self.goto_next_search_result)
        QShortcut(QKeySequence("Shift+F3"), self).activated.connect(self.goto_previous_search_result)
        QShortcut(QKeySequence("F11"), self).activated.connect(self._toggle_focus_mode)
        QShortcut(QKeySequence("Esc"), self).activated.connect(self._handle_escape)

        # ── Ribbon ────────────────────────────────────────────────────────────
        ribbon = QWidget()
        self.ribbon = ribbon
        ribbon.setObjectName("Ribbon")
        ribbon.setFixedHeight(72)
        ribbon_layout = QVBoxLayout(ribbon)
        ribbon_layout.setContentsMargins(8, 6, 8, 6)
        ribbon_layout.setSpacing(0)

        ribbon_shell = QFrame()
        ribbon_shell.setObjectName("RibbonShell")
        ribbon_shell_layout = QHBoxLayout(ribbon_shell)
        ribbon_shell_layout.setContentsMargins(8, 9, 8, 9)
        ribbon_shell_layout.setSpacing(8)
        ribbon_layout.addWidget(ribbon_shell)

        def _sep():
            line = QFrame()
            line.setFrameShape(QFrame.VLine)
            line.setObjectName("RibbonDivider")
            line.setFixedWidth(6)
            return line

        def _tray(role="default"):
            frame = QFrame()
            frame.setObjectName("RibbonTray")
            frame.setProperty("trayRole", role)
            layout = QHBoxLayout(frame)
            layout.setContentsMargins(4, 4, 4, 4)
            layout.setSpacing(3)
            return frame, layout

        def _rb(label, tip="", role="secondary"):
            btn = QPushButton(label)
            btn.setToolTip(tip)
            btn.setFixedHeight(28)
            btn.setObjectName("RibbonButton")
            btn.setProperty("role", role)
            return btn

        def _rb_compact(label, tip=""):
            btn = _rb(label, tip, role="utility")
            btn.setProperty("compact", True)
            btn.setFixedWidth(34)
            return btn

        # Group: Library
        self.library_toggle_btn = _rb("", "Show or hide the full left library pane", role="utility")
        self.library_toggle_btn.setFixedWidth(34)
        self.library_toggle_btn.clicked.connect(self._toggle_library)
        self.open_pdf_btn = _rb("", "Open or import PDFs into the library", role="secondary")
        self.open_pdf_btn.setFixedWidth(38)
        self.open_pdf_menu = QMenu(self)
        self.open_pdf_menu.addAction("Open PDF in Library...", self.open_pdf)
        self.open_pdf_menu.addAction("Add PDFs to Library...", self.add_multiple_pdfs)
        self.open_pdf_menu.addAction("Add Folder to Library...", self.add_pdf_folder)
        self.open_pdf_menu.addSeparator()
        self.open_pdf_menu.addAction("Add PDFs to Current Project...", self.add_multiple_pdfs_to_current_project)
        self.open_pdf_menu.addAction("Add Folder to Current Project...", self.add_pdf_folder_to_current_project)
        self.open_pdf_btn.setMenu(self.open_pdf_menu)
        library_tray, library_tray_layout = _tray("utility")
        library_tray_layout.addWidget(self.library_toggle_btn)
        library_tray_layout.addWidget(self.open_pdf_btn)
        ribbon_shell_layout.addWidget(library_tray)

        # Group: Navigation
        self.prev_page_btn = _rb_compact("", "Previous page")
        self.prev_page_btn.clicked.connect(self.goto_previous)
        self.page_spin = QSpinBox()
        self.page_spin.setObjectName("RibbonPageSpin")
        self.page_spin.setMinimum(1)
        self.page_spin.setValue(1)
        self.page_spin.setEnabled(False)
        self.page_spin.setFixedWidth(38)
        self.page_spin.setFixedHeight(26)
        self.page_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.page_spin.setReadOnly(True)
        self.page_spin.setAlignment(Qt.AlignCenter)
        self.page_spin.setFocusPolicy(Qt.NoFocus)
        self.page_spin.valueChanged.connect(lambda v: self.render_page(v-1))
        self.page_label = QLabel("/ -")
        self.page_label.setObjectName("PageTotalLabel")
        self.page_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.page_label.setFixedWidth(28)
        self.page_label.setFixedHeight(26)
        self.next_page_btn = _rb_compact("", "Next page")
        self.next_page_btn.clicked.connect(self.goto_next)
        self.page_slider = QSlider(Qt.Horizontal)
        self.page_slider.setMinimum(1)
        self.page_slider.setEnabled(False)
        self.page_slider.setFixedWidth(92)
        self.page_slider.valueChanged.connect(lambda v: self.render_page(v-1))
        nav_tray, nav_tray_layout = _tray("mechanics")
        nav_tray_layout.addWidget(self.prev_page_btn)
        nav_tray_layout.addWidget(self.page_spin)
        nav_tray_layout.addWidget(self.page_label)
        nav_tray_layout.addWidget(self.next_page_btn)
        nav_tray_layout.addWidget(_sep())
        nav_tray_layout.addWidget(self.page_slider)
        ribbon_shell_layout.addWidget(nav_tray)

        # Group: Search
        self.pdf_search_box = QLineEdit()
        self.pdf_search_box.setObjectName("RibbonSearchInput")
        self.pdf_search_box.setPlaceholderText("Search PDF text…")
        self.pdf_search_box.setMinimumWidth(180)
        self.pdf_search_box.setMaximumWidth(280)
        self.pdf_search_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.pdf_search_box.returnPressed.connect(self.run_pdf_search)
        self.search_status_label = QLabel("")
        self.search_status_label.setObjectName("PageStatus")
        self.search_status_label.setAlignment(Qt.AlignCenter)
        self.search_status_label.setMinimumWidth(40)
        self.search_status_label.setFixedHeight(26)
        self.search_status_label.setVisible(False)
        self.search_prev_btn = _rb_compact("", "Previous search result")
        self.search_prev_btn.clicked.connect(self.goto_previous_search_result)
        self.search_prev_btn.setVisible(False)
        self.search_next_btn = _rb_compact("", "Next search result")
        self.search_next_btn.clicked.connect(self.goto_next_search_result)
        self.search_next_btn.setVisible(False)
        search_tray, search_tray_layout = _tray("search")
        search_tray_layout.addWidget(self.pdf_search_box)
        search_tray_layout.addWidget(self.search_prev_btn)
        search_tray_layout.addWidget(self.search_status_label)
        search_tray_layout.addWidget(self.search_next_btn)
        ribbon_shell_layout.addWidget(search_tray, 1)

        # Group: Annotate
        self.explain_btn = _rb("", "Generate an AI explanation for the current annotation", role="secondary")
        self.explain_btn.setFixedWidth(34)
        self.explain_btn.clicked.connect(self.explain_annotation)

        # Group: Session
        self.session_status_label = QLabel("Session: None")
        self.session_status_label.setObjectName("SessionPill")
        self.session_status_label.setAlignment(Qt.AlignCenter)
        self.session_status_label.setFixedHeight(28)
        self.session_status_label.setMinimumWidth(96)
        self.session_status_label.setMaximumWidth(148)
        self.session_status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.session_menu_btn = _rb("", "Start or manage the current reading session", role="secondary")
        self.session_menu_btn.setFixedWidth(38)
        self.session_menu_btn.clicked.connect(self._handle_session_button)
        self.more_btn = _rb("", "Open additional reader and utility actions", role="utility")
        self.more_btn.setFixedWidth(34)
        self.more_menu = QMenu(self)
        self.more_menu.aboutToShow.connect(self._rebuild_more_menu)
        self.more_btn.setMenu(self.more_menu)
        action_tray, action_tray_layout = _tray("workflow")
        action_tray_layout.addWidget(self.explain_btn)
        action_tray_layout.addWidget(self.session_status_label)
        action_tray_layout.addWidget(self.session_menu_btn)
        action_tray_layout.addWidget(self.more_btn)
        ribbon_shell_layout.addWidget(action_tray)

        self.ribbon_status_label = QLabel("No document open")
        self.ribbon_status_label.setObjectName("RibbonStatus")
        self.ribbon_status_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.ribbon_status_label.setFixedHeight(28)
        self.ribbon_status_label.setMinimumWidth(110)
        self.ribbon_status_label.setMaximumWidth(240)
        self.ribbon_status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.ribbon_status_label.setVisible(False)

        self.theme_btn = _rb("", "Toggle light and dark theme", role="utility")
        self.theme_btn.setProperty("pill", True)
        self.theme_btn.setProperty("mode", True)
        self.theme_btn.setFixedWidth(34)
        self.theme_btn.setCheckable(True)
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.inspector_toggle_btn = _rb("", "Show or hide the right annotation pane", role="utility")
        self.inspector_toggle_btn.setFixedWidth(34)
        self.inspector_toggle_btn.clicked.connect(self._toggle_inspector)
        self.focus_mode_btn = _rb("", "Focus Mode: hide interface chrome for focused reading", role="utility")
        self.focus_mode_btn.setFixedWidth(34)
        self.focus_mode_btn.setCheckable(True)
        self.focus_mode_btn.clicked.connect(self._toggle_focus_mode)
        self.reader_mode_btn = _rb("", "Switch to triage mode", role="secondary")
        self.reader_mode_btn.setProperty("modeSelector", True)
        self.reader_mode_btn.setFixedWidth(34)
        self.reader_mode_btn.clicked.connect(self._on_reader_mode_clicked)
        status_tray, status_tray_layout = _tray("status")
        status_tray_layout.addWidget(self.reader_mode_btn)
        status_tray_layout.addWidget(self.focus_mode_btn)
        status_tray_layout.addWidget(self.theme_btn)
        status_tray_layout.addWidget(self.inspector_toggle_btn)
        ribbon_shell_layout.addStretch(1)
        ribbon_shell_layout.addWidget(status_tray)

        # ── PDF label ─────────────────────────────────────────────────────────
        self.label = SelectableLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setScaledContents(False)

        self.pages_widget = QWidget()
        self.pages_widget.setObjectName("PageCanvas")
        self.pages_layout = QVBoxLayout(self.pages_widget)
        self.pages_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.pages_layout.setContentsMargins(16, 16, 16, 16)
        self.pages_layout.addWidget(self.label)

        self.pages_scroll = QScrollArea()
        self.pages_scroll.setWidget(self.pages_widget)
        self.pages_scroll.setWidgetResizable(True)
        self.pages_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.pages_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.pages_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.pages_scroll.viewport().installEventFilter(self)
        self.focus_inspector_handle = QToolButton(self.pages_scroll)
        self.focus_inspector_handle.setObjectName("FocusInspectorHandle")
        self.focus_inspector_handle.setAutoRaise(True)
        self.focus_inspector_handle.setFixedSize(26, 48)
        self.focus_inspector_handle.setToolTip("Show annotation pane")
        self.focus_inspector_handle.clicked.connect(self._open_focus_annotation_panel)
        self.focus_inspector_handle.hide()
        self.label.installEventFilter(self)

        # ── Library panel (left, collapsible) ────────────────────────────────
        self.library_panel = QWidget()
        self.library_panel.setObjectName("LibraryPanel")
        self.library_panel.setMinimumWidth(240)
        self.library_panel.setMinimumHeight(0)
        lib_layout = QVBoxLayout(self.library_panel)
        lib_layout.setContentsMargins(10, 10, 10, 10)
        lib_layout.setSpacing(8)
        library_grip_row = QHBoxLayout()
        library_grip_row.setContentsMargins(0, 0, 0, 0)
        library_grip_row.addStretch(1)
        self.library_resize_grip = PanelResizeGrip("left", self.library_panel)
        self.library_resize_grip.setObjectName("PanelResizeGrip")
        self.library_resize_grip.setFixedSize(24, 16)
        library_grip_row.addWidget(self.library_resize_grip)
        lib_layout.addLayout(library_grip_row)
        project_header = QLabel("<b>Project Space</b>")
        project_header.setObjectName("SectionHeader")
        lib_layout.addWidget(project_header)
        project_row = QHBoxLayout()
        project_row.setContentsMargins(0, 0, 0, 0)
        project_row.setSpacing(6)
        self.project_combo = QComboBox()
        self.project_combo.setObjectName("ScopeSelector")
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        project_row.addWidget(self.project_combo, 1)
        new_project_btn = _rb("New", "Create a new project")
        self.new_project_menu = QMenu(self)
        self.new_project_menu.addAction("Empty Project...", self.create_project)
        self.new_project_menu.addAction("From Staged Sources...", self.create_project_from_staged_sources)
        self.new_project_menu.addSeparator()
        self.new_project_menu.addAction("Add Existing Screened Source...", self.add_existing_screened_source_to_project)
        new_project_btn.setMenu(self.new_project_menu)
        project_row.addWidget(new_project_btn)
        lib_layout.addLayout(project_row)
        self.scope_hint_label = QLabel("Scope: all available project records")
        self.scope_hint_label.setObjectName("MetaLabel")
        self.scope_hint_label.setWordWrap(True)
        lib_layout.addWidget(self.scope_hint_label)
        documents_header = QLabel("<b>Documents</b>")
        documents_header.setObjectName("SectionHeader")
        lib_layout.addWidget(documents_header)
        current_source_label = QLabel("Current Source")
        current_source_label.setObjectName("FieldLabel")
        lib_layout.addWidget(current_source_label)
        self.active_record_card = QFrame()
        self.active_record_card.setObjectName("ActiveRecordCard")
        self.active_record_card.setFixedHeight(82)
        self.active_record_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.active_record_card.installEventFilter(self)
        active_record_layout = QVBoxLayout(self.active_record_card)
        active_record_layout.setContentsMargins(10, 9, 10, 9)
        active_record_layout.setSpacing(4)
        self.active_record_title_label = QLabel("No source open")
        self.active_record_title_label.setObjectName("ActiveRecordTitle")
        self.active_record_title_label.setWordWrap(False)
        self.active_record_title_label.setTextInteractionFlags(Qt.NoTextInteraction)
        self.active_record_title_label.setFixedHeight(34)
        active_record_layout.addWidget(self.active_record_title_label)
        self.active_record_meta_label = QLabel("Open a source in the reader to pin it here.")
        self.active_record_meta_label.setObjectName("ActiveRecordMeta")
        self.active_record_meta_label.setWordWrap(False)
        self.active_record_meta_label.setTextInteractionFlags(Qt.NoTextInteraction)
        self.active_record_meta_label.setFixedHeight(18)
        active_record_layout.addWidget(self.active_record_meta_label)
        lib_layout.addWidget(self.active_record_card)
        self.doc_search_box = QLineEdit()
        self.doc_search_box.setObjectName("LibrarySearchInput")
        self.doc_search_box.setPlaceholderText("Search documents…")
        self.doc_search_box.textChanged.connect(self._refresh_doc_list)
        lib_layout.addWidget(self.doc_search_box)
        self.source_library_filter = QComboBox()
        self.source_library_filter.setObjectName("LibraryFilter")
        self._configure_source_filter_options(preserve_value=False)
        self.source_library_filter.currentIndexChanged.connect(self._refresh_doc_list)
        lib_layout.addWidget(self.source_library_filter)
        doc_controls = QHBoxLayout()
        doc_controls.setContentsMargins(0, 0, 0, 0)
        doc_controls.setSpacing(6)
        self.doc_sort_combo = QComboBox()
        self.doc_sort_combo.addItem("Recent", "updated_desc")
        self.doc_sort_combo.addItem("Title", "title_asc")
        self.doc_sort_combo.addItem("Priority", "priority_desc")
        self.doc_sort_combo.currentIndexChanged.connect(self._refresh_doc_list)
        self.doc_status_filter = QComboBox()
        self.doc_status_filter.addItem("All statuses", "")
        self.doc_status_filter.addItem("New", "new")
        self.doc_status_filter.addItem("Reading", "reading")
        self.doc_status_filter.addItem("Reviewed", "reviewed")
        self.doc_status_filter.addItem("Archived", "archived")
        self.doc_status_filter.currentIndexChanged.connect(self._refresh_doc_list)
        doc_controls.addWidget(self.doc_sort_combo, 1)
        doc_controls.addWidget(self.doc_status_filter, 1)
        lib_layout.addLayout(doc_controls)
        self.doc_list_hint = QLabel("Browse project sources and records.")
        self.doc_list_hint.setObjectName("MetaLabel")
        self.doc_list_hint.setWordWrap(True)
        lib_layout.addWidget(self.doc_list_hint)
        self.doc_list = QListWidget()
        self.doc_list.setObjectName("InfoList")
        self.doc_list.setWordWrap(False)
        self.doc_list.setUniformItemSizes(False)
        self.doc_list.setTextElideMode(Qt.ElideRight)
        self.doc_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.doc_list.customContextMenuRequested.connect(self._open_doc_list_menu)
        self.doc_list.itemClicked.connect(self._on_doc_clicked)
        self.doc_list.viewport().installEventFilter(self)
        lib_layout.addWidget(self.doc_list)
        lib_layout.addWidget(self._hsep())
        organizer_header = QHBoxLayout()
        organizer_header.setContentsMargins(0, 0, 0, 0)
        organizer_header.setSpacing(6)
        organizer_label = QLabel("<b>Source Organizer</b>")
        organizer_label.setObjectName("SectionHeader")
        organizer_header.addWidget(organizer_label)
        organizer_header.addStretch()
        self.organizer_toggle_btn = _rb("Hide", "Show or hide the source organizer")
        self.organizer_toggle_btn.setFixedWidth(56)
        self.organizer_toggle_btn.clicked.connect(self._toggle_organizer)
        organizer_header.addWidget(self.organizer_toggle_btn)
        lib_layout.addLayout(organizer_header)
        self.organizer_panel = QWidget()
        self.organizer_panel.setObjectName("OrganizerPanel")
        organizer_layout = QVBoxLayout(self.organizer_panel)
        organizer_layout.setContentsMargins(0, 0, 0, 0)
        organizer_layout.setSpacing(6)
        record_row = QHBoxLayout()
        record_row.setContentsMargins(0, 0, 0, 0)
        record_row.setSpacing(6)
        self.annotation_record_combo = QComboBox()
        self.annotation_record_combo.setObjectName("OrganizerInput")
        self.annotation_record_combo.currentIndexChanged.connect(self._on_annotation_record_changed)
        record_row.addWidget(self.annotation_record_combo, 1)
        new_record_btn = _rb("New Record", "Create a fresh annotation record for this PDF in the current project")
        new_record_btn.setObjectName("OrganizerButton")
        new_record_btn.clicked.connect(self.create_fresh_annotation_record)
        record_row.addWidget(new_record_btn)
        organizer_layout.addLayout(record_row)
        self.doc_title_edit = QLineEdit()
        self.doc_title_edit.setObjectName("OrganizerInput")
        self.doc_title_edit.setPlaceholderText("Title")
        self.doc_title_edit.editingFinished.connect(self._autosave_document_metadata)
        organizer_layout.addWidget(self.doc_title_edit)
        self.doc_author_edit = QLineEdit()
        self.doc_author_edit.setObjectName("OrganizerInput")
        self.doc_author_edit.setPlaceholderText("Author(s)")
        self.doc_author_edit.editingFinished.connect(self._autosave_document_metadata)
        organizer_layout.addWidget(self.doc_author_edit)
        org_row = QHBoxLayout()
        org_row.setContentsMargins(0, 0, 0, 0)
        org_row.setSpacing(6)
        self.doc_year_edit = QLineEdit()
        self.doc_year_edit.setObjectName("OrganizerInput")
        self.doc_year_edit.setPlaceholderText("Year")
        self.doc_year_edit.editingFinished.connect(self._autosave_document_metadata)
        org_row.addWidget(self.doc_year_edit, 1)
        self.doc_status_combo = QComboBox()
        self.doc_status_combo.setObjectName("OrganizerInput")
        self.doc_status_combo.addItems(["new", "reading", "reviewed", "archived"])
        self.doc_status_combo.currentIndexChanged.connect(self._autosave_document_metadata)
        self.doc_priority_combo = QComboBox()
        self.doc_priority_combo.setObjectName("OrganizerInput")
        self.doc_priority_combo.addItems(["1", "2", "3", "4", "5"])
        self.doc_priority_combo.setCurrentText("3")
        self.doc_priority_combo.currentIndexChanged.connect(self._autosave_document_metadata)
        org_row.addWidget(self.doc_status_combo, 1)
        org_row.addWidget(self.doc_priority_combo, 1)
        organizer_layout.addLayout(org_row)
        self.doc_type_edit = QLineEdit()
        self.doc_type_edit.setObjectName("OrganizerInput")
        self.doc_type_edit.setPlaceholderText("Reading type (paper, book, memo…)")
        self.doc_type_edit.editingFinished.connect(self._autosave_document_metadata)
        organizer_layout.addWidget(self.doc_type_edit)
        self.doc_source_edit = QLineEdit()
        self.doc_source_edit.setObjectName("OrganizerInput")
        self.doc_source_edit.setPlaceholderText("Journal / book / source")
        self.doc_source_edit.editingFinished.connect(self._autosave_document_metadata)
        organizer_layout.addWidget(self.doc_source_edit)
        citation_row = QHBoxLayout()
        citation_row.setContentsMargins(0, 0, 0, 0)
        citation_row.setSpacing(6)
        self.doc_volume_edit = QLineEdit()
        self.doc_volume_edit.setObjectName("OrganizerInput")
        self.doc_volume_edit.setPlaceholderText("Volume")
        self.doc_volume_edit.editingFinished.connect(self._autosave_document_metadata)
        self.doc_issue_edit = QLineEdit()
        self.doc_issue_edit.setObjectName("OrganizerInput")
        self.doc_issue_edit.setPlaceholderText("Issue")
        self.doc_issue_edit.editingFinished.connect(self._autosave_document_metadata)
        self.doc_pages_edit = QLineEdit()
        self.doc_pages_edit.setObjectName("OrganizerInput")
        self.doc_pages_edit.setPlaceholderText("Pages")
        self.doc_pages_edit.editingFinished.connect(self._autosave_document_metadata)
        citation_row.addWidget(self.doc_volume_edit, 1)
        citation_row.addWidget(self.doc_issue_edit, 1)
        citation_row.addWidget(self.doc_pages_edit, 1)
        organizer_layout.addLayout(citation_row)
        self.doc_doi_edit = QLineEdit()
        self.doc_doi_edit.setObjectName("OrganizerInput")
        self.doc_doi_edit.setPlaceholderText("DOI")
        self.doc_doi_edit.editingFinished.connect(self._autosave_document_metadata)
        organizer_layout.addWidget(self.doc_doi_edit)
        self.doc_url_edit = QLineEdit()
        self.doc_url_edit.setObjectName("OrganizerInput")
        self.doc_url_edit.setPlaceholderText("URL")
        self.doc_url_edit.editingFinished.connect(self._autosave_document_metadata)
        organizer_layout.addWidget(self.doc_url_edit)
        self.doc_publisher_edit = QLineEdit()
        self.doc_publisher_edit.setObjectName("OrganizerInput")
        self.doc_publisher_edit.setPlaceholderText("Publisher")
        self.doc_publisher_edit.editingFinished.connect(self._autosave_document_metadata)
        organizer_layout.addWidget(self.doc_publisher_edit)
        self.doc_path_label = QLabel("Select a document to edit its metadata.")
        self.doc_path_label.setWordWrap(True)
        self.doc_path_label.setObjectName("MetaLabel")
        organizer_layout.addWidget(self.doc_path_label)
        self.save_source_details_btn = _rb("Save Source Details", "Save document organization details", role="contextual")
        self.save_source_details_btn.setObjectName("OrganizerButton")
        self.save_source_details_btn.setProperty("buttonRole", "primary")
        self.save_source_details_btn.clicked.connect(lambda: self.save_document_metadata(show_feedback=True))
        organizer_layout.addWidget(self.save_source_details_btn)
        self.organizer_status_label = QLabel("Changes autosave when fields lose focus.")
        self.organizer_status_label.setObjectName("OrganizerStatus")
        self.organizer_status_label.setProperty("statusState", "idle")
        self.organizer_status_label.setWordWrap(True)
        organizer_layout.addWidget(self.organizer_status_label)
        lib_layout.addWidget(self.organizer_panel)
        self.organizer_panel.setVisible(False)
        self._load_projects()
        self._refresh_doc_list()
        self.library_scroll = QScrollArea()
        self.library_scroll.setWidget(self.library_panel)
        self.library_scroll.setWidgetResizable(True)
        self.library_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.library_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.library_scroll.setFrameShape(QFrame.NoFrame)
        self.library_scroll.setMinimumWidth(240)
        self.library_scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)

        # ── Annotation panel (right) ──────────────────────────────────────────
        right_panel = QWidget()
        right_panel.setObjectName("InspectorPanel")
        right_panel.setMinimumWidth(260)
        right_panel.setMaximumWidth(520)
        right_panel.setMinimumHeight(0)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(6)
        right_grip_row = QHBoxLayout()
        right_grip_row.setContentsMargins(0, 0, 0, 0)
        self.inspector_resize_grip = PanelResizeGrip("right", right_panel)
        self.inspector_resize_grip.setObjectName("PanelResizeGrip")
        self.inspector_resize_grip.setFixedSize(24, 16)
        right_grip_row.addWidget(self.inspector_resize_grip)
        right_grip_row.addStretch(1)
        right_layout.addLayout(right_grip_row)

        self.reader_mode_status_label = QLabel("Mode: Read")
        self.reader_mode_status_label.setObjectName("WorkspaceStatusLabel")
        self.reader_mode_status_label.setProperty("statusState", "idle")
        self.reader_mode_status_label.setWordWrap(True)
        right_layout.addWidget(self.reader_mode_status_label)

        self.triage_panel = QWidget()
        self.triage_panel.setObjectName("TriageInclusionPanel")
        self.triage_panel.setAttribute(Qt.WA_StyledBackground, True)
        self.triage_panel.setAutoFillBackground(True)
        triage_layout = QVBoxLayout(self.triage_panel)
        triage_layout.setContentsMargins(8, 8, 8, 8)
        triage_layout.setSpacing(6)
        triage_header = QLabel("<b>Inclusion metadata</b>")
        triage_header.setObjectName("WorkspaceSectionHeader")
        triage_layout.addWidget(triage_header)
        self.triage_panel_hint = QLabel("Screen this source before committing it to a project.")
        self.triage_panel_hint.setObjectName("WorkspaceStatusLabel")
        self.triage_panel_hint.setProperty("statusState", "idle")
        self.triage_panel_hint.setWordWrap(True)
        triage_layout.addWidget(self.triage_panel_hint)
        self.triage_status_combo = QComboBox()
        self.triage_status_combo.addItem("Candidate", "candidate")
        self.triage_status_combo.addItem("Included", "included")
        self.triage_status_combo.addItem("Excluded", "excluded")
        self.triage_status_combo.addItem("Deferred", "deferred")
        self.triage_status_combo.currentIndexChanged.connect(self._mark_triage_metadata_dirty)
        triage_layout.addWidget(self.triage_status_combo)
        self.triage_scope_combo = QComboBox()
        self.triage_scope_combo.addItem("No relevance scope", "")
        self.triage_scope_combo.addItem("Central", "central")
        self.triage_scope_combo.addItem("Supporting", "supporting")
        self.triage_scope_combo.addItem("Methodological", "methodological")
        self.triage_scope_combo.addItem("Comparative", "comparative")
        self.triage_scope_combo.addItem("Peripheral", "peripheral")
        self.triage_scope_combo.currentIndexChanged.connect(self._mark_triage_metadata_dirty)
        triage_layout.addWidget(self.triage_scope_combo)
        self.triage_depth_combo = QComboBox()
        self.triage_depth_combo.addItem("Screening depth unset", "")
        self.triage_depth_combo.addItem("Abstract", "abstract")
        self.triage_depth_combo.addItem("Skim", "skim")
        self.triage_depth_combo.addItem("Targeted", "targeted")
        self.triage_depth_combo.addItem("Full", "full")
        self.triage_depth_combo.currentIndexChanged.connect(self._mark_triage_metadata_dirty)
        triage_layout.addWidget(self.triage_depth_combo)
        self.triage_reasoning_edit = QTextEdit()
        self.triage_reasoning_edit.setObjectName("AnnotationNoteInput")
        self.triage_reasoning_edit.setPlaceholderText("Inclusion or exclusion reasoning...")
        self.triage_reasoning_edit.setMaximumHeight(84)
        self.triage_reasoning_edit.setTabChangesFocus(True)
        self.triage_reasoning_edit.textChanged.connect(self._mark_triage_metadata_dirty)
        triage_layout.addWidget(self.triage_reasoning_edit)
        self.triage_role_note_edit = QTextEdit()
        self.triage_role_note_edit.setObjectName("AnnotationNoteInput")
        self.triage_role_note_edit.setPlaceholderText("Project role note...")
        self.triage_role_note_edit.setMaximumHeight(72)
        self.triage_role_note_edit.setTabChangesFocus(True)
        self.triage_role_note_edit.textChanged.connect(self._mark_triage_metadata_dirty)
        triage_layout.addWidget(self.triage_role_note_edit)
        self.triage_save_btn = QPushButton("Save Inclusion Metadata")
        self.triage_save_btn.setObjectName("AccentButton")
        self.triage_save_btn.clicked.connect(self.save_triage_metadata)
        triage_layout.addWidget(self.triage_save_btn)
        self.triage_panel.setVisible(False)
        right_layout.addWidget(self.triage_panel)

        self.project_context_panel = QWidget()
        self.project_context_panel.setObjectName("ProjectContextPanel")
        self.project_context_panel.setAttribute(Qt.WA_StyledBackground, True)
        self.project_context_panel.setAutoFillBackground(True)
        project_context_layout = QVBoxLayout(self.project_context_panel)
        project_context_layout.setContentsMargins(8, 8, 8, 8)
        project_context_layout.setSpacing(6)
        project_context_header_row = QHBoxLayout()
        project_context_header_row.setContentsMargins(0, 0, 0, 0)
        project_context_header_row.setSpacing(6)
        project_context_header = QLabel("<b>Project context</b>")
        project_context_header.setObjectName("WorkspaceSectionHeader")
        project_context_header_row.addWidget(project_context_header, 1)
        self.project_context_toggle_btn = QPushButton("Hide")
        self.project_context_toggle_btn.setObjectName("RibbonButton")
        self.project_context_toggle_btn.setFixedWidth(56)
        self.project_context_toggle_btn.clicked.connect(self._toggle_project_context_panel)
        project_context_header_row.addWidget(self.project_context_toggle_btn)
        project_context_layout.addLayout(project_context_header_row)
        self.project_context_status = QLabel("Open a project source to show context.")
        self.project_context_status.setObjectName("WorkspaceStatusLabel")
        self.project_context_status.setProperty("statusState", "idle")
        self.project_context_status.setWordWrap(True)
        project_context_layout.addWidget(self.project_context_status)
        self.project_context_body = QWidget()
        project_context_body_layout = QVBoxLayout(self.project_context_body)
        project_context_body_layout.setContentsMargins(0, 0, 0, 0)
        project_context_body_layout.setSpacing(6)
        self.project_scope_label = QLabel("")
        self.project_scope_label.setObjectName("MetaLabel")
        self.project_scope_label.setWordWrap(True)
        project_context_body_layout.addWidget(self.project_scope_label)
        self.project_central_sources_label = QLabel("")
        self.project_central_sources_label.setObjectName("MetaLabel")
        self.project_central_sources_label.setWordWrap(True)
        project_context_body_layout.addWidget(self.project_central_sources_label)
        self.project_current_role_label = QLabel("")
        self.project_current_role_label.setObjectName("MetaLabel")
        self.project_current_role_label.setWordWrap(True)
        project_context_body_layout.addWidget(self.project_current_role_label)
        project_context_layout.addWidget(self.project_context_body)
        self.project_context_collapsed = False
        self.project_context_panel.setVisible(False)
        right_layout.addWidget(self.project_context_panel)

        saved_annotations_panel = QWidget()
        saved_annotations_panel.setObjectName("SavedAnnotationsPanel")
        saved_annotations_panel.setAttribute(Qt.WA_StyledBackground, True)
        saved_annotations_panel.setAutoFillBackground(True)
        saved_annotations_panel.setMinimumHeight(0)
        saved_annotations_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)
        self.saved_annotations_panel = saved_annotations_panel
        saved_annotations_layout = QVBoxLayout(saved_annotations_panel)
        saved_annotations_layout.setContentsMargins(8, 8, 8, 8)
        saved_annotations_layout.setSpacing(6)

        workspace_panel = QWidget()
        workspace_panel.setObjectName("AnnotationWorkspacePanel")
        workspace_panel.setAttribute(Qt.WA_StyledBackground, True)
        workspace_panel.setAutoFillBackground(True)
        workspace_panel.setMinimumHeight(0)
        workspace_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)
        self.annotation_workspace_panel = workspace_panel
        workspace_layout = QVBoxLayout(workspace_panel)
        workspace_layout.setContentsMargins(8, 8, 8, 8)
        workspace_layout.setSpacing(6)

        saved_annotations_header = QLabel("<b>Saved annotations</b>")
        saved_annotations_header.setObjectName("SavedSectionHeader")
        saved_annotations_layout.addWidget(saved_annotations_header)
        self.annotation_list_hint = QLabel("Annotations for the source currently open in the reader.")
        self.annotation_list_hint.setObjectName("MetaLabel")
        self.annotation_list_hint.setWordWrap(True)
        saved_annotations_layout.addWidget(self.annotation_list_hint)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search annotations…")
        self.search_box.textChanged.connect(self._filter_annotations)
        saved_annotations_layout.addWidget(self.search_box)
        self.annotation_scope_combo = QComboBox()
        self.annotation_scope_combo.addItem("Page 1", "page")
        self.annotation_scope_combo.addItem("This document", "document")
        self.annotation_scope_combo.addItem("Project", "project")
        self.annotation_scope_combo.currentIndexChanged.connect(self.load_annotations)
        saved_annotations_layout.addWidget(self.annotation_scope_combo)
        annotation_controls = QHBoxLayout()
        annotation_controls.setContentsMargins(0, 0, 0, 0)
        annotation_controls.setSpacing(6)
        self.annotation_type_filter_combo = QComboBox()
        self.annotation_type_filter_combo.addItem("All types", "")
        self.annotation_type_filter_combo.addItem("Quote", "quote")
        self.annotation_type_filter_combo.addItem("Paraphrase", "paraphrase")
        self.annotation_type_filter_combo.addItem("Interpretation", "interpretation")
        self.annotation_type_filter_combo.addItem("Synthesis", "synthesis")
        self.annotation_type_filter_combo.currentIndexChanged.connect(self._filter_annotations)
        annotation_controls.addWidget(self.annotation_type_filter_combo, 1)
        self.annotation_sort_combo = QComboBox()
        self.annotation_sort_combo.addItem("Recent", "recent")
        self.annotation_sort_combo.addItem("Page", "page")
        self.annotation_sort_combo.addItem("Type", "type")
        self.annotation_sort_combo.currentIndexChanged.connect(self.load_annotations)
        annotation_controls.addWidget(self.annotation_sort_combo, 1)
        saved_annotations_layout.addLayout(annotation_controls)
        self.annotation_tag_filter_combo = QComboBox()
        self.annotation_tag_filter_combo.addItem("All tags", "")
        self.annotation_tag_filter_combo.currentIndexChanged.connect(self._filter_annotations)
        saved_annotations_layout.addWidget(self.annotation_tag_filter_combo)

        self.annotation_list = QListWidget()
        self.annotation_list.setObjectName("InfoList")
        self.annotation_list.setWordWrap(True)
        self.annotation_list.setUniformItemSizes(False)
        self.annotation_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.annotation_list.customContextMenuRequested.connect(self._open_annotation_list_menu)
        self.annotation_list.itemClicked.connect(self.on_annotation_clicked)
        self.annotation_list.itemDoubleClicked.connect(self.on_annotation_edit_requested)
        self.annotation_list.setMinimumHeight(36)
        saved_annotations_layout.addWidget(self.annotation_list, 1)
        workspace_header_row = QHBoxLayout()
        workspace_header_row.setContentsMargins(0, 0, 0, 0)
        workspace_header_row.setSpacing(6)
        workspace_header = QLabel("<b>Annotation workspace</b>")
        workspace_header.setObjectName("WorkspaceSectionHeader")
        workspace_header_row.addWidget(workspace_header, 1)
        self.annotation_workspace_toggle_btn = _rb("Hide", "Show or hide the annotation workspace")
        self.annotation_workspace_toggle_btn.setFixedWidth(56)
        self.annotation_workspace_toggle_btn.clicked.connect(self._toggle_annotation_workspace)
        workspace_header_row.addWidget(self.annotation_workspace_toggle_btn)
        workspace_layout.addLayout(workspace_header_row)
        self.annotation_state_label = QLabel("Draft state: ready for a new annotation")
        self.annotation_state_label.setObjectName("WorkspaceStatusLabel")
        self.annotation_state_label.setProperty("statusState", "idle")
        self.annotation_state_label.setWordWrap(True)
        workspace_layout.addWidget(self.annotation_state_label)

        type_label = QLabel("Type")
        type_label.setObjectName("FieldLabel")
        workspace_layout.addWidget(type_label)
        self.annotation_type_combo = QComboBox()
        self.annotation_type_combo.addItem("Paraphrase", "paraphrase")
        self.annotation_type_combo.addItem("Interpretation", "interpretation")
        self.annotation_type_combo.addItem("Direct quote", "quote")
        self.annotation_type_combo.addItem("Synthesis", "synthesis")
        self.annotation_type_combo.currentIndexChanged.connect(self._update_annotation_type_ui)
        self.annotation_type_combo.setObjectName("AnnotationTypeControl")
        workspace_layout.addWidget(self.annotation_type_combo)
        self.annotation_type_badge = QLabel("Paraphrase")
        self.annotation_type_badge.setObjectName("AnnotationTypeBadge")
        workspace_layout.addWidget(self.annotation_type_badge)
        self.annotation_type_hint = QLabel("")
        self.annotation_type_hint.setObjectName("MetaLabel")
        self.annotation_type_hint.setWordWrap(True)
        workspace_layout.addWidget(self.annotation_type_hint)
        tags_label = QLabel("Tags")
        tags_label.setObjectName("FieldLabel")
        workspace_layout.addWidget(tags_label)
        tag_row = QHBoxLayout()
        tag_row.setContentsMargins(0, 0, 0, 0)
        tag_row.setSpacing(6)
        self.annotation_tag_input = QLineEdit()
        self.annotation_tag_input.setPlaceholderText("Add tags and press Enter…")
        self.annotation_tag_input.returnPressed.connect(self._add_tags_from_input)
        tag_row.addWidget(self.annotation_tag_input, 1)
        self.annotation_add_tag_btn = _rb("Add", "Add tags to this annotation")
        self.annotation_add_tag_btn.setFixedWidth(52)
        self.annotation_add_tag_btn.clicked.connect(self._add_tags_from_input)
        tag_row.addWidget(self.annotation_add_tag_btn)
        workspace_layout.addLayout(tag_row)
        self.annotation_tags_chip_panel = QWidget()
        self.annotation_tags_chip_layout = QHBoxLayout(self.annotation_tags_chip_panel)
        self.annotation_tags_chip_layout.setContentsMargins(0, 0, 0, 0)
        self.annotation_tags_chip_layout.setSpacing(6)
        workspace_layout.addWidget(self.annotation_tags_chip_panel)
        suggested_tags_label = QLabel("Suggested tags")
        suggested_tags_label.setObjectName("FieldLabel")
        workspace_layout.addWidget(suggested_tags_label)
        self.annotation_suggested_tags_panel = QWidget()
        self.annotation_suggested_tags_layout = QGridLayout(self.annotation_suggested_tags_panel)
        self.annotation_suggested_tags_layout.setContentsMargins(0, 0, 0, 0)
        self.annotation_suggested_tags_layout.setHorizontalSpacing(6)
        self.annotation_suggested_tags_layout.setVerticalSpacing(6)
        workspace_layout.addWidget(self.annotation_suggested_tags_panel)

        writing_project_label = QLabel("Writing project")
        writing_project_label.setObjectName("FieldLabel")
        workspace_layout.addWidget(writing_project_label)
        writing_project_row = QHBoxLayout()
        writing_project_row.setContentsMargins(0, 0, 0, 0)
        writing_project_row.setSpacing(6)
        self.annotation_writing_project_combo = QComboBox()
        self.annotation_writing_project_combo.currentIndexChanged.connect(self._sync_annotation_writing_project_selection)
        writing_project_row.addWidget(self.annotation_writing_project_combo, 1)
        new_writing_project_btn = _rb("New", "Create a writing project for composition-focused annotations")
        new_writing_project_btn.clicked.connect(self.create_writing_project)
        writing_project_row.addWidget(new_writing_project_btn)
        workspace_layout.addLayout(writing_project_row)

        sel_label = QLabel("Selected text")
        sel_label.setObjectName("FieldLabel")
        workspace_layout.addWidget(sel_label)
        self.selected_text_edit = QTextEdit()
        self.selected_text_edit.setObjectName("SourceAnchorText")
        self.selected_text_edit.setPlaceholderText("Drag on PDF to populate…")
        self.selected_text_edit.setMaximumHeight(80)
        self.selected_text_edit.setReadOnly(True)
        self.selected_text_edit.setTabChangesFocus(True)
        self.selected_text_edit.textChanged.connect(self._update_toolbar_context)
        workspace_layout.addWidget(self.selected_text_edit)

        note_label = QLabel("Note")
        note_label.setObjectName("FieldLabel")
        workspace_layout.addWidget(note_label)
        self.note_edit = QTextEdit()
        self.note_edit.setObjectName("AnnotationNoteInput")
        self.note_edit.setMaximumHeight(80)
        self.note_edit.setTabChangesFocus(True)
        workspace_layout.addWidget(self.note_edit)

        ai_label = QLabel("AI explanation")
        ai_label.setObjectName("FieldLabel")
        workspace_layout.addWidget(ai_label)
        self.ai_explanation_edit = QTextEdit()
        self.ai_explanation_edit.setReadOnly(True)
        self.ai_explanation_edit.setPlaceholderText("Generated explanations will appear here…")
        self.ai_explanation_edit.setMaximumHeight(100)
        self.ai_explanation_edit.setObjectName("AIOutput")
        self.ai_explanation_edit.setTabChangesFocus(True)
        workspace_layout.addWidget(self.ai_explanation_edit)
        self.explain_hint_label = QLabel("Explain attaches AI output to a saved annotation. Draft annotations are saved first.")
        self.explain_hint_label.setObjectName("MetaLabel")
        self.explain_hint_label.setWordWrap(True)
        workspace_layout.addWidget(self.explain_hint_label)

        conf_label = QLabel("Confidence")
        conf_label.setObjectName("FieldLabel")
        workspace_layout.addWidget(conf_label)
        self.confidence_combo = QComboBox()
        self.confidence_combo.setObjectName("ConfidenceControl")
        self.confidence_combo.addItems(["low", "medium", "high"])
        self.confidence_combo.setCurrentText("medium")
        workspace_layout.addWidget(self.confidence_combo)
        annotation_btn_row = QHBoxLayout()
        annotation_btn_row.setContentsMargins(0, 0, 0, 0)
        annotation_btn_row.setSpacing(6)
        self.save_annotation_btn = QPushButton("Save Annotation")
        self.save_annotation_btn.setObjectName("AccentButton")
        self.save_annotation_btn.clicked.connect(self._save_annotation_from_button)
        annotation_btn_row.addWidget(self.save_annotation_btn, 1)
        workspace_layout.addLayout(annotation_btn_row)
        workspace_layout.addStretch()

        self.right_panel_splitter = QSplitter(Qt.Vertical)
        self.right_panel_splitter.setObjectName("InspectorSplitter")
        self.right_panel_splitter.setChildrenCollapsible(True)
        self.right_panel_splitter.setHandleWidth(18)
        self.right_panel_splitter.setMinimumHeight(0)
        self.right_panel_splitter.addWidget(saved_annotations_panel)
        self.right_panel_splitter.addWidget(workspace_panel)
        self.right_panel_splitter.setCollapsible(0, False)
        self.right_panel_splitter.setCollapsible(1, True)
        self.right_panel_splitter.setStretchFactor(0, 1)
        self.right_panel_splitter.setStretchFactor(1, 0)
        self.right_panel_splitter.setSizes([340, 420])
        self.right_panel_splitter.splitterMoved.connect(self._on_right_panel_splitter_moved)
        right_layout.addWidget(self.right_panel_splitter, 1)
        self.annotation_workspace_visible = True
        self.annotation_workspace_last_sizes = [340, 420]
        self.annotation_focus_mode = False
        self.annotation_saved_panel_compact = False
        self.inspector_scroll = QScrollArea()
        self.inspector_scroll.setWidget(right_panel)
        self.inspector_scroll.setWidgetResizable(True)
        self.inspector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.inspector_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.inspector_scroll.setFrameShape(QFrame.NoFrame)
        self.inspector_scroll.setMinimumWidth(260)
        self.inspector_scroll.setMaximumWidth(520)
        self.inspector_scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)

        # ── Main layout ───────────────────────────────────────────────────────
        container = QWidget()
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(ribbon)

        self.body_splitter = QSplitter(Qt.Horizontal)
        self.body_splitter.setChildrenCollapsible(False)
        self.body_splitter.addWidget(self.library_scroll)
        self.body_splitter.addWidget(self.pages_scroll)
        self.body_splitter.addWidget(self.inspector_scroll)
        self.body_splitter.setCollapsible(0, True)
        self.body_splitter.setCollapsible(1, False)
        self.body_splitter.setCollapsible(2, True)
        self.body_splitter.setStretchFactor(0, 0)
        self.body_splitter.setStretchFactor(1, 1)
        self.body_splitter.setStretchFactor(2, 0)
        self.body_splitter.setSizes([280, 900, 300])
        self._update_library_toggle_label()
        self._update_inspector_toggle_label()

        body_widget = QWidget()
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(self.body_splitter)
        root_layout.addWidget(body_widget, 1)

        self.setCentralWidget(container)
        self._load_writing_projects()
        self._load_system_annotation_tags()
        self._refresh_annotation_tag_chips()
        self._refresh_suggested_tag_chips()
        self._update_organizer_toggle_label()
        self._update_scope_hint()
        self._update_annotation_workspace_state()
        self._update_annotation_type_ui()
        self._apply_theme()
        self._update_ribbon_status()

    def _hsep(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setObjectName("PanelDivider")
        return line

    @staticmethod
    def _ui_font(point_size=10, weight=QFont.Weight.Normal):
        families = set(QFontDatabase.families())
        for family in ("Segoe UI Variable Text", "Segoe UI"):
            if family in families:
                font = QFont(family, point_size)
                break
        else:
            font = QApplication.font()
            font.setPointSize(point_size)
        font.setWeight(weight)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        # Prefer smoother grayscale rendering over hard grid-fitting; the latter
        # can make compact dark-mode toolbar text look jagged on some displays.
        font.setHintingPreference(QFont.HintingPreference.PreferVerticalHinting)
        return font

    def _pixmap_from_fitz(self, pix):
        fmt = QImage.Format_RGBA8888 if pix.alpha else QImage.Format_RGB888
        qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
        return QPixmap.fromImage(qimg)

    def _phosphor_icon(self, name: str, size: int = 18, color: QColor | None = None) -> QIcon:
        icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "icons", "phosphor", f"{name}.svg")
        icon_path = os.path.abspath(icon_path)
        stroke = color or QColor(getattr(self, "_theme_palette", {}).get("button_text", "#233142"))
        if not os.path.exists(icon_path):
            return QIcon()
        try:
            with open(icon_path, "r", encoding="utf-8") as fh:
                svg_text = fh.read().replace("currentColor", stroke.name())
            renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            return QIcon(pixmap)
        except Exception:
            return QIcon(icon_path)

    def _toolbar_icon(self, name: str, size: int = 18, color: QColor | None = None) -> QIcon:
        return self._phosphor_icon(name, size=size, color=color)

    def _apply_toolbar_icons(self):
        palette = getattr(self, "_theme_palette", {})
        icon_color = QColor(palette.get("button_text", "#233142"))
        utility_color = QColor(palette.get("muted", "#6a798b"))
        accent_color = QColor(palette.get("accent_text", palette.get("button_text", "#233142")))
        if hasattr(self, "library_toggle_btn"):
            self.library_toggle_btn.setIcon(self._toolbar_icon("sidebar", color=icon_color))
            self.library_toggle_btn.setIconSize(QSize(16, 16))
        if hasattr(self, "inspector_toggle_btn"):
            self.inspector_toggle_btn.setIcon(self._toolbar_icon("sidebar-right", color=utility_color))
            self.inspector_toggle_btn.setIconSize(QSize(16, 16))
        if hasattr(self, "focus_mode_btn"):
            focus_color = accent_color if getattr(self, "focus_mode", False) else utility_color
            self.focus_mode_btn.setIcon(self._toolbar_icon("eye", color=focus_color))
            self.focus_mode_btn.setIconSize(QSize(16, 16))
        if hasattr(self, "reader_mode_btn"):
            mode = getattr(self, "reader_mode", "full")
            mode_icon = "book-open" if mode == "triage" else "clipboard-text"
            mode_color = accent_color if mode == "triage" else icon_color
            self.reader_mode_btn.setIcon(self._toolbar_icon(mode_icon, color=mode_color))
            self.reader_mode_btn.setIconSize(QSize(16, 16))
        if hasattr(self, "focus_inspector_handle"):
            self.focus_inspector_handle.setIcon(self._toolbar_icon("dots-six-vertical", color=utility_color))
            self.focus_inspector_handle.setIconSize(QSize(14, 14))
        if hasattr(self, "prev_page_btn"):
            self.prev_page_btn.setIcon(self._toolbar_icon("caret-left", color=icon_color))
            self.prev_page_btn.setIconSize(QSize(16, 16))
        if hasattr(self, "next_page_btn"):
            self.next_page_btn.setIcon(self._toolbar_icon("caret-right", color=icon_color))
            self.next_page_btn.setIconSize(QSize(16, 16))
        if hasattr(self, "search_prev_btn"):
            self.search_prev_btn.setIcon(self._toolbar_icon("caret-left", color=utility_color))
            self.search_prev_btn.setIconSize(QSize(14, 14))
        if hasattr(self, "search_next_btn"):
            self.search_next_btn.setIcon(self._toolbar_icon("caret-right", color=utility_color))
            self.search_next_btn.setIconSize(QSize(14, 14))
        if hasattr(self, "open_pdf_btn"):
            self.open_pdf_btn.setIcon(self._toolbar_icon("plus", color=icon_color))
            self.open_pdf_btn.setIconSize(QSize(16, 16))
        if hasattr(self, "explain_btn"):
            explain_color = accent_color if self.explain_btn.property("role") == "contextual" else icon_color
            self.explain_btn.setIcon(self._toolbar_icon("question", color=explain_color))
            self.explain_btn.setIconSize(QSize(16, 16))
        if hasattr(self, "session_menu_btn"):
            session_color = accent_color if self.session_menu_btn.property("role") == "contextual" else icon_color
            self.session_menu_btn.setIcon(self._toolbar_icon("play", color=session_color))
            self.session_menu_btn.setIconSize(QSize(16, 16))
        if hasattr(self, "more_btn"):
            self.more_btn.setIcon(self._toolbar_icon("dots-three", color=utility_color))
            self.more_btn.setIconSize(QSize(16, 16))
        if hasattr(self, "theme_btn"):
            theme_icon = "sun" if self.theme_mode == "dark" else "moon"
            self.theme_btn.setIcon(self._toolbar_icon(theme_icon, color=accent_color))
            self.theme_btn.setIconSize(QSize(16, 16))
        if hasattr(self, "library_resize_grip"):
            self.library_resize_grip.setPixmap(self._toolbar_icon("dots-six-vertical", size=14, color=utility_color).pixmap(14, 14))
            self.library_resize_grip.setToolTip("Drag to resize library panel")
        if hasattr(self, "inspector_resize_grip"):
            self.inspector_resize_grip.setPixmap(self._toolbar_icon("dots-six-vertical", size=14, color=utility_color).pixmap(14, 14))
            self.inspector_resize_grip.setToolTip("Drag to resize annotation panel")

    def _apply_theme(self):
        if self.theme_mode == "dark":
            palette = {
                "main_bg": "#10161f",
                "text": "#dfe8f2",
                "muted": "#adbac9",
                "ribbon_bg": "#0d131b",
                "ribbon_bg_top": "#1b2430",
                "ribbon_bg_bottom": "#101720",
                "ribbon_shell_top": "#1f2935",
                "ribbon_shell_bottom": "#131b24",
                "ribbon_button_bg": "#203040",
                "ribbon_button_border": "#4c647d",
                "ribbon_button_hover": "#2b3d50",
                "ribbon_button_pressed": "#182432",
                "ribbon_divider": "#5a7088",
                "ribbon_border": "#385066",
                "tray_bg": "#223243",
                "tray_border": "#49627b",
                "status_bg": "#0c131a",
                "status_border": "#223140",
                "header_bg": "#0f1722",
                "header_border": "#223246",
                "saved_header_bg": "#0f1722",
                "saved_header_border": "#223246",
                "workspace_header_bg": "#17325f",
                "workspace_header_border": "#4d76bb",
                "scope_bg": "#162231",
                "scope_border": "#456485",
                "button_text": "#d7e1ed",
                "button_hover": "#2a3b4f",
                "button_pressed": "#203448",
                "button_border": "#4a6380",
                "accent_bg": "#17325f",
                "accent_hover": "#1d3c71",
                "accent_border": "#4d76bb",
                "accent_text": "#d9e9ff",
                "active_bg": "#14283f",
                "active_border": "#31557f",
                "active_item_bg": "#223347",
                "active_item_border": "#6a93c1",
                "panel_bg": "#10161d",
                "panel_border": "#18232f",
                "surface_bg": "#16222e",
                "surface_border": "#385063",
                "item_bg": "#1b2a37",
                "item_border": "#273949",
                "workspace_bg": "#14283d",
                "workspace_border": "#38536f",
                "saved_panel_bg": "#0d141c",
                "saved_panel_border": "#192634",
                "workspace_band": "#4d76bb",
                "canvas_bg": "#253240",
                "splitter": "#1e2a39",
                "splitter_hover": "#30445f",
                "input_bg": "#101923",
                "input_border": "#425970",
                "input_text": "#dfe8f2",
                "workspace_input_bg": "#1b3149",
                "workspace_input_border": "#35506f",
                "selection_bg": "#2e4d79",
                "selection_text": "#f6fbff",
                "list_hover": "#1c2938",
                "list_selected": "#203142",
                "list_selected_border": "#587ca5",
                "readonly_bg": "#141d28",
                "ai_bg": "#162231",
                "check_bg": "#17212d",
                "check_border": "#4a5f77",
                "slider_bg": "#304154",
                "slider_handle": "#7ea7e6",
                "tooltip_bg": "#0c1118",
            }
        else:
            palette = {
                "main_bg": "#f2efe9",
                "text": "#182636",
                "muted": "#4d5f74",
                "ribbon_bg": "#ece8e1",
                "ribbon_bg_top": "#f7f3ed",
                "ribbon_bg_bottom": "#e7e2da",
                "ribbon_shell_top": "#f8f5ef",
                "ribbon_shell_bottom": "#e6e1d8",
                "ribbon_button_bg": "#f7f4ee",
                "ribbon_button_border": "#b8b5ae",
                "ribbon_button_hover": "#ffffff",
                "ribbon_button_pressed": "#e9e4dc",
                "ribbon_divider": "#c9c0b4",
                "ribbon_border": "#c7c0b4",
                "tray_bg": "#efeae2",
                "tray_border": "#d7cec0",
                "status_bg": "#f4f0ea",
                "status_border": "#d7cec0",
                "header_bg": "#f2f5f8",
                "header_border": "#d4dde8",
                "saved_header_bg": "#f4f6f8",
                "saved_header_border": "#d6dee8",
                "workspace_header_bg": "#edf4ff",
                "workspace_header_border": "#c6d8ef",
                "scope_bg": "#f4f8ff",
                "scope_border": "#c8d8ee",
                "button_text": "#24384d",
                "button_hover": "#f5f8fc",
                "button_pressed": "#dde7f1",
                "button_border": "#b8cadf",
                "accent_bg": "#e4eefc",
                "accent_hover": "#d8e8fb",
                "accent_border": "#bdd2f0",
                "accent_text": "#184999",
                "active_bg": "#edf3fc",
                "active_border": "#c6d7ed",
                "active_item_bg": "#e6f0fb",
                "active_item_border": "#90b2d8",
                "panel_bg": "#f6f2ec",
                "panel_border": "#e4ddd2",
                "surface_bg": "#fffdf9",
                "surface_border": "#d9d1c5",
                "item_bg": "#f9fbfe",
                "item_border": "#ddd7cd",
                "workspace_bg": "#f5f8fc",
                "workspace_border": "#d6dde7",
                "saved_panel_bg": "#f9f6f1",
                "saved_panel_border": "#e2dbd0",
                "workspace_band": "#8bb1e8",
                "canvas_bg": "#ddd5c8",
                "splitter": "#ddd5c8",
                "splitter_hover": "#ccc1b1",
                "input_bg": "#ffffff",
                "input_border": "#d1c9bc",
                "input_text": "#182636",
                "workspace_input_bg": "#f7fbff",
                "workspace_input_border": "#c9d8ea",
                "selection_bg": "#dce9ff",
                "selection_text": "#1e2a38",
                "list_hover": "#f4efe8",
                "list_selected": "#deebfb",
                "list_selected_border": "#9fbde0",
                "readonly_bg": "#faf8f3",
                "ai_bg": "#f5f7fa",
                "check_bg": "#ffffff",
                "check_border": "#a8b9cf",
                "slider_bg": "#d7d2c9",
                "slider_handle": "#4f82d9",
                "tooltip_bg": "#233142",
            }
        self._theme_palette = palette
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background: {palette["main_bg"]};
                color: {palette["text"]};
            }}
            #Ribbon {{
                background: {palette["main_bg"]};
            }}
            #RibbonShell {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 {palette["ribbon_shell_top"]},
                    stop: 1 {palette["ribbon_shell_bottom"]}
                );
                border: 1px solid {palette["ribbon_border"]};
                border-radius: 11px;
            }}
            #RibbonTray {{
                background: {palette["tray_bg"]};
                border: 1px solid {palette["tray_border"]};
                border-radius: 7px;
            }}
            #RibbonTray[trayRole="mechanics"], #RibbonTray[trayRole="search"] {{
                background: {palette["surface_bg"]};
                border-color: {palette["surface_border"]};
            }}
            #RibbonTray[trayRole="workflow"] {{
                background: {palette["tray_bg"]};
                border-color: {palette["tray_border"]};
            }}
            #RibbonTray[trayRole="status"] {{
                background: {palette["status_bg"]};
                border-color: {palette["status_border"]};
            }}
            #RibbonButton, #AccentButton {{
                min-height: 26px;
                border: 1px solid {palette["ribbon_button_border"]};
                border-radius: 6px;
                padding: 0 10px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 {palette["button_hover"]},
                    stop: 1 {palette["ribbon_button_bg"]}
                );
                color: {palette["button_text"]};
                font-weight: normal;
            }}
            #RibbonButton[role="secondary"] {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 {palette["button_hover"]},
                    stop: 1 {palette["ribbon_button_bg"]}
                );
                border-color: {palette["ribbon_button_border"]};
                color: {palette["button_text"]};
            }}
            #RibbonTray[trayRole="workflow"] #RibbonButton[role="secondary"] {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 {palette["button_hover"]},
                    stop: 1 {palette["button_pressed"]}
                );
                border-color: {palette["button_border"]};
            }}
            #RibbonButton[role="utility"] {{
                background: {palette["status_bg"]};
                border-color: {palette["status_border"]};
                color: {palette["muted"]};
            }}
            #RibbonButton[role="contextual"] {{
                background: {palette["accent_bg"]};
                border-color: {palette["accent_border"]};
                color: {palette["accent_text"]};
                font-weight: bold;
            }}
            #RibbonButton[compact="true"] {{
                min-width: 26px;
                max-width: 26px;
                padding: 0;
                font-weight: bold;
                text-align: center;
            }}
            #RibbonButton:hover {{
                background: {palette["ribbon_button_hover"]};
                border-color: {palette["active_border"]};
                color: {palette["text"]};
            }}
            #RibbonButton[role="utility"]:hover {{
                background: {palette["surface_bg"]};
                border-color: {palette["surface_border"]};
                color: {palette["text"]};
            }}
            #RibbonButton[role="contextual"]:hover {{
                background: {palette["accent_hover"]};
                border-color: {palette["accent_border"]};
                color: {palette["accent_text"]};
            }}
            #RibbonButton:pressed, #RibbonButton:checked {{
                background: {palette["ribbon_button_pressed"]};
                border-color: {palette["active_border"]};
            }}
            #RibbonButton[pill="true"] {{
                padding: 0 12px;
                border-radius: 11px;
                background: {palette["ribbon_button_bg"]};
            }}
            #RibbonButton[mode="true"] {{
                min-width: 48px;
            }}
            #AccentButton {{
                background: {palette["accent_bg"]};
                border-color: {palette["accent_border"]};
                color: {palette["accent_text"]};
                font-weight: bold;
            }}
            #AccentButton:hover {{
                background: {palette["accent_hover"]};
                border-color: {palette["accent_border"]};
            }}
            #RibbonSearchInput, #RibbonPageSpin {{
                background: {palette["input_bg"]};
                border: 1px solid {palette["input_border"]};
                border-radius: 6px;
                padding: 3px 8px;
                color: {palette["input_text"]};
                min-height: 24px;
            }}
            #RibbonPageSpin {{
                background: {palette["input_bg"]};
                border-color: {palette["input_border"]};
                border-radius: 6px;
                padding: 2px 4px;
                font-weight: bold;
            }}
            #PageTotalLabel {{
                background: transparent;
                color: {palette["muted"]};
                font-size: 12px;
                padding: 0 2px 0 0;
            }}
            #RibbonStatus {{
                background: transparent;
                color: {palette["muted"]};
                padding: 0 3px;
            }}
            #RibbonButton[modeSelector="true"] {{
                min-width: 26px;
                max-width: 26px;
                min-height: 26px;
                max-height: 26px;
                border-radius: 6px;
                padding: 0;
                text-align: center;
            }}
            #SessionPill {{
                background: {palette["status_bg"]};
                border: none;
                border-radius: 11px;
                color: {palette["muted"]};
                font-weight: normal;
                padding: 3px 10px;
            }}
            #PageStatus, #MetaLabel, #FieldLabel {{
                color: {palette["muted"]};
                font-size: 12px;
            }}
            #SectionHeader {{
                color: {palette["text"]};
                background: transparent;
                border: none;
                border-bottom: 1px solid {palette["header_border"]};
                border-radius: 0;
                padding: 2px 2px 6px 2px;
                font-size: 12px;
                font-weight: bold;
            }}
            #SavedSectionHeader {{
                color: {palette["text"]};
                background: transparent;
                border: none;
                border-bottom: 1px solid {palette["saved_header_border"]};
                border-radius: 0;
                padding: 2px 2px 6px 2px;
                font-size: 12px;
                font-weight: bold;
            }}
            #WorkspaceSectionHeader {{
                color: {palette["text"]};
                background: transparent;
                border: none;
                border-bottom: 2px solid {palette["workspace_header_border"]};
                border-radius: 0;
                padding: 2px 2px 6px 2px;
                font-size: 12px;
                font-weight: bold;
            }}
            #ActiveRecordCard {{
                color: {palette["text"]};
                background: {palette["active_bg"]};
                border: 1px solid {palette["active_border"]};
                border-radius: 10px;
            }}
            #ActiveRecordTitle {{
                color: {palette["text"]};
                background: transparent;
                font-size: 13px;
                font-weight: bold;
                line-height: 1.25;
            }}
            #ActiveRecordMeta {{
                color: {palette["muted"]};
                background: transparent;
                font-size: 12px;
                font-weight: normal;
            }}
            #ScopeSelector {{
                background: {palette["scope_bg"]};
                border: 1px solid {palette["scope_border"]};
                border-radius: 11px;
                padding: 7px 10px;
                color: {palette["text"]};
                font-size: 12px;
                font-weight: normal;
            }}
            #ScopeSelector:hover {{
                border-color: {palette["active_border"]};
            }}
            #WorkspaceStatusLabel {{
                color: {palette["muted"]};
                background: {palette["readonly_bg"]};
                border: 1px solid {palette["workspace_input_border"]};
                border-radius: 8px;
                padding: 6px 9px;
                font-size: 12px;
                font-weight: normal;
            }}
            #WorkspaceStatusLabel[statusState="active"] {{
                color: {palette["accent_text"]};
                background: {palette["accent_bg"]};
                border-color: {palette["accent_border"]};
                font-weight: bold;
            }}
            #WorkspaceStatusLabel[statusState="dirty"] {{
                color: {palette["text"]};
                background: {palette["active_bg"]};
                border-color: {palette["active_border"]};
                font-weight: bold;
            }}
            #WorkspaceStatusLabel[statusState="blocked"] {{
                color: {palette["muted"]};
                background: {palette["saved_panel_bg"]};
                border-color: {palette["saved_panel_border"]};
            }}
            #FieldLabel {{
                font-size: 12px;
                font-weight: normal;
            }}
            #RibbonDivider, #PanelDivider {{
                color: {palette["ribbon_border"]};
            }}
            #RibbonDivider {{
                background: transparent;
                border-left: 1px solid {palette["ribbon_divider"]};
                margin: 2px 3px;
            }}
            #LibraryPanel, #InspectorPanel {{
                background: {palette["panel_bg"]};
            }}
            #TriageInclusionPanel {{
                background: {palette["workspace_bg"]};
                border: 1px solid {palette["workspace_border"]};
                border-radius: 10px;
                padding: 4px;
            }}
            #OrganizerPanel {{
                background: {palette["workspace_bg"]};
                border: none;
                border-radius: 0;
                padding: 2px 0 0 0;
            }}
            #SavedAnnotationsPanel {{
                background: {palette["saved_panel_bg"]};
                border: none;
                border-radius: 0;
                padding: 6px 0 0 0;
            }}
            #AnnotationWorkspacePanel {{
                background: {palette["workspace_bg"]};
                border-top: 4px solid {palette["workspace_band"]};
                border-left: none;
                border-right: none;
                border-bottom: none;
                border-radius: 0;
                padding: 10px 0 0 0;
            }}
            #ProjectContextPanel {{
                background: {palette["workspace_bg"]};
                border: 1px solid {palette["workspace_border"]};
                border-radius: 10px;
                padding: 4px;
            }}
            #AnnotationWorkspacePanel > QWidget {{
                background: transparent;
            }}
            #LibraryPanel {{
                border-right: none;
            }}
            #InspectorPanel {{
                border-left: none;
            }}
            #InspectorPanel QLineEdit,
            #InspectorPanel QComboBox,
            #InspectorPanel QTextEdit {{
                background: {palette["saved_panel_bg"]};
                border-color: {palette["saved_panel_border"]};
            }}
            #PageCanvas, QScrollArea {{
                background: {palette["canvas_bg"]};
                border: none;
            }}
            QSplitter::handle {{
                background: {palette["splitter"]};
                width: 6px;
            }}
            QSplitter::handle:hover {{
                background: {palette["splitter_hover"]};
            }}
            QSplitter#InspectorSplitter::handle:vertical {{
                background: {palette["workspace_band"]};
                height: 18px;
                margin: 6px 0;
                border-radius: 7px;
            }}
            QSplitter#InspectorSplitter::handle:vertical:hover {{
                background: {palette["workspace_header_border"]};
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 10px;
                margin: 2px 2px 2px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {palette["button_border"]};
                border-radius: 5px;
                min-height: 28px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {palette["active_border"]};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                background: transparent;
                border: none;
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 10px;
                margin: 0 2px 2px 2px;
            }}
            QScrollBar::handle:horizontal {{
                background: {palette["button_border"]};
                border-radius: 5px;
                min-width: 28px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {palette["active_border"]};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                background: transparent;
                border: none;
                width: 0px;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: transparent;
            }}
            QLineEdit, QTextEdit, QComboBox, QSpinBox {{
                background: {palette["input_bg"]};
                border: 1px solid {palette["input_border"]};
                border-radius: 8px;
                padding: 6px 8px;
                selection-background-color: {palette["selection_bg"]};
                selection-color: {palette["selection_text"]};
                color: {palette["input_text"]};
            }}
            #AnnotationWorkspacePanel QLineEdit,
            #AnnotationWorkspacePanel QTextEdit,
            #AnnotationWorkspacePanel QComboBox,
            #AnnotationWorkspacePanel QSpinBox {{
                background: {palette["workspace_input_bg"]};
                border: 1px solid {palette["workspace_input_border"]};
            }}
            #AnnotationTypeBadge {{
                border-radius: 9px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }}
            #AnnotationTypeBadge[annotationType="quote"] {{
                color: #7a4300;
                background: #ffe2a5;
                border: 1px solid #d89523;
            }}
            #AnnotationTypeBadge[annotationType="paraphrase"] {{
                color: #0d3f79;
                background: #d9ebff;
                border: 1px solid #6aa7e8;
            }}
            #AnnotationTypeBadge[annotationType="interpretation"] {{
                color: #51237a;
                background: #eadcff;
                border: 1px solid #a275d6;
            }}
            #AnnotationTypeBadge[annotationType="synthesis"] {{
                color: #155c35;
                background: #d9f5e6;
                border: 1px solid #5eb987;
            }}
            #AnnotationTypeControl {{
                font-weight: normal;
            }}
            #SourceAnchorText {{
                background: {palette["readonly_bg"]};
                border: 1px dashed {palette["workspace_input_border"]};
                color: {palette["muted"]};
            }}
            #AnnotationNoteInput {{
                background: {palette["workspace_input_bg"]};
                border: 1px solid {palette["workspace_input_border"]};
            }}
            #ConfidenceControl {{
                font-weight: bold;
                border-radius: 9px;
                background: {palette["active_bg"]};
                border: 1px solid {palette["active_border"]};
            }}
            QListWidget {{
                outline: 0;
                background: {palette["surface_bg"]};
                border: none;
                border-radius: 0;
                padding: 4px;
                color: {palette["input_text"]};
            }}
            #InfoList {{
                background: {palette["surface_bg"]};
                border: none;
                border-radius: 0;
                padding: 2px;
            }}
            #OrganizerInput {{
                min-height: 24px;
                max-height: 24px;
                padding: 3px 6px;
                font-size: 11px;
                border-radius: 8px;
            }}
            #OrganizerButton {{
                min-height: 28px;
                max-height: 28px;
                padding: 0 10px;
                font-size: 11px;
                font-weight: bold;
                border-radius: 8px;
                background: {palette["ribbon_button_bg"]};
                border: 1px solid {palette["button_border"]};
                color: {palette["button_text"]};
            }}
            #OrganizerButton[buttonRole="primary"] {{
                background: {palette["accent_bg"]};
                border-color: {palette["accent_border"]};
                color: {palette["accent_text"]};
            }}
            #OrganizerButton[saveState="saved"] {{
                background: {palette["active_bg"]};
                border-color: {palette["active_border"]};
                color: {palette["text"]};
            }}
            #OrganizerButton[saveState="blocked"] {{
                background: {palette["status_bg"]};
                border-color: {palette["status_border"]};
                color: {palette["muted"]};
            }}
            #OrganizerButton:hover {{
                background: {palette["accent_hover"]};
                border-color: {palette["active_border"]};
            }}
            #OrganizerButton:pressed {{
                background: {palette["button_pressed"]};
                padding-top: 1px;
            }}
            #OrganizerStatus {{
                color: {palette["muted"]};
                font-size: 10px;
                padding: 0 2px 2px 2px;
            }}
            #OrganizerStatus[statusState="saved"] {{
                color: {palette["accent_text"]};
                font-weight: bold;
            }}
            #OrganizerStatus[statusState="blocked"] {{
                color: {palette["muted"]};
                font-weight: bold;
            }}
            #TagChipButton {{
                min-height: 24px;
                border-radius: 9px;
                padding: 0 10px;
                background: {palette["active_bg"]};
                border: 1px solid {palette["active_border"]};
                color: {palette["text"]};
                font-size: 11px;
                font-weight: normal;
            }}
            #TagChipButton:hover {{
                background: {palette["list_hover"]};
            }}
            #SuggestedTagChip {{
                min-height: 20px;
                border-radius: 8px;
                padding: 0 7px;
                background: {palette["input_bg"]};
                border: 1px solid {palette["input_border"]};
                color: {palette["muted"]};
                font-size: 10px;
            }}
            #SuggestedTagChip:hover {{
                background: {palette["button_hover"]};
                color: {palette["text"]};
            }}
            #SuggestedTagChip:disabled {{
                background: {palette["readonly_bg"]};
                color: {palette["muted"]};
                border-color: {palette["input_border"]};
            }}
            QListWidget::item {{
                margin: 4px 0;
                padding: 10px 10px;
                border-radius: 8px;
                background: {palette["item_bg"]};
                border: none;
                font-size: 12px;
                font-weight: normal;
            }}
            #InspectorPanel QListWidget::item {{
                background: {palette["surface_bg"]};
            }}
            #LibraryPanel QListWidget::item {{
                background: {palette["surface_bg"]};
            }}
            #ListRowTitle {{
                background: transparent;
                font-size: 12px;
            }}
            #ListRowSubtitle {{
                background: transparent;
                font-size: 11px;
            }}
            #ListRowMeta {{
                background: transparent;
                font-size: 10px;
            }}
            #LibrarySearchInput {{
                background: {palette["input_bg"]};
                border: 1px solid {palette["input_border"]};
                border-radius: 8px;
                padding: 6px 9px;
                color: {palette["input_text"]};
                min-height: 24px;
            }}
            #FocusInspectorHandle {{
                background: rgba(20, 30, 42, 34);
                border: 1px solid rgba(160, 180, 205, 46);
                border-radius: 11px;
                padding: 0;
                color: {palette["muted"]};
            }}
            #FocusInspectorHandle:hover {{
                background: rgba(60, 82, 108, 82);
                border-color: {palette["surface_border"]};
            }}
            #PanelResizeGrip {{
                background: transparent;
                border: none;
                padding: 0;
            }}
            QListWidget::item:hover {{
                background: {palette["list_hover"]};
            }}
            QListWidget::item:selected {{
                background: {palette["list_selected"]};
                border: 1px solid {palette["list_selected_border"]};
            }}
            QTextEdit[readOnly="true"] {{
                background: {palette["readonly_bg"]};
            }}
            #AIOutput {{
                background: {palette["ai_bg"]};
                color: {palette["input_text"]};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QCheckBox {{
                color: {palette["button_text"]};
                spacing: 6px;
                font-size: 12px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid {palette["check_border"]};
                background: {palette["check_bg"]};
            }}
            QCheckBox::indicator:checked {{
                background: {palette["slider_handle"]};
                border-color: {palette["slider_handle"]};
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                border-radius: 3px;
                background: {palette["slider_bg"]};
            }}
            QSlider::handle:horizontal {{
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
                background: {palette["slider_handle"]};
            }}
            QToolTip {{
                background: {palette["tooltip_bg"]};
                color: #f7fafc;
                border: 1px solid {palette["tooltip_bg"]};
                padding: 4px 6px;
            }}
        """)
        if hasattr(self, "theme_btn"):
            self.theme_btn.setChecked(self.theme_mode == "dark")
            self.theme_btn.setText("")
            self.theme_btn.setToolTip("Switch to light mode" if self.theme_mode == "dark" else "Switch to dark mode")
        if hasattr(self, "focus_mode_btn"):
            self.focus_mode_btn.setChecked(getattr(self, "focus_mode", False))
            self.focus_mode_btn.setText("")
            self.focus_mode_btn.setToolTip("Exit Focus Mode" if getattr(self, "focus_mode", False) else "Focus Mode")
        if hasattr(self, "inspector_toggle_btn"):
            self._update_inspector_toggle_label()
        if hasattr(self, "fit_check"):
            self.fit_check.setChecked(self.fit_to_width)
        if hasattr(self, "continuous_check"):
            self.continuous_check.setChecked(self.continuous)
        if hasattr(self, "session_menu_btn"):
            self.session_menu_btn.setText("")
            self.session_menu_btn.setToolTip(
                "End current reading session" if self.current_session_id else "Start reading session"
            )
        if hasattr(self, "session_status_label"):
            session_text = self._session_pill_text()
            self.session_status_label.setText(session_text)
            self.session_status_label.setToolTip(self.current_session_intention or session_text)
        self._apply_toolbar_icons()
        self._update_toolbar_context()
        if hasattr(self, "doc_list"):
            self._refresh_doc_list()
        if hasattr(self, "annotation_list"):
            try:
                self.load_annotations()
            except Exception:
                runtime_trace(f"_apply_theme load_annotations refresh failed: {traceback.format_exc().splitlines()[-1]}")

    def _update_ribbon_status(self):
        if not hasattr(self, "ribbon_status_label"):
            return
        parts = []
        project_name = ""
        if hasattr(self, "project_combo"):
            project_name = (self.project_combo.currentText() or "").strip()
        if project_name:
            parts.append(self._truncate_session_text(project_name, max_len=22))
        if self.current_document_id is not None and self.total_pages:
            parts.append(f"Page {self.current_page + 1}/{self.total_pages}")
        else:
            parts.append("No doc")
        status_text = " | ".join(parts)
        self.ribbon_status_label.setText(status_text)
        self.ribbon_status_label.setToolTip(status_text)

    def _truncate_session_text(self, text: str, max_len: int = 24) -> str:
        text = (text or "").strip()
        if len(text) <= max_len:
            return text
        return text[: max_len - 1].rstrip() + "…"

    def _refresh_widget_style(self, widget):
        if widget is None:
            return
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()

    def _elide_for_label(self, label: QLabel, text: str) -> str:
        value = (text or "").strip()
        if not value:
            return ""
        width = max(40, label.width() - 4)
        return QFontMetrics(label.font()).elidedText(value, Qt.ElideRight, width)

    def _sync_active_record_text(self):
        if not hasattr(self, "active_record_title_label"):
            return
        title = getattr(self, "_active_record_title_full", "No source open")
        meta = getattr(self, "_active_record_meta_full", "Open a source in the reader to pin it here.")
        self.active_record_title_label.setText(self._elide_for_label(self.active_record_title_label, title))
        self.active_record_meta_label.setText(self._elide_for_label(self.active_record_meta_label, meta))

    def _set_search_status_text(self, text: str):
        if not hasattr(self, "search_status_label"):
            return
        value = (text or "").strip()
        self.search_status_label.setText(value)
        self.search_status_label.setVisible(bool(value))
        self._update_search_nav_buttons()

    def _update_search_nav_buttons(self):
        has_query = bool(getattr(self, "search_query", ""))
        has_results = bool(getattr(self, "search_results", []))
        should_show = has_query or has_results
        for button in (getattr(self, "search_prev_btn", None), getattr(self, "search_next_btn", None)):
            if button is None:
                continue
            button.setVisible(should_show)
            button.setEnabled(has_results)

    def _make_list_row_widget(
        self,
        title: str,
        subtitle: str = "",
        meta: str = "",
        active: bool = False,
        accent_color: str = "",
        role: str = "generic",
    ):
        palette = getattr(self, "_theme_palette", {})
        if role == "document":
            if self.theme_mode == "dark":
                title_color = accent_color or "#f3f8ff"
                subtitle_color = "#d8e3ef"
                meta_color = "#abc0d6"
            else:
                title_color = accent_color or palette.get("text", "#233142")
                subtitle_color = palette.get("muted", "#6a798b")
                meta_color = palette.get("muted", "#6a798b")
        else:
            title_color = accent_color or palette.get("text", "#233142")
            subtitle_color = palette.get("text", "#233142")
            meta_color = palette.get("muted", "#6a798b")
        widget = QWidget()
        widget.setAttribute(Qt.WA_TranslucentBackground, True)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(3)

        title_label = QLabel((title or "").strip() or "Untitled")
        title_label.setWordWrap(True)
        title_label.setObjectName("ListRowTitle")
        title_label.setToolTip((title or "").strip())
        title_font = self._ui_font(
            11 if role == "document" else 10,
            QFont.Weight.DemiBold if (active or role == "document") else QFont.Weight.Normal,
        )
        title_label.setFont(title_font)
        title_lines = 3 if role == "document" else 2
        title_label.setMaximumHeight(QFontMetrics(title_font).lineSpacing() * title_lines + 6)
        title_label.setStyleSheet(
            f"color: {title_color}; background: transparent;"
        )
        layout.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle.strip())
            subtitle_label.setWordWrap(True)
            subtitle_label.setObjectName("ListRowSubtitle")
            subtitle_label.setFont(self._ui_font(10))
            subtitle_label.setMaximumHeight(34)
            subtitle_label.setStyleSheet(
                f"color: {subtitle_color}; background: transparent;"
            )
            layout.addWidget(subtitle_label)

        if meta:
            meta_label = QLabel(meta.strip())
            meta_label.setWordWrap(True)
            meta_label.setObjectName("ListRowMeta")
            meta_label.setFont(self._ui_font(9))
            meta_label.setMaximumHeight(30 if role == "document" else 24)
            meta_label.setToolTip(meta.strip())
            meta_label.setStyleSheet(
                f"color: {meta_color}; background: transparent;"
            )
            layout.addWidget(meta_label)

        return widget

    def _wrapped_text_height(self, text: str, font: QFont, width: int, max_lines: int | None = None) -> int:
        content = (text or "").strip()
        if not content or width <= 0:
            return 0
        metrics = QFontMetrics(font)
        rect = metrics.boundingRect(QRect(0, 0, width, 4096), Qt.TextWordWrap, content)
        height = rect.height()
        if max_lines is not None:
            height = min(height, metrics.lineSpacing() * max_lines)
        return height

    def _document_row_height(self, title: str, meta: str, list_width: int) -> int:
        content_width = max(120, list_width - 44)
        title_font = self._ui_font(11, QFont.Weight.DemiBold)
        meta_font = self._ui_font(9)
        title_height = self._wrapped_text_height(title, title_font, content_width, max_lines=3)
        meta_height = self._wrapped_text_height(meta, meta_font, content_width, max_lines=2)
        return max(96, 34 + title_height + (3 if meta_height else 0) + meta_height)

    def _sync_doc_list_row_heights(self):
        if not hasattr(self, "doc_list"):
            return
        list_width = self.doc_list.viewport().width()
        if list_width <= 0:
            return
        for index in range(self.doc_list.count()):
            item = self.doc_list.item(index)
            if item is None:
                continue
            row_data = item.data(Qt.UserRole + 1) or {}
            if row_data.get("role") != "document":
                continue
            height = self._document_row_height(
                row_data.get("title", ""),
                row_data.get("meta", ""),
                list_width,
            )
            item.setSizeHint(QSize(200, height))

    def _has_explain_context(self) -> bool:
        if self.current_annotation_id:
            return True
        if hasattr(self, "selected_text_edit") and self.selected_text_edit.toPlainText().strip():
            return True
        return False

    def _update_toolbar_context(self):
        if hasattr(self, "explain_btn"):
            explain_role = "contextual" if self._has_explain_context() else "secondary"
            self.explain_btn.setProperty("role", explain_role)
            self.explain_btn.setEnabled(self.current_document_id is not None)
            self._refresh_widget_style(self.explain_btn)
        if hasattr(self, "session_menu_btn"):
            if self.current_session_id:
                session_role = "secondary"
            elif self.current_document_id is not None:
                session_role = "contextual"
            else:
                session_role = "utility"
            self.session_menu_btn.setProperty("role", session_role)
            self._refresh_widget_style(self.session_menu_btn)
        if hasattr(self, "more_btn"):
            self.more_btn.setProperty("role", "utility")
            self._refresh_widget_style(self.more_btn)
        if hasattr(self, "inspector_toggle_btn"):
            self.inspector_toggle_btn.setProperty("role", "utility")
            self._refresh_widget_style(self.inspector_toggle_btn)
        if hasattr(self, "focus_mode_btn"):
            self.focus_mode_btn.setProperty("role", "contextual" if getattr(self, "focus_mode", False) else "utility")
            self._refresh_widget_style(self.focus_mode_btn)

    def _fetch_session_intention(self, session_id: str) -> str:
        if not session_id:
            return ""
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT reading_intention FROM reading_sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
                return (row[0] or "").strip() if row else ""
        except sqlite3.Error:
            return ""

    def _session_pill_text(self) -> str:
        intention = (self.current_session_intention or "").strip()
        if not intention and self.current_session_id:
            intention = self._fetch_session_intention(self.current_session_id)
            self.current_session_intention = intention
        if not self.current_session_id:
            return "No session"
        if intention:
            return self._truncate_session_text(intention, max_len=16)
        return "Session active"

    def _end_current_session(self):
        self.current_session_id = None
        self.current_session_intention = ""
        self._apply_theme()
        self._update_ribbon_status()

    def _handle_session_button(self):
        if self.current_session_id:
            self._end_current_session()
            return
        self.start_reading_session()

    def _save_annotation_from_button(self):
        return self.save_annotation(triage=self.reader_mode == "triage")

    def _current_source_id(self):
        if getattr(self, "current_project_source_id", None):
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT source_id FROM project_sources WHERE id = ? LIMIT 1",
                    (self.current_project_source_id,),
                ).fetchone()
                if row:
                    return row[0]
        if getattr(self, "current_library_project_source_id", None):
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT source_id FROM project_sources WHERE id = ? LIMIT 1",
                    (self.current_library_project_source_id,),
                ).fetchone()
                if row:
                    return row[0]
        if getattr(self, "current_document_id", None):
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    """
                    SELECT source_id
                    FROM project_sources
                    WHERE legacy_document_id = ?
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT 1
                    """,
                    (self.current_document_id,),
                ).fetchone()
                if row:
                    return row[0]
                row = conn.execute(
                    """
                    SELECT s.id
                    FROM documents d
                    JOIN sources s
                        ON (
                            (d.file_path IS NOT NULL AND d.file_path <> '' AND s.file_path = d.file_path)
                            OR (
                                (d.file_path IS NULL OR d.file_path = '')
                                AND s.canonical_title = d.title
                            )
                        )
                    WHERE d.id = ?
                    ORDER BY s.updated_at DESC, s.created_at DESC
                    LIMIT 1
                    """
                    ,
                    (self.current_document_id,),
                ).fetchone()
                if row:
                    return row[0]
        return None

    def _current_inclusion_project_id(self):
        return self.current_project_id if getattr(self, "current_project_id", None) else None

    def _set_combo_by_data(self, combo, value):
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _mark_triage_metadata_dirty(self):
        if getattr(self, "updating_triage_panel", False):
            return
        self.triage_metadata_dirty = True
        self._set_workspace_status(self.triage_panel_hint, "Unsaved inclusion metadata", "dirty")

    def _set_workspace_status(self, label, text, state="idle"):
        if label is None:
            return
        label.setText(text)
        label.setProperty("statusState", state)
        label.style().unpolish(label)
        label.style().polish(label)

    def _toggle_project_context_panel(self):
        self.project_context_collapsed = not getattr(self, "project_context_collapsed", False)
        self._update_project_context_panel()

    def _project_context_data(self):
        if not self.current_project_id or not self.current_project_source_id:
            return None
        with sqlite3.connect(self.db_path) as conn:
            project = conn.execute(
                """
                SELECT title, COALESCE(research_question, '')
                FROM review_projects
                WHERE id = ?
                LIMIT 1
                """,
                (self.current_project_id,),
            ).fetchone()
            current = conn.execute(
                """
                SELECT
                    COALESCE(s.canonical_title, ps.display_title, d.title, '') AS source_title,
                    si.relevance_scope,
                    si.screening_depth,
                    si.project_role_note
                FROM project_sources ps
                LEFT JOIN documents d ON d.id = ps.legacy_document_id
                LEFT JOIN sources s ON s.id = ps.source_id
                LEFT JOIN source_inclusion si
                    ON si.source_id = ps.source_id
                   AND si.project_id = ps.project_id
                WHERE ps.id = ?
                LIMIT 1
                """,
                (self.current_project_source_id,),
            ).fetchone()
            central_rows = conn.execute(
                """
                SELECT COALESCE(s.canonical_title, ps.display_title, d.title, 'Untitled source') AS title
                FROM project_sources ps
                LEFT JOIN documents d ON d.id = ps.legacy_document_id
                LEFT JOIN sources s ON s.id = ps.source_id
                JOIN source_inclusion si
                    ON si.source_id = ps.source_id
                   AND si.project_id = ps.project_id
                WHERE ps.project_id = ?
                  AND si.relevance_scope = 'central'
                ORDER BY LOWER(COALESCE(s.canonical_title, ps.display_title, d.title, '')) ASC
                LIMIT 6
                """,
                (self.current_project_id,),
            ).fetchall()
        if not project or not current:
            return None
        return {
            "project_title": project[0] or "Untitled project",
            "scope": project[1] or "",
            "source_title": current[0] or "Untitled source",
            "relevance_scope": current[1] or "",
            "screening_depth": current[2] or "",
            "project_role_note": current[3] or "",
            "central_sources": [row[0] for row in central_rows],
        }

    def _update_project_context_panel(self):
        if not hasattr(self, "project_context_panel"):
            return
        data = self._project_context_data()
        if not data:
            self.project_context_panel.setVisible(False)
            return
        self.project_context_panel.setVisible(True)
        collapsed = getattr(self, "project_context_collapsed", False)
        self.project_context_toggle_btn.setText("Show" if collapsed else "Hide")
        self.project_context_body.setVisible(not collapsed)
        role_bits = []
        if data["relevance_scope"]:
            role_bits.append(str(data["relevance_scope"]).title())
        if data["screening_depth"]:
            role_bits.append(f"Depth: {data['screening_depth']}")
        role_text = " - ".join(role_bits) if role_bits else "No role metadata yet"
        self._set_workspace_status(
            self.project_context_status,
            f"{data['project_title']} - {role_text}",
            "idle",
        )
        scope = data["scope"].strip() or "No project scope statement recorded yet."
        self.project_scope_label.setText(f"Scope: {scope}")
        central_sources = data["central_sources"]
        if central_sources:
            central_text = "; ".join(central_sources)
            if len(central_sources) >= 6:
                central_text += "; ..."
            self.project_central_sources_label.setText(f"Central sources: {central_text}")
        else:
            self.project_central_sources_label.setText("Central sources: none marked yet.")
        note = data["project_role_note"].strip()
        if note:
            self.project_current_role_label.setText(f"Current source role: {note}")
        else:
            self.project_current_role_label.setText(f"Current source: {data['source_title']}")

    def _on_reader_mode_clicked(self):
        next_mode = "full" if self.reader_mode == "triage" else "triage"
        if next_mode == self.reader_mode:
            return
        if self.reader_mode == "triage" and self.triage_metadata_dirty:
            answer = QMessageBox.question(
                self,
                "Save Triage Metadata?",
                "Save the inclusion metadata before returning to Full Read?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if answer == QMessageBox.Cancel:
                self._update_reader_mode_button()
                return
            if answer == QMessageBox.Save and not self.save_triage_metadata():
                self._update_reader_mode_button()
                return
        self._set_reader_mode(next_mode)

    def _set_reader_mode(self, mode):
        self.reader_mode = "triage" if mode == "triage" else "full"
        self._update_reader_mode_button()
        is_triage = self.reader_mode == "triage"
        self.triage_panel.setVisible(is_triage)
        if is_triage:
            self._set_inspector_visible(True)
            self._load_triage_metadata_for_current_source()
        self._update_annotation_workspace_state()

    def _update_reader_mode_button(self):
        if not hasattr(self, "reader_mode_btn"):
            return
        is_triage = self.reader_mode == "triage"
        label = "Switch to read mode" if is_triage else "Switch to triage mode"
        self.reader_mode_btn.setText("")
        self.reader_mode_btn.setAccessibleName(label)
        self.reader_mode_btn.setToolTip(label)
        self.reader_mode_btn.setProperty("role", "contextual" if is_triage else "secondary")
        self.reader_mode_btn.style().unpolish(self.reader_mode_btn)
        self.reader_mode_btn.style().polish(self.reader_mode_btn)
        if hasattr(self, "reader_mode_status_label"):
            if is_triage:
                self._set_workspace_status(self.reader_mode_status_label, "Mode: Triage - screening source", "active")
            else:
                self._set_workspace_status(self.reader_mode_status_label, "Mode: Read - annotating source", "idle")
        self._apply_toolbar_icons()

    def _load_triage_metadata_for_current_source(self):
        if not hasattr(self, "triage_panel"):
            return
        self.updating_triage_panel = True
        try:
            source_id = self._current_source_id()
            self.triage_inclusion_record_id = None
            if not source_id:
                self._set_workspace_status(
                    self.triage_panel_hint,
                    "No source open - open a library source before saving inclusion metadata.",
                    "blocked",
                )
                self._set_combo_by_data(self.triage_status_combo, "candidate")
                self._set_combo_by_data(self.triage_scope_combo, "")
                self._set_combo_by_data(self.triage_depth_combo, "")
                self.triage_reasoning_edit.clear()
                self.triage_role_note_edit.clear()
                return
            source_db = self._source_triage_db()
            project_id = self._current_inclusion_project_id()
            loaded_project_record = True
            record = source_db.get_inclusion_record(source_id, project_id=project_id, db_path=self.db_path)
            if record is None and project_id is not None:
                loaded_project_record = False
                record = source_db.get_inclusion_record(source_id, db_path=self.db_path)
            if record:
                self.triage_inclusion_record_id = record.get("id") if loaded_project_record else None
                if loaded_project_record:
                    self._set_workspace_status(self.triage_panel_hint, "Screening loaded for this workspace", "idle")
                else:
                    self._set_workspace_status(
                        self.triage_panel_hint,
                        "Global screening loaded - save to create workspace-specific metadata.",
                        "active",
                    )
                self._set_combo_by_data(self.triage_status_combo, record.get("inclusion_status") or "candidate")
                self._set_combo_by_data(self.triage_scope_combo, record.get("relevance_scope") or "")
                self._set_combo_by_data(self.triage_depth_combo, record.get("screening_depth") or "")
                self.triage_reasoning_edit.setPlainText(record.get("inclusion_reasoning") or "")
                self.triage_role_note_edit.setPlainText(record.get("project_role_note") or "")
            else:
                self._set_workspace_status(self.triage_panel_hint, "Ready to screen this source", "idle")
                self._set_combo_by_data(self.triage_status_combo, "candidate")
                self._set_combo_by_data(self.triage_scope_combo, "")
                self._set_combo_by_data(self.triage_depth_combo, "")
                self.triage_reasoning_edit.clear()
                self.triage_role_note_edit.clear()
        finally:
            self.updating_triage_panel = False
            self.triage_metadata_dirty = False

    def save_triage_metadata(self):
        source_id = self._current_source_id()
        if not source_id:
            QMessageBox.information(self, "No Source Open", "Open a library source before saving inclusion metadata.")
            return False
        status = self.triage_status_combo.currentData() or "candidate"
        scope = self.triage_scope_combo.currentData() or None
        depth = self.triage_depth_combo.currentData() or None
        reasoning = self.triage_reasoning_edit.toPlainText().strip()
        role_note = self.triage_role_note_edit.toPlainText().strip() or None
        if status in {"included", "excluded"} and not reasoning:
            QMessageBox.warning(self, "Reasoning Required", f"Add reasoning before marking this source as {status}.")
            return False
        if status == "included" and not scope:
            QMessageBox.warning(self, "Scope Required", "Choose a relevance scope before including this source.")
            return False
        try:
            source_db = self._source_triage_db()
            record_id = self.triage_inclusion_record_id
            if not record_id:
                record_id = source_db.create_inclusion_record(
                    source_id,
                    project_id=self._current_inclusion_project_id(),
                    db_path=self.db_path,
                )
                self.triage_inclusion_record_id = record_id
            source_db.update_inclusion_status(
                record_id,
                status,
                reasoning=reasoning if reasoning else None,
                db_path=self.db_path,
            )
            source_db.update_inclusion_scope(record_id, scope, db_path=self.db_path)
            source_db.update_inclusion_notes(
                record_id,
                project_role_note=role_note,
                screening_depth=depth,
                db_path=self.db_path,
            )
            self.triage_metadata_dirty = False
            if hasattr(self, "source_library_filter"):
                current_filter = self._source_filter_value()
                next_filter = None
                if self.current_project_id and current_filter == "needs_project_screening":
                    next_filter = "project_screened"
                elif not self.current_project_id and current_filter == "needs_screening":
                    next_filter = "staged"
                if next_filter is not None:
                    with QSignalBlocker(self.source_library_filter):
                        self._set_combo_by_data(self.source_library_filter, next_filter)
            self._refresh_doc_list()
            self._load_triage_metadata_for_current_source()
            self._set_workspace_status(self.triage_panel_hint, "Inclusion metadata saved", "idle")
            return True
        except Exception as exc:
            self._set_workspace_status(self.triage_panel_hint, "Save failed - review the message and try again.", "blocked")
            QMessageBox.warning(self, "Triage Save Error", str(exc))
            return False

    def _rebuild_more_menu(self):
        if not hasattr(self, "more_menu"):
            return
        self.more_menu.clear()
        if self.current_session_id:
            end_session_action = self.more_menu.addAction("End Current Session")
            end_session_action.triggered.connect(self._end_current_session)
            self.more_menu.addSeparator()
        refresh_action = self.more_menu.addAction("Refresh View")
        refresh_action.triggered.connect(self.refresh_current_view)
        cleanup_action = self.more_menu.addAction("Clean Up Metadata...")
        cleanup_action.triggered.connect(self.clean_up_library_metadata)
        self.more_menu.addSeparator()
        export_action = self.more_menu.addAction("Export…")
        export_action.triggered.connect(self.export_deliverable)
        thumbnails_action = self.more_menu.addAction("Page Thumbnails")
        thumbnails_action.setEnabled(self.doc is not None)
        thumbnails_action.triggered.connect(self.open_thumbnails)
        shortcuts_action = self.more_menu.addAction("Customize Shortcuts…")
        shortcuts_action.triggered.connect(self.customize_shortcuts)
        self.more_menu.addSeparator()
        zoom_in_action = self.more_menu.addAction("Zoom In")
        zoom_in_action.setEnabled(self.doc is not None)
        zoom_in_action.triggered.connect(self.zoom_in)
        zoom_out_action = self.more_menu.addAction("Zoom Out")
        zoom_out_action.setEnabled(self.doc is not None)
        zoom_out_action.triggered.connect(self.zoom_out)
        fit_action = self.more_menu.addAction("Fit to Width")
        fit_action.setCheckable(True)
        fit_action.setChecked(self.fit_to_width)
        fit_action.setEnabled(self.doc is not None)
        fit_action.triggered.connect(
            lambda checked: self.on_fit_width_changed(Qt.Checked if checked else Qt.Unchecked)
        )
        continuous_action = self.more_menu.addAction("Continuous Pages")
        continuous_action.setCheckable(True)
        continuous_action.setChecked(self.continuous)
        continuous_action.setEnabled(self.doc is not None)
        continuous_action.triggered.connect(lambda checked: self.toggle_continuous(bool(checked)))
        if self.search_query:
            self.more_menu.addSeparator()
            next_match_action = self.more_menu.addAction("Next Search Match")
            next_match_action.triggered.connect(self.goto_next_search_result)
            previous_match_action = self.more_menu.addAction("Previous Search Match")
            previous_match_action.triggered.connect(self.goto_previous_search_result)

    def toggle_theme(self):
        self.theme_mode = "dark" if self.theme_mode == "light" else "light"
        self._apply_theme()

    def _update_organizer_toggle_label(self):
        if not hasattr(self, "organizer_toggle_btn") or not hasattr(self, "organizer_panel"):
            return
        visible = self.organizer_panel.isVisible()
        self.organizer_toggle_btn.setText("Hide" if visible else "Show")
        self.organizer_toggle_btn.setChecked(not visible)

    def _toggle_organizer(self):
        if not hasattr(self, "organizer_panel"):
            return
        self.organizer_panel.setVisible(not self.organizer_panel.isVisible())
        self._update_organizer_toggle_label()

    def _set_organizer_save_feedback(self, message, state="idle", button_text=None, reset_button=True):
        if hasattr(self, "organizer_status_label"):
            self.organizer_status_label.setText(message)
            self.organizer_status_label.setProperty("statusState", state)
            self.organizer_status_label.style().unpolish(self.organizer_status_label)
            self.organizer_status_label.style().polish(self.organizer_status_label)
        if hasattr(self, "save_source_details_btn"):
            self.save_source_details_btn.setText(button_text or "Save Source Details")
            self.save_source_details_btn.setProperty("saveState", state if state in {"saved", "blocked"} else "")
            self.save_source_details_btn.style().unpolish(self.save_source_details_btn)
            self.save_source_details_btn.style().polish(self.save_source_details_btn)
            if reset_button and state in {"saved", "blocked"}:
                QTimer.singleShot(1600, self._reset_source_details_button)

    def _reset_source_details_button(self):
        if not hasattr(self, "save_source_details_btn"):
            return
        self.save_source_details_btn.setText("Save Source Details")
        self.save_source_details_btn.setProperty("saveState", "")
        self.save_source_details_btn.style().unpolish(self.save_source_details_btn)
        self.save_source_details_btn.style().polish(self.save_source_details_btn)

    def _update_annotation_workspace_toggle_label(self):
        if not hasattr(self, "annotation_workspace_toggle_btn"):
            return
        visible = getattr(self, "annotation_workspace_visible", True)
        self.annotation_workspace_toggle_btn.setText("Hide" if visible else "Show")
        self.annotation_workspace_toggle_btn.setChecked(not visible)

    def _set_annotation_workspace_visible(self, visible, remember_sizes=True):
        if not hasattr(self, "right_panel_splitter") or not hasattr(self, "annotation_workspace_panel"):
            return
        visible = bool(visible)
        if visible == getattr(self, "annotation_workspace_visible", True):
            self._update_annotation_workspace_toggle_label()
            return
        if remember_sizes:
            sizes = self.right_panel_splitter.sizes()
            if len(sizes) == 2 and sizes[1] > 40:
                self.annotation_workspace_last_sizes = sizes
        self.annotation_workspace_visible = visible
        self.annotation_workspace_panel.setVisible(visible)
        if visible:
            sizes = getattr(self, "annotation_workspace_last_sizes", [340, 420])
            if not sizes or len(sizes) != 2:
                sizes = [340, 420]
            total = sum(self.right_panel_splitter.sizes()) or sum(sizes) or 760
            bottom = max(260, sizes[1])
            top = max(180, total - bottom)
            self.right_panel_splitter.setSizes([top, bottom])
        else:
            total = sum(self.right_panel_splitter.sizes()) or 760
            self.right_panel_splitter.setSizes([max(260, total), 0])
        self._update_annotation_workspace_toggle_label()

    def _toggle_annotation_workspace(self):
        visible = not getattr(self, "annotation_workspace_visible", True)
        if not visible:
            self.annotation_focus_mode = False
            self._apply_annotation_saved_panel_mode(False)
        self._set_annotation_workspace_visible(visible)
        if visible:
            has_active_draft = (
                (self.annotation_draft_mode == "editing_existing" and self.current_annotation_id)
                or self.selected_text_edit.toPlainText().strip()
            )
            self._set_annotation_focus_mode(bool(has_active_draft))

    def _apply_annotation_saved_panel_mode(self, compact):
        compact = bool(compact)
        self.annotation_saved_panel_compact = compact
        show_saved_panel_chrome = (
            not compact
            and self.current_document_id is not None
            and self.annotation_saved_panel_has_results
        )
        if hasattr(self, "annotation_list_hint"):
            self.annotation_list_hint.setVisible(not compact)
        if hasattr(self, "search_box"):
            self.search_box.setVisible(show_saved_panel_chrome)
        if hasattr(self, "annotation_scope_combo"):
            self.annotation_scope_combo.setVisible(show_saved_panel_chrome)
        if hasattr(self, "annotation_type_filter_combo"):
            self.annotation_type_filter_combo.setVisible(show_saved_panel_chrome)
        if hasattr(self, "annotation_sort_combo"):
            self.annotation_sort_combo.setVisible(show_saved_panel_chrome)
        if hasattr(self, "annotation_tag_filter_combo"):
            self.annotation_tag_filter_combo.setVisible(show_saved_panel_chrome)
        if hasattr(self, "annotation_list"):
            self.annotation_list.setMaximumHeight(96 if compact else 16777215)
        self._filter_annotations()

    def _set_annotation_focus_mode(self, active):
        active = bool(active)
        self.annotation_focus_mode = active
        self._apply_annotation_saved_panel_mode(active)
        if hasattr(self, "right_panel_splitter"):
            total = sum(self.right_panel_splitter.sizes()) or 760
            if active:
                top = 128 if self.current_annotation_id else 90
                self.right_panel_splitter.setSizes([top, max(320, total - top)])
            elif getattr(self, "annotation_workspace_visible", True):
                sizes = getattr(self, "annotation_workspace_last_sizes", [340, 420])
                if not sizes or len(sizes) != 2:
                    sizes = [340, 420]
                self.right_panel_splitter.setSizes(sizes)

    def _on_right_panel_splitter_moved(self, pos, index):
        if not hasattr(self, "right_panel_splitter"):
            return
        sizes = self.right_panel_splitter.sizes()
        if len(sizes) != 2:
            return
        top_size, bottom_size = sizes
        if bottom_size > 40:
            self.annotation_workspace_last_sizes = sizes
        if not getattr(self, "annotation_focus_mode", False):
            return
        if top_size >= 180 and getattr(self, "annotation_saved_panel_compact", False):
            self._apply_annotation_saved_panel_mode(False)
        elif top_size <= 140 and not getattr(self, "annotation_saved_panel_compact", False):
            self._apply_annotation_saved_panel_mode(True)

    def focus_pdf_search(self):
        if hasattr(self, "pdf_search_box"):
            self.pdf_search_box.setFocus()
            self.pdf_search_box.selectAll()

    def _clear_pdf_search(self, clear_box=False):
        self.search_results = []
        self.search_result_index = -1
        self.search_query = ""
        if clear_box and hasattr(self, "pdf_search_box"):
            self.pdf_search_box.clear()
        self._set_search_status_text("")

    def run_pdf_search(self):
        if self.doc is None or not hasattr(self, "pdf_search_box"):
            return
        query = self.pdf_search_box.text().strip()
        self.search_results = []
        self.search_result_index = -1
        self.search_query = query
        if not query:
            self._set_search_status_text("")
            self.draw_page_highlights(self.current_page)
            return
        flags = fitz.TEXT_DEHYPHENATE | fitz.TEXT_PRESERVE_WHITESPACE
        for page_index in range(self.total_pages):
            page = self.doc.load_page(page_index)
            try:
                rects = page.search_for(query, flags=flags)
            except TypeError:
                rects = page.search_for(query)
            for rect in rects or []:
                self.search_results.append({"page": page_index, "rect": rect})
        if not self.search_results:
            self._set_search_status_text("0")
            self.draw_page_highlights(self.current_page)
            return
        self.search_result_index = 0
        self._go_to_search_result(0)

    def _go_to_search_result(self, index):
        if not self.search_results:
            return
        self.search_result_index = index % len(self.search_results)
        match = self.search_results[self.search_result_index]
        self._set_search_status_text(f"{self.search_result_index + 1}/{len(self.search_results)}")
        self.render_page(match["page"])

    def goto_next_search_result(self):
        if not self.search_results:
            if hasattr(self, "pdf_search_box") and self.pdf_search_box.text().strip():
                self.run_pdf_search()
            return
        self._go_to_search_result(self.search_result_index + 1)

    def goto_previous_search_result(self):
        if not self.search_results:
            if hasattr(self, "pdf_search_box") and self.pdf_search_box.text().strip():
                self.run_pdf_search()
            return
        self._go_to_search_result(self.search_result_index - 1)

    def _normalize_tag_label(self, label):
        cleaned = re.sub(r"\s+", " ", (label or "").strip())
        return cleaned.strip(" ,;#")

    def _clear_layout_widgets(self, layout):
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self._clear_layout_widgets(child_layout)

    def _load_system_annotation_tags(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT label FROM tags WHERE category = 'system' ORDER BY LOWER(label)"
                ).fetchall()
            self.system_annotation_tags = [row[0] for row in rows if row and row[0]]
        except sqlite3.Error:
            self.system_annotation_tags = ["theory", "method", "finding", "limitation", "contradiction", "definition", "evidence"]

    def _add_single_annotation_tag(self, tag):
        cleaned = self._normalize_tag_label(tag)
        if not cleaned:
            return
        merged = list(self.current_annotation_tags)
        merged.append(cleaned)
        self._set_annotation_tags(merged)

    def _remove_annotation_tag(self, tag):
        cleaned = self._normalize_tag_label(tag)
        self._set_annotation_tags([existing for existing in self.current_annotation_tags if existing.lower() != cleaned.lower()])

    def _set_annotation_tags(self, tags):
        normalized = []
        seen = set()
        for tag in tags or []:
            cleaned = self._normalize_tag_label(tag)
            key = cleaned.lower()
            if not cleaned or key in seen:
                continue
            normalized.append(cleaned)
            seen.add(key)
        self.current_annotation_tags = normalized
        self._refresh_annotation_tag_chips()
        self._refresh_suggested_tag_chips()

    def _refresh_annotation_tag_chips(self):
        if not hasattr(self, "annotation_tags_chip_layout"):
            return
        self._clear_layout_widgets(self.annotation_tags_chip_layout)
        if not self.current_annotation_tags:
            empty_label = QLabel("No tags yet.")
            empty_label.setObjectName("MetaLabel")
            self.annotation_tags_chip_layout.addWidget(empty_label)
            self.annotation_tags_chip_layout.addStretch()
            return
        for tag in self.current_annotation_tags:
            chip = QPushButton(f"{tag} ×")
            chip.setObjectName("TagChipButton")
            chip.setCursor(Qt.PointingHandCursor)
            chip.clicked.connect(lambda _=False, value=tag: self._remove_annotation_tag(value))
            self.annotation_tags_chip_layout.addWidget(chip)
        self.annotation_tags_chip_layout.addStretch()

    def _refresh_suggested_tag_chips(self):
        if not hasattr(self, "annotation_suggested_tags_layout"):
            return
        self._clear_layout_widgets(self.annotation_suggested_tags_layout)
        if not self.system_annotation_tags:
            self._load_system_annotation_tags()
        active = {tag.lower() for tag in self.current_annotation_tags}
        max_cols = 4
        for idx, tag in enumerate(self.system_annotation_tags):
            chip = QPushButton(tag)
            chip.setObjectName("SuggestedTagChip")
            chip.setCursor(Qt.PointingHandCursor)
            chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            chip.setMinimumWidth(chip.sizeHint().width())
            chip.setEnabled(tag.lower() not in active)
            chip.clicked.connect(lambda _=False, value=tag: self._add_single_annotation_tag(value))
            self.annotation_suggested_tags_layout.addWidget(chip, idx // max_cols, idx % max_cols)

    def _add_tags_from_input(self):
        if not hasattr(self, "annotation_tag_input"):
            return
        raw = self.annotation_tag_input.text().strip()
        if not raw:
            return
        parts = re.split(r"[,\n;]+", raw)
        merged = list(self.current_annotation_tags)
        merged.extend(parts)
        self._set_annotation_tags(merged)
        self.annotation_tag_input.clear()

    def _populate_annotation_tag_filter(self, labels):
        if not hasattr(self, "annotation_tag_filter_combo"):
            return
        current = self.annotation_tag_filter_combo.currentData() or ""
        self.annotation_tag_filter_combo.blockSignals(True)
        self.annotation_tag_filter_combo.clear()
        self.annotation_tag_filter_combo.addItem("All tags", "")
        for label in sorted({self._normalize_tag_label(tag) for tag in labels if self._normalize_tag_label(tag)}, key=str.lower):
            self.annotation_tag_filter_combo.addItem(label, label.lower())
        idx = self.annotation_tag_filter_combo.findData(current)
        self.annotation_tag_filter_combo.setCurrentIndex(max(0, idx))
        self.annotation_tag_filter_combo.blockSignals(False)

    def _current_annotation_type(self):
        if not hasattr(self, "annotation_type_combo"):
            return "interpretation"
        return self.annotation_type_combo.currentData() or "interpretation"

    def _set_annotation_type(self, annotation_type):
        if not hasattr(self, "annotation_type_combo"):
            return
        target = annotation_type or "interpretation"
        idx = self.annotation_type_combo.findData(target)
        if idx < 0:
            idx = self.annotation_type_combo.findData("interpretation")
        self.annotation_type_combo.setCurrentIndex(max(0, idx))

    def _current_annotation_writing_project_id(self):
        if not hasattr(self, "annotation_writing_project_combo"):
            return None
        return self.annotation_writing_project_combo.currentData() or None

    def _set_annotation_writing_project(self, project_id):
        if not hasattr(self, "annotation_writing_project_combo"):
            return
        target = project_id or ""
        idx = self.annotation_writing_project_combo.findData(target)
        if idx < 0:
            idx = 0
        self.annotation_writing_project_combo.setCurrentIndex(idx)
        self.current_annotation_writing_project_id = self.annotation_writing_project_combo.currentData() or None

    def _sync_annotation_writing_project_selection(self):
        self.current_annotation_writing_project_id = self._current_annotation_writing_project_id()

    def _set_annotation_draft_mode(self, mode):
        self.annotation_draft_mode = mode or "idle"
        self._update_annotation_workspace_state()

    def _clear_annotation_editor(self, clear_type=False, clear_writing_project=False):
        self.current_annotation_id = None
        self._set_annotation_draft_mode("idle")
        self.selected_text_edit.clear()
        self.note_edit.clear()
        self.ai_explanation_edit.clear()
        if hasattr(self, "annotation_tag_input"):
            self.annotation_tag_input.clear()
        self._set_annotation_tags([])
        self.selection_start_index = None
        self.selection_end_index = None
        self.selection_char_start = None
        self.selection_char_end = None
        self.selection_finalized = False
        self.focus_multi_select_pending = False
        self.selection_regions = []
        self.selected_rect = None
        self.selected_page = None
        self.selected_label = None
        if clear_type:
            self._set_annotation_type("interpretation")
        if clear_writing_project:
            self._set_annotation_writing_project(None)

    def _update_annotation_workspace_state(self):
        if not hasattr(self, "annotation_state_label"):
            return
        if self.annotation_draft_mode == "editing_existing" and self.current_annotation_id:
            self._set_workspace_status(self.annotation_state_label, "Editing saved annotation", "active")
            self._set_annotation_workspace_visible(True, remember_sizes=False)
            self._set_annotation_focus_mode(True)
            if hasattr(self, "save_annotation_btn"):
                self.save_annotation_btn.setText("Update Annotation")
        elif self.selected_text_edit.toPlainText().strip():
            if getattr(self, "reader_mode", "full") == "triage":
                self._set_workspace_status(self.annotation_state_label, "New triage annotation draft", "active")
            else:
                self._set_workspace_status(self.annotation_state_label, "New annotation draft", "active")
            self._set_annotation_workspace_visible(True, remember_sizes=False)
            self._set_annotation_focus_mode(True)
            if hasattr(self, "save_annotation_btn"):
                self.save_annotation_btn.setText("Save Triage Note" if getattr(self, "reader_mode", "full") == "triage" else "Save Annotation")
        else:
            if getattr(self, "reader_mode", "full") == "triage":
                self._set_workspace_status(
                    self.annotation_state_label,
                    "Select text to capture a triage annotation",
                    "idle",
                )
            else:
                self._set_workspace_status(self.annotation_state_label, "Ready for a new annotation", "idle")
            self._set_annotation_workspace_visible(False, remember_sizes=False)
            self._set_annotation_focus_mode(False)
            if hasattr(self, "save_annotation_btn"):
                self.save_annotation_btn.setText("Save Triage Note" if getattr(self, "reader_mode", "full") == "triage" else "Save Annotation")

    def _update_scope_hint(self):
        if not hasattr(self, "scope_hint_label"):
            return
        if self.current_project_id and hasattr(self, "project_combo"):
            project_title = self.project_combo.currentText().strip() or "current project"
            self.scope_hint_label.setText(f"Scope: sources and records in {project_title}")
        else:
            self.scope_hint_label.setText("Scope: all available project records")

    def _update_annotation_type_ui(self):
        annotation_type = self._current_annotation_type()
        type_labels = {
            "quote": "Direct quote",
            "paraphrase": "Paraphrase",
            "interpretation": "Interpretation",
            "synthesis": "Synthesis",
        }
        if hasattr(self, "annotation_type_badge"):
            self.annotation_type_badge.setText(type_labels.get(annotation_type, "Interpretation"))
            self.annotation_type_badge.setProperty("annotationType", annotation_type)
            self.annotation_type_badge.style().unpolish(self.annotation_type_badge)
            self.annotation_type_badge.style().polish(self.annotation_type_badge)
        if hasattr(self, "annotation_type_combo"):
            self.annotation_type_combo.setProperty("annotationType", annotation_type)
            self.annotation_type_combo.style().unpolish(self.annotation_type_combo)
            self.annotation_type_combo.style().polish(self.annotation_type_combo)
        if annotation_type == "quote":
            self.annotation_type_hint.setText("Use for verbatim source text. Selection is required and page number will anchor the citation.")
            self.selected_text_edit.setPlaceholderText("Select the exact quoted text on the PDF…")
            self.note_edit.setPlaceholderText("Optional: add context or why this quote matters.")
        elif annotation_type == "paraphrase":
            self.annotation_type_hint.setText("Use for restating the source in your own words. Selection anchors the source; your note is the primary content.")
            self.selected_text_edit.setPlaceholderText("Select the source passage you are paraphrasing…")
            self.note_edit.setPlaceholderText("Restate the idea in your own words.")
        elif annotation_type == "interpretation":
            self.annotation_type_hint.setText("Use for your analysis or reaction. Selection gives context; the note is clearly your voice.")
            self.selected_text_edit.setPlaceholderText("Select the passage that triggered your interpretation…")
            self.note_edit.setPlaceholderText("What do you think about this? Record your analysis in your own voice.")
        else:
            self.annotation_type_hint.setText("Use for cross-source or freeform synthesis. A text selection is optional; your note is required.")
            self.selected_text_edit.setPlaceholderText("Optional: select text for context, or leave blank for a free synthesis note.")
            self.note_edit.setPlaceholderText("Capture the connection, comparison, or synthesis in your own words.")

    def _update_library_toggle_label(self):
        if not hasattr(self, "library_toggle_btn") or not hasattr(self, "body_splitter"):
            return
        sizes = self.body_splitter.sizes()
        library_hidden = bool(sizes and sizes[0] == 0)
        self.library_toggle_btn.setText("")
        self.library_toggle_btn.setToolTip("Show library pane" if library_hidden else "Hide library pane")
        self.library_toggle_btn.setChecked(library_hidden)

    def _update_inspector_toggle_label(self):
        if not hasattr(self, "inspector_toggle_btn") or not hasattr(self, "body_splitter"):
            return
        sizes = self.body_splitter.sizes()
        inspector_hidden = bool(len(sizes) >= 3 and sizes[2] == 0)
        self.inspector_toggle_btn.setText("")
        self.inspector_toggle_btn.setToolTip(
            "Show annotation pane" if inspector_hidden else "Hide annotation pane"
        )
        self.inspector_toggle_btn.setChecked(inspector_hidden)

    def _begin_side_panel_resize(self, side: str, global_pos: QPoint):
        self._active_panel_resize_side = side
        self._update_side_panel_resize(side, global_pos)

    def _update_side_panel_resize(self, side: str, global_pos: QPoint):
        if not hasattr(self, "body_splitter"):
            return
        pos = self.body_splitter.mapFromGlobal(global_pos)
        total = self.body_splitter.width()
        sizes = self.body_splitter.sizes()
        if len(sizes) != 3 or total <= 0:
            return
        left_min, left_max = 220, 520
        right_min, right_max = 260, 520
        if side == "left":
            left = max(left_min, min(left_max, pos.x()))
            center = max(360, total - left - sizes[2])
            right = max(right_min, total - left - center)
            self.body_splitter.setSizes([left, center, right])
            self._library_restore_width = left
        elif side == "right":
            right = max(right_min, min(right_max, total - pos.x()))
            left = sizes[0]
            center = max(360, total - left - right)
            self.body_splitter.setSizes([left, center, right])

    def _end_side_panel_resize(self):
        self._active_panel_resize_side = None
        self._update_library_toggle_label()
        self._update_inspector_toggle_label()

    def _toggle_library(self):
        sizes = self.body_splitter.sizes()
        if sizes and sizes[0] == 0:
            restored = getattr(self, "_library_restore_width", 280)
            self.library_scroll.setMinimumWidth(240)
            self.body_splitter.setSizes([restored, max(400, sizes[1]), sizes[2]])
        else:
            if sizes:
                self._library_restore_width = max(220, sizes[0])
                self.library_scroll.setMinimumWidth(0)
                self.body_splitter.setSizes([0, sizes[1] + sizes[0], sizes[2]])
        self._update_library_toggle_label()

    def _toggle_inspector(self):
        if getattr(self, "focus_mode", False):
            self._set_inspector_visible(False)
            return
        sizes = self.body_splitter.sizes()
        if len(sizes) != 3:
            return
        if sizes[2] == 0:
            restored = getattr(self, "_inspector_restore_width", 320)
            self.inspector_scroll.setMinimumWidth(260)
            self.body_splitter.setSizes([sizes[0], max(400, sizes[1] - restored), restored])
        else:
            self._inspector_restore_width = max(260, sizes[2])
            self.inspector_scroll.setMinimumWidth(0)
            self.body_splitter.setSizes([sizes[0], sizes[1] + sizes[2], 0])
        self._update_inspector_toggle_label()
        self._update_focus_handle_visibility()

    def _set_inspector_visible(self, visible: bool, width: int | None = None):
        if not hasattr(self, "body_splitter"):
            return
        sizes = self.body_splitter.sizes()
        if len(sizes) != 3:
            return
        visible = bool(visible)
        if visible:
            restored = width or getattr(self, "_inspector_restore_width", 320)
            restored = max(260, restored)
            self.inspector_scroll.setMinimumWidth(260)
            center = max(400, sizes[1] - restored) if sizes[2] == 0 else sizes[1]
            self.body_splitter.setSizes([sizes[0], center, restored])
        else:
            if sizes[2] > 0:
                self._inspector_restore_width = max(260, sizes[2])
            self.inspector_scroll.setMinimumWidth(0)
            self.body_splitter.setSizes([sizes[0], sizes[1] + sizes[2], 0])
        self._update_inspector_toggle_label()
        self._update_focus_handle_visibility()

    def _open_focus_annotation_panel(self):
        if not getattr(self, "focus_mode", False):
            return
        sizes = self.body_splitter.sizes()
        total = sum(sizes) if len(sizes) == 3 else self.body_splitter.width()
        right = min(max(getattr(self, "_inspector_restore_width", 340), 300), 460)
        center = max(420, total - right)
        self.inspector_scroll.setMinimumWidth(260)
        self.library_scroll.setMinimumWidth(0)
        self.body_splitter.setSizes([0, center, right])
        self._set_annotation_workspace_visible(True, remember_sizes=False)
        self._update_inspector_toggle_label()
        self._update_focus_handle_visibility()

    def _position_focus_handle(self):
        if not hasattr(self, "focus_inspector_handle") or not hasattr(self, "pages_scroll"):
            return
        margin = 14
        x = max(0, self.pages_scroll.viewport().width() - self.focus_inspector_handle.width() - margin)
        y = margin
        self.focus_inspector_handle.move(x, y)

    def _update_focus_handle_visibility(self):
        if not hasattr(self, "focus_inspector_handle"):
            return
        sizes = self.body_splitter.sizes() if hasattr(self, "body_splitter") else []
        inspector_hidden = bool(len(sizes) == 3 and sizes[2] == 0)
        visible = bool(getattr(self, "focus_mode", False) and inspector_hidden)
        self._position_focus_handle()
        self.focus_inspector_handle.setVisible(visible)
        if visible:
            self.focus_inspector_handle.raise_()

    def _enter_focus_mode(self):
        if getattr(self, "focus_mode", False) or not hasattr(self, "body_splitter"):
            return
        sizes = self.body_splitter.sizes()
        self._focus_restore_state = {
            "sizes": sizes,
            "ribbon_visible": self.ribbon.isVisible() if hasattr(self, "ribbon") else True,
            "fullscreen": self.isFullScreen(),
            "window_state": self.windowState(),
            "geometry": self.saveGeometry(),
        }
        if len(sizes) == 3:
            if sizes[0] > 0:
                self._library_restore_width = max(220, sizes[0])
            if sizes[2] > 0:
                self._inspector_restore_width = max(260, sizes[2])
        self.focus_mode = True
        if hasattr(self, "ribbon"):
            self.ribbon.setVisible(False)
        self.library_scroll.setMinimumWidth(0)
        self.inspector_scroll.setMinimumWidth(0)
        total = sum(sizes) if len(sizes) == 3 else self.body_splitter.width()
        self.body_splitter.setSizes([0, max(600, total), 0])
        if not self.isFullScreen():
            self.showFullScreen()
        self._apply_toolbar_icons()
        self._update_toolbar_context()
        self._update_focus_handle_visibility()

    def _exit_focus_mode(self):
        if not getattr(self, "focus_mode", False):
            return
        restore = getattr(self, "_focus_restore_state", {}) or {}
        self.focus_mode = False
        if hasattr(self, "ribbon"):
            self.ribbon.setVisible(bool(restore.get("ribbon_visible", True)))
        self.library_scroll.setMinimumWidth(240)
        self.inspector_scroll.setMinimumWidth(260)
        sizes = restore.get("sizes")
        if isinstance(sizes, list) and len(sizes) == 3:
            self.body_splitter.setSizes(sizes)
        previous_state = restore.get("window_state", Qt.WindowNoState)
        previous_geometry = restore.get("geometry")
        if not restore.get("fullscreen", False) and self.isFullScreen():
            self.showNormal()
            if previous_geometry is not None:
                self.restoreGeometry(previous_geometry)
            self.setWindowState(previous_state)
        elif restore.get("fullscreen", False):
            self.setWindowState(previous_state)
        self._focus_restore_state = {}
        self._update_library_toggle_label()
        self._update_inspector_toggle_label()
        self._apply_toolbar_icons()
        self._update_toolbar_context()
        self._update_focus_handle_visibility()

    def _toggle_focus_mode(self):
        if getattr(self, "focus_mode", False):
            self._exit_focus_mode()
        else:
            self._enter_focus_mode()

    def keyReleaseEvent(self, event):
        if (
            getattr(self, "focus_mode", False)
            and event.key() in (Qt.Key_Control, Qt.Key_Meta)
            and getattr(self, "focus_multi_select_pending", False)
            and self.selected_text_edit.toPlainText().strip()
        ):
            self.focus_multi_select_pending = False
            self.selection_finalized = True
            self._open_focus_annotation_panel()
            QTimer.singleShot(0, self.note_edit.setFocus)
            event.accept()
            return
        super().keyReleaseEvent(event)

    def _handle_escape(self):
        if getattr(self, "focus_mode", False):
            sizes = self.body_splitter.sizes() if hasattr(self, "body_splitter") else []
            if self._cancel_focus_selection():
                return
            if len(sizes) == 3 and sizes[2] > 0:
                self._set_inspector_visible(False)
                return
            self._exit_focus_mode()

    def _cancel_focus_selection(self):
        has_draft = (
            self.annotation_draft_mode == "draft_new"
            or bool(self.selected_text_edit.toPlainText().strip())
            or self.selection_start_index is not None
            or bool(self.selection_regions)
        )
        if not has_draft:
            return False
        page_to_redraw = self.selected_page if self.selected_page is not None else self.current_page
        self._clear_annotation_editor(clear_type=False, clear_writing_project=False)
        if self.doc is not None and page_to_redraw is not None:
            self.draw_page_highlights(page_to_redraw)
        self._set_inspector_visible(False)
        return True

    def _hide_focus_annotation_panel_on_page_click(self):
        if not getattr(self, "focus_mode", False):
            return
        if self.selected_text_edit.toPlainText().strip():
            return
        sizes = self.body_splitter.sizes() if hasattr(self, "body_splitter") else []
        if len(sizes) == 3 and sizes[2] > 0:
            self._set_inspector_visible(False)

    def _load_projects(self, select_project_id=None):
        default_project_id = None
        rows = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT id, title
                    FROM review_projects
                    ORDER BY updated_at DESC, created_at DESC, title ASC
                    """
                ).fetchall()
                if not rows:
                    default_project_id = str(uuid.uuid4())
                    now = datetime.now().isoformat()
                    conn.execute(
                        """
                        INSERT INTO review_projects (id, title, research_question, structure_json, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (default_project_id, "General Research", "", "{}", now, now),
                    )
                    conn.commit()
                    rows = [(default_project_id, "General Research")]
        except sqlite3.Error:
            rows = []

        target_project_id = select_project_id or self.current_project_id or default_project_id or (rows[0][0] if rows else None)
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItem("Library", "")
        active_index = 0
        for idx, (project_id, title) in enumerate(rows, start=1):
            self.project_combo.addItem(title or "Untitled project", project_id)
            if project_id == target_project_id:
                active_index = idx
        self.project_combo.setCurrentIndex(active_index)
        self.project_combo.blockSignals(False)
        self.current_project_id = self.project_combo.currentData() or None
        self._configure_source_filter_options()
        self._update_scope_hint()

    def _load_writing_projects(self, select_project_id=None):
        if not hasattr(self, "annotation_writing_project_combo"):
            self.current_annotation_writing_project_id = select_project_id or None
            return
        rows = []
        target_project_id = select_project_id
        if target_project_id is None:
            target_project_id = self._current_annotation_writing_project_id()
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT id, title
                    FROM writing_projects
                    WHERE COALESCE(status, 'active') <> 'archived'
                    ORDER BY updated_at DESC, created_at DESC, title ASC
                    """
                ).fetchall()
        except sqlite3.Error:
            rows = []
        self.annotation_writing_project_combo.blockSignals(True)
        self.annotation_writing_project_combo.clear()
        self.annotation_writing_project_combo.addItem("General reading", "")
        active_index = 0
        for idx, (project_id, title) in enumerate(rows, start=1):
            self.annotation_writing_project_combo.addItem(title or "Untitled writing project", project_id)
            if project_id == target_project_id:
                active_index = idx
        self.annotation_writing_project_combo.setCurrentIndex(active_index)
        self.annotation_writing_project_combo.blockSignals(False)
        self.current_annotation_writing_project_id = self.annotation_writing_project_combo.currentData() or None

    def create_writing_project(self):
        title, ok = QInputDialog.getText(self, "New Writing Project", "Project title:")
        if not ok or not title.strip():
            return
        project_type, ok_type = QInputDialog.getItem(
            self,
            "Writing Project Type",
            "Type:",
            ["paper", "essay", "thesis_chapter", "presentation", "general"],
            0,
            False,
        )
        if not ok_type:
            return
        project_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO writing_projects (id, title, type, status, due_date, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (project_id, title.strip(), project_type, "active", None, now, now),
                )
                conn.commit()
        except sqlite3.Error as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Writing Project Error", f"Could not create the writing project.\n\n{exc}")
            return
        self._load_writing_projects(select_project_id=project_id)

    def _on_project_changed(self):
        self.current_project_id = self.project_combo.currentData() or None
        self._configure_source_filter_options()
        self._update_scope_hint()
        self._clear_annotation_editor(clear_type=True, clear_writing_project=False)
        self._refresh_current_project_source()
        self._refresh_doc_list()
        self.load_annotations()
        self._update_ribbon_status()
        if self.current_document_id and self.current_project_source_id:
            self._load_current_document_into_organizer()
        elif self.current_document_id and not self.current_project_source_id:
            self._clear_doc_organizer()
        if self.reader_mode == "triage":
            self._load_triage_metadata_for_current_source()
        self._update_project_context_panel()
        if self.doc is not None:
            self.draw_page_highlights(self.current_page)

    def create_project(self):
        title, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok or not title.strip():
            return
        question, ok_question = QInputDialog.getText(self, "Research Question", "Optional research question:")
        if not ok_question:
            question = ""
        project_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO review_projects (id, title, research_question, structure_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (project_id, title.strip(), question.strip(), "{}", now, now),
                )
                conn.commit()
        except sqlite3.Error as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Project Error", f"Could not create the project.\n\n{exc}")
            return
        self._load_projects(select_project_id=project_id)
        self._refresh_doc_list()

    def _staged_included_sources(self):
        return [
            row
            for row in self._source_triage_db().get_staging_pool(db_path=self.db_path)
            if row.get("inclusion_status") == "included"
        ]

    def _source_confirmation_text(self, source):
        parts = [source.get("title") or os.path.basename(source.get("file_path") or "") or "Untitled source"]
        meta = []
        if source.get("relevance_scope"):
            meta.append(str(source["relevance_scope"]).title())
        if source.get("screening_depth"):
            meta.append(f"Depth: {source['screening_depth']}")
        if source.get("inclusion_reasoning"):
            meta.append(self._truncate_session_text(source["inclusion_reasoning"], max_len=82))
        if meta:
            parts.append(" - ".join(meta))
        return "\n".join(parts)

    def _scope_material_for_sources(self, source_ids):
        if not source_ids:
            return []
        placeholders = ",".join("?" for _ in source_ids)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT DISTINCT
                    a.id,
                    COALESCE(s.canonical_title, d.title, s.file_path, 'Untitled source') AS source_title,
                    a.page_number,
                    COALESCE(a.selected_text, '') AS selected_text,
                    COALESCE(a.note_content, '') AS note_content
                FROM sources s
                LEFT JOIN documents d
                    ON (
                        (s.file_path IS NOT NULL AND s.file_path <> '' AND d.file_path = s.file_path)
                        OR (
                            (s.file_path IS NULL OR s.file_path = '')
                            AND d.title = s.canonical_title
                        )
                    )
                LEFT JOIN project_sources ps ON ps.source_id = s.id
                JOIN annotations a
                    ON (
                        (d.id IS NOT NULL AND a.document_id = d.id)
                        OR (ps.id IS NOT NULL AND a.project_source_id = ps.id)
                    )
                WHERE s.id IN ({placeholders})
                  AND a.triage = 1
                  AND COALESCE(a.annotation_type, 'interpretation') = 'interpretation'
                ORDER BY source_title ASC, a.page_number ASC, a.created_at ASC
                """,
                tuple(source_ids),
            ).fetchall()
        material = []
        for _annotation_id, source_title, page_number, selected_text, note_content in rows:
            body = (note_content or selected_text or "").strip()
            if not body:
                continue
            page = f"p. {int(page_number) + 1}" if page_number is not None else "page unknown"
            material.append(f"{source_title} ({page}): {body}")
        return material

    def _update_staged_source_inclusion_from_review(self, source):
        inclusion_id = source.get("inclusion_id")
        if not inclusion_id:
            return
        source_db = self._source_triage_db()
        source_db.update_inclusion_scope(
            inclusion_id,
            source.get("relevance_scope") or None,
            db_path=self.db_path,
        )
        source_db.update_inclusion_notes(
            inclusion_id,
            project_role_note=source.get("project_role_note") or None,
            screening_depth=source.get("screening_depth") or None,
            db_path=self.db_path,
        )

    def _collect_project_from_staged_inputs(self, staged_sources):
        dialog = QDialog(self)
        dialog.setWindowTitle("Create Project from Staged Sources")
        dialog.resize(980, 620)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        intro = QLabel("Review included staged sources, tune their project roles, and draft the scope before creating the project.")
        intro.setObjectName("MetaLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        source_table = QTableWidget(len(staged_sources), 6)
        source_table.setHorizontalHeaderLabels(["Include", "Title", "Role", "Depth", "Reasoning", "Project Note"])
        source_table.verticalHeader().setVisible(False)
        source_table.setAlternatingRowColors(True)
        source_table.setSelectionBehavior(QTableWidget.SelectRows)
        source_table.setSelectionMode(QTableWidget.SingleSelection)
        header = source_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        header.setSectionResizeMode(5, QHeaderView.Interactive)
        source_table.setColumnWidth(4, 230)
        source_table.setColumnWidth(5, 210)
        source_table.setMinimumHeight(220)

        scope_options = [
            ("Central", "central"),
            ("Supporting", "supporting"),
            ("Methodological", "methodological"),
            ("Comparative", "comparative"),
            ("Peripheral", "peripheral"),
        ]
        depth_options = [
            ("Abstract", "abstract"),
            ("Skim", "skim"),
            ("Targeted", "targeted"),
            ("Full", "full"),
        ]
        role_combos = {}
        depth_combos = {}
        for row, source in enumerate(staged_sources):
            include_item = QTableWidgetItem("")
            include_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            include_item.setCheckState(Qt.Checked)
            include_item.setData(Qt.UserRole, source)
            source_table.setItem(row, 0, include_item)

            title_item = QTableWidgetItem(source.get("title") or os.path.basename(source.get("file_path") or "") or "Untitled source")
            title_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            source_table.setItem(row, 1, title_item)

            role_combo = QComboBox()
            for label, value in scope_options:
                role_combo.addItem(label, value)
            self._set_combo_by_data(role_combo, source.get("relevance_scope") or "supporting")
            source_table.setCellWidget(row, 2, role_combo)
            role_combos[row] = role_combo

            depth_combo = QComboBox()
            depth_combo.addItem("Unset", "")
            for label, value in depth_options:
                depth_combo.addItem(label, value)
            self._set_combo_by_data(depth_combo, source.get("screening_depth") or "")
            source_table.setCellWidget(row, 3, depth_combo)
            depth_combos[row] = depth_combo

            reason_item = QTableWidgetItem(source.get("inclusion_reasoning") or "")
            reason_item.setToolTip(source.get("inclusion_reasoning") or "")
            reason_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            source_table.setItem(row, 4, reason_item)

            note_item = QTableWidgetItem(source.get("project_role_note") or "")
            source_table.setItem(row, 5, note_item)
        layout.addWidget(source_table)

        title_edit = QLineEdit()
        title_edit.setPlaceholderText("Project title")
        layout.addWidget(title_edit)

        scope_material_label = QLabel("Central interpretation notes available for scope drafting:")
        scope_material_label.setObjectName("MetaLabel")
        layout.addWidget(scope_material_label)

        scope_material = QTextEdit()
        scope_material.setReadOnly(True)
        scope_material.setMaximumHeight(118)
        central_source_ids = [
            source["source_id"]
            for source in staged_sources
            if source.get("relevance_scope") == "central"
        ]
        central_material = self._scope_material_for_sources(central_source_ids)
        scope_material.setPlainText("\n\n".join(central_material) if central_material else "No central triage interpretation notes yet.")
        layout.addWidget(scope_material)

        scope_edit = QTextEdit()
        scope_edit.setPlaceholderText("Draft the project research question or scope statement")
        scope_edit.setMaximumHeight(110)
        scope_edit.setTabChangesFocus(True)
        layout.addWidget(scope_edit)

        hint = QLabel("Select at least one central source. Abstract-depth sources are allowed, but should usually be revisited after project creation.")
        hint.setObjectName("MetaLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        create_btn = QPushButton("Create Project")
        create_btn.setObjectName("AccentButton")
        button_row.addWidget(cancel_btn)
        button_row.addWidget(create_btn)
        layout.addLayout(button_row)

        cancel_btn.clicked.connect(dialog.reject)
        create_btn.clicked.connect(dialog.accept)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        selected_sources = []
        for row in range(source_table.rowCount()):
            item = source_table.item(row, 0)
            if item.checkState() != Qt.Checked:
                continue
            source = dict(item.data(Qt.UserRole))
            source["relevance_scope"] = role_combos[row].currentData()
            source["screening_depth"] = depth_combos[row].currentData() or None
            source["project_role_note"] = (source_table.item(row, 5).text() if source_table.item(row, 5) else "").strip()
            selected_sources.append(source)
        return {
            "title": title_edit.text().strip(),
            "scope": scope_edit.toPlainText().strip(),
            "sources": selected_sources,
        }

    def create_project_from_staged_sources(self):
        staged_sources = self._staged_included_sources()
        if not staged_sources:
            QMessageBox.information(
                self,
                "No Included Staged Sources",
                "Mark at least one staged source as included before creating a project from the staging pool.",
            )
            return
        inputs = self._collect_project_from_staged_inputs(staged_sources)
        if not inputs:
            return
        title = inputs["title"]
        selected_sources = inputs["sources"]
        if not title:
            QMessageBox.warning(self, "Project Title Required", "Add a project title before creating the project.")
            return
        if not selected_sources:
            QMessageBox.warning(self, "Sources Required", "Select at least one staged source for this project.")
            return
        if not any(source.get("relevance_scope") == "central" for source in selected_sources):
            QMessageBox.warning(
                self,
                "Central Source Required",
                "Select at least one source with relevance scope set to central.",
            )
            return
        project_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        source_ids = [source["source_id"] for source in selected_sources]
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO review_projects (id, title, research_question, structure_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (project_id, title, inputs["scope"], "{}", now, now),
                )
                conn.commit()
            for source in selected_sources:
                self._update_staged_source_inclusion_from_review(source)
            self._source_triage_db().seed_project_inclusions(
                project_id,
                source_ids,
                db_path=self.db_path,
            )
            for source_id in source_ids:
                self._attach_source_to_project(source_id, project_id)
        except Exception as exc:
            QMessageBox.warning(self, "Project Creation Error", f"Could not create the project from staged sources.\n\n{exc}")
            return
        self._load_projects(select_project_id=project_id)
        self._refresh_doc_list()
        QMessageBox.information(
            self,
            "Project Created",
            f"Created {title} with {len(source_ids)} staged {self._pluralize(len(source_ids), 'source')}.",
        )

    def _screened_sources_available_for_project(self):
        if not self.current_project_id:
            return []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    s.id AS source_id,
                    COALESCE(s.canonical_title, s.file_path, 'Untitled source') AS title,
                    COALESCE(s.file_path, '') AS file_path,
                    si.inclusion_status,
                    si.relevance_scope,
                    si.screening_depth,
                    si.inclusion_reasoning,
                    si.project_role_note,
                    si.updated_at,
                    COALESCE(rp.title, 'Global screening') AS screened_context
                FROM sources s
                JOIN source_inclusion si ON si.source_id = s.id
                LEFT JOIN review_projects rp ON rp.id = si.project_id
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM project_sources ps
                    WHERE ps.source_id = s.id
                      AND ps.project_id = ?
                    LIMIT 1
                )
                AND si.updated_at = (
                    SELECT MAX(si2.updated_at)
                    FROM source_inclusion si2
                    WHERE si2.source_id = s.id
                )
                ORDER BY LOWER(COALESCE(s.canonical_title, s.file_path, '')) ASC
                """,
                (self.current_project_id,),
            ).fetchall()
        return [
            {
                "source_id": row[0],
                "title": row[1],
                "file_path": row[2],
                "inclusion_status": row[3],
                "relevance_scope": row[4],
                "screening_depth": row[5],
                "inclusion_reasoning": row[6],
                "project_role_note": row[7],
                "updated_at": row[8],
                "screened_context": row[9],
            }
            for row in rows
        ]

    def _screened_source_row_text(self, source):
        title = source.get("title") or os.path.basename(source.get("file_path") or "") or "Untitled source"
        meta = []
        if source.get("inclusion_status"):
            meta.append(str(source["inclusion_status"]).title())
        if source.get("relevance_scope"):
            meta.append(str(source["relevance_scope"]).title())
        if source.get("screening_depth"):
            meta.append(f"Depth: {source['screening_depth']}")
        if source.get("screened_context"):
            meta.append(source["screened_context"])
        return f"{title}\n{' - '.join(meta)}" if meta else title

    def _collect_existing_source_project_inputs(self, sources):
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Existing Screened Source")
        dialog.resize(460, 560)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        intro = QLabel("Choose a screened source to reuse or re-triage for this project.")
        intro.setObjectName("MetaLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        source_list = QListWidget()
        source_list.setWordWrap(True)
        source_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        source_list.setMinimumHeight(220)
        for source in sources:
            item = QListWidgetItem(self._screened_source_row_text(source))
            item.setSizeHint(QSize(420, 64))
            item.setData(Qt.UserRole, source)
            source_list.addItem(item)
        source_list.setCurrentRow(0)
        layout.addWidget(source_list)

        action_combo = QComboBox()
        action_combo.addItem("Use existing screening", "reuse")
        action_combo.addItem("Re-triage for this project", "retriage")
        layout.addWidget(action_combo)

        scope_combo = QComboBox()
        scope_combo.addItem("Central", "central")
        scope_combo.addItem("Supporting", "supporting")
        scope_combo.addItem("Methodological", "methodological")
        scope_combo.addItem("Comparative", "comparative")
        scope_combo.addItem("Peripheral", "peripheral")
        layout.addWidget(scope_combo)

        reasoning_edit = QTextEdit()
        reasoning_edit.setPlaceholderText("Why does this source belong in this project?")
        reasoning_edit.setMaximumHeight(92)
        reasoning_edit.setTabChangesFocus(True)
        layout.addWidget(reasoning_edit)

        role_note_edit = QTextEdit()
        role_note_edit.setPlaceholderText("Optional project role note")
        role_note_edit.setMaximumHeight(72)
        role_note_edit.setTabChangesFocus(True)
        layout.addWidget(role_note_edit)

        def populate_from_selection():
            source = source_list.currentItem().data(Qt.UserRole) if source_list.currentItem() else {}
            self._set_combo_by_data(scope_combo, source.get("relevance_scope") or "supporting")
            reasoning_edit.setPlainText(source.get("inclusion_reasoning") or "")
            role_note_edit.setPlainText(source.get("project_role_note") or "")

        source_list.currentItemChanged.connect(lambda _current, _previous: populate_from_selection())
        populate_from_selection()

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        add_btn = QPushButton("Continue")
        add_btn.setObjectName("AccentButton")
        button_row.addWidget(cancel_btn)
        button_row.addWidget(add_btn)
        layout.addLayout(button_row)
        cancel_btn.clicked.connect(dialog.reject)
        add_btn.clicked.connect(dialog.accept)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        item = source_list.currentItem()
        if item is None:
            return None
        return {
            "source": item.data(Qt.UserRole),
            "action": action_combo.currentData(),
            "scope": scope_combo.currentData(),
            "reasoning": reasoning_edit.toPlainText().strip(),
            "role_note": role_note_edit.toPlainText().strip(),
        }

    def _project_inclusion_record_id(self, source_id, project_id):
        source_db = self._source_triage_db()
        existing = source_db.get_inclusion_record(source_id, project_id=project_id, db_path=self.db_path)
        if existing:
            return existing["id"]
        return source_db.create_inclusion_record(source_id, project_id=project_id, db_path=self.db_path)

    def _seed_project_inclusion_from_screening(self, source):
        source_id = source["source_id"]
        record_id = self._project_inclusion_record_id(source_id, self.current_project_id)
        source_db = self._source_triage_db()
        status = source.get("inclusion_status") or "candidate"
        reasoning = source.get("inclusion_reasoning") or None
        if status in {"included", "excluded"} and not reasoning:
            status = "candidate"
        source_db.update_inclusion_status(
            record_id,
            status,
            reasoning=reasoning,
            db_path=self.db_path,
        )
        source_db.update_inclusion_scope(
            record_id,
            source.get("relevance_scope") or None,
            db_path=self.db_path,
        )
        source_db.update_inclusion_notes(
            record_id,
            project_role_note=source.get("project_role_note") or None,
            screening_depth=source.get("screening_depth") or None,
            db_path=self.db_path,
        )
        return record_id

    def _add_existing_source_using_screening(self, source, scope, reasoning, role_note):
        if not reasoning:
            QMessageBox.warning(self, "Reasoning Required", "Add project-specific reasoning before including this source.")
            return False
        source_id = source["source_id"]
        source_db = self._source_triage_db()
        record_id = self._project_inclusion_record_id(source_id, self.current_project_id)
        source_db.update_inclusion_status(
            record_id,
            "included",
            reasoning=reasoning,
            db_path=self.db_path,
        )
        source_db.update_inclusion_scope(record_id, scope, db_path=self.db_path)
        source_db.update_inclusion_notes(
            record_id,
            project_role_note=role_note or None,
            screening_depth=source.get("screening_depth"),
            db_path=self.db_path,
        )
        self._attach_source_to_project(source_id, self.current_project_id)
        return True

    def _source_document_for_open(self, source_id):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT d.id, d.file_path
                FROM sources s
                JOIN documents d
                    ON (
                        (s.file_path IS NOT NULL AND s.file_path <> '' AND d.file_path = s.file_path)
                        OR (
                            (s.file_path IS NULL OR s.file_path = '')
                            AND d.title = s.canonical_title
                        )
                    )
                WHERE s.id = ?
                ORDER BY d.updated_at DESC, d.created_at DESC
                LIMIT 1
                """,
                (source_id,),
            ).fetchone()
        return row if row else None

    def _open_source_for_project_retriage(self, source):
        source_id = source["source_id"]
        self._seed_project_inclusion_from_screening(source)
        self._attach_source_to_project(source_id, self.current_project_id)
        doc_row = self._source_document_for_open(source_id)
        self._load_projects(select_project_id=self.current_project_id)
        self._set_reader_mode("triage")
        self._refresh_doc_list()
        if doc_row and doc_row[1] and os.path.exists(doc_row[1]):
            self._load_pdf(doc_row[1], target_document_id=doc_row[0])
        else:
            QMessageBox.information(
                self,
                "Source Attached",
                "The source was attached to the project, but no local PDF file was available to open for re-triage.",
            )

    def add_existing_screened_source_to_project(self):
        if not self.current_project_id:
            QMessageBox.information(
                self,
                "Choose a Project",
                "Select or create a project before adding an existing screened source.",
            )
            return
        sources = self._screened_sources_available_for_project()
        if not sources:
            QMessageBox.information(
                self,
                "No Screened Sources",
                "No screened sources are available to add to this project yet.",
            )
            return
        inputs = self._collect_existing_source_project_inputs(sources)
        if not inputs:
            return
        if inputs["action"] == "reuse":
            if not self._add_existing_source_using_screening(
                inputs["source"],
                inputs["scope"],
                inputs["reasoning"],
                inputs["role_note"],
            ):
                return
            self._refresh_doc_list()
            QMessageBox.information(self, "Source Added", "Added the screened source to this project.")
        else:
            self._open_source_for_project_retriage(inputs["source"])

    def _assign_document_to_project(self, document_id, project_id):
        if not document_id or not project_id:
            return
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO review_project_documents (project_id, document_id)
                VALUES (?, ?)
                """,
                (project_id, document_id),
            )
            conn.execute(
                "UPDATE review_projects SET updated_at = ? WHERE id = ?",
                (now, project_id),
            )
            conn.commit()
        self._ensure_project_source_for_document(document_id, project_id)

    def _document_id_for_source(self, conn, source_id):
        row = conn.execute(
            """
            SELECT d.id
            FROM sources s
            JOIN documents d
                ON (
                    (s.file_path IS NOT NULL AND s.file_path <> '' AND d.file_path = s.file_path)
                    OR (
                        (s.file_path IS NULL OR s.file_path = '')
                        AND d.title = s.canonical_title
                    )
                )
            WHERE s.id = ?
            ORDER BY d.updated_at DESC, d.created_at DESC
            LIMIT 1
            """,
            (source_id,),
        ).fetchone()
        return row[0] if row else None

    def _attach_source_to_project(self, source_id, project_id):
        if not source_id or not project_id:
            return None
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            existing = conn.execute(
                """
                SELECT id
                FROM project_sources
                WHERE project_id = ? AND source_id = ?
                LIMIT 1
                """,
                (project_id, source_id),
            ).fetchone()
            if existing:
                return existing[0]
            source = conn.execute(
                """
                SELECT canonical_title, file_path, citation_metadata, created_at, updated_at
                FROM sources
                WHERE id = ?
                LIMIT 1
                """,
                (source_id,),
            ).fetchone()
            if not source:
                raise ValueError(f"Source does not exist: {source_id}")
            title, file_path, citation_metadata, created_at, updated_at = source
            document_id = self._document_id_for_source(conn, source_id)
            conn.commit()
        if document_id:
            self._assign_document_to_project(document_id, project_id)
            return self._get_project_source_id_for_document(document_id, project_id)
        project_source_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO project_sources (
                    id, project_id, source_id, legacy_document_id, display_title,
                    status, priority, reading_type, local_notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_source_id,
                    project_id,
                    source_id,
                    None,
                    title or file_path or "Untitled source",
                    "new",
                    3,
                    "",
                    None,
                    created_at or now,
                    updated_at or now,
                ),
            )
            conn.execute(
                "UPDATE review_projects SET updated_at = ? WHERE id = ?",
                (now, project_id),
            )
            conn.commit()
        return project_source_id

    def _get_project_source_id_for_document(self, document_id, project_id=None):
        if not document_id:
            return None
        with sqlite3.connect(self.db_path) as conn:
            if project_id:
                row = conn.execute(
                    """
                    SELECT id
                    FROM project_sources
                    WHERE legacy_document_id = ? AND project_id = ?
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT 1
                    """,
                    (document_id, project_id),
                ).fetchone()
                return row[0] if row else None
            row = conn.execute(
                """
                SELECT id
                FROM project_sources
                WHERE legacy_document_id = ?
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (document_id,),
            ).fetchone()
        return row[0] if row else None

    def _refresh_current_project_source(self):
        self.current_project_source_id = self._get_project_source_id_for_document(
            self.current_document_id,
            self.current_project_id,
        )

    def _ensure_project_source_for_document(self, document_id, project_id):
        if not document_id or not project_id:
            return None
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT title, file_path, source_url, reading_type, COALESCE(status, 'new'),
                       COALESCE(priority, 3), COALESCE(citation_metadata, ''),
                       created_at, updated_at
                FROM documents
                WHERE id = ?
                """,
                (document_id,),
            ).fetchone()
            if not row:
                return None
            title, file_path, source_url, reading_type, status, priority, citation_metadata, created_at, updated_at = row
            normalized_path = (file_path or "").strip()
            normalized_title = (title or "").strip() or normalized_path or document_id
            if normalized_path:
                source_row = conn.execute(
                    "SELECT id FROM sources WHERE file_path = ? LIMIT 1",
                    (normalized_path,),
                ).fetchone()
            else:
                source_row = conn.execute(
                    "SELECT id FROM sources WHERE canonical_title = ? LIMIT 1",
                    (normalized_title,),
                ).fetchone()
            if source_row:
                source_id = source_row[0]
                conn.execute(
                    """
                    UPDATE sources
                    SET canonical_title = ?, source_url = ?, citation_metadata = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (normalized_title, source_url, citation_metadata, updated_at, source_id),
                )
            else:
                source_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO sources (
                        id, file_path, canonical_title, source_url, citation_metadata,
                        doc_fingerprint, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        normalized_path or None,
                        normalized_title,
                        source_url,
                        citation_metadata,
                        None,
                        created_at,
                        updated_at,
                    ),
                )
            project_source_row = conn.execute(
                """
                SELECT id
                FROM project_sources
                WHERE project_id = ? AND legacy_document_id = ?
                LIMIT 1
                """,
                (project_id, document_id),
            ).fetchone()
            if project_source_row:
                project_source_id = project_source_row[0]
                conn.execute(
                    """
                    UPDATE project_sources
                    SET source_id = ?, display_title = ?, status = ?, priority = ?,
                        reading_type = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        source_id,
                        title,
                        status,
                        priority,
                        reading_type,
                        updated_at,
                        project_source_id,
                    ),
                )
            else:
                project_source_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO project_sources (
                        id, project_id, source_id, legacy_document_id, display_title,
                        status, priority, reading_type, local_notes, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_source_id,
                        project_id,
                        source_id,
                        document_id,
                        title,
                        status,
                        priority,
                        reading_type,
                        None,
                        created_at,
                        updated_at,
                    ),
                )
            conn.commit()
        return project_source_id

    def _get_project_document_for_path(self, path, project_id):
        if not project_id:
            return None
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                """
                SELECT
                    d.id,
                    COALESCE(s.citation_metadata, d.citation_metadata, ''),
                    ps.id
                FROM project_sources ps
                JOIN documents d ON d.id = ps.legacy_document_id
                LEFT JOIN sources s ON s.id = ps.source_id
                WHERE d.file_path = ? AND ps.project_id = ?
                ORDER BY ps.updated_at DESC, ps.created_at DESC
                LIMIT 1
                """,
                (path, project_id),
            ).fetchone()

    def _get_alternate_project_document_for_path(self, path, project_id, exclude_document_id):
        if not project_id or not path:
            return None
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                """
                SELECT d.id
                FROM documents d
                JOIN review_project_documents rpd ON rpd.document_id = d.id
                WHERE d.file_path = ? AND rpd.project_id = ? AND d.id <> ?
                ORDER BY d.updated_at DESC
                LIMIT 1
                """,
                (path, project_id, exclude_document_id),
            ).fetchone()

    def _get_alternate_project_record_for_path(self, path, project_id, exclude_project_source_id):
        if not project_id or not path:
            return None
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                """
                SELECT ps.id, d.id
                FROM project_sources ps
                JOIN documents d ON d.id = ps.legacy_document_id
                WHERE ps.project_id = ? AND d.file_path = ? AND ps.id <> ?
                ORDER BY ps.updated_at DESC, ps.created_at DESC
                LIMIT 1
                """,
                (project_id, path, exclude_project_source_id),
            ).fetchone()

    def _clone_document_record(self, source_document_id, path, title, citation_guess):
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            source = conn.execute(
                """
                SELECT title, source_url, reading_type, total_pages, citation_metadata
                FROM documents
                WHERE id = ?
                """,
                (source_document_id,),
            ).fetchone()
            doc_id = str(uuid.uuid4())
            source_title = source[0] if source and source[0] else title
            source_url = source[1] if source else None
            reading_type = source[2] if source and source[2] else ""
            total_pages = source[3] if source and source[3] else self.total_pages
            source_citation = source[4] if source and source[4] else ""
            citation_metadata = source_citation or json.dumps({k: v for k, v in citation_guess.items() if k != "title"})
            conn.execute(
                """
                INSERT INTO documents (
                    id, title, file_path, source_url, reading_type, status, priority,
                    total_pages, citation_metadata, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, source_title, path, source_url, reading_type, "new", 3, total_pages, citation_metadata, now, now),
            )
            conn.commit()
        return doc_id

    def _citation_metadata_from_form(self):
        return {
            "authors": self.doc_author_edit.text().strip(),
            "year": self.doc_year_edit.text().strip(),
            "source": self.doc_source_edit.text().strip(),
            "volume": self.doc_volume_edit.text().strip(),
            "issue": self.doc_issue_edit.text().strip(),
            "pages": self.doc_pages_edit.text().strip(),
            "doi": self.doc_doi_edit.text().strip(),
            "url": self.doc_url_edit.text().strip(),
            "publisher": self.doc_publisher_edit.text().strip(),
        }

    def _update_active_record_label(self, data=None):
        if not data:
            self._active_record_title_full = "No source open"
            hint = "Open a source in the reader to pin it here."
            self._active_record_meta_full = hint
            self._sync_active_record_text()
            self.active_record_card.setToolTip("")
            return
        title = data.get("title") or os.path.basename(data.get("file_path") or "") or "Untitled record"
        status = data.get("status") or "new"
        priority = data.get("priority") or 3
        created_at = (data.get("created_at") or "")[:10]
        citation = data.get("citation_metadata") or {}
        meta_parts = [status.title()]
        authors = (citation.get("authors") or "").strip()
        if authors:
            meta_parts.append(authors)
        year = (citation.get("year") or "").strip()
        if year:
            meta_parts.append(year)
        meta_parts.append(f"P{priority}")
        if created_at:
            meta_parts.append(created_at)
        meta_line = " • ".join(part for part in meta_parts if part)
        self._active_record_title_full = title
        self._active_record_meta_full = meta_line
        self._sync_active_record_text()
        self.active_record_card.setToolTip(f"{title}\n{meta_line}".strip())

    def _update_window_title_for_record(self, data=None):
        if not data:
            self.setWindowTitle("Scholar - Prototype PDF Viewer")
            return
        title = data.get("title") or os.path.basename(data.get("file_path") or "") or "Untitled record"
        status = data.get("status") or "new"
        created_at = (data.get("created_at") or "")[:10]
        created_part = f" - {created_at}" if created_at else ""
        self.setWindowTitle(f"Scholar - {title} [{status}]{created_part}")

    def _record_label(self, title, project_title, created_at, document_id):
        display_title = title or "Untitled record"
        project_part = project_title or "Unassigned"
        created_part = (created_at or "")[:10] if created_at else ""
        suffix = f" ({created_part})" if created_part else ""
        return f"{display_title} - {project_part}{suffix}"

    def _base_record_title(self, title):
        cleaned = (title or "").strip()
        return re.sub(r"\s+\(Pass\s+\d+\)$", "", cleaned, flags=re.IGNORECASE).strip() or cleaned or "Untitled record"

    def _make_fresh_record_title(self, path, seed_title=None, project_id=None):
        project_id = project_id or self.current_project_id
        base_title = self._base_record_title(seed_title or os.path.basename(path))
        if not project_id:
            return f"{base_title} (Pass 2)"
        with sqlite3.connect(self.db_path) as conn:
            existing_titles = [
                row[0]
                for row in conn.execute(
                    """
                    SELECT COALESCE(ps.display_title, d.title, '')
                    FROM project_sources ps
                    JOIN documents d ON d.id = ps.legacy_document_id
                    WHERE ps.project_id = ? AND d.file_path = ?
                    """,
                    (project_id, path),
                ).fetchall()
            ]
        pass_numbers = []
        for title in existing_titles:
            normalized = (title or "").strip()
            if self._base_record_title(normalized).lower() != base_title.lower():
                continue
            match = re.search(r"\(Pass\s+(\d+)\)$", normalized, flags=re.IGNORECASE)
            if match:
                pass_numbers.append(int(match.group(1)))
            elif normalized:
                pass_numbers.append(1)
        next_pass = (max(pass_numbers) + 1) if pass_numbers else 2
        return f"{base_title} (Pass {next_pass})"

    def _refresh_annotation_record_options(self, path, selected_project_source_id=None):
        self.annotation_record_combo.blockSignals(True)
        self.annotation_record_combo.clear()
        if not path:
            self.annotation_record_combo.addItem("No record selected", "")
            self.annotation_record_combo.blockSignals(False)
            return
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT ps.id, d.id, COALESCE(ps.display_title, d.title, ''), COALESCE(rp.title, ''), ps.created_at
                FROM project_sources ps
                JOIN documents d ON d.id = ps.legacy_document_id
                LEFT JOIN review_projects rp ON rp.id = ps.project_id
                WHERE d.file_path = ?
                ORDER BY ps.updated_at DESC, ps.created_at DESC
                """,
                (path,),
            ).fetchall()
        active_index = 0
        if not rows:
            self.annotation_record_combo.addItem("No saved record", "")
        else:
            seen = set()
            for idx, (project_source_id, document_id, title, project_title, created_at) in enumerate(rows):
                if project_source_id in seen:
                    continue
                seen.add(project_source_id)
                self.annotation_record_combo.addItem(
                    self._record_label(title, project_title, created_at, project_source_id),
                    project_source_id,
                )
                if project_source_id == selected_project_source_id:
                    active_index = self.annotation_record_combo.count() - 1
        self.annotation_record_combo.setCurrentIndex(active_index)
        self.annotation_record_combo.blockSignals(False)

    def _on_annotation_record_changed(self):
        project_source_id = self.annotation_record_combo.currentData()
        if not project_source_id or project_source_id == self.current_project_source_id:
            return
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT d.file_path, d.id
                FROM project_sources ps
                JOIN documents d ON d.id = ps.legacy_document_id
                WHERE ps.id = ?
                """,
                (project_source_id,),
            ).fetchone()
        if row and row[0] and os.path.exists(row[0]):
            self._load_pdf(row[0], target_document_id=row[1])

    def create_fresh_annotation_record(self):
        if not self.current_document_id:
            QMessageBox.information(self, "No document loaded", "Open a PDF before creating a fresh record.")
            return
        if not self.current_project_id:
            QMessageBox.information(self, "No project selected", "Select a project space before creating a fresh record.")
            return
        path = self.doc_path_label.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Missing file", "This document record does not have an accessible file path.")
            return
        title = self._make_fresh_record_title(
            path,
            self.doc_title_edit.text().strip() or os.path.basename(path),
            self.current_project_id,
        )
        citation_guess = self._citation_metadata_from_form()
        new_document_id = self._clone_document_record(self.current_document_id, path, title, {"title": title, **citation_guess})
        self._assign_document_to_project(new_document_id, self.current_project_id)
        self._refresh_doc_list()
        self._load_pdf(path, target_document_id=new_document_id)

    def _duplicate_import_decision(self, path, existing_document_id=None):
        if not self.current_project_id or existing_document_id is None:
            return "normal", existing_document_id
        project_title = self.project_combo.currentText().strip() if hasattr(self, "project_combo") else "current project"
        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Question)
        message_box.setWindowTitle("PDF Already In Project")
        message_box.setText("This PDF is already in the current project space.")
        message_box.setInformativeText(
            f"{os.path.basename(path)} already has a record in {project_title}.\n\n"
            "Choose whether to reopen the existing record or create a new pass with a clean annotation slate."
        )
        open_existing_btn = message_box.addButton("Open Existing", QMessageBox.AcceptRole)
        fresh_record_btn = message_box.addButton("New Pass", QMessageBox.ActionRole)
        cancel_btn = message_box.addButton("Cancel", QMessageBox.RejectRole)
        message_box.setDefaultButton(open_existing_btn)
        message_box.exec()
        clicked = message_box.clickedButton()
        if clicked == open_existing_btn:
            return "reuse", existing_document_id
        if clicked == fresh_record_btn:
            return "fresh", existing_document_id
        return "cancel", existing_document_id

    def _create_fresh_record_for_path(self, source_document_id, path):
        title = os.path.basename(path)
        citation_guess = {}
        try:
            with fitz.open(path) as pdf_doc:
                citation_guess = self._prefill_citation_metadata(path, pdf_doc)
                title = self._make_fresh_record_title(
                    path,
                    citation_guess.get("title") or title,
                    self.current_project_id,
                )
        except Exception:
            title = self._make_fresh_record_title(path, title, self.current_project_id)
        new_document_id = self._clone_document_record(
            source_document_id,
            path,
            title,
            citation_guess,
        )
        if self.current_project_id:
            self._assign_document_to_project(new_document_id, self.current_project_id)
        return new_document_id

    def _parse_citation_from_filename(self, path):
        basename = re.split(r"[\\/]", path or "")[-1]
        stem = os.path.splitext(basename)[0]
        cleaned = re.sub(r"[_\-]+", " ", stem)
        year_match = re.search(r"\b(19|20)\d{2}\b", cleaned)
        year = year_match.group(0) if year_match else ""
        authors = ""
        if year_match:
            prefix = cleaned[:year_match.start()].strip(" ,.-")
            suffix = cleaned[year_match.end():].strip(" ,.-")
            if prefix and suffix:
                authors = prefix
        title = cleaned
        if year_match:
            title = cleaned[year_match.end():].strip(" ,.-")
            if not title:
                title = cleaned[:year_match.start()].strip(" ,.-")
        if authors and title:
            title = re.sub(r"^\b(et al|and)\b", "", title, flags=re.IGNORECASE).strip(" ,.-")
        return {
            "authors": authors,
            "year": year,
            "title": title,
        }

    def _prefill_citation_metadata(self, path, pdf_doc):
        filename_guess = self._parse_citation_from_filename(path)
        metadata = pdf_doc.metadata or {}
        title = (metadata.get("title") or "").strip() or filename_guess.get("title") or os.path.basename(path)
        authors = (metadata.get("author") or "").strip() or filename_guess.get("authors", "")
        subject = (metadata.get("subject") or "").strip()
        keywords = (metadata.get("keywords") or "").strip()
        doi_match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", keywords or subject, flags=re.IGNORECASE)
        url_match = re.search(r"https?://\S+", subject or keywords or "", flags=re.IGNORECASE)
        year_match = re.search(r"\b(19|20)\d{2}\b", " ".join(filter(None, [subject, keywords, metadata.get("creationDate", ""), filename_guess.get("year", "")])))
        publisher = (metadata.get("producer") or metadata.get("creator") or "").strip()
        return {
            "authors": authors,
            "year": year_match.group(0) if year_match else filename_guess.get("year", ""),
            "source": subject,
            "volume": "",
            "issue": "",
            "pages": "",
            "doi": doi_match.group(0) if doi_match else "",
            "url": url_match.group(0) if url_match else "",
            "publisher": publisher,
            "title": title,
        }

    def _source_triage_db(self):
        try:
            from . import db as source_db
        except Exception:
            import db as source_db
        return source_db

    def _source_filter_value(self):
        if not hasattr(self, "source_library_filter"):
            return "all"
        return self.source_library_filter.currentData() or "all"

    def _source_filter_options(self):
        if self.current_project_id:
            return [
                ("All Project Sources", "all"),
                ("Needs Project Screening", "needs_project_screening"),
                ("Screened in Project", "project_screened"),
                ("Included", "project_included"),
                ("Excluded", "project_excluded"),
            ]
        return [
            ("All Sources", "all"),
            ("Needs Screening", "needs_screening"),
            ("Staged", "staged"),
            ("Excluded", "excluded"),
            ("In Projects", "in_projects"),
        ]

    def _configure_source_filter_options(self, preserve_value=True):
        if not hasattr(self, "source_library_filter"):
            return
        current_value = self._source_filter_value() if preserve_value else "all"
        options = self._source_filter_options()
        valid_values = {value for _label, value in options}
        if current_value not in valid_values:
            current_value = "all"
        with QSignalBlocker(self.source_library_filter):
            self.source_library_filter.clear()
            for label, value in options:
                self.source_library_filter.addItem(label, value)
            self._set_combo_by_data(self.source_library_filter, current_value)

    def _inclusion_meta_parts(self, inclusion_status, relevance_scope, screening_depth):
        parts = []
        if inclusion_status:
            parts.append(f"Triage: {str(inclusion_status).title()}")
        else:
            parts.append("Needs screening")
        if relevance_scope:
            parts.append(str(relevance_scope).title())
        if screening_depth:
            parts.append(f"Depth: {screening_depth}")
        return parts

    def _source_view_label(self, view_filter, row_count):
        noun = "source" if row_count == 1 else "sources"
        if self.current_project_id:
            labels = {
                "all": f"{row_count} {noun} in this project.",
                "needs_project_screening": (
                    "1 project source needs screening."
                    if row_count == 1
                    else f"{row_count} project sources need screening."
                ),
                "project_screened": f"{row_count} screened {noun} in this project.",
                "project_included": f"{row_count} included {noun} in this project.",
                "project_excluded": f"{row_count} excluded {noun} in this project.",
            }
            return labels.get(view_filter, f"{row_count} {noun} in this project.")
        labels = {
            "needs_screening": (
                "1 source needs screening."
                if row_count == 1
                else f"{row_count} sources need screening."
            ),
            "staged": f"{row_count} staged {noun}.",
            "excluded": f"{row_count} excluded {noun}.",
            "in_projects": f"{row_count} {noun} in projects.",
        }
        return labels.get(view_filter, f"{row_count} {noun} in the library.")

    def _build_source_filter_clause(self, view_filter):
        effective_inclusion_id = "COALESCE(si_project.id, si_global.id)"
        effective_status = "COALESCE(si_project.inclusion_status, si_global.inclusion_status)"
        if view_filter in {"needs_screening", "needs_project_screening"}:
            return f"{effective_inclusion_id} IS NULL"
        if view_filter == "project_screened":
            return f"{effective_inclusion_id} IS NOT NULL"
        if view_filter == "project_included":
            return f"{effective_status} = 'included'"
        if view_filter == "project_excluded":
            return f"{effective_status} = 'excluded'"
        if view_filter == "staged":
            return "si_global.inclusion_status IN ('candidate', 'included', 'deferred')"
        if view_filter == "excluded":
            return f"{effective_status} = 'excluded'"
        if view_filter == "in_projects":
            return "(project_ps.id IS NOT NULL OR si_project.id IS NOT NULL)"
        return ""

    def _refresh_doc_list(self):
        runtime_trace(
            f"_refresh_doc_list start project_id={self.current_project_id!r} "
            f"project_source_id={self.current_project_source_id!r} doc_id={self.current_document_id!r}"
        )
        self.doc_list.clear()
        try:
            search = self.doc_search_box.text().strip().lower() if hasattr(self, "doc_search_box") else ""
            status_filter = self.doc_status_filter.currentData() if hasattr(self, "doc_status_filter") else ""
            sort_mode = self.doc_sort_combo.currentData() if hasattr(self, "doc_sort_combo") else "updated_desc"
            view_filter = self._source_filter_value()
            order_by = {
                "title_asc": "LOWER(COALESCE(ps.display_title, d.title, s.canonical_title, s.file_path, '')) ASC, ps.created_at DESC, ps.id ASC",
                "priority_desc": "COALESCE(ps.priority, 0) DESC, COALESCE(ps.updated_at, s.updated_at) DESC, COALESCE(ps.created_at, s.created_at) DESC, LOWER(COALESCE(ps.display_title, d.title, s.canonical_title, s.file_path, '')) ASC",
                "updated_desc": "COALESCE(ps.updated_at, s.updated_at) DESC, COALESCE(ps.created_at, s.created_at) DESC, LOWER(COALESCE(ps.display_title, d.title, s.canonical_title, s.file_path, '')) ASC",
            }.get(sort_mode, "COALESCE(ps.updated_at, s.updated_at) DESC, COALESCE(ps.created_at, s.created_at) DESC, LOWER(COALESCE(ps.display_title, d.title, s.canonical_title, s.file_path, '')) ASC")
            clauses = []
            params = []
            if search:
                clauses.append("(LOWER(COALESCE(ps.display_title, d.title, s.canonical_title, '')) LIKE ? OR LOWER(COALESCE(d.file_path, s.file_path, '')) LIKE ?)")
                needle = f"%{search}%"
                params.extend([needle, needle])
            if status_filter:
                clauses.append("COALESCE(ps.status, 'new') = ?")
                params.append(status_filter)
            if self.current_project_id:
                clauses.append("ps.project_id = ?")
                params.append(self.current_project_id)
            source_filter_clause = self._build_source_filter_clause(view_filter)
            if source_filter_clause:
                clauses.append(source_filter_clause)
            where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    f"""
                    WITH latest_project_source AS (
                        SELECT ps1.*
                        FROM project_sources ps1
                        WHERE ps1.updated_at = (
                            SELECT MAX(COALESCE(ps2.updated_at, ps2.created_at, ''))
                            FROM project_sources ps2
                            WHERE ps2.source_id = ps1.source_id
                        )
                    )
                    SELECT
                        ps.id,
                        d.id,
                        COALESCE(ps.display_title, d.title, s.canonical_title, ''),
                        COALESCE(d.file_path, s.file_path, ''),
                        COALESCE(ps.status, 'new'),
                        COALESCE(ps.priority, 3),
                        COALESCE(ps.reading_type, d.reading_type, ''),
                        ps.updated_at,
                        COALESCE(s.citation_metadata, d.citation_metadata, ''),
                        ps.created_at,
                        COALESCE(rp.title, ''),
                        s.id,
                        COALESCE(si_project.id, si_global.id),
                        COALESCE(si_project.project_id, si_global.project_id),
                        COALESCE(si_project.inclusion_status, si_global.inclusion_status),
                        COALESCE(si_project.relevance_scope, si_global.relevance_scope),
                        COALESCE(si_project.screening_depth, si_global.screening_depth),
                        COALESCE(si_project.inclusion_reasoning, si_global.inclusion_reasoning),
                        COALESCE(si_project.project_role_note, si_global.project_role_note),
                        COALESCE(si_project.decided_at, si_global.decided_at),
                        project_ps.id
                    FROM sources s
                    LEFT JOIN latest_project_source ps ON ps.source_id = s.id
                    LEFT JOIN documents d ON d.id = ps.legacy_document_id
                    LEFT JOIN review_projects rp ON rp.id = ps.project_id
                    LEFT JOIN source_inclusion si_project
                        ON si_project.id = (
                            SELECT si_project_pick.id
                            FROM source_inclusion si_project_pick
                            WHERE si_project_pick.source_id = s.id
                              AND ps.project_id IS NOT NULL
                              AND si_project_pick.project_id = ps.project_id
                            ORDER BY COALESCE(si_project_pick.updated_at, si_project_pick.created_at) DESC
                            LIMIT 1
                       )
                    LEFT JOIN source_inclusion si_global
                        ON si_global.id = (
                            SELECT si_global_pick.id
                            FROM source_inclusion si_global_pick
                            WHERE si_global_pick.source_id = s.id
                              AND si_global_pick.project_id IS NULL
                            ORDER BY COALESCE(si_global_pick.updated_at, si_global_pick.created_at) DESC
                            LIMIT 1
                       )
                    LEFT JOIN project_sources project_ps ON project_ps.source_id = s.id
                    {where_sql}
                    GROUP BY s.id
                    ORDER BY {order_by}
                    """,
                    params,
                ).fetchall()
            row_count = len(rows)
            for (
                project_source_id,
                document_id,
                title,
                file_path,
                status,
                priority,
                reading_type,
                updated_at,
                citation_metadata,
                created_at,
                project_title,
                source_id,
                inclusion_id,
                inclusion_project_id,
                inclusion_status,
                relevance_scope,
                screening_depth,
                inclusion_reasoning,
                project_role_note,
                decided_at,
                _project_membership_id,
            ) in rows:
                display_title = title or os.path.basename(file_path or "") or "Untitled record"
                try:
                    citation = json.loads(citation_metadata) if citation_metadata else {}
                except Exception:
                    citation = {}
                is_active = project_source_id == self.current_project_source_id
                meta_parts = [("Open" if is_active else (status or "new").title())]
                meta_parts.extend(self._inclusion_meta_parts(inclusion_status, relevance_scope, screening_depth))
                if citation.get("authors"):
                    meta_parts.append(citation["authors"])
                if citation.get("year"):
                    meta_parts.append(citation["year"])
                if reading_type:
                    meta_parts.append(reading_type)
                meta_parts.append(f"P{priority}")
                if not self.current_project_id and project_title:
                    meta_parts.append(project_title)
                if created_at:
                    meta_parts.append((created_at or "")[:10])
                item = QListWidgetItem()
                title = display_title
                subtitle = ""
                meta_line = " • ".join(part for part in meta_parts if part)
                item.setSizeHint(QSize(200, self._document_row_height(title, meta_line, self.doc_list.viewport().width() or 200)))
                item.setData(Qt.UserRole, {
                    "id": project_source_id,
                    "project_source_id": project_source_id,
                    "source_id": source_id,
                    "document_id": document_id,
                    "title": title or "",
                    "file_path": file_path,
                    "status": status,
                    "priority": priority,
                    "reading_type": reading_type,
                    "updated_at": updated_at or "",
                    "created_at": created_at or "",
                    "project_title": project_title or "",
                    "citation_metadata": citation,
                    "inclusion_id": inclusion_id,
                    "inclusion_project_id": inclusion_project_id,
                    "inclusion_status": inclusion_status,
                    "relevance_scope": relevance_scope,
                    "screening_depth": screening_depth,
                    "inclusion_reasoning": inclusion_reasoning,
                    "project_role_note": project_role_note,
                    "decided_at": decided_at,
                })
                item.setData(Qt.UserRole + 1, {
                    "title": title,
                    "meta": meta_line,
                    "role": "document",
                })
                item.setFont(self._ui_font(10))
                if is_active:
                    item.setSelected(True)
                self.doc_list.addItem(item)
                row_widget = self._make_list_row_widget(
                    title=title,
                    subtitle=subtitle,
                    meta=meta_line,
                    active=is_active,
                    accent_color=self._theme_palette["accent_text"] if is_active else "",
                    role="document",
                )
                row_widget.setToolTip(title)
                self.doc_list.setItemWidget(item, row_widget)
            if hasattr(self, "doc_list_hint"):
                if row_count == 0:
                    if search or status_filter or view_filter != "all":
                        if view_filter in {"needs_screening", "needs_project_screening"}:
                            self.doc_list_hint.setText(
                                "No project sources need screening."
                                if self.current_project_id
                                else "No sources need screening."
                            )
                        elif view_filter == "project_screened":
                            self.doc_list_hint.setText("No screened sources in this project yet.")
                        elif view_filter == "project_included":
                            self.doc_list_hint.setText("No included sources in this project yet.")
                        elif view_filter == "project_excluded":
                            self.doc_list_hint.setText("No excluded sources in this project.")
                        elif view_filter == "staged":
                            self.doc_list_hint.setText("No staged sources yet.")
                        elif view_filter == "excluded":
                            self.doc_list_hint.setText("No excluded sources.")
                        elif view_filter == "in_projects":
                            self.doc_list_hint.setText("No sources are attached to projects yet.")
                        else:
                            self.doc_list_hint.setText("No sources match the current search or filters.")
                    elif self.current_project_id:
                        self.doc_list_hint.setText("No sources in this project yet. Add PDFs or records to begin.")
                    else:
                        self.doc_list_hint.setText("No sources available yet.")
                else:
                    if view_filter != "all" or self.current_project_id:
                        self.doc_list_hint.setText(self._source_view_label(view_filter, row_count))
                    else:
                        self.doc_list_hint.setText(self._source_view_label(view_filter, row_count))
            self._sync_doc_list_row_heights()
            runtime_trace(f"_refresh_doc_list loaded {len(rows)} rows")
        except Exception:
            runtime_trace(f"_refresh_doc_list failed: {traceback.format_exc().splitlines()[-1]}")
            pass

    def _populate_doc_organizer(self, data):
        self.updating_doc_organizer = True
        self.current_library_project_source_id = data.get("project_source_id") or data.get("id")
        self.current_library_doc_id = data.get("document_id") or data.get("id")
        self.current_library_source_id = data.get("source_id")
        if self.current_library_project_source_id == self.current_project_source_id:
            self._update_active_record_label(data)
            self._update_window_title_for_record(data)
        else:
            self._update_active_record_label(None)
        title = data.get("title") or os.path.basename(data.get("file_path") or "")
        self._refresh_annotation_record_options(data.get("file_path") or "", selected_project_source_id=self.current_library_project_source_id)
        self.doc_title_edit.setText(title)
        citation = data.get("citation_metadata") or {}
        self.doc_author_edit.setText(citation.get("authors", ""))
        self.doc_year_edit.setText(citation.get("year", ""))
        status = data.get("status") or "new"
        status_index = self.doc_status_combo.findText(status)
        self.doc_status_combo.setCurrentIndex(status_index if status_index >= 0 else 0)
        priority = str(data.get("priority") or 3)
        priority_index = self.doc_priority_combo.findText(priority)
        self.doc_priority_combo.setCurrentIndex(priority_index if priority_index >= 0 else 2)
        self.doc_type_edit.setText(data.get("reading_type") or "")
        self.doc_source_edit.setText(citation.get("source", ""))
        self.doc_volume_edit.setText(citation.get("volume", ""))
        self.doc_issue_edit.setText(citation.get("issue", ""))
        self.doc_pages_edit.setText(citation.get("pages", ""))
        self.doc_doi_edit.setText(citation.get("doi", ""))
        self.doc_url_edit.setText(citation.get("url", ""))
        self.doc_publisher_edit.setText(citation.get("publisher", ""))
        self.doc_path_label.setText(data.get("file_path") or "No file path recorded.")
        self.updating_doc_organizer = False
        self._update_project_context_panel()

    def _clear_doc_organizer(self):
        self.updating_doc_organizer = True
        self.current_library_doc_id = None
        self.current_library_project_source_id = None
        self.current_library_source_id = None
        self._update_active_record_label(None)
        self._update_window_title_for_record(None)
        self.doc_title_edit.clear()
        self.doc_author_edit.clear()
        self.doc_year_edit.clear()
        self.doc_status_combo.setCurrentIndex(0)
        self.doc_priority_combo.setCurrentText("3")
        self.doc_type_edit.clear()
        self.doc_source_edit.clear()
        self.doc_volume_edit.clear()
        self.doc_issue_edit.clear()
        self.doc_pages_edit.clear()
        self.doc_doi_edit.clear()
        self.doc_url_edit.clear()
        self.doc_publisher_edit.clear()
        self.annotation_record_combo.blockSignals(True)
        self.annotation_record_combo.clear()
        self.annotation_record_combo.addItem("No record selected", "")
        self.annotation_record_combo.blockSignals(False)
        self.doc_path_label.setText("Select a document to edit its metadata.")
        self.updating_doc_organizer = False
        self._update_project_context_panel()

    def _clear_loaded_document_state(self):
        self.current_document_id = None
        self.current_project_source_id = None
        self.current_document_path = ""
        self.annotation_saved_panel_has_results = False
        self.current_library_project_source_id = None
        self.current_library_source_id = None
        self.current_session_id = None
        self.current_session_intention = ""
        self._update_active_record_label(None)
        self._update_window_title_for_record(None)
        self.doc = None
        self._update_project_context_panel()
        self.total_pages = 0
        self.current_page = 0
        self.current_char_index = []
        self.selection_regions = []
        self.selection_start_index = None
        self.selection_end_index = None
        self.selection_char_start = None
        self.selection_char_end = None
        self.selected_rect = None
        self.selected_page = None
        self.selected_label = None
        self.current_pixmap = None
        self.page_annotation_markers = {}
        self._clear_annotation_editor(clear_type=True, clear_writing_project=True)
        self.annotation_list.clear()
        self.annotation_list.addItem(QListWidgetItem("No document loaded."))
        self._apply_annotation_saved_panel_mode(getattr(self, "annotation_focus_mode", False))
        self._update_toolbar_context()
        self.label.clear()
        self.page_spin.setEnabled(False)
        self.page_spin.setValue(1)
        self.page_slider.setEnabled(False)
        self.page_slider.setValue(1)
        self.page_label.setText("/ -")
        self._update_ribbon_status()

    def _on_doc_clicked(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return
        runtime_trace(
            f"_on_doc_clicked project_source_id={data.get('project_source_id')!r} "
            f"document_id={data.get('document_id')!r} path={data.get('file_path', '')!r}"
        )
        self._populate_doc_organizer(data)
        file_path = data.get("file_path", "")
        document_id = data.get("document_id") or data.get("id")
        if file_path and os.path.exists(file_path):
            normalized_path = os.path.normcase(os.path.abspath(file_path))
            load_key = (normalized_path, document_id)
            if self._document_load_in_progress:
                runtime_trace(f"_on_doc_clicked ignored while load in progress key={load_key!r}")
                return
            if (
                self.doc is not None
                and self.current_document_id == document_id
                and os.path.normcase(os.path.abspath(self.current_document_path or file_path)) == normalized_path
            ):
                runtime_trace(f"_on_doc_clicked ignored already-open key={load_key!r}")
                return
            if self._pending_document_load_key == load_key:
                runtime_trace(f"_on_doc_clicked ignored duplicate pending key={load_key!r}")
                return
            self._pending_document_load_key = load_key
            # Defer opening until the QListWidget click event finishes. Opening
            # refreshes this same list, and doing that synchronously can crash Qt.
            QTimer.singleShot(
                0,
                lambda path=file_path, doc_id=document_id, key=load_key: self._load_pdf(
                    path,
                    target_document_id=doc_id,
                    queued_load_key=key,
                ),
            )
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "File not found", f"Could not find:\n{file_path}")

    def _open_doc_list_menu(self, pos):
        item = self.doc_list.itemAt(pos)
        if item is None:
            return
        data = item.data(Qt.UserRole)
        if not isinstance(data, dict):
            return
        menu = QMenu(self)
        open_action = menu.addAction("Open Record")
        rename_action = menu.addAction("Rename Record")
        triage_menu = menu.addMenu("Triage Status")
        candidate_action = triage_menu.addAction("Candidate")
        deferred_action = triage_menu.addAction("Deferred")
        included_action = triage_menu.addAction("Included...")
        excluded_action = triage_menu.addAction("Excluded...")
        remove_action = None
        if self.current_project_id:
            remove_action = menu.addAction("Remove from This Project")
        chosen = menu.exec(self.doc_list.viewport().mapToGlobal(pos))
        if chosen == open_action:
            self._on_doc_clicked(item)
        elif chosen == rename_action:
            self._rename_project_record(data)
        elif chosen == candidate_action:
            self._set_source_inclusion_from_menu(data, "candidate")
        elif chosen == deferred_action:
            self._set_source_inclusion_from_menu(data, "deferred")
        elif chosen == included_action:
            self._set_source_inclusion_from_menu(data, "included")
        elif chosen == excluded_action:
            self._set_source_inclusion_from_menu(data, "excluded")
        elif remove_action is not None and chosen == remove_action:
            self._remove_document_from_current_project(data)

    def _ensure_inclusion_record_for_source(self, data):
        source_id = data.get("source_id")
        if not source_id:
            QMessageBox.information(self, "No source record", "This row is not linked to a library source yet.")
            return None
        source_db = self._source_triage_db()
        project_id = data.get("inclusion_project_id")
        existing = source_db.get_inclusion_record(source_id, project_id=project_id, db_path=self.db_path)
        if existing:
            return existing["id"]
        return source_db.create_inclusion_record(source_id, project_id=project_id, db_path=self.db_path)

    def _prompt_for_inclusion_reasoning(self, status, current_reasoning=""):
        title = f"{status.title()} Reasoning"
        prompt = f"Why should this source be {status}?"
        reasoning, ok = QInputDialog.getMultiLineText(
            self,
            title,
            prompt,
            current_reasoning or "",
        )
        if not ok:
            return None
        reasoning = reasoning.strip()
        if not reasoning:
            QMessageBox.warning(
                self,
                "Reasoning Required",
                f"Add reasoning before marking a source as {status}.",
            )
            return None
        return reasoning

    def _prompt_for_relevance_scope(self, current_scope=""):
        scopes = ["central", "supporting", "methodological", "comparative", "peripheral"]
        current_index = scopes.index(current_scope) if current_scope in scopes else 1
        scope, ok = QInputDialog.getItem(
            self,
            "Relevance Scope",
            "How does this source function?",
            scopes,
            current_index,
            False,
        )
        return scope if ok else None

    def _set_source_inclusion_from_menu(self, data, status):
        try:
            source_db = self._source_triage_db()
            record_id = self._ensure_inclusion_record_for_source(data)
            if not record_id:
                return
            reasoning = None
            if status in {"included", "excluded"}:
                reasoning = self._prompt_for_inclusion_reasoning(
                    status,
                    data.get("inclusion_reasoning") or "",
                )
                if reasoning is None:
                    return
            scope = None
            if status == "included":
                scope = self._prompt_for_relevance_scope(data.get("relevance_scope") or "")
                if scope is None:
                    return
            source_db.update_inclusion_status(
                record_id,
                status,
                reasoning=reasoning,
                db_path=self.db_path,
            )
            if status == "included":
                source_db.update_inclusion_scope(record_id, scope, db_path=self.db_path)
            self._refresh_doc_list()
        except Exception as exc:
            QMessageBox.warning(self, "Triage Status Error", str(exc))

    def _open_annotation_list_menu(self, pos):
        item = self.annotation_list.itemAt(pos)
        if item is None:
            return
        data = item.data(Qt.UserRole)
        if not isinstance(data, dict) or not data.get("id"):
            return
        menu = QMenu(self)
        open_page_action = menu.addAction("Open Page")
        edit_action = menu.addAction("Edit Annotation")
        delete_action = menu.addAction("Delete Annotation")
        chosen = menu.exec(self.annotation_list.viewport().mapToGlobal(pos))
        if chosen == open_page_action:
            self.on_annotation_clicked(item)
        elif chosen == edit_action:
            self.on_annotation_edit_requested(item)
        elif chosen == delete_action:
            self._delete_annotation(data)

    def _delete_annotation(self, data):
        annotation_id = data.get("id")
        if not annotation_id:
            return
        from PySide6.QtWidgets import QMessageBox
        answer = QMessageBox.question(
            self,
            "Delete Annotation",
            "Delete this annotation and its linked AI output?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM annotation_writing_projects WHERE annotation_id = ?", (annotation_id,))
            conn.execute("DELETE FROM annotation_tags WHERE annotation_id = ?", (annotation_id,))
            conn.execute("DELETE FROM ai_outputs WHERE annotation_id = ?", (annotation_id,))
            conn.execute("DELETE FROM annotations WHERE id = ?", (annotation_id,))
            conn.commit()
        if self.current_annotation_id == annotation_id:
            self._clear_annotation_editor(clear_type=True, clear_writing_project=False)
        self.load_annotations()
        if self.doc is not None:
            self.draw_page_highlights(self.current_page)

    def _rename_project_record(self, data):
        project_source_id = data.get("project_source_id") or data.get("id")
        current_title = data.get("title") or os.path.basename(data.get("file_path") or "") or "Untitled record"
        if not project_source_id:
            return
        new_title, ok = QInputDialog.getText(self, "Rename Record", "Record title:", text=current_title)
        if not ok:
            return
        new_title = new_title.strip()
        if not new_title:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE project_sources
                SET display_title = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_title, datetime.now().isoformat(), project_source_id),
            )
            conn.commit()
        if self.current_library_project_source_id == project_source_id:
            self.doc_title_edit.setText(new_title)
        if self.current_project_source_id == project_source_id:
            self._load_current_document_into_organizer()
        self._refresh_doc_list()

    def _remove_document_from_current_project(self, data):
        if not self.current_project_id:
            return
        project_source_id = data.get("project_source_id") or data.get("id")
        document_id = data.get("document_id")
        file_path = data.get("file_path") or ""
        if not project_source_id:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                DELETE FROM project_sources
                WHERE project_id = ? AND id = ?
                """,
                (self.current_project_id, project_source_id),
            )
            if document_id:
                remaining = conn.execute(
                    "SELECT 1 FROM project_sources WHERE project_id = ? AND legacy_document_id = ? LIMIT 1",
                    (self.current_project_id, document_id),
                ).fetchone()
                if not remaining:
                    conn.execute(
                        """
                        DELETE FROM review_project_documents
                        WHERE project_id = ? AND document_id = ?
                        """,
                        (self.current_project_id, document_id),
                    )
            conn.execute(
                "UPDATE review_projects SET updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), self.current_project_id),
            )
            conn.commit()
        if self.current_library_project_source_id == project_source_id:
            self._clear_doc_organizer()
        if self.current_project_source_id == project_source_id:
            alternate = self._get_alternate_project_record_for_path(file_path, self.current_project_id, project_source_id)
            if alternate and file_path and os.path.exists(file_path):
                self._load_pdf(file_path, target_document_id=alternate[1])
            else:
                self._clear_loaded_document_state()
        self._refresh_doc_list()

    def save_document_metadata(self, show_feedback=True):
        if not self.current_library_doc_id and self.current_document_id:
            self.current_library_doc_id = self.current_document_id
        if (
            self.current_library_doc_id
            and not self.current_library_project_source_id
            and getattr(self, "current_project_id", None)
        ):
            self._assign_document_to_project(self.current_library_doc_id, self.current_project_id)
            self.current_library_project_source_id = self._get_project_source_id_for_document(
                self.current_library_doc_id,
                self.current_project_id,
            )
        if not self.current_library_doc_id:
            from PySide6.QtWidgets import QMessageBox
            self._set_organizer_save_feedback("Pick a source before saving details.", "blocked", "No Source", reset_button=True)
            QMessageBox.information(self, "No document selected", "Pick a document from the library first.")
            return False
        title = self.doc_title_edit.text().strip()
        status = self.doc_status_combo.currentText()
        priority = int(self.doc_priority_combo.currentText())
        reading_type = self.doc_type_edit.text().strip()
        citation_metadata = json.dumps(self._citation_metadata_from_form())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE documents
                SET title = ?, status = ?, priority = ?, reading_type = ?, citation_metadata = ?, updated_at = ?
                WHERE id = ?
                """,
                (title, status, priority, reading_type, citation_metadata, datetime.now().isoformat(), self.current_library_doc_id),
            )
            source_id = self._ensure_source_for_document_row(conn, self.current_library_doc_id)
            self.current_library_source_id = source_id
            if source_id:
                conn.execute(
                    """
                    UPDATE sources
                    SET canonical_title = ?, citation_metadata = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (title, citation_metadata, datetime.now().isoformat(), source_id),
                )
            if self.current_library_project_source_id:
                conn.execute(
                    """
                    UPDATE project_sources
                    SET display_title = ?, status = ?, priority = ?, reading_type = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        title,
                        status,
                        priority,
                        reading_type,
                        datetime.now().isoformat(),
                        self.current_library_project_source_id,
                    ),
                )
            conn.commit()
        if getattr(self, "current_project_id", None):
            self._assign_document_to_project(self.current_library_doc_id, self.current_project_id)
        if self.current_library_project_source_id == self.current_project_source_id:
            self._load_current_document_into_organizer()
        self._refresh_doc_list()
        if show_feedback:
            timestamp = datetime.now().strftime("%I:%M %p").lstrip("0")
            self._set_organizer_save_feedback(f"Source details saved at {timestamp}.", "saved", "Saved", reset_button=True)
        return True

    def _autosave_document_metadata(self):
        if self.updating_doc_organizer or not self.current_library_doc_id:
            return
        self.save_document_metadata(show_feedback=False)

    def refresh_current_view(self):
        self._refresh_doc_list()
        self._load_projects(select_project_id=self.current_project_id)
        self.load_annotations()
        if not self.current_document_id:
            return
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT file_path FROM documents WHERE id = ?",
                (self.current_document_id,),
            ).fetchone()
        if row and row[0] and os.path.exists(row[0]):
            target_page = self.current_page
            self._load_pdf(row[0], target_document_id=self.current_document_id)
            if self.doc is not None and self.total_pages:
                self.render_page(max(0, min(target_page, self.total_pages - 1)))
        else:
            self._load_current_document_into_organizer()

    def open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", os.path.expanduser("~"), "PDF Files (*.pdf)")
        if path:
            self._load_pdf(path, assign_to_current_project=False)

    def add_multiple_pdfs(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add PDFs to Library",
            os.path.expanduser("~"),
            "PDF Files (*.pdf)",
        )
        if paths:
            self._import_pdf_paths(paths, assign_to_current_project=False, open_first=False)

    def add_pdf_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Add Folder to Library",
            os.path.expanduser("~"),
        )
        if not folder:
            return
        paths = self._pdf_paths_in_folder(folder)
        if not paths:
            QMessageBox.information(self, "No PDFs Found", "No PDF files were found in the selected folder.")
            return
        self._import_pdf_paths(paths, assign_to_current_project=False, open_first=False)

    def add_multiple_pdfs_to_current_project(self):
        if not self.current_project_id:
            QMessageBox.information(self, "No Project Selected", "Choose or create a project space before adding PDFs to it.")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add PDFs to Current Project",
            os.path.expanduser("~"),
            "PDF Files (*.pdf)",
        )
        if paths:
            self._import_pdf_paths(paths, assign_to_current_project=True, open_first=True)

    def add_pdf_folder_to_current_project(self):
        if not self.current_project_id:
            QMessageBox.information(self, "No Project Selected", "Choose or create a project space before adding a folder to it.")
            return
        folder = QFileDialog.getExistingDirectory(
            self,
            "Add Folder to Current Project",
            os.path.expanduser("~"),
        )
        if not folder:
            return
        paths = self._pdf_paths_in_folder(folder)
        if not paths:
            QMessageBox.information(self, "No PDFs Found", "No PDF files were found in the selected folder.")
            return
        self._import_pdf_paths(paths, assign_to_current_project=True, open_first=True)

    def _pdf_paths_in_folder(self, folder):
        paths = []
        for root, _, files in os.walk(folder):
            for filename in files:
                if filename.lower().endswith(".pdf"):
                    paths.append(os.path.join(root, filename))
        return sorted(paths, key=lambda path: os.path.basename(path).lower())

    def _pluralize(self, count, singular, plural=None):
        return singular if count == 1 else (plural or f"{singular}s")

    def _import_scope_label(self, assign_to_current_project):
        if assign_to_current_project and self.current_project_id and hasattr(self, "project_combo"):
            project_title = self.project_combo.currentText().strip() or "the current project"
            return f"to {project_title}"
        return "to the global library"

    def _import_summary_text(self, imported, reused, fresh_records, skipped, assign_to_current_project):
        processed = imported + reused
        pdf_word = self._pluralize(processed, "PDF")
        scope_label = self._import_scope_label(assign_to_current_project)
        return (
            f"Imported {processed} {pdf_word} {scope_label}.\n"
            f"New sources: {fresh_records}\n"
            f"Existing sources: {reused}\n"
            f"Skipped: {skipped}"
        )

    def _looks_like_bad_import_title(self, title):
        cleaned = (title or "").strip()
        if len(cleaned) < 4:
            return True
        if not re.search(r"[A-Za-z0-9]", cleaned):
            return True
        if re.fullmatch(r"(doi:?\s*)?10\.\d{4,9}/\S+", cleaned, flags=re.IGNORECASE):
            return True
        low_quality_markers = (
            "microsoft word",
            "acrobat distiller",
            "untitled",
            "document",
            "top line of doc",
            "top line of document",
        )
        normalized = re.sub(r"\s+", " ", cleaned.lower())
        if normalized in low_quality_markers:
            return True
        placeholder_patterns = (
            r"^top\s+line\s+of\s+doc(ument)?\b",
            r"^pdf\s+er\d+\b",
            r"^bes\d+\b",
            r"^project\s+muse\b",
        )
        return any(re.search(pattern, normalized) for pattern in placeholder_patterns)

    def _clean_import_citation_guess(self, path, citation_guess):
        cleaned = dict(citation_guess or {})
        filename_guess = self._parse_citation_from_filename(path)
        title = (cleaned.get("title") or "").strip()
        if self._looks_like_bad_import_title(title):
            title = filename_guess.get("title") or os.path.splitext(os.path.basename(path))[0]
        cleaned["title"] = title.strip() or os.path.basename(path)
        if not cleaned.get("authors") and filename_guess.get("authors"):
            cleaned["authors"] = filename_guess["authors"]
        if not cleaned.get("year") and filename_guess.get("year"):
            cleaned["year"] = filename_guess["year"]
        return cleaned

    def _prepare_import_review_items(self, paths):
        items = []
        failed = []
        for path in paths:
            try:
                with fitz.open(path) as pdf_doc:
                    citation_guess = self._clean_import_citation_guess(
                        path,
                        self._prefill_citation_metadata(path, pdf_doc),
                    )
                    items.append(
                        {
                            "path": path,
                            "total_pages": pdf_doc.page_count,
                            "citation_guess": citation_guess,
                        }
                    )
            except Exception as exc:
                failed.append((path, str(exc)))
        return items, failed

    def _collect_import_review_items(self, paths, assign_to_current_project=False):
        review_items, failed = self._prepare_import_review_items(paths)
        if not review_items:
            if failed:
                preview = "\n".join(f"- {os.path.basename(path)}: {message}" for path, message in failed[:5])
                more = "\n..." if len(failed) > 5 else ""
                QMessageBox.warning(self, "PDF Import Failed", f"No PDFs could be prepared for import.\n\n{preview}{more}")
            return None, failed, 0

        dialog = QDialog(self)
        dialog.setWindowTitle("Review PDF Import")
        dialog.resize(920, 360)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        destination = self._import_scope_label(assign_to_current_project)
        intro = QLabel(f"Review titles and basic citation metadata before adding these PDFs {destination}.")
        intro.setObjectName("MetaLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        table = QTableWidget(len(review_items), 6)
        table.setHorizontalHeaderLabels(["Import", "Title", "Author(s)", "Year", "Pages", "File"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Interactive)
        table.setColumnWidth(2, 280)
        table.setColumnWidth(5, 260)
        visible_rows = max(3, min(len(review_items), 8))
        table.setMinimumHeight(82 + visible_rows * 30)
        table.setMaximumHeight(118 + visible_rows * 30)

        for row, item in enumerate(review_items):
            citation = item["citation_guess"]
            include_item = QTableWidgetItem("")
            include_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            include_item.setCheckState(Qt.Checked)
            include_item.setData(Qt.UserRole, item)
            table.setItem(row, 0, include_item)
            table.setItem(row, 1, QTableWidgetItem(citation.get("title", "")))
            table.setItem(row, 2, QTableWidgetItem(citation.get("authors", "")))
            table.setItem(row, 3, QTableWidgetItem(citation.get("year", "")))
            pages_item = QTableWidgetItem(str(item["total_pages"]))
            pages_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            table.setItem(row, 4, pages_item)
            file_item = QTableWidgetItem(os.path.basename(item["path"]))
            file_item.setToolTip(item["path"])
            file_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            table.setItem(row, 5, file_item)
        layout.addWidget(table)

        if failed:
            failed_hint = QLabel(f"{len(failed)} PDF {self._pluralize(len(failed), 'file')} could not be previewed and will be skipped.")
            failed_hint.setObjectName("MetaLabel")
            failed_hint.setWordWrap(True)
            layout.addWidget(failed_hint)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        import_btn = QPushButton("Import Selected")
        import_btn.setObjectName("AccentButton")
        button_row.addWidget(cancel_btn)
        button_row.addWidget(import_btn)
        layout.addLayout(button_row)

        cancel_btn.clicked.connect(dialog.reject)
        import_btn.clicked.connect(dialog.accept)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None, failed, 0

        selected = []
        for row in range(table.rowCount()):
            include_item = table.item(row, 0)
            if include_item.checkState() != Qt.Checked:
                continue
            item = dict(include_item.data(Qt.UserRole))
            citation = dict(item["citation_guess"])
            citation["title"] = (table.item(row, 1).text() if table.item(row, 1) else "").strip()
            citation["authors"] = (table.item(row, 2).text() if table.item(row, 2) else "").strip()
            citation["year"] = (table.item(row, 3).text() if table.item(row, 3) else "").strip()
            citation["title"] = citation["title"] or os.path.basename(item["path"])
            item["citation_guess"] = self._clean_import_citation_guess(item["path"], citation)
            selected.append(item)
        if not selected:
            QMessageBox.information(self, "Nothing Selected", "Select at least one PDF to import.")
            return None, failed, 0
        return selected, failed, table.rowCount() - len(selected)

    def _metadata_cleanup_candidates(self):
        candidates = []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    s.id AS source_id,
                    d.id AS document_id,
                    COALESCE(d.title, s.canonical_title, '') AS title,
                    COALESCE(d.file_path, s.file_path, '') AS file_path,
                    COALESCE(s.citation_metadata, d.citation_metadata, '') AS citation_metadata
                FROM sources s
                LEFT JOIN documents d
                    ON (
                        (s.file_path IS NOT NULL AND s.file_path <> '' AND d.file_path = s.file_path)
                        OR (
                            (s.file_path IS NULL OR s.file_path = '')
                            AND d.title = s.canonical_title
                        )
                    )
                ORDER BY LOWER(COALESCE(d.title, s.canonical_title, s.file_path, '')) ASC
                """
            ).fetchall()
        seen = set()
        for source_id, document_id, title, file_path, citation_metadata in rows:
            key = (source_id, document_id)
            if key in seen:
                continue
            seen.add(key)
            if not self._looks_like_bad_import_title(title):
                continue
            try:
                citation = json.loads(citation_metadata) if citation_metadata else {}
            except Exception:
                citation = {}
            suggestion = self._clean_import_citation_guess(file_path or "", {"title": title, **citation})
            candidates.append(
                {
                    "source_id": source_id,
                    "document_id": document_id,
                    "current_title": title or "",
                    "suggested_title": suggestion.get("title") or title or "",
                    "authors": suggestion.get("authors") or citation.get("authors", ""),
                    "year": suggestion.get("year") or citation.get("year", ""),
                    "file_path": file_path or "",
                    "citation_metadata": citation,
                }
            )
        return candidates

    def _apply_metadata_cleanup_updates(self, updates):
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            for item in updates:
                title = (item.get("title") or "").strip()
                if not title:
                    continue
                citation = dict(item.get("citation_metadata") or {})
                citation["authors"] = (item.get("authors") or "").strip()
                citation["year"] = (item.get("year") or "").strip()
                citation_json = json.dumps(citation)
                document_id = item.get("document_id")
                source_id = item.get("source_id")
                if document_id:
                    conn.execute(
                        """
                        UPDATE documents
                        SET title = ?, citation_metadata = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (title, citation_json, now, document_id),
                    )
                if source_id:
                    conn.execute(
                        """
                        UPDATE sources
                        SET canonical_title = ?, citation_metadata = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (title, citation_json, now, source_id),
                    )
                    conn.execute(
                        """
                        UPDATE project_sources
                        SET display_title = ?, updated_at = ?
                        WHERE source_id = ?
                        """,
                        (title, now, source_id),
                    )
            conn.commit()

    def clean_up_library_metadata(self):
        candidates = self._metadata_cleanup_candidates()
        if not candidates:
            QMessageBox.information(self, "Metadata Cleanup", "No suspicious source titles were found.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Clean Up Metadata")
        dialog.resize(920, 420)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        intro = QLabel("Review suspicious source titles already in the library. Checked rows will be updated everywhere the source title appears.")
        intro.setObjectName("MetaLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        table = QTableWidget(len(candidates), 6)
        table.setHorizontalHeaderLabels(["Update", "Current Title", "New Title", "Author(s)", "Year", "File"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Interactive)
        table.setColumnWidth(1, 170)
        table.setColumnWidth(3, 240)
        table.setColumnWidth(5, 220)
        visible_rows = max(3, min(len(candidates), 8))
        table.setMinimumHeight(90 + visible_rows * 30)
        table.setMaximumHeight(130 + visible_rows * 30)

        for row, item in enumerate(candidates):
            update_item = QTableWidgetItem("")
            update_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            update_item.setCheckState(Qt.Checked)
            update_item.setData(Qt.UserRole, item)
            table.setItem(row, 0, update_item)
            current_item = QTableWidgetItem(item["current_title"])
            current_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            table.setItem(row, 1, current_item)
            table.setItem(row, 2, QTableWidgetItem(item["suggested_title"]))
            table.setItem(row, 3, QTableWidgetItem(item["authors"]))
            table.setItem(row, 4, QTableWidgetItem(item["year"]))
            file_item = QTableWidgetItem(os.path.basename(item["file_path"]))
            file_item.setToolTip(item["file_path"])
            file_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            table.setItem(row, 5, file_item)
        layout.addWidget(table)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        apply_btn = QPushButton("Apply Cleanup")
        apply_btn.setObjectName("AccentButton")
        button_row.addWidget(cancel_btn)
        button_row.addWidget(apply_btn)
        layout.addLayout(button_row)

        cancel_btn.clicked.connect(dialog.reject)
        apply_btn.clicked.connect(dialog.accept)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        updates = []
        for row in range(table.rowCount()):
            update_item = table.item(row, 0)
            if update_item.checkState() != Qt.Checked:
                continue
            item = dict(update_item.data(Qt.UserRole))
            item["title"] = (table.item(row, 2).text() if table.item(row, 2) else "").strip()
            item["authors"] = (table.item(row, 3).text() if table.item(row, 3) else "").strip()
            item["year"] = (table.item(row, 4).text() if table.item(row, 4) else "").strip()
            if not item["title"]:
                continue
            updates.append(item)
        if not updates:
            QMessageBox.information(self, "Metadata Cleanup", "No rows were selected for cleanup.")
            return
        self._apply_metadata_cleanup_updates(updates)
        self._refresh_doc_list()
        if self.current_document_id:
            self._load_current_document_into_organizer()
        QMessageBox.information(
            self,
            "Metadata Cleanup Complete",
            f"Updated {len(updates)} {self._pluralize(len(updates), 'source title')}.",
        )

    def _import_pdf_paths(self, paths, assign_to_current_project=False, open_first=False):
        unique_paths = []
        seen = set()
        for raw_path in paths:
            normalized = os.path.normcase(os.path.normpath(raw_path))
            if normalized in seen:
                continue
            seen.add(normalized)
            unique_paths.append(raw_path)
        reviewed_items, failed, review_skipped = self._collect_import_review_items(
            unique_paths,
            assign_to_current_project=assign_to_current_project,
        )
        if reviewed_items is None:
            return
        imported = 0
        reused = 0
        fresh_records = 0
        skipped = review_skipped
        selected_paths = []
        for item in reviewed_items:
            path = item["path"]
            selected_paths.append(path)
            try:
                result = self._index_pdf_document(
                    path,
                    total_pages=item["total_pages"],
                    citation_guess=item["citation_guess"],
                    assign_to_current_project=assign_to_current_project,
                )
                if result == "reuse":
                    reused += 1
                elif result == "fresh":
                    imported += 1
                    fresh_records += 1
                elif result == "cancel":
                    skipped += 1
                else:
                    imported += 1
                    if result == "imported":
                        fresh_records += 1
            except Exception as exc:
                failed.append((path, str(exc)))
        if not assign_to_current_project:
            if hasattr(self, "project_combo"):
                with QSignalBlocker(self.project_combo):
                    self.project_combo.setCurrentIndex(0)
                self.current_project_id = None
                self._update_scope_hint()
            if hasattr(self, "source_library_filter"):
                with QSignalBlocker(self.source_library_filter):
                    self._set_combo_by_data(self.source_library_filter, "needs_screening")
        self._refresh_doc_list()
        if self.current_document_id and self.current_project_source_id:
            self._load_current_document_into_organizer()
        elif open_first and imported and not self.current_document_id:
            self._load_pdf(selected_paths[0], assign_to_current_project=assign_to_current_project)
        summary_text = self._import_summary_text(
            imported,
            reused,
            fresh_records,
            skipped,
            assign_to_current_project,
        )
        if failed:
            preview = "\n".join(f"- {os.path.basename(path)}: {message}" for path, message in failed[:5])
            more = "\n..." if len(failed) > 5 else ""
            message_box = QMessageBox(
                QMessageBox.Warning,
                "PDF Import Completed with Issues",
                f"{summary_text}\n\nFailed: {len(failed)}\n{preview}{more}",
                QMessageBox.Ok,
                self,
            )
            message_box.setMinimumWidth(360)
            message_box.exec()
        else:
            message_box = QMessageBox(QMessageBox.Information, "PDF Import Complete", summary_text, QMessageBox.Ok, self)
            message_box.setMinimumWidth(360)
            message_box.exec()

    def _load_pdf(self, path: str, target_document_id=None, assign_to_current_project=False, queued_load_key=None):
        normalized_path = os.path.normcase(os.path.abspath(path))
        active_key = (normalized_path, target_document_id)
        if queued_load_key is not None and self._pending_document_load_key != queued_load_key:
            runtime_trace(f"_load_pdf skipped stale queued load key={queued_load_key!r}")
            return
        if self._document_load_in_progress:
            runtime_trace(f"_load_pdf ignored while another load is in progress key={active_key!r}")
            return
        if (
            self.doc is not None
            and self.current_document_id == target_document_id
            and os.path.normcase(os.path.abspath(self.current_document_path or path)) == normalized_path
        ):
            runtime_trace(f"_load_pdf skipped already-open key={active_key!r}")
            self._pending_document_load_key = None
            return
        self._document_load_in_progress = True
        try:
            runtime_trace(
                f"_load_pdf start path={path!r} target_document_id={target_document_id!r} "
                f"assign_to_current_project={assign_to_current_project!r}"
            )
            self._pending_document_load_key = None
            if assign_to_current_project and self.current_project_id and target_document_id is None:
                existing = self._get_project_document_for_path(path, self.current_project_id)
                if existing:
                    decision, existing_document_id = self._duplicate_import_decision(path, existing[0])
                    if decision == "cancel":
                        return
                    if decision == "fresh":
                        target_document_id = self._create_fresh_record_for_path(existing_document_id, path)
                        assign_to_current_project = False
                    elif decision == "reuse":
                        target_document_id = existing_document_id
                        assign_to_current_project = False
            self.doc = fitz.open(path)
            self.total_pages = self.doc.page_count
            self.current_document_path = path
            runtime_trace(f"_load_pdf opened path={path!r} total_pages={self.total_pages}")
            self.current_page = 0
            self._clear_annotation_editor(clear_type=True, clear_writing_project=False)
            self.page_spin.setMaximum(self.total_pages)
            self.page_spin.setEnabled(True)
            self.page_slider.setMaximum(self.total_pages)
            self.page_slider.setEnabled(True)
            self.page_label.setText(f"/ {self.total_pages}")
            self._clear_pdf_search(clear_box=True)
            self.fit_to_width = False
            self.current_char_index = []
            self.save_document_to_db(
                path,
                preferred_document_id=target_document_id,
                assign_to_current_project=assign_to_current_project,
            )
            self._refresh_doc_list()
            self._load_current_document_into_organizer()
            if self.reader_mode == "triage":
                self._load_triage_metadata_for_current_source()
            self._update_project_context_panel()
            self.render_page(self.current_page)
            self._update_ribbon_status()
            self._update_toolbar_context()
            try:
                self.load_annotations()
            except Exception:
                runtime_trace("_load_pdf load_annotations failed after open")
                print("Annotation load failed after opening PDF:")
                print(traceback.format_exc())
        except Exception as e:
            runtime_trace(f"_load_pdf failed path={path!r}: {e}")
            print(f"Failed to open PDF: {e}")
        finally:
            self._document_load_in_progress = False

    def _index_pdf_document(self, path, preferred_document_id=None, assign_to_current_project=False, total_pages=None, citation_guess=None):
        if assign_to_current_project and self.current_project_id and preferred_document_id is None:
            existing = self._get_project_document_for_path(path, self.current_project_id)
            if existing:
                decision, existing_document_id = self._duplicate_import_decision(path, existing[0])
                if decision == "cancel":
                    return "cancel"
                if decision == "reuse":
                    self.current_document_id = existing_document_id
                    self.current_project_source_id = existing[2] if len(existing) > 2 else self._get_project_source_id_for_document(existing_document_id, self.current_project_id)
                    return "reuse"
                if decision == "fresh":
                    self.current_document_id = self._create_fresh_record_for_path(existing_document_id, path)
                    self.current_project_source_id = self._get_project_source_id_for_document(self.current_document_id, self.current_project_id)
                    return "fresh"
        if total_pages is None or citation_guess is None:
            pdf_doc = fitz.open(path)
            try:
                total_pages = pdf_doc.page_count
                citation_guess = self._prefill_citation_metadata(path, pdf_doc)
            finally:
                pdf_doc.close()
        self._upsert_document_record(
            path,
            total_pages,
            citation_guess,
            preferred_document_id=preferred_document_id,
            assign_to_current_project=assign_to_current_project,
            activate=False,
        )
        return "imported"

    def render_page(self, page_index: int):
        if self.doc is None:
            return
        try:
            runtime_trace(
                f"render_page start requested={page_index} current={self.current_page} "
                f"total={self.total_pages} continuous={self.continuous} zoom={self.zoom_factor:.3f} "
                f"fit={self.fit_to_width}"
            )
            page_index = max(0, min(page_index, self.total_pages - 1))
            self.page_labels = {}
            self.page_pixmaps = {}

            def _clear_pages_layout():
                for i in reversed(range(self.pages_layout.count())):
                    item = self.pages_layout.itemAt(i)
                    w = item.widget()
                    if w is not None:
                        w.setParent(None)

            # single-page or continuous rendering
            if getattr(self, 'continuous', False):
                # render all pages with image widgets
                _clear_pages_layout()
                for pi in range(self.total_pages):
                    p = self.doc.load_page(pi)
                    zoom = self.zoom_factor
                    mat = fitz.Matrix(zoom, zoom)
                    pix = p.get_pixmap(matrix=mat)
                    pm = self._pixmap_from_fitz(pix)
                    lbl = SelectableLabel(self, page_index=pi)
                    lbl.setPixmap(pm)
                    lbl.setScaledContents(False)
                    lbl.adjustSize()
                    self.pages_layout.addWidget(lbl)
                    self.page_labels[pi] = lbl
                    self.page_pixmaps[pi] = pm.copy()
                if self.selected_page not in self.page_labels:
                    self.selected_label = None
                self.current_page = page_index
                self.page_spin.blockSignals(True)
                self.page_spin.setValue(self.current_page + 1)
                self.page_spin.blockSignals(False)
                self.page_slider.blockSignals(True)
                self.page_slider.setValue(self.current_page + 1)
                self.page_slider.blockSignals(False)
                self._refresh_annotations_after_page_change()
                self._update_ribbon_status()
                for pi in range(self.total_pages):
                    self.draw_page_highlights(pi)
                runtime_trace(f"render_page complete continuous page={self.current_page}")
                return
            _clear_pages_layout()
            self.pages_layout.addWidget(self.label)
            self.label.show()
            page = self.doc.load_page(page_index)
            if getattr(self, 'fit_to_width', False):
                try:
                    viewport_w = max(100, self.pages_scroll.viewport().width() - 20)
                    page_rect = page.rect
                    zoom = max(0.2, min(4.0, viewport_w / page_rect.width))
                except Exception:
                    zoom = self.zoom_factor
            else:
                zoom = self.zoom_factor
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            pixmap = self._pixmap_from_fitz(pix)
            self.label.page_index = page_index
            self.label.setPixmap(pixmap)
            self.current_pixmap = pixmap.copy()
            self.page_labels[page_index] = self.label
            self.page_pixmaps[page_index] = pixmap.copy()
            self.current_char_index = self._build_char_index(page)
            self.selection_start_index = None
            self.selection_end_index = None
            self.selection_char_start = None
            self.selection_char_end = None
            self.selected_rect = None
            if self.selected_page != page_index:
                self.selected_label = None
            self.label.setFixedSize(pixmap.size())
            self.label.adjustSize()
            self.current_page = page_index
            self.draw_page_highlights(page_index)
            # keep spinbox in sync without triggering its slot
            old_block = self.page_spin.blockSignals(True)
            self.page_spin.setValue(self.current_page + 1)
            self.page_spin.blockSignals(old_block)
            self.page_slider.blockSignals(True)
            self.page_slider.setValue(self.current_page + 1)
            self.page_slider.blockSignals(False)
            self._refresh_annotations_after_page_change()
            self._update_ribbon_status()
            runtime_trace(f"render_page complete single page={self.current_page}")
        except Exception as e:
            runtime_trace(f"render_page failed page_index={page_index}: {e}")
            err = traceback.format_exc()
            print(err)
            self.label.setText(f"Failed to render page: {e}")

    def _normalize_text(self, text: str) -> str:
        text = re.sub(r"-\s*\n", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _build_char_index(self, page):
        try:
            raw_dict = page.get_text("rawdict")
        except TypeError:
            raw_dict = page.get_text("dict")
        if not isinstance(raw_dict, dict):
            return []
        # Collect chars per block, preserving block identity
        blocks_data = []
        for block in raw_dict.get("blocks", []):
            if block.get("type", 0) != 0:  # skip image blocks
                continue
            block_chars = []
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    for ch in span.get("chars", []):
                        if isinstance(ch, dict):
                            bbox = ch.get("bbox") or ch.get("origin")
                            if not bbox or len(bbox) < 4:
                                continue
                            x0, y0, x1, y1 = bbox[0], bbox[1], bbox[2], bbox[3]
                            char = ch.get("c") or ch.get("char") or ch.get("text") or ""
                        else:
                            x0, y0, x1, y1, char = ch[0], ch[1], ch[2], ch[3], ch[4]
                        if not char:
                            continue
                        block_chars.append({
                            "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                            "cx": (x0 + x1) / 2,
                            "cy": (y0 + y1) / 2,
                            "ch": char,
                        })
            if block_chars:
                bx0 = min(c["x0"] for c in block_chars)
                by0 = min(c["y0"] for c in block_chars)
                bx1 = max(c["x1"] for c in block_chars)
                blocks_data.append({"chars": block_chars, "bx0": bx0, "by0": by0, "bx1": bx1})

        if not blocks_data:
            return []

        page_width = max(1.0, float(page.rect.width))

        # Detect broad text columns so multi-selections follow visual reading order
        # even when the user drags or ctrl-selects regions in reverse.
        x_positions = sorted(b["bx0"] for b in blocks_data)
        column_gap_threshold = max(page_width * 0.12, 40.0)
        column_starts = []
        for x in x_positions:
            if not column_starts or abs(x - column_starts[-1]) > column_gap_threshold:
                column_starts.append(x)

        use_column_order = len(column_starts) > 1
        for block in blocks_data:
            if use_column_order:
                block["column"] = min(
                    range(len(column_starts)),
                    key=lambda idx: abs(block["bx0"] - column_starts[idx]),
                )
            else:
                block["column"] = 0

        # Reading order is column-major for multi-column layouts and
        # top-to-bottom for single-column layouts.
        blocks_data.sort(key=lambda b: (b["column"], round(b["by0"] / 20) * 20, b["bx0"]))

        sorted_chars = []
        line_id = 0
        for block_id, block in enumerate(blocks_data):
            chars = block["chars"]
            # Sort chars within block by (cy, cx)
            chars.sort(key=lambda c: (round(c["cy"], 2), c["cx"]))
            previous_y = None
            for ch in chars:
                if previous_y is not None and abs(ch["cy"] - previous_y) > max(3.0, (ch["y1"] - ch["y0"]) * 0.5):
                    line_id += 1
                ch["line"] = line_id
                ch["block"] = block_id
                ch["column"] = block["column"]
                ch["block_bx0"] = block["bx0"]
                ch["block_bx1"] = block["bx1"]
                ch["index"] = len(sorted_chars)
                sorted_chars.append(ch)
                previous_y = ch["cy"]
            line_id += 1  # gap between blocks

        return sorted_chars

    def _nearest_char_index(self, page_x, page_y):
        if not self.current_char_index:
            return None
        # Weight y distance 5x so same-column chars always beat same-row chars
        # in the other column. Within the same line, x proximity decides.
        nearest = min(
            self.current_char_index,
            key=lambda c: (abs(c["cy"] - page_y) * 5) + abs(c["cx"] - page_x),
        )
        return nearest["index"]

    def _range_chars(self, start_idx, end_idx):
        if start_idx is None or end_idx is None:
            return []
        lo, hi = sorted((start_idx, end_idx))
        chars = self.current_char_index[lo:hi + 1]
        if not chars:
            return chars
        start_char = self.current_char_index[lo]
        end_char = self.current_char_index[hi]
        s_bx0 = start_char.get("block_bx0", 0)
        e_bx0 = end_char.get("block_bx0", 0)
        # If start and end are in the same column (x-origins within 50 pts),
        # restrict to blocks in that column only — prevents cross-column sweeps.
        if abs(s_bx0 - e_bx0) < 50:
            col_x0 = min(s_bx0, e_bx0) - 10
            col_x1 = max(
                start_char.get("block_bx1", s_bx0 + 999),
                end_char.get("block_bx1", e_bx0 + 999),
            ) + 10
            chars = [c for c in chars if col_x0 <= c.get("block_bx0", c["cx"]) <= col_x1]
        return chars

    def _selection_bounds(self, chars):
        if not chars:
            return None
        x0 = min(c["x0"] for c in chars)
        y0 = min(c["y0"] for c in chars)
        x1 = max(c["x1"] for c in chars)
        y1 = max(c["y1"] for c in chars)
        return x0, y0, x1, y1

    def _bounds_to_relative_rect(self, bounds, page_rect):
        if bounds is None:
            return None
        x0, y0, x1, y1 = bounds
        page_width = max(1.0, float(page_rect.width))
        page_height = max(1.0, float(page_rect.height))
        return {
            "x": x0 / page_width,
            "y": y0 / page_height,
            "width": max(0.0, (x1 - x0) / page_width),
            "height": max(0.0, (y1 - y0) / page_height),
        }

    def _chars_to_line_relative_rects(self, chars, page_rect):
        if not chars:
            return []
        spans = {}
        for ch in chars:
            key = (ch.get("block"), ch.get("line"))
            if key not in spans:
                spans[key] = {"x0": ch["x0"], "x1": ch["x1"], "y0": ch["y0"], "y1": ch["y1"]}
            else:
                spans[key]["x0"] = min(spans[key]["x0"], ch["x0"])
                spans[key]["x1"] = max(spans[key]["x1"], ch["x1"])
                spans[key]["y0"] = min(spans[key]["y0"], ch["y0"])
                spans[key]["y1"] = max(spans[key]["y1"], ch["y1"])
        rects = []
        for span in sorted(spans.values(), key=lambda item: (item["y0"], item["x0"])):
            rect = self._bounds_to_relative_rect(
                (span["x0"], span["y0"], span["x1"], span["y1"]),
                page_rect,
            )
            if rect is not None and self._valid_relative_rect(rect, max_area=0.08):
                rects.append(rect)
        return rects

    def _valid_relative_rect(self, rect, max_area=0.35):
        if not isinstance(rect, dict):
            return False
        try:
            x = float(rect.get("x", 0))
            y = float(rect.get("y", 0))
            width = float(rect.get("width", 0))
            height = float(rect.get("height", 0))
        except (TypeError, ValueError):
            return False
        if width <= 0 or height <= 0:
            return False
        if width * height > max_area:
            return False
        return -0.02 <= x <= 1.02 and -0.02 <= y <= 1.02 and x + width >= 0 and y + height >= 0

    def _pos_to_page_coords(self, page_index: int, label: QLabel, pos: QPoint):
        page = self.doc.load_page(page_index)
        pixmap = label.pixmap()
        if pixmap is None:
            return None
        pixmap_size = pixmap.size()
        page_rect = page.rect
        return (
            pos.x() * page_rect.width / pixmap_size.width(),
            pos.y() * page_rect.height / pixmap_size.height(),
        )

    def begin_selection(self, page_index: int, label: QLabel, pos: QPoint, add: bool = False):
        if self.doc is None or page_index < 0 or label.pixmap() is None:
            return
        if self.selected_page is not None and self.selected_page != page_index:
            add = False
        if self.current_annotation_id is not None:
            add = False
        if not add:
            self.selection_regions = []
            self.current_annotation_id = None
            self._set_annotation_draft_mode("draft_new")
            self.note_edit.clear()
            self.ai_explanation_edit.clear()
        coords = self._pos_to_page_coords(page_index, label, pos)
        if coords is None:
            return
        page_x, page_y = coords
        self.current_page = page_index
        self.selected_page = page_index
        self.selected_label = label
        self.current_char_index = self._build_char_index(self.doc.load_page(page_index))
        index = self._nearest_char_index(page_x, page_y)
        if index is None:
            return
        self.selection_start_index = index
        self.selection_end_index = index
        self.selection_finalized = False
        if not add:
            self.focus_multi_select_pending = False
        self._update_selection_text()
        self.draw_page_highlights(page_index)

    def update_selection(self, page_index: int, label: QLabel, pos: QPoint):
        if self.selection_start_index is None:
            return
        coords = self._pos_to_page_coords(page_index, label, pos)
        if coords is None:
            return
        page_x, page_y = coords
        index = self._nearest_char_index(page_x, page_y)
        if index is None:
            return
        self.selection_end_index = index
        self.selection_finalized = False
        self._update_selection_text()
        self.draw_page_highlights(page_index)

    def finalize_selection(self, page_index: int, label: QLabel, pos: QPoint, add: bool = False):
        if self.selection_start_index is None:
            return
        coords = self._pos_to_page_coords(page_index, label, pos)
        if coords is None:
            return
        page_x, page_y = coords
        index = self._nearest_char_index(page_x, page_y)
        if index is None:
            return
        self.selection_end_index = index
        if self.selection_start_index == self.selection_end_index and not self.selection_regions:
            self.selection_start_index = None
            self.selection_end_index = None
            self.selection_finalized = False
            self._update_selection_text()
            self.draw_page_highlights(page_index)
            return
        if add and self.selection_start_index != self.selection_end_index:
            # Commit current drag as a region, keep previous regions
            self.selection_regions.append(
                (self.selection_start_index, self.selection_end_index)
            )
            self.selection_start_index = None
            self.selection_end_index = None
            if getattr(self, "focus_mode", False):
                self.selection_finalized = False
                self.focus_multi_select_pending = True
            else:
                self.selection_finalized = True
        else:
            self.selection_finalized = True
            self.focus_multi_select_pending = False
        self._update_selection_text()
        self.draw_page_highlights(page_index)

    def _all_selected_chars(self):
        """Return chars from all committed regions plus the current drag."""
        all_chars = []
        seen = set()
        for group in self._selected_char_groups():
            for c in group:
                if c["index"] not in seen:
                    all_chars.append(c)
                    seen.add(c["index"])
        all_chars.sort(key=lambda c: c["index"])
        return all_chars

    def _selected_char_groups(self):
        groups = []
        seen = set()
        ranges = list(self.selection_regions)
        if self.selection_start_index is not None and self.selection_end_index is not None:
            ranges.append((self.selection_start_index, self.selection_end_index))
        for start_idx, end_idx in ranges:
            group = []
            for ch in self._range_chars(start_idx, end_idx):
                if ch["index"] in seen:
                    continue
                group.append(ch)
                seen.add(ch["index"])
            if group:
                group.sort(key=lambda c: c["index"])
                groups.append(group)
        groups.sort(key=lambda group: group[0]["index"])
        return groups

    def _selection_text_from_groups(self, groups):
        chunks = []
        previous_end = None
        for group in groups:
            chunk = self._normalize_text("".join(c["ch"] for c in group))
            if not chunk:
                continue
            current_start = group[0]["index"]
            if previous_end is not None and current_start > previous_end + 1:
                chunks.append("[...]")
            chunks.append(chunk)
            previous_end = group[-1]["index"]
        return " ".join(chunks).strip()

    def _update_selection_text(self):
        groups = self._selected_char_groups()
        chars = [ch for group in groups for ch in group]
        if not chars:
            self.selected_text_edit.clear()
            self.selection_char_start = None
            self.selection_char_end = None
            self.selected_rect = None
            self._update_annotation_workspace_state()
            return
        chars.sort(key=lambda c: c["index"])
        normalized = self._selection_text_from_groups(groups)
        self.selected_text_edit.setPlainText(normalized)
        if normalized.strip():
            if getattr(self, "focus_mode", False) and getattr(self, "selection_finalized", False):
                self._open_focus_annotation_panel()
                QTimer.singleShot(0, self.note_edit.setFocus)
            elif not getattr(self, "focus_mode", False):
                self._set_annotation_workspace_visible(True, remember_sizes=False)
        self.selection_char_start = chars[0]["index"]
        self.selection_char_end = chars[-1]["index"]
        bounds = self._selection_bounds(chars)
        target_label = self.selected_label or self.page_labels.get(self.selected_page)
        if bounds is not None and target_label is not None and target_label.pixmap() is not None and self.selected_page is not None:
            x0, y0, x1, y1 = bounds
            page = self.doc.load_page(self.selected_page)
            self.selected_rect = QRect(
                int(x0 * target_label.pixmap().width() / page.rect.width),
                int(y0 * target_label.pixmap().height() / page.rect.height),
                int((x1 - x0) * target_label.pixmap().width() / page.rect.width),
                int((y1 - y0) * target_label.pixmap().height() / page.rect.height),
            )
        else:
            self.selected_rect = None
        self._update_annotation_workspace_state()

    def _draw_selection_spans(self, painter, page, label):
        groups = self._selected_char_groups()
        if not groups:
            return
        pixmap = label.pixmap()
        if pixmap is None:
            return
        pixmap_size = pixmap.size()
        page_rect = page.rect
        scale_x = pixmap_size.width() / page_rect.width
        scale_y = pixmap_size.height() / page_rect.height
        spans = {}
        for group_index, chars in enumerate(groups):
            for ch in chars:
                line = (group_index, ch.get("block"), ch["line"])
                if line not in spans:
                    spans[line] = {"x0": ch["x0"], "x1": ch["x1"], "y0": ch["y0"], "y1": ch["y1"]}
                else:
                    spans[line]["x0"] = min(spans[line]["x0"], ch["x0"])
                    spans[line]["x1"] = max(spans[line]["x1"], ch["x1"])
                    spans[line]["y0"] = min(spans[line]["y0"], ch["y0"])
                    spans[line]["y1"] = max(spans[line]["y1"], ch["y1"])

        highlight_pen = QPen(QColor(30, 120, 255, 220))
        highlight_pen.setWidth(1)
        painter.setPen(highlight_pen)
        painter.setBrush(QBrush(QColor(100, 180, 255, 120)))
        for span in spans.values():
            x = int(span["x0"] * scale_x)
            y = int(span["y0"] * scale_y)
            w = int((span["x1"] - span["x0"]) * scale_x)
            h = int((span["y1"] - span["y0"]) * scale_y)
            painter.drawRect(x, y, w, h)

    def draw_page_highlights(self, page_index):
        label = self.page_labels.get(page_index)
        base_pixmap = self.page_pixmaps.get(page_index)
        if label is None or label.pixmap() is None or base_pixmap is None:
            return
        annotations = self.get_page_annotations(page_index)
        self.page_annotation_markers[page_index] = []
        pixmap = base_pixmap.copy()
        painter = QPainter(pixmap)
        for anno in annotations:
            colors = self._annotation_highlight_colors(anno.get("annotation_type"))
            pen = QPen(colors["pen"])
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(QBrush(colors["brush"]))
            rects = anno.get("rects")
            if not isinstance(rects, list) or not rects:
                rects = [{
                    "x": anno.get("x", 0),
                    "y": anno.get("y", 0),
                    "width": anno.get("width", 0),
                    "height": anno.get("height", 0),
                }]
            rects = [rect for rect in rects if self._valid_relative_rect(rect)]
            for rect in rects:
                x = int(rect.get("x", 0) * pixmap.width())
                y = int(rect.get("y", 0) * pixmap.height())
                w = int(rect.get("width", 0) * pixmap.width())
                h = int(rect.get("height", 0) * pixmap.height())
                if w > 0 and h > 0:
                    painter.drawRect(x, y, w, h)
        if self.search_results and self.doc is not None and page_index < self.total_pages:
            page = self.doc.load_page(page_index)
            page_rect = page.rect
            for idx, match in enumerate(self.search_results):
                if match.get("page") != page_index:
                    continue
                rect = match.get("rect")
                if rect is None:
                    continue
                is_active = idx == self.search_result_index
                pen = QPen(QColor(255, 196, 61, 235) if is_active else QColor(232, 220, 110, 185))
                pen.setWidth(3 if is_active else 2)
                painter.setPen(pen)
                painter.setBrush(QBrush(QColor(255, 224, 102, 70 if is_active else 38)))
                x = int(rect.x0 * pixmap.width() / page_rect.width)
                y = int(rect.y0 * pixmap.height() / page_rect.height)
                w = int((rect.x1 - rect.x0) * pixmap.width() / page_rect.width)
                h = int((rect.y1 - rect.y0) * pixmap.height() / page_rect.height)
                if w > 0 and h > 0:
                    painter.drawRect(x, y, w, h)
        if self.selected_page == page_index:
            self._draw_selection_spans(painter, self.doc.load_page(page_index), label)
        self._draw_annotation_markers(painter, pixmap, page_index, annotations)
        painter.end()
        label.setPixmap(pixmap)

    def _draw_annotation_markers(self, painter, pixmap, page_index, annotations):
        marker_positions = []
        self.page_annotation_markers[page_index] = []
        for anno in annotations:
            annotation_id = anno.get("id")
            rects = anno.get("rects")
            if not annotation_id or not isinstance(rects, list) or not rects:
                continue
            valid_rects = [
                rect for rect in rects
                if self._valid_relative_rect(rect)
            ]
            if not valid_rects:
                continue
            anchor = min(valid_rects, key=lambda rect: (rect.get("y", 0), rect.get("x", 0)))
            marker_rect = self._annotation_marker_rect(pixmap, anchor, marker_positions)
            marker_positions.append(marker_rect)
            self.page_annotation_markers[page_index].append({
                "annotation_id": annotation_id,
                "rect": marker_rect,
            })
            colors = self._annotation_highlight_colors(anno.get("annotation_type"))
            fill = QColor(colors["pen"])
            fill.setAlpha(210 if annotation_id == self.current_annotation_id else 178)
            border = QColor(colors["pen"])
            border.setAlpha(240)
            painter.setPen(QPen(border, 1))
            painter.setBrush(QBrush(fill))
            painter.drawRoundedRect(marker_rect, 5, 5)
            painter.setPen(QColor(255, 255, 255))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(max(8, font.pointSize()))
            painter.setFont(font)
            painter.drawText(marker_rect, Qt.AlignCenter, self._annotation_marker_text(anno.get("annotation_type")))

    def _annotation_marker_rect(self, pixmap, anchor_rect, existing_rects):
        marker_size = 18
        gap = 6
        page_width = pixmap.width()
        page_height = pixmap.height()
        anchor_x = int((anchor_rect.get("x", 0) + anchor_rect.get("width", 0)) * page_width)
        anchor_y = int(anchor_rect.get("y", 0) * page_height)
        preferred_x = min(page_width - marker_size - gap, anchor_x + gap)
        if preferred_x < gap:
            preferred_x = gap
        preferred_y = max(gap, min(page_height - marker_size - gap, anchor_y))
        marker_rect = QRect(preferred_x, preferred_y, marker_size, marker_size)
        if marker_rect.right() > page_width - gap:
            left_x = max(gap, int(anchor_rect.get("x", 0) * page_width) - marker_size - gap)
            marker_rect.moveLeft(left_x)
        while any(marker_rect.intersects(existing) for existing in existing_rects):
            next_y = marker_rect.y() + marker_size + 4
            if next_y + marker_size > page_height - gap:
                next_y = max(gap, marker_rect.y() - marker_size - 4)
                if next_y == marker_rect.y():
                    break
            marker_rect.moveTop(next_y)
        return marker_rect

    def _annotation_marker_text(self, annotation_type):
        return {
            "quote": "Q",
            "paraphrase": "P",
            "interpretation": "I",
            "synthesis": "S",
        }.get(annotation_type or "interpretation", "I")

    def handle_page_annotation_marker_click(self, page_index, label, pos):
        marker = self._annotation_marker_at(page_index, pos)
        if marker is None:
            return False
        annotation_id = marker.get("annotation_id")
        if not annotation_id:
            return False
        self._open_annotation_by_id(annotation_id)
        return True

    def _annotation_marker_at(self, page_index, pos):
        for marker in self.page_annotation_markers.get(page_index, []):
            rect = marker.get("rect")
            if isinstance(rect, QRect) and rect.contains(pos):
                return marker
        return None

    def _annotation_highlight_colors(self, annotation_type):
        palette = {
            "quote": {
                "pen": QColor(194, 120, 3, 215),
                "brush": QColor(245, 191, 66, 88),
            },
            "paraphrase": {
                "pen": QColor(28, 116, 214, 215),
                "brush": QColor(104, 177, 255, 88),
            },
            "interpretation": {
                "pen": QColor(138, 78, 192, 215),
                "brush": QColor(181, 126, 232, 86),
            },
            "synthesis": {
                "pen": QColor(38, 140, 89, 215),
                "brush": QColor(89, 198, 145, 88),
            },
        }
        return palette.get(annotation_type or "interpretation", palette["interpretation"])

    def _annotation_list_colors(self, annotation_type):
        colors = self._annotation_highlight_colors(annotation_type)
        background = QColor(colors["brush"])
        background.setAlpha(52)
        foreground = QColor(colors["pen"])
        return {
            "background": background,
            "foreground": foreground,
        }

    def _load_annotation_record(self, annotation_id):
        if not annotation_id:
            return None
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    """
                    SELECT annotations.id, page_number, position_json, COALESCE(annotation_type, 'interpretation'),
                           selected_text, note_content, confidence_level,
                           (
                               SELECT awp.project_id
                               FROM annotation_writing_projects awp
                               WHERE awp.annotation_id = annotations.id
                               LIMIT 1
                           ) AS writing_project_id,
                           (
                               SELECT GROUP_CONCAT(t.label, '||')
                               FROM annotation_tags at
                               JOIN tags t ON t.id = at.tag_id
                               WHERE at.annotation_id = annotations.id
                           ) AS tag_labels,
                           annotations.document_id,
                           annotations.project_source_id
                    FROM annotations
                    WHERE id = ?
                    """,
                    (annotation_id,),
                ).fetchone()
        except sqlite3.Error:
            return None
        if row is None:
            return None
        (
            anno_id,
            page,
            position_json,
            annotation_type,
            selected_text,
            note,
            confidence,
            writing_project_id,
            tag_labels,
            annotation_document_id,
            annotation_project_source_id,
        ) = row
        try:
            position = json.loads(position_json or "{}")
        except Exception:
            position = {}
        return {
            "id": anno_id,
            "page": page,
            "position": position,
            "note": note or "",
            "selected_text": selected_text or "",
            "annotation_type": annotation_type or "interpretation",
            "writing_project_id": writing_project_id,
            "document_id": annotation_document_id,
            "project_source_id": annotation_project_source_id,
            "tags": [tag for tag in (tag_labels or "").split("||") if tag],
            "confidence": confidence or "medium",
        }

    def _open_annotation_by_id(self, annotation_id):
        data = self._load_annotation_record(annotation_id)
        if data:
            self._open_annotation_record(data)

    def _open_annotation_record(self, data):
        if not isinstance(data, dict):
            return
        anno_id = data.get("id")
        page = data.get("page", self.current_page)
        position = data.get("position", {})
        note = data.get("note", "")
        annotation_type = data.get("annotation_type", "interpretation")
        selected_text = data.get("selected_text", "")
        writing_project_id = data.get("writing_project_id")
        tags = data.get("tags") or []
        target_document_id = data.get("document_id")
        if target_document_id and target_document_id != self.current_document_id:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    row = conn.execute(
                        "SELECT file_path FROM documents WHERE id = ?",
                        (target_document_id,),
                    ).fetchone()
                if row and row[0] and os.path.exists(row[0]):
                    self._load_pdf(row[0], target_document_id=target_document_id)
            except sqlite3.Error:
                return
        self.current_annotation_id = anno_id
        self._set_annotation_draft_mode("editing_existing")
        self._set_annotation_type(annotation_type)
        self._set_annotation_writing_project(writing_project_id)
        self._set_annotation_tags(tags)
        self.render_page(page)
        self.current_char_index = self._build_char_index(self.doc.load_page(page))
        char_start = position.get("char_start")
        char_end = position.get("char_end")
        regions = position.get("regions") if isinstance(position, dict) else None
        self.selected_page = page
        self.selected_label = self.page_labels.get(page, self.label)
        if isinstance(regions, list) and regions:
            self.selection_regions = []
            for region in regions:
                try:
                    start_idx = int(region.get("char_start"))
                    end_idx = int(region.get("char_end"))
                except (AttributeError, TypeError, ValueError):
                    continue
                self.selection_regions.append((start_idx, end_idx))
            self.selection_start_index = None
            self.selection_end_index = None
            self.selection_finalized = True
            self._update_selection_text()
        elif char_start is None or char_end is None:
            self.selected_text_edit.setPlainText(selected_text)
            self.note_edit.setPlainText(note)
            return
        else:
            self.selection_regions = []
            self.selection_start_index = char_start
            self.selection_end_index = char_end
            self.selection_finalized = True
            self._update_selection_text()
        self.note_edit.setPlainText(note)
        self.ai_explanation_edit.clear()
        self.draw_page_highlights(page)
        # show stored AI explanation separately from the editable note
        if anno_id:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT content_json FROM ai_outputs WHERE annotation_id = ? AND output_type = 'explanation' ORDER BY created_at DESC LIMIT 1",
                    (anno_id,)
                ).fetchone()
        if row:
            content = json.loads(row[0])
            self.ai_explanation_edit.setPlainText(content.get('explanation', ''))

    def _navigate_to_annotation_record(self, data):
        if not isinstance(data, dict):
            return
        page = data.get("page")
        if page is None:
            position = data.get("position", {})
            page = position.get("page") if isinstance(position, dict) else None
        if page is None:
            return
        try:
            page = int(page)
        except (TypeError, ValueError):
            return
        target_document_id = data.get("document_id")
        if target_document_id and target_document_id != self.current_document_id:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    row = conn.execute(
                        "SELECT file_path FROM documents WHERE id = ?",
                        (target_document_id,),
                    ).fetchone()
                if row and row[0] and os.path.exists(row[0]):
                    self._load_pdf(row[0], target_document_id=target_document_id)
            except sqlite3.Error:
                return
        if self.doc is None or page < 0 or page >= self.total_pages:
            return
        self.render_page(page)
        if getattr(self, "continuous", False):
            label = self.page_labels.get(page)
            if label is not None:
                self.pages_scroll.ensureWidgetVisible(label, 0, 24)

    def on_annotation_clicked(self, item: QListWidgetItem):
        self._navigate_to_annotation_record(item.data(Qt.UserRole))

    def on_annotation_edit_requested(self, item: QListWidgetItem):
        self._open_annotation_record(item.data(Qt.UserRole))

    def goto_previous(self):
        if self.doc is None:
            return
        self.render_page(self.current_page - 1)

    def goto_next(self):
        if self.doc is None:
            return
        self.render_page(self.current_page + 1)

    def toggle_continuous(self, on: bool):
        self.continuous = on
        # re-render current mode
        if self.doc is not None:
            self.render_page(self.current_page)

    def open_thumbnails(self):
        if self.doc is None:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Thumbnails")
        grid = QGridLayout(dlg)
        row = col = 0
        for i in range(self.total_pages):
            p = self.doc.load_page(i)
            pix = p.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
            pm = self._pixmap_from_fitz(pix)
            lbl = QLabel()
            lbl.setPixmap(pm)
            lbl.mousePressEvent = lambda ev, idx=i: (self.render_page(idx), dlg.accept())
            grid.addWidget(lbl, row, col)
            col += 1
            if col >= 6:
                col = 0
                row += 1
        dlg.exec()

    def customize_shortcuts(self):
        prev_seq, ok1 = QInputDialog.getText(self, "Customize", "Previous page key sequence:", text="Left")
        if ok1 and prev_seq:
            self.shortcut_prev.setKey(QKeySequence(prev_seq))
        next_seq, ok2 = QInputDialog.getText(self, "Customize", "Next page key sequence:", text="Right")
        if ok2 and next_seq:
            self.shortcut_next.setKey(QKeySequence(next_seq))

    def _list_writing_projects(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                return conn.execute(
                    """
                    SELECT id, title
                    FROM writing_projects
                    WHERE COALESCE(status, 'active') <> 'archived'
                    ORDER BY updated_at DESC, created_at DESC, title ASC
                    """
                ).fetchall()
        except sqlite3.Error:
            return []

    def _list_review_projects(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                return conn.execute(
                    """
                    SELECT id, title
                    FROM review_projects
                    ORDER BY updated_at DESC, created_at DESC, title ASC
                    """
                ).fetchall()
        except sqlite3.Error:
            return []

    def export_deliverable(self):
        from PySide6.QtWidgets import QMessageBox

        options = [
            "Reading Summary (Current Document)",
            "Annotated Bibliography (Project Space)",
            "Writing Project Export",
        ]
        choice, ok = QInputDialog.getItem(
            self,
            "Export Deliverable",
            "Choose an export:",
            options,
            0,
            False,
        )
        if not ok or not choice:
            return

        try:
            from .export import (
                render_annotated_bibliography,
                render_reading_summary,
                render_writing_project_export,
                write_export_file,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Export Error", f"Could not load export tools.\n\n{exc}")
            return

        if choice == "Reading Summary (Current Document)":
            if self.current_document_id is None:
                QMessageBox.information(self, "No document loaded", "Open a document before exporting a reading summary.")
                return
            try:
                suggested_name, content = render_reading_summary(
                    self.db_path,
                    self.current_document_id,
                    self.current_project_source_id,
                )
            except Exception as exc:
                QMessageBox.warning(self, "Export Error", f"Could not build the reading summary.\n\n{exc}")
                return
        elif choice == "Annotated Bibliography (Project Space)":
            rows = self._list_review_projects()
            if not rows:
                QMessageBox.information(self, "No project spaces", "Create a project space first, then add sources to it.")
                return
            titles = [title or "Untitled project" for _, title in rows]
            default_index = 0
            if self.current_project_id:
                for idx, (project_id, _) in enumerate(rows):
                    if project_id == self.current_project_id:
                        default_index = idx
                        break
            selected_title, ok_project = QInputDialog.getItem(
                self,
                "Annotated Bibliography",
                "Choose a project space:",
                titles,
                default_index,
                False,
            )
            if not ok_project or not selected_title:
                return
            selected_project_id = rows[titles.index(selected_title)][0]
            try:
                suggested_name, content = render_annotated_bibliography(
                    self.db_path,
                    selected_project_id,
                )
            except Exception as exc:
                QMessageBox.warning(self, "Export Error", f"Could not build the annotated bibliography.\n\n{exc}")
                return
        else:
            rows = self._list_writing_projects()
            if not rows:
                QMessageBox.information(self, "No writing projects", "Create a writing project first, then tag annotations to it.")
                return
            titles = [title or "Untitled writing project" for _, title in rows]
            default_index = 0
            if self.current_annotation_writing_project_id:
                for idx, (project_id, _) in enumerate(rows):
                    if project_id == self.current_annotation_writing_project_id:
                        default_index = idx
                        break
            selected_title, ok_project = QInputDialog.getItem(
                self,
                "Writing Project Export",
                "Choose a writing project:",
                titles,
                default_index,
                False,
            )
            if not ok_project or not selected_title:
                return
            selected_project_id = rows[titles.index(selected_title)][0]
            try:
                suggested_name, content = render_writing_project_export(
                    self.db_path,
                    selected_project_id,
                )
            except Exception as exc:
                QMessageBox.warning(self, "Export Error", f"Could not build the writing project export.\n\n{exc}")
                return

        default_dir = os.path.dirname(self.db_path)
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Export",
            os.path.join(default_dir, suggested_name),
            "Markdown Files (*.md);;Text Files (*.txt)",
        )
        if not output_path:
            return
        try:
            write_export_file(output_path, content)
        except Exception as exc:
            QMessageBox.warning(self, "Export Error", f"Could not write the export file.\n\n{exc}")
            return
        QMessageBox.information(self, "Export Created", f"Saved:\n{output_path}")

    def zoom_in(self):
        self.zoom_factor = min(4.0, self.zoom_factor * 1.2)
        if hasattr(self, "fit_check"):
            self.fit_check.setChecked(False)
        runtime_trace(f"zoom_in new_zoom={self.zoom_factor:.3f}")
        self.render_page(self.current_page)

    def zoom_out(self):
        self.zoom_factor = max(0.2, self.zoom_factor / 1.2)
        if hasattr(self, "fit_check"):
            self.fit_check.setChecked(False)
        runtime_trace(f"zoom_out new_zoom={self.zoom_factor:.3f}")
        self.render_page(self.current_page)

    def on_fit_width_changed(self, state):
        self.fit_to_width = state == Qt.Checked
        self.render_page(self.current_page)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel and event.modifiers() == Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
            return True
        if hasattr(self, "doc_list") and obj == self.doc_list.viewport() and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self._sync_doc_list_row_heights)
        if hasattr(self, "active_record_card") and obj == self.active_record_card and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self._sync_active_record_text)
        if hasattr(self, "pages_scroll") and obj == self.pages_scroll.viewport() and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self._position_focus_handle)
        return super().eventFilter(obj, event)

    def start_reading_session(self):
        if self.current_document_id is None:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No document", "Open a PDF before starting a session.")
            return
        from PySide6.QtWidgets import QInputDialog
        intention, ok = QInputDialog.getText(
            self, "New Reading Session", "What is your reading intention for this session?"
        )
        if not ok:
            return
        session_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO reading_sessions (id, document_id, project_source_id, reading_intention, start_page, session_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                self.current_document_id,
                self.current_project_source_id,
                intention.strip(),
                self.current_page,
                datetime.now().isoformat(),
            ))
            conn.commit()
        self.current_session_id = session_id
        self.current_session_intention = intention.strip()
        self._apply_theme()
        self._update_ribbon_status()

    def _ensure_source_for_document_row(self, conn, document_id):
        row = conn.execute(
            """
            SELECT id, title, file_path, source_url, citation_metadata, created_at, updated_at
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()
        if not row:
            return None
        _document_id, title, file_path, source_url, citation_metadata, created_at, updated_at = row
        normalized_path = (file_path or "").strip()
        normalized_title = (title or "").strip() or normalized_path or document_id
        source_row = None
        if normalized_path:
            source_row = conn.execute(
                "SELECT id FROM sources WHERE file_path = ? LIMIT 1",
                (normalized_path,),
            ).fetchone()
        if source_row is None and not normalized_path and normalized_title:
            source_row = conn.execute(
                "SELECT id FROM sources WHERE canonical_title = ? LIMIT 1",
                (normalized_title,),
            ).fetchone()
        if source_row:
            source_id = source_row[0]
            conn.execute(
                """
                UPDATE sources
                SET file_path = COALESCE(?, file_path),
                    canonical_title = ?,
                    source_url = COALESCE(?, source_url),
                    citation_metadata = COALESCE(NULLIF(?, ''), citation_metadata),
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    normalized_path or None,
                    normalized_title,
                    source_url,
                    citation_metadata or "",
                    updated_at or datetime.now().isoformat(),
                    source_id,
                ),
            )
            return source_id
        source_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        conn.execute(
            """
            INSERT INTO sources (
                id, file_path, canonical_title, source_url, citation_metadata,
                doc_fingerprint, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                normalized_path or None,
                normalized_title,
                source_url,
                citation_metadata,
                None,
                created_at or now,
                updated_at or now,
            ),
        )
        return source_id

    def _upsert_document_record(self, path, total_pages, citation_guess=None, preferred_document_id=None, assign_to_current_project=False, activate=True):
        citation_guess = self._clean_import_citation_guess(path, citation_guess or {})
        title = citation_guess.get("title") or os.path.basename(path)
        preferred_project_source_id = None
        document_id = None
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            existing = None
            if preferred_document_id:
                existing = cursor.execute(
                    "SELECT id, COALESCE(citation_metadata, '') FROM documents WHERE id = ?",
                    (preferred_document_id,),
                ).fetchone()
            if existing is None and self.current_project_id:
                existing = self._get_project_document_for_path(path, self.current_project_id)
            if existing is None:
                cursor.execute("SELECT id, COALESCE(citation_metadata, '') FROM documents WHERE file_path = ? ORDER BY updated_at DESC", (path,))
                existing = cursor.fetchone()
            if existing:
                document_id = existing[0]
                existing_citation = existing[1]
                if len(existing) > 2:
                    preferred_project_source_id = existing[2]
                cursor.execute("""
                    UPDATE documents
                    SET title = ?, total_pages = ?, updated_at = ?
                    WHERE id = ?
                """, (title, total_pages, datetime.now().isoformat(), document_id))
                if citation_guess and not existing_citation:
                    cursor.execute(
                        "UPDATE documents SET citation_metadata = ? WHERE id = ?",
                        (json.dumps({k: v for k, v in citation_guess.items() if k != "title"}), document_id),
                    )
            else:
                document_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO documents (id, title, file_path, total_pages, status, priority, citation_metadata, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    document_id,
                    title,
                    path,
                    total_pages,
                    "new",
                    3,
                    json.dumps({k: v for k, v in citation_guess.items() if k != "title"}),
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                ))
            self._ensure_source_for_document_row(conn, document_id)
            conn.commit()
        if activate:
            self.current_document_id = document_id
        if assign_to_current_project and self.current_project_id:
            self._assign_document_to_project(document_id, self.current_project_id)
        if not activate:
            return document_id
        if preferred_project_source_id and self.current_project_id:
            self.current_project_source_id = preferred_project_source_id
        else:
            self._refresh_current_project_source()
        return document_id

    def save_document_to_db(self, path, preferred_document_id=None, assign_to_current_project=False):
        citation_guess = {}
        total_pages = self.total_pages
        if self.doc is not None:
            citation_guess = self._prefill_citation_metadata(path, self.doc)
            total_pages = self.doc.page_count
        return self._upsert_document_record(
            path,
            total_pages,
            citation_guess,
            preferred_document_id=preferred_document_id,
            assign_to_current_project=assign_to_current_project,
            activate=True,
        )

    def _load_current_document_into_organizer(self):
        if not self.current_document_id:
            return
        with sqlite3.connect(self.db_path) as conn:
            if self.current_project_source_id:
                row = conn.execute(
                    """
                    SELECT
                        ps.id,
                        d.id,
                        COALESCE(ps.display_title, d.title, s.canonical_title, ''),
                        COALESCE(d.file_path, s.file_path, ''),
                        COALESCE(ps.status, 'new'),
                        COALESCE(ps.priority, 3),
                        COALESCE(ps.reading_type, d.reading_type, ''),
                        COALESCE(s.citation_metadata, d.citation_metadata, ''),
                        ps.created_at,
                        COALESCE(rp.title, '')
                    FROM project_sources ps
                    LEFT JOIN documents d ON d.id = ps.legacy_document_id
                    LEFT JOIN sources s ON s.id = ps.source_id
                    LEFT JOIN review_projects rp ON rp.id = ps.project_id
                    WHERE ps.id = ?
                    """,
                    (self.current_project_source_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT
                        NULL,
                        d.id,
                        COALESCE(d.title, s.canonical_title, ''),
                        COALESCE(d.file_path, s.file_path, ''),
                        COALESCE(d.status, 'new'),
                        COALESCE(d.priority, 3),
                        COALESCE(d.reading_type, ''),
                        COALESCE(s.citation_metadata, d.citation_metadata, ''),
                        d.created_at,
                        '',
                        s.id
                    FROM documents d
                    LEFT JOIN sources s
                        ON (
                            (d.file_path IS NOT NULL AND d.file_path <> '' AND s.file_path = d.file_path)
                            OR (
                                (d.file_path IS NULL OR d.file_path = '')
                                AND s.canonical_title = d.title
                            )
                        )
                    WHERE d.id = ?
                    ORDER BY s.updated_at DESC, s.created_at DESC
                    LIMIT 1
                    """,
                    (self.current_document_id,),
                ).fetchone()
        try:
            citation = json.loads(row[7]) if row and row[7] else {}
        except Exception:
            citation = {}
        if row:
            data = {
                "id": row[0],
                "project_source_id": row[0],
                "document_id": row[1],
                "title": row[2] or "",
                "file_path": row[3] or "",
                "status": row[4] or "new",
                "priority": row[5] or 3,
                "reading_type": row[6] or "",
                "created_at": row[8] or "",
                "project_title": row[9] or "",
                "source_id": row[10] if len(row) > 10 else None,
                "citation_metadata": citation,
            }
            self._update_active_record_label(data)
            self._populate_doc_organizer(data)

    def save_annotation(self, triage=False):
        if self.doc is None or self.current_document_id is None:
            return None
        from PySide6.QtWidgets import QMessageBox
        annotation_type = self._current_annotation_type()
        selected_text = self.selected_text_edit.toPlainText().strip()
        note = self.note_edit.toPlainText().strip()
        confidence = self.confidence_combo.currentText()
        requires_selection = annotation_type in {"quote", "paraphrase", "interpretation"}
        requires_note = annotation_type in {"paraphrase", "interpretation", "synthesis"}
        if requires_selection and not selected_text:
            QMessageBox.warning(self, "Selection Required", "This annotation type requires a text selection from the PDF.")
            return None
        if requires_note and not note:
            QMessageBox.warning(self, "Note Required", "This annotation type requires your own note content.")
            return None
        page_index = self.selected_page if self.selected_page is not None else self.current_page
        live_chars = self._all_selected_chars()
        existing_row = None
        if self.annotation_draft_mode == "editing_existing" and self.current_annotation_id:
            with sqlite3.connect(self.db_path) as conn:
                existing_row = conn.execute(
                    """
                    SELECT page_number, position_json
                    FROM annotations
                    WHERE id = ?
                    """,
                    (self.current_annotation_id,),
                ).fetchone()
        # Build regions list: committed regions + current drag
        all_regions = list(self.selection_regions)
        if self.selection_start_index is not None and self.selection_end_index is not None:
            all_regions.append((self.selection_start_index, self.selection_end_index))
        if existing_row and not live_chars and not all_regions:
            page_index = existing_row[0] if existing_row[0] is not None else page_index
            position_json = existing_row[1] or "{}"
        else:
            page_rect = self.doc.load_page(page_index).rect
            regions_out = []
            saved_rects = []
            for s, e in all_regions:
                lo, hi = sorted((s, e))
                region_chars = self._range_chars(lo, hi)
                region_data = {"char_start": lo, "char_end": hi}
                region_rect = self._bounds_to_relative_rect(self._selection_bounds(region_chars), page_rect)
                if region_rect is not None:
                    region_data.update(region_rect)
                line_rects = self._chars_to_line_relative_rects(region_chars, page_rect)
                if line_rects:
                    region_data["rects"] = line_rects
                    saved_rects.extend(line_rects)
                regions_out.append(region_data)
            char_start = self.selection_char_start if self.selection_char_start is not None else 0
            char_end = self.selection_char_end if self.selection_char_end is not None else len(selected_text)
            overall_rect = self._bounds_to_relative_rect(self._selection_bounds(live_chars), page_rect)
            if overall_rect is not None:
                x = overall_rect["x"]
                y = overall_rect["y"]
                width = overall_rect["width"]
                height = overall_rect["height"]
            else:
                x, y, width, height = 0, 0, 0, 0
            position_json = json.dumps({
                "x": x, "y": y, "width": width, "height": height,
                "char_start": char_start, "char_end": char_end,
                "page": page_index,
                "regions": regions_out,
                "rects": saved_rects,
            })
        annotation_id = self.current_annotation_id if (self.annotation_draft_mode == "editing_existing" and self.current_annotation_id) else str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if self.annotation_draft_mode == "editing_existing" and self.current_annotation_id:
                cursor.execute(
                    """
                    UPDATE annotations
                    SET project_source_id = ?, session_id = ?, page_number = ?, position_json = ?,
                        annotation_type = ?, selected_text = ?, note_content = ?, confidence_level = ?,
                        triage = CASE WHEN ? THEN 1 ELSE triage END
                    WHERE id = ?
                    """,
                    (
                        self.current_project_source_id,
                        self.current_session_id,
                        page_index,
                        position_json,
                        annotation_type,
                        selected_text,
                        note,
                        confidence,
                        1 if triage else 0,
                        annotation_id,
                    ),
                )
                cursor.execute(
                    "DELETE FROM annotation_writing_projects WHERE annotation_id = ?",
                    (annotation_id,),
                )
                cursor.execute(
                    "DELETE FROM annotation_tags WHERE annotation_id = ?",
                    (annotation_id,),
                )
            else:
                cursor.execute("""
                    INSERT INTO annotations (
                        id, document_id, project_source_id, session_id, page_number,
                        position_json, annotation_type, selected_text, note_content, confidence_level, triage, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    annotation_id,
                    self.current_document_id,
                    self.current_project_source_id,
                    self.current_session_id,
                    page_index,
                    position_json,
                    annotation_type,
                    selected_text,
                    note,
                    confidence,
                    1 if triage else 0,
                    datetime.now().isoformat(),
                ))
            writing_project_id = self._current_annotation_writing_project_id()
            if writing_project_id:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO annotation_writing_projects (annotation_id, project_id)
                    VALUES (?, ?)
                    """,
                    (annotation_id, writing_project_id),
                )
            for tag_label in self.current_annotation_tags:
                normalized_tag = self._normalize_tag_label(tag_label)
                if not normalized_tag:
                    continue
                tag_row = cursor.execute(
                    "SELECT id FROM tags WHERE LOWER(label) = ? LIMIT 1",
                    (normalized_tag.lower(),),
                ).fetchone()
                if tag_row:
                    tag_id = tag_row[0]
                else:
                    tag_id = str(uuid.uuid4())
                    cursor.execute(
                        "INSERT INTO tags (id, label, category, color_hex) VALUES (?, ?, ?, ?)",
                        (tag_id, normalized_tag, "user", None),
                    )
                cursor.execute(
                    "INSERT OR IGNORE INTO annotation_tags (annotation_id, tag_id) VALUES (?, ?)",
                    (annotation_id, tag_id),
                )
            conn.commit()
        self.current_annotation_id = annotation_id
        # clear fields
        self._clear_annotation_editor(clear_type=False, clear_writing_project=False)
        # refresh sidebar and current page highlights
        self.load_annotations()
        self.draw_page_highlights(page_index)
        return annotation_id

    def explain_annotation(self):
        from PySide6.QtWidgets import QMessageBox
        selected_text = self.selected_text_edit.toPlainText().strip()
        note = self.note_edit.toPlainText().strip()
        annotation_type = self._current_annotation_type()
        annotation_id = self.current_annotation_id
        requires_note = annotation_type in {"paraphrase", "interpretation", "synthesis"}
        needs_save = self.annotation_draft_mode in {"draft_new", "editing_existing"} or annotation_id is None
        if needs_save:
            if not selected_text and self.current_annotation_id is None:
                QMessageBox.warning(self, "No Annotation", "Create or reopen an annotation first, then run Explain Annotation.")
                return
            if self.current_annotation_id is None and requires_note and not note:
                QMessageBox.warning(
                    self,
                    "Add Your Note First",
                    "Explain Annotation is grounded in a saved annotation.\n\nAdd your note first, then run Explain Annotation.",
                )
                return
            annotation_id = self.save_annotation(triage=self.reader_mode == "triage")
            if not annotation_id:
                return
            self._open_annotation_by_id(annotation_id)
            note = self.note_edit.toPlainText().strip()
        if annotation_id is None:
            QMessageBox.warning(self, "No Annotation", "Create or reopen an annotation first, then run Explain Annotation.")
            return
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT selected_text, document_id, project_source_id, page_number, session_id FROM annotations WHERE id = ?",
                (annotation_id,)
            ).fetchone()
        if not row:
            return
        import asyncio
        selected_text, document_id, project_source_id, page_number, session_id = row
        asyncio.ensure_future(
            self._explain_async(
                selected_text,
                annotation_id,
                document_id,
                project_source_id,
                page_number,
                session_id,
                note,
            )
        )

    async def _explain_async(self, text, annotation_id, document_id, project_source_id, page_number, session_id, user_note=""):
        from PySide6.QtWidgets import QMessageBox
        interpreted_note = (user_note or "").strip()
        if not interpreted_note:
            interpreted_note, ok = QInputDialog.getText(
                self,
                "Your Interpretation",
                "Add your interpretation before seeing the AI response:",
            )
            if not ok:
                return
            interpreted_note = interpreted_note.strip()
        context = self._assemble_context(text, interpreted_note, document_id, page_number, session_id)
        from .ai import explain_passage
        try:
            result = await explain_passage(context)
        except Exception as exc:
            QMessageBox.warning(self, "AI Error", f"Could not generate an explanation.\n\n{exc}")
            return
        # save to ai_outputs linked to this annotation
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO ai_outputs (id, document_id, project_source_id, annotation_id, output_type, content_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                document_id,
                project_source_id,
                annotation_id,
                "explanation",
                json.dumps({
                    "explanation": result["explanation"],
                    "user_interpretation": context.get("user_interpretation", ""),
                }),
                datetime.now().isoformat(),
            ))
            conn.commit()
        self.load_annotations()
        if self.current_annotation_id == annotation_id:
            self.ai_explanation_edit.setPlainText(result["explanation"])
        QMessageBox.information(self, "AI Explanation", result["explanation"])

    def _assemble_context(self, selected_text: str, user_interpretation: str, document_id=None, page_number=None, session_id=None) -> dict:
        context = {
            "selected_text": selected_text,
            "user_interpretation": user_interpretation,
        }
        if document_id:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT title, reading_type, file_path FROM documents WHERE id = ?",
                    (document_id,)
                ).fetchone()
                if row:
                    context["doc_title"] = row[0] or ""
                    context["reading_type"] = row[1] or ""
                    file_path = row[2] or ""
                else:
                    file_path = ""
        else:
            file_path = ""
        if page_number is not None and page_number >= 0:
            source_doc = None
            close_after = False
            try:
                if self.current_document_id == document_id and self.doc is not None and page_number < self.total_pages:
                    source_doc = self.doc
                elif file_path and os.path.exists(file_path):
                    source_doc = fitz.open(file_path)
                    close_after = True
                if source_doc is not None and page_number < source_doc.page_count:
                    page = source_doc.load_page(page_number)
                    context["surrounding_text"] = self._normalize_text(page.get_text("text"))
            finally:
                if close_after and source_doc is not None:
                    source_doc.close()
        if session_id:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT reading_intention FROM reading_sessions WHERE id = ?",
                    (session_id,)
                ).fetchone()
                if row:
                    context["session_intention"] = row[0] or ""
        return context

    def _current_annotation_scope(self):
        if hasattr(self, "annotation_scope_combo"):
            return self.annotation_scope_combo.currentData() or "page"
        return "page"

    def _update_annotation_scope_labels(self):
        if not hasattr(self, "annotation_scope_combo"):
            return
        selected_scope = self._current_annotation_scope()
        self.annotation_scope_combo.blockSignals(True)
        page_text = f"Page {self.current_page + 1}" if self.doc is not None else "Current page"
        if self.annotation_scope_combo.count() > 0:
            self.annotation_scope_combo.setItemText(0, page_text)
        for index in range(self.annotation_scope_combo.count()):
            if self.annotation_scope_combo.itemData(index) == selected_scope:
                self.annotation_scope_combo.setCurrentIndex(index)
                break
        self.annotation_scope_combo.blockSignals(False)

    def _refresh_annotations_after_page_change(self):
        self._update_annotation_scope_labels()
        if self._current_annotation_scope() != "page":
            return
        try:
            runtime_trace(
                f"_refresh_annotations_after_page_change page={self.current_page} "
                f"scope={self._current_annotation_scope()}"
            )
            self.load_annotations()
        except Exception:
            runtime_trace("_refresh_annotations_after_page_change failed")
            print("Annotation refresh failed:")
            print(traceback.format_exc())

    def _annotation_scope_label(self, scope, count):
        if scope == "page":
            return f"Saved annotations on page {self.current_page + 1}: {count}"
        if scope == "project" and self.current_project_id:
            project_title = self.project_combo.currentText() if hasattr(self, "project_combo") else "current project"
            return f"Saved annotations in {project_title}: {count}"
        return f"Saved annotations for the current source: {count}"

    def _filter_annotations(self):
        query = self.search_box.text().strip().lower() if hasattr(self, "search_box") else ""
        type_filter = self.annotation_type_filter_combo.currentData() if hasattr(self, "annotation_type_filter_combo") else ""
        tag_filter = self.annotation_tag_filter_combo.currentData() if hasattr(self, "annotation_tag_filter_combo") else ""
        for i in range(self.annotation_list.count()):
            item = self.annotation_list.item(i)
            data = item.data(Qt.UserRole) or {}
            if not data:
                matches_query = (not query) or (query in item.text().lower())
                item.setHidden(not matches_query)
                continue
            item_type = data.get("annotation_type", "")
            item_tags = [str(tag).lower() for tag in (data.get("tags") or [])]
            matches_query = (not query) or (query in item.text().lower())
            matches_type = (not type_filter) or (item_type == type_filter)
            matches_tag = (not tag_filter) or (tag_filter in item_tags)
            matches_focus = True
            if getattr(self, "annotation_saved_panel_compact", False) and self.current_annotation_id:
                matches_focus = data.get("id") == self.current_annotation_id
            item.setHidden(not (matches_query and matches_type and matches_tag and matches_focus))

    def _load_annotations_legacy(self):
        self.annotation_list.clear()
        if self.current_document_id is None:
            self.annotation_list.addItem(QListWidgetItem("No document loaded."))
            return
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, page_number, position_json, COALESCE(annotation_type, 'interpretation'),
                       selected_text, note_content, confidence_level, created_at,
                       (
                           SELECT awp.project_id
                           FROM annotation_writing_projects awp
                           WHERE awp.annotation_id = annotations.id
                           LIMIT 1
                       ),
                       (
                           SELECT wp.title
                           FROM annotation_writing_projects awp
                           JOIN writing_projects wp ON wp.id = awp.project_id
                           WHERE awp.annotation_id = annotations.id
                           LIMIT 1
                       )
                FROM annotations
                WHERE (
                    project_source_id = ?
                    OR (project_source_id IS NULL AND document_id = ?)
                )
                ORDER BY annotations.created_at DESC
            """, (self.current_project_source_id, self.current_document_id))
            rows = cursor.fetchall()
        if not rows:
            self.annotation_list.addItem(QListWidgetItem("No annotations yet."))
            return
        with sqlite3.connect(self.db_path) as conn2:
            explained_ids = {r[0] for r in conn2.execute(
                "SELECT DISTINCT annotation_id FROM ai_outputs WHERE output_type = 'explanation'"
            ).fetchall()}
        type_labels = {
            "quote": "Quote",
            "paraphrase": "Paraphrase",
            "interpretation": "Interpretation",
            "synthesis": "Synthesis",
        }
        for row in rows:
            anno_id, page, position_json, annotation_type, selected_text, note, confidence, created_at = row
            primary_text = selected_text if annotation_type == "quote" else (note or selected_text)
            snippet = primary_text[:60] + ("..." if len(primary_text) > 60 else "")
            note_line = f"\n💬 {note}" if note else ""
            ai_marker = " 🤖" if anno_id in explained_ids else ""
            item_text = f"📌 {type_labels.get(annotation_type, 'Interpretation')} • Page {page + 1}  [{confidence}]{ai_marker}\n{snippet}{note_line if annotation_type == 'quote' else ''}"
            item = QListWidgetItem(item_text)
            item.setSizeHint(QSize(200, 80))
            try:
                position = json.loads(position_json or "{}")
            except Exception:
                position = {}
            item.setData(Qt.UserRole, {
                "id": anno_id,
                "page": page,
                "position": position,
                "note": note or "",
                "selected_text": selected_text or "",
                "annotation_type": annotation_type or "interpretation",
            })
            self.annotation_list.addItem(item)

    def load_annotations(self):
        runtime_trace(
            f"load_annotations start doc_id={self.current_document_id!r} "
            f"project_source_id={self.current_project_source_id!r} page={self.current_page} "
            f"scope={self._current_annotation_scope()!r}"
        )
        self.annotation_list.clear()
        if self.current_document_id is None:
            self.annotation_saved_panel_has_results = False
            self._populate_annotation_tag_filter([])
            if hasattr(self, "annotation_list_hint"):
                self.annotation_list_hint.setText("Open a source to review saved annotations here.")
            self._apply_annotation_saved_panel_mode(getattr(self, "annotation_focus_mode", False))
            self.annotation_list.addItem(QListWidgetItem("No document loaded."))
            return
        scope = self._current_annotation_scope()
        try:
            with sqlite3.connect(self.db_path) as conn:
                if scope == "project" and self.current_project_id:
                    where_sql = "ps.project_id = ?"
                    params = [self.current_project_id]
                    joins = "LEFT JOIN project_sources ps ON ps.id = annotations.project_source_id"
                else:
                    where_sql = "(annotations.project_source_id = ? OR (annotations.project_source_id IS NULL AND annotations.document_id = ?))"
                    params = [self.current_project_source_id, self.current_document_id]
                    joins = ""
                    if scope == "page":
                        where_sql += " AND annotations.page_number = ?"
                        params.append(self.current_page)
                rows = conn.execute(
                    f"""
                    SELECT annotations.id, annotations.page_number, annotations.position_json, COALESCE(annotations.annotation_type, 'interpretation'),
                           annotations.selected_text, annotations.note_content, annotations.confidence_level, annotations.created_at,
                           (
                               SELECT awp.project_id
                               FROM annotation_writing_projects awp
                               WHERE awp.annotation_id = annotations.id
                               LIMIT 1
                           ) AS writing_project_id,
                           (
                               SELECT wp.title
                               FROM annotation_writing_projects awp
                               JOIN writing_projects wp ON wp.id = awp.project_id
                               WHERE awp.annotation_id = annotations.id
                               LIMIT 1
                           ) AS writing_project_title,
                           (
                               SELECT GROUP_CONCAT(t.label, '||')
                               FROM annotation_tags at
                               JOIN tags t ON t.id = at.tag_id
                               WHERE at.annotation_id = annotations.id
                           ) AS tag_labels,
                           annotations.document_id,
                           annotations.project_source_id,
                           COALESCE(aps.display_title, d.title, s.canonical_title, d.file_path, '') AS source_title
                    FROM annotations
                    LEFT JOIN documents d ON d.id = annotations.document_id
                    LEFT JOIN project_sources aps ON aps.id = annotations.project_source_id
                    LEFT JOIN sources s ON s.id = aps.source_id
                    {joins}
                    WHERE {where_sql}
                    ORDER BY annotations.created_at DESC
                    """,
                    params,
                    ).fetchall()
        except sqlite3.Error:
            runtime_trace("load_annotations falling back after sqlite error")
            with sqlite3.connect(self.db_path) as conn:
                if scope == "project" and self.current_project_id:
                    where_sql = "ps.project_id = ?"
                    params = [self.current_project_id]
                    joins = "LEFT JOIN project_sources ps ON ps.id = annotations.project_source_id"
                else:
                    where_sql = "(annotations.project_source_id = ? OR (annotations.project_source_id IS NULL AND annotations.document_id = ?))"
                    params = [self.current_project_source_id, self.current_document_id]
                    joins = ""
                    if scope == "page":
                        where_sql += " AND annotations.page_number = ?"
                        params.append(self.current_page)
                rows = [
                    row
                    for row in conn.execute(
                        f"""
                        SELECT annotations.id, annotations.page_number, annotations.position_json, COALESCE(annotations.annotation_type, 'interpretation'),
                               annotations.selected_text, annotations.note_content, annotations.confidence_level, annotations.created_at,
                               NULL AS writing_project_id,
                               NULL AS writing_project_title,
                               NULL AS tag_labels,
                               annotations.document_id,
                               annotations.project_source_id,
                               COALESCE(aps.display_title, d.title, s.canonical_title, d.file_path, '') AS source_title
                        FROM annotations
                        LEFT JOIN documents d ON d.id = annotations.document_id
                        LEFT JOIN project_sources aps ON aps.id = annotations.project_source_id
                        LEFT JOIN sources s ON s.id = aps.source_id
                        {joins}
                        WHERE {where_sql}
                        ORDER BY annotations.created_at DESC
                        """,
                        params,
                    ).fetchall()
                ]
        sort_mode = self.annotation_sort_combo.currentData() if hasattr(self, "annotation_sort_combo") else "recent"
        if sort_mode == "page":
            rows.sort(key=lambda row: (row[1], row[7] or "", row[0]))
        elif sort_mode == "type":
            type_order = {"quote": 0, "paraphrase": 1, "interpretation": 2, "synthesis": 3}
            rows.sort(key=lambda row: (type_order.get(row[3] or "interpretation", 9), row[1], row[7] or "", row[0]))
        else:
            rows.sort(key=lambda row: (row[7] or "", row[0]), reverse=True)
        if not rows:
            self.annotation_saved_panel_has_results = False
            runtime_trace("load_annotations complete rows=0")
            self._populate_annotation_tag_filter([])
            if hasattr(self, "annotation_list_hint"):
                if scope == "page":
                    self.annotation_list_hint.setText(f"No annotations on page {self.current_page + 1}. Switch to This document to review all notes.")
                elif scope == "project" and self.current_project_id:
                    self.annotation_list_hint.setText("No annotations in this project yet. Add notes while reading sources in this project.")
                else:
                    self.annotation_list_hint.setText("No annotations for this source yet. Select text in the PDF to start one.")
            self._apply_annotation_saved_panel_mode(getattr(self, "annotation_focus_mode", False))
            self.annotation_list.addItem(QListWidgetItem("No annotations yet."))
            return
        self.annotation_saved_panel_has_results = True
        self._apply_annotation_saved_panel_mode(getattr(self, "annotation_focus_mode", False))
        if hasattr(self, "annotation_list_hint"):
            self.annotation_list_hint.setText(self._annotation_scope_label(scope, len(rows)))
        available_tags = set()
        with sqlite3.connect(self.db_path) as conn2:
            explained_ids = {
                r[0]
                for r in conn2.execute(
                    "SELECT DISTINCT annotation_id FROM ai_outputs WHERE output_type = 'explanation'"
                ).fetchall()
            }
        type_labels = {
            "quote": "Quote",
            "paraphrase": "Paraphrase",
            "interpretation": "Interpretation",
            "synthesis": "Synthesis",
        }
        for row in rows:
            (
                anno_id,
                page,
                position_json,
                annotation_type,
                selected_text,
                note,
                confidence,
                created_at,
                writing_project_id,
                writing_project_title,
                tag_labels,
                annotation_document_id,
                annotation_project_source_id,
                source_title,
            ) = row
            tags = [tag for tag in (tag_labels or "").split("||") if tag]
            available_tags.update(tags)
            primary_text = selected_text if annotation_type == "quote" else (note or selected_text)
            snippet = primary_text[:60] + ("..." if len(primary_text) > 60 else "")
            ai_marker = " [AI]" if anno_id in explained_ids else ""
            meta_parts = []
            if writing_project_title:
                meta_parts.append(f"Draft: {writing_project_title}")
            if scope == "project" and source_title:
                meta_parts.append(f"Source: {source_title[:40]}{'...' if len(source_title) > 40 else ''}")
            if tags:
                meta_parts.append(f"Tags: {', '.join(tags[:3])}")
            item = QListWidgetItem()
            meta_line = " • ".join(meta_parts)
            title_line = f"{type_labels.get(annotation_type, 'Interpretation')} • Page {page + 1} • {confidence}{ai_marker}"
            row_height = 78
            if meta_line:
                row_height += 14
            item.setSizeHint(QSize(200, row_height))
            list_colors = self._annotation_list_colors(annotation_type)
            item.setBackground(QBrush(list_colors["background"]))
            item.setForeground(QBrush(list_colors["foreground"]))
            try:
                position = json.loads(position_json or "{}")
            except Exception:
                position = {}
            item.setData(Qt.UserRole, {
                "id": anno_id,
                "page": page,
                "position": position,
                "note": note or "",
                "selected_text": selected_text or "",
                "annotation_type": annotation_type or "interpretation",
                "writing_project_id": writing_project_id,
                "document_id": annotation_document_id,
                "project_source_id": annotation_project_source_id,
                "tags": tags,
            })
            if anno_id == self.current_annotation_id:
                item.setBackground(QBrush(QColor(self._theme_palette["active_item_bg"])))
                item.setForeground(QBrush(QColor(self._theme_palette["text"])))
                item.setSelected(True)
            self.annotation_list.addItem(item)
            row_widget = self._make_list_row_widget(
                title=title_line,
                subtitle=snippet,
                meta=meta_line,
                active=anno_id == self.current_annotation_id,
                accent_color=list_colors["foreground"].name(),
                role="annotation",
            )
            self.annotation_list.setItemWidget(item, row_widget)
        self._populate_annotation_tag_filter(available_tags)
        self._filter_annotations()
        runtime_trace(f"load_annotations complete rows={len(rows)}")

    def get_page_annotations(self, page_index):
        annotations = []
        if self.current_document_id is None:
            return annotations
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, position_json, COALESCE(annotation_type, 'interpretation')
                FROM annotations
                WHERE (
                    project_source_id = ?
                    OR (project_source_id IS NULL AND document_id = ?)
                ) AND page_number = ?
            """, (self.current_project_source_id, self.current_document_id, page_index))
            rows = cursor.fetchall()
        for (annotation_id, position_json, annotation_type) in rows:
            try:
                data = json.loads(position_json)
                if isinstance(data, dict):
                    data["id"] = annotation_id
                    data["annotation_type"] = annotation_type or "interpretation"
                    annotations.append(data)
            except Exception:
                continue
        return annotations


def _install_runtime_diagnostics():
    global RUNTIME_CRASH_LOG
    crash_log_path = os.path.join(os.path.dirname(__file__), "..", "runtime-errors.log")
    crash_log_path = os.path.abspath(crash_log_path)
    try:
        crash_log = open(crash_log_path, "a", encoding="utf-8")
        crash_log.write(f"\n=== Scholar runtime started {datetime.now().isoformat()} ===\n")
        crash_log.flush()
        faulthandler.enable(crash_log)
    except Exception:
        crash_log = None

    def _log_exception(exc_type, exc_value, exc_tb):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print(text, file=sys.stderr)
        if crash_log is not None:
            crash_log.write(text)
            crash_log.flush()

    sys.excepthook = _log_exception
    RUNTIME_CRASH_LOG = crash_log
    return crash_log


if __name__ == "__main__":
    import asyncio
    import qasync

    crash_log = _install_runtime_diagnostics()
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.Round
    )
    app = QApplication(sys.argv)
    app.setFont(PDFViewer._ui_font())
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    with loop:
        viewer = PDFViewer()
        viewer.show()
        loop.run_forever()
