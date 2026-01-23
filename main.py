import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QPushButton, QComboBox, QLabel, 
                              QTextEdit, QFileDialog, QSplitter, QMessageBox,
                              QLineEdit, QGroupBox, QStatusBar, QTextBrowser, QDialog, QFormLayout, QSpinBox, QComboBox as QComboBoxWidget, QStyle, QPlainTextEdit, QCheckBox, QTabWidget)
from PyQt6.QtCore import Qt, QTimer, QSettings, QSize, QEvent
import ctypes
from PyQt6.QtGui import QFont, QAction, QKeySequence, QSyntaxHighlighter, QTextCharFormat, QColor, QTextCursor
import re
import tempfile
import json
import uuid

from injection_manager import InjectionManager, TargetGame, InjectionMethod, GameMode


class GSCSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for GSC language"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Define formatting styles
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#569cd6"))
        self.keyword_format.setFontWeight(700)
        
        self.builtin_format = QTextCharFormat()
        self.builtin_format.setForeground(QColor("#4ec9b0"))
        
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#ce9178"))
        
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#6a9955"))
        self.comment_format.setFontItalic(True)
        
        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor("#b5cea8"))
        
        self.function_format = QTextCharFormat()
        self.function_format.setForeground(QColor("#dcdcaa"))
        
        # Define keywords
        self.keywords = [
            'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'default',
            'break', 'continue', 'return', 'wait', 'waittill', 'endon',
            'notify', 'thread', 'true', 'false', 'undefined', 'function'
        ]
        
        # Built-in identifiers
        self.builtins = [
            'self', 'level', 'game', 'iprintln', 'iprintlnbold', 'setdvar',
            'getdvar', 'precachemodel', 'precacheshader', 'spawn', 'spawnstruct',
            'getent', 'getentarray', 'distance', 'vectornormalize', 'angles_to_forward',
            'playfx', 'playsound', 'playsoundatpos', 'earthquake', 'radiusdamage'
        ]
        
        # Build highlighting rules
        self.rules = []
        
        # Keywords
        for word in self.keywords:
            pattern = f'\\b{word}\\b'
            self.rules.append((re.compile(pattern), self.keyword_format))
        
        # Built-ins
        for word in self.builtins:
            pattern = f'\\b{word}\\b'
            self.rules.append((re.compile(pattern), self.builtin_format))
        
        # Numbers
        self.rules.append((re.compile(r'\b[0-9]+\.?[0-9]*\b'), self.number_format))
        
        # Strings
        self.rules.append((re.compile(r'"[^"\\]*(\\.[^"\\]*)*"'), self.string_format))
        
        # Single-line comments
        self.rules.append((re.compile(r'//[^\n]*'), self.comment_format))
        
        # Functions
        self.rules.append((re.compile(r'\b[A-Za-z_][A-Za-z0-9_]*(?=\s*\()'), self.function_format))
    
    def highlightBlock(self, text):
        # Apply syntax highlighting rules
        for pattern, format in self.rules:
            for match in pattern.finditer(text):
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, format)
        
        # Multi-line comments
        self.setCurrentBlockState(0)
        start_index = 0
        if self.previousBlockState() != 1:
            start_index = text.find('/*')
        
        while start_index >= 0:
            end_index = text.find('*/', start_index)
            if end_index == -1:
                self.setCurrentBlockState(1)
                comment_length = len(text) - start_index
            else:
                comment_length = end_index - start_index + 2
            
            self.setFormat(start_index, comment_length, self.comment_format)
            start_index = text.find('/*', start_index + comment_length)


class LineNumberArea(QWidget):
    """Widget for displaying line numbers"""
    
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
    
    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)
    
    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class GSCEditor(QPlainTextEdit):
    """Custom text editor with line numbers and syntax highlighting"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set font
        font = QFont("Consolas", 11)
        font.setFixedPitch(True)
        self.setFont(font)
        
        # Set tab width
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
        
        # Apply syntax highlighter
        self.highlighter = GSCSyntaxHighlighter(self.document())
        
        # Line numbers
        self.line_number_area = LineNumberArea(self)
        # name for stylesheet targeting
        self.line_number_area.setObjectName("lineNumberArea")
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.update_line_number_area_width(0)
        
        # Set style
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                selection-background-color: #264f78;
            }
        """)
        
        # Set initial content
        self.setPlainText(self.get_default_template())
        # storage for lint error ranges as (start_pos, length)
        self.lint_error_positions = []

    def is_modified(self):
        try:
            return self.document().isModified()
        except Exception:
            return False
    
    def get_default_template(self):
        return """// GSC IDE - Plutonium Script
// Game: Black Ops 2 (T6)
// Mode: Multiplayer/Zombies

#include maps\\mp\\_utility;
#include common_scripts\\utility;

init()
{
\tlevel thread onPlayerConnect();
}

onPlayerConnect()
{
\tfor(;;)
\t{
\t\tlevel waittill("connected", player);
\t\tplayer thread onPlayerSpawned();
\t}
}

onPlayerSpawned()
{
\tself endon("disconnect");
\t
\tfor(;;)
\t{
\t\tself waittill("spawned_player");
\t\tself iprintlnbold("^2Welcome! ^7Script loaded via GSC IDE");
\t}
}
"""
    
    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return space
    
    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    
    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
    
    def line_number_area_paint_event(self, event):
        from PyQt6.QtGui import QPainter
        from PyQt6.QtCore import QRect
        
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#252526"))
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#858585"))
                painter.drawText(0, int(top), self.line_number_area.width() - 5, 
                               self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight, number)
            
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def set_lint_error_positions(self, positions):
        """positions: list of (start_pos, length) tuples in document coordinates."""
        try:
            self.lint_error_positions = positions or []
            # repaint viewport to show squiggles
            self.viewport().update()
        except Exception:
            pass

    def paintEvent(self, event):
        # call base paint to render text and selections
        super().paintEvent(event)
        # if there are lint ranges, draw wavy underlines on the viewport
        if not getattr(self, 'lint_error_positions', None):
            return
        try:
            from PyQt6.QtGui import QPainter, QPen
            from PyQt6.QtCore import QPointF
            import math

            painter = QPainter(self.viewport())
            pen = QPen(QColor('#ff5c5c'))
            pen.setWidthF(1.4)
            painter.setPen(pen)

            for start_pos, length in list(self.lint_error_positions):
                if length <= 0:
                    continue
                end_pos = start_pos + length
                pos = start_pos
                # iterate across blocks in case the range spans lines
                while pos < end_pos:
                    block = self.document().findBlock(pos)
                    if not block.isValid():
                        break
                    block_start = block.position()
                    block_end = block_start + block.length() - 1
                    seg_end = min(end_pos, block_end)

                    # cursor at segment start and end to get coordinates
                    start_cursor = QTextCursor(self.document())
                    start_cursor.setPosition(pos)
                    end_cursor = QTextCursor(self.document())
                    end_cursor.setPosition(seg_end)

                    r1 = self.cursorRect(start_cursor)
                    r2 = self.cursorRect(end_cursor)

                    x1 = r1.x()
                    x2 = r2.x()
                    # sometimes end cursor at line end returns same x as start; clamp to viewport
                    if x2 <= x1:
                        x2 = x1 + max(6, self.fontMetrics().horizontalAdvance(' ')*1)

                    y = r1.bottom() - 2
                    amplitude = 3
                    wavelength = 6
                    points = []
                    x = x1
                    # draw points from x1 to x2
                    while x <= x2:
                        rel = x - x1
                        y_offset = math.sin((rel / wavelength) * 2 * math.pi) * amplitude
                        points.append(QPointF(x, y + y_offset))
                        x += 2

                    # ensure last point at x2
                    points.append(QPointF(x2, y))
                    # draw polyline
                    from PyQt6.QtGui import QPolygonF
                    painter.drawPolyline(QPolygonF(points))

                    pos = seg_end + 1
            painter.end()
        except Exception:
            pass


class GSCIDEWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.injection_manager = InjectionManager()
        self.settings = QSettings("GSC-IDE", "GSCIDE")
        
        self.init_ui()
        self.setup_timer()
        
    def init_ui(self):
        self.setWindowTitle("GSC IDE - Call of Duty Script Editor (Plutonium)")
        self.setGeometry(100, 100, 1400, 900)
        
        # Set dark theme colors
        # Base stylesheet (dark by default) - improved visuals
        self.base_css = """
        QMainWindow { background-color: #151718; }
        QLabel { color: #e6eef3; }
        QComboBox, QLineEdit { background-color: #232526; color: #e6eef3; border: 1px solid #3a3d3f; padding: 6px; border-radius: 6px; }
        QPushButton { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0b78c0, stop:1 #0961a8); color: white; border:none; padding:8px 12px; border-radius:6px; }
        QPushButton:hover { background-color: #0f8ee0; }
        QPlainTextEdit, QTextEdit { background-color: #0f1314; color: #dbe9ee; border: 1px solid #2f3334; }
        QGroupBox { color: #e6eef3; border: 1px solid #2f3334; border-radius: 8px; margin-top: 12px; padding-top: 12px; }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 8px; }
        QMenuBar { background: #171919; color: #e6eef3; }
        QMenuBar::item:selected { background: #1f8bbf; }
        QMenu { background: #171919; color: #e6eef3; border: 1px solid #2f3334; }
        QMenu::item:selected { background: #0f6aa0; }
        QStatusBar { background: #0f6aa0; color: white; }
        /* Editor gutter */
        QWidget#lineNumberArea { background: #0d1111; }
        """

        self.setStyleSheet(self.base_css)
        
        # Menu bar will be created after editor is initialized
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Editor
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Editor header
        editor_header = QLabel("Code Editor")
        editor_header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        left_layout.addWidget(editor_header)

        # Find/Replace bar (hidden by default)
        self.find_widget = QWidget()
        self.find_widget.setStyleSheet("background-color: #1b2426; border: 1px solid #2f4448; padding:6px; border-radius:6px;")
        find_layout = QHBoxLayout(self.find_widget)
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find...")
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace...")
        find_next_btn = QPushButton("Find")
        replace_btn = QPushButton("Replace")
        close_find_btn = QPushButton("Close")
        find_layout.addWidget(self.find_input)
        find_layout.addWidget(self.replace_input)
        find_layout.addWidget(find_next_btn)
        find_layout.addWidget(replace_btn)
        find_layout.addWidget(close_find_btn)
        self.find_widget.setVisible(False)
        left_layout.addWidget(self.find_widget)

        # Vertical splitter for editor and error console
        vertical_splitter = QSplitter(Qt.Orientation.Vertical)

        # Text editor
        # Tabbed editors
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(lambda idx: self.close_tab(idx))

        # create initial editor tab
        self.editor = GSCEditor()
        self.tab_paths = {}  # map editor widget -> filename
        self.tab_widget.addTab(self.editor, "Untitled")
        self.tab_paths[self.editor] = None
        vertical_splitter.addWidget(self.tab_widget)

        # attach signals for the initial editor
        self.attach_editor_signals(self.editor)

        # autosave setup
        try:
            self.autosave_dir = os.path.join(tempfile.gettempdir(), 'gscide_autosave')
            os.makedirs(self.autosave_dir, exist_ok=True)
            self.autosave_index = os.path.join(self.autosave_dir, 'index.json')
            # check for recovery files
            self.check_autosave_recovery()
            self.autosave_timer = QTimer(self)
            self.autosave_timer.setInterval(10000)  # 10s
            self.autosave_timer.timeout.connect(self.autosave_all)
            self.autosave_timer.start()
            # per-editor autosave timers map
            self._autosave_timers = {}
            self.autosave_map = {}  # editor -> autosave filename
        except Exception:
            self.autosave_dir = None

        # Apply saved editor font size if present
        try:
            saved_fs = self.settings.value('editor_font_size', None)
            if saved_fs:
                font = self.editor.font()
                font.setPointSize(int(saved_fs))
                self.editor.setFont(font)
                self.editor.update_line_number_area_width(0)
        except Exception:
            pass

        # Error/Debug console under the editor (clickable links)
        self.error_console = QTextBrowser()
        self.error_console.setReadOnly(True)
        self.error_console.setMaximumHeight(200)
        self.error_console.setOpenExternalLinks(False)
        self.error_console.setStyleSheet("background-color: #120f0f; color: #ff9b9b; border-top:1px solid #2b2b2b; padding:6px;")
        self.error_console.anchorClicked.connect(self.goto_error)
        vertical_splitter.addWidget(self.error_console)

        left_layout.addWidget(vertical_splitter)

        # Editor info bar
        self.editor_info = QLabel("Line: 1 | Column: 1")
        self.editor_info.setStyleSheet("padding: 5px; background-color: #2b2b2b;")
        left_layout.addWidget(self.editor_info)
        # cursor updates will be connected per-tab
        try:
            self.tab_widget.currentChanged.connect(lambda idx: self.update_cursor_info())
        except Exception:
            pass
        # Live linting timer (debounced)
        try:
            self.live_lint_timer = QTimer(self)
            self.live_lint_timer.setSingleShot(True)
            self.live_lint_timer.setInterval(500)  # 500ms debounce
            self.live_lint_timer.timeout.connect(self.lint_script)
        except Exception:
            pass

        # Find/Replace button wiring
        find_next_btn.clicked.connect(lambda: self.find_next())
        replace_btn.clicked.connect(lambda: self.replace_one())
        close_find_btn.clicked.connect(lambda: self.find_widget.setVisible(False))

        # Install event filter to catch Escape key to close find widget
        try:
            self.tab_widget.installEventFilter(self)
        except Exception:
            pass
        
        splitter.addWidget(left_panel)
        
        # Right panel - Controls
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Injection settings
        self.injection_group = QGroupBox("Plutonium Injection")
        injection_layout = QVBoxLayout()
        
        # Info label
        info_label = QLabel("Optimized for Plutonium launcher\nScripts load automatically on game start")
        info_label.setStyleSheet("color: #4CAF50; padding: 10px;")
        info_label.setWordWrap(True)
        injection_layout.addWidget(info_label)
        
        # Game selection
        injection_layout.addWidget(QLabel("Target Game:"))
        self.game_combo = QComboBox()
        self.game_combo.addItems([
            "Plutonium T6 (Black Ops 2)",
            "Plutonium T5 (Black Ops 1)", 
            "Plutonium T4 (World at War)",
            "Plutonium IW5 (MW3)"
        ])
        injection_layout.addWidget(self.game_combo)
        
        # Method selection
        injection_layout.addWidget(QLabel("Method:"))
        self.method_combo = QComboBox()
        self.method_combo.addItems([
            "Plutonium Scripts Folder",
            "Direct Memory (Not Recommended)",
            "Network (Console)"
        ])
        injection_layout.addWidget(self.method_combo)
        
        # Mode selection
        injection_layout.addWidget(QLabel("Game Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Multiplayer", "Zombies", "Both"])
        injection_layout.addWidget(self.mode_combo)
        
        # Script name
        injection_layout.addWidget(QLabel("Script Name:"))
        self.script_name = QLineEdit("my_mod")
        injection_layout.addWidget(self.script_name)
        
        self.script_name_label = QLabel("Will be saved as: my_mod.gsc")
        self.script_name_label.setStyleSheet("color: #888; font-size: 10px;")
        injection_layout.addWidget(self.script_name_label)
        self.script_name.textChanged.connect(
            lambda: self.script_name_label.setText(f"Will be saved as: {self.script_name.text()}.gsc")
        )
        
        # Plutonium path info
        self.plut_path_label = QLabel()
        self.update_plutonium_path()
        injection_layout.addWidget(self.plut_path_label)
        
        # Game status
        self.game_status_label = QLabel()
        self.update_game_status()
        injection_layout.addWidget(self.game_status_label)
        
        # Deploy button
        deploy_btn = QPushButton("Deploy Script to Plutonium (F5)")
        deploy_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 15px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        deploy_btn.clicked.connect(self.deploy_script)
        injection_layout.addWidget(deploy_btn)
        
        # Open folder button
        open_folder_btn = QPushButton("Open Scripts Folder")
        open_folder_btn.clicked.connect(self.open_scripts_folder)
        injection_layout.addWidget(open_folder_btn)
        
        injection_layout.addStretch()
        self.injection_group.setLayout(injection_layout)
        right_layout.addWidget(self.injection_group)
        
        # Output console
        self.output_group = QGroupBox("Output")
        output_layout = QVBoxLayout()
        self.output_console = QTextEdit()
        self.output_console.setReadOnly(True)
        self.output_console.setMaximumHeight(200)
        self.log("GSC IDE initialized. Ready to deploy scripts.")
        output_layout.addWidget(self.output_console)
        self.output_group.setLayout(output_layout)
        right_layout.addWidget(self.output_group)
        
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([900, 500])
        
        main_layout.addWidget(splitter)
        
        # Create menu bar now that editor exists
        self.create_menu_bar()

        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        # persistent small status label on the right
        self.status_label = QLabel("Ready")
        try:
            self.statusBar.addPermanentWidget(self.status_label)
        except Exception:
            pass
        self.statusBar.showMessage("Ready")

        # Apply saved theme (dark/light)
        self.current_theme = self.settings.value('theme', 'dark')
        self.apply_theme(self.current_theme)

        # Caps Lock indicator (always show ON/OFF and adapt to theme)
        try:
            self.caps_label = QLabel("")
            # color will be adjusted in update_caps_lock based on theme
            self.caps_label.setStyleSheet("padding:2px 6px; border-radius:4px; background: transparent; color: #fff; font-weight: bold;")
            self.statusBar.addPermanentWidget(self.caps_label)
            self.caps_timer = QTimer()
            self.caps_timer.timeout.connect(self.update_caps_lock)
            self.caps_timer.start(300)
            # set initial state
            self.update_caps_lock()
        except Exception:
            self.caps_label = None
        
    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_action = QAction("New", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.new_file)
        file_menu.addAction(new_action)
        
        open_action = QAction("Open", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Save As...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(save_as_action)
        
        # Recent files submenu (populated from QSettings)
        self.recent_menu = file_menu.addMenu("Open Recent")
        # populate after menu creation
        # items are managed via self.update_recent_menu()
        self.update_recent_menu()
        
        # Quick clear recent shortcut
        clear_recent_shortcut = QAction("Clear Recent", self)
        clear_recent_shortcut.setShortcut(QKeySequence("Ctrl+Shift+R"))
        clear_recent_shortcut.triggered.connect(self.clear_recent_files)
        file_menu.addAction(clear_recent_shortcut)
        self.addAction(clear_recent_shortcut)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        
        undo_action = QAction("Undo", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self.editor.undo)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("Redo", self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.triggered.connect(self.editor.redo)
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        copy_action = QAction("Copy", self)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.triggered.connect(self.editor.copy)
        edit_menu.addAction(copy_action)
        
        cut_action = QAction("Cut", self)
        cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        cut_action.triggered.connect(self.editor.cut)
        edit_menu.addAction(cut_action)
        
        paste_action = QAction("Paste", self)
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        paste_action.triggered.connect(self.editor.paste)
        edit_menu.addAction(paste_action)
        
        # GSC menu
        gsc_menu = menubar.addMenu("GSC")
        
        inject_action = QAction("Deploy Script", self)
        inject_action.setShortcut(QKeySequence("F5"))
        inject_action.triggered.connect(self.deploy_script)
        gsc_menu.addAction(inject_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        # Preferences
        prefs_action = QAction("Preferences...", self)
        prefs_action.setShortcut(QKeySequence("Ctrl+,"))
        prefs_action.triggered.connect(self.open_preferences)
        file_menu.addAction(prefs_action)
        self.addAction(prefs_action)
        
        # Find/Replace actions and shortcuts
        find_action = QAction("Find", self)
        find_action.setShortcut(QKeySequence.StandardKey.Find)
        find_action.triggered.connect(lambda: self.show_find(True))
        edit_menu.addAction(find_action)

        # ensure action is available globally
        self.addAction(find_action)

        replace_action = QAction("Replace", self)
        replace_action.setShortcut(QKeySequence("Ctrl+H"))
        replace_action.triggered.connect(lambda: self.show_find(False))
        edit_menu.addAction(replace_action)
        self.addAction(replace_action)

        # View menu (toggle panels)
        view_menu = menubar.addMenu("View")
        # Injection panel visibility (persisted)
        injection_vis = self.settings.value('panel_injection', True)
        if isinstance(injection_vis, str):
            injection_vis = injection_vis.lower() in ('1', 'true', 'yes', 'on')
        toggle_injection = QAction("Toggle Injection Panel", self, checkable=True)
        toggle_injection.setChecked(bool(injection_vis))
        toggle_injection.setShortcut(QKeySequence("Ctrl+Shift+I"))
        def _set_injection(checked):
            self.injection_group.setVisible(checked)
            try:
                self.settings.setValue('panel_injection', checked)
            except Exception:
                pass
        toggle_injection.triggered.connect(_set_injection)
        view_menu.addAction(toggle_injection)

        output_vis = self.settings.value('panel_output', True)
        if isinstance(output_vis, str):
            output_vis = output_vis.lower() in ('1', 'true', 'yes', 'on')
        toggle_output = QAction("Toggle Output Panel", self, checkable=True)
        toggle_output.setChecked(bool(output_vis))
        toggle_output.setShortcut(QKeySequence("Ctrl+Shift+O"))
        def _set_output(checked):
            self.output_group.setVisible(checked)
            try:
                self.settings.setValue('panel_output', checked)
            except Exception:
                pass
        toggle_output.triggered.connect(_set_output)
        view_menu.addAction(toggle_output)

        # Theme toggle
        theme_action = QAction("Toggle Theme", self)
        theme_action.setShortcut(QKeySequence("Ctrl+T"))
        theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(theme_action)

        # Register shortcuts globally so they work regardless of focus
        self.addAction(toggle_injection)
        self.addAction(toggle_output)
        self.addAction(theme_action)

        # Toolbar for quick actions
        toolbar = self.addToolBar("Main")
        new_act = QAction("New", self)
        new_act.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        new_act.setToolTip("New file (Ctrl+N)")
        new_act.triggered.connect(self.new_file)
        toolbar.addAction(new_act)

        open_act = QAction("Open", self)
        open_act.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        open_act.setToolTip("Open file (Ctrl+O)")
        open_act.triggered.connect(self.open_file)
        toolbar.addAction(open_act)

        save_act = QAction("Save", self)
        save_act.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        save_act.setToolTip("Save file (Ctrl+S)")
        save_act.triggered.connect(self.save_file)
        toolbar.addAction(save_act)

        toolbar.addSeparator()

        # Reuse the Find/Replace actions already created for the Edit menu
        try:
            find_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView))
            find_action.setToolTip("Find (Ctrl+F)")
            toolbar.addAction(find_action)
        except Exception:
            pass

        try:
            replace_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
            replace_action.setToolTip("Replace (Ctrl+H)")
            toolbar.addAction(replace_action)
        except Exception:
            pass

        toolbar.addSeparator()

        deploy_act = QAction("Deploy", self)
        deploy_act.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        deploy_act.setToolTip("Deploy script to Plutonium (F5)")
        deploy_act.setShortcut(QKeySequence("F5"))
        deploy_act.triggered.connect(self.deploy_script)
        toolbar.addAction(deploy_act)

        # Font size controls
        toolbar.addSeparator()
        inc_font = QAction("A+", self)
        inc_font.setToolTip("Increase editor font size")
        inc_font.triggered.connect(lambda: self.set_editor_font_size(1))
        toolbar.addAction(inc_font)

        dec_font = QAction("A-", self)
        dec_font.setToolTip("Decrease editor font size")
        dec_font.triggered.connect(lambda: self.set_editor_font_size(-1))
        toolbar.addAction(dec_font)
        # Tab actions
        close_tab_act = QAction("Close Tab", self)
        close_tab_act.setShortcut(QKeySequence("Ctrl+W"))
        close_tab_act.triggered.connect(lambda: self.close_tab(self.tab_widget.currentIndex()))
        self.addAction(close_tab_act)
        toolbar.addAction(close_tab_act)
    
    def setup_timer(self):
        # Update game status every 2 seconds
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_game_status)
        # Also refresh Plutonium install detection periodically
        self.timer.timeout.connect(self.update_plutonium_path)
        self.timer.start(2000)

    def update_cursor_info(self):
        try:
            editor = self.current_editor()
            if editor is None:
                return
            cursor = editor.textCursor()
            line = cursor.blockNumber() + 1
            column = cursor.columnNumber() + 1
            self.editor_info.setText(f"Line: {line} | Column: {column}")
            # Update small status label with current file and position
            try:
                file_display = os.path.basename(self.tab_paths.get(editor)) if self.tab_paths.get(editor) else "Untitled"
                if hasattr(self, 'status_label'):
                    self.status_label.setText(f"{file_display} — Ln {line}, Col {column}")
            except Exception:
                pass
        except Exception:
            pass

    def schedule_live_lint(self):
        """Start or restart the debounced live-lint timer if enabled in settings."""
        try:
            lint_live = self.settings.value('lint_live', True)
            if isinstance(lint_live, str):
                lint_live = lint_live.lower() in ('1', 'true', 'yes', 'on')
            if not lint_live:
                return
            # restart timer
            try:
                self.live_lint_timer.start()
            except Exception:
                # fallback: call lint directly
                self.lint_script()
        except Exception:
            pass

    def attach_editor_signals(self, editor: GSCEditor):
        try:
            editor.cursorPositionChanged.connect(self.update_cursor_info)
        except Exception:
            pass
        try:
            editor.textChanged.connect(self.schedule_live_lint)
        except Exception:
            pass
        # per-editor autosave timer: debounce rapid edits
        try:
            if getattr(self, 'autosave_dir', None):
                t = QTimer(self)
                t.setSingleShot(True)
                t.setInterval(3000)
                # capture editor in lambda default
                t.timeout.connect(lambda ed=editor: self.autosave_editor(ed))
                self._autosave_timers[editor] = t
                # when text changes, start/reset timer
                def _on_edit():
                    try:
                        timer = self._autosave_timers.get(editor)
                        if timer:
                            timer.start()
                    except Exception:
                        pass
                editor.textChanged.connect(_on_edit)
        except Exception:
            pass

    def current_editor(self) -> GSCEditor:
        try:
            w = self.tab_widget.currentWidget()
            if isinstance(w, GSCEditor):
                return w
        except Exception:
            pass
        return getattr(self, 'editor', None)

    # --- Linting ---
    def lint_script(self):
        """Simple GSC linter: unmatched brackets/parentheses and unterminated strings.
        Produces precise character positions and underlines problematic ranges in the editor.
        """
        editor = self.current_editor()
        if editor is None:
            return True
        text = editor.toPlainText()
        lines = text.splitlines()
        stack = []  # tuples (char, line, col)
        errors = []  # list of dicts: {line, col, len, msg}
        pos_list = []

        in_string = False
        string_char = None
        string_start_line = None
        string_start_col = None

        pairs = {'}': '{', ')': '(', ']': '['}

        for i, line in enumerate(lines, start=1):
            j = 0
            while j < len(line):
                ch = line[j]
                # naive escape handling: if previous char is backslash, skip special handling
                prev = line[j-1] if j > 0 else ''
                if ch in ('"', "'") and prev != '\\':
                    if not in_string:
                        in_string = True
                        string_char = ch
                        string_start_line = i
                        string_start_col = j
                    elif ch == string_char:
                        in_string = False
                        string_char = None
                        string_start_line = None
                        string_start_col = None
                elif not in_string:
                    if ch in ('{', '(', '['):
                        stack.append((ch, i, j))
                    elif ch in ('}', ')', ']'):
                        if stack and stack[-1][0] == pairs[ch]:
                            stack.pop()
                        else:
                            errors.append({'line': i, 'col': j, 'len': 1, 'msg': f"Unmatched closing '{ch}'"})
                j += 1

        if in_string and string_start_line is not None:
            errors.append({'line': string_start_line, 'col': string_start_col, 'len': 1, 'msg': 'Unterminated string literal'})

        # any remaining openings are errors
        for opener, line_no, col in stack:
            errors.append({'line': line_no, 'col': col, 'len': 1, 'msg': f"Unmatched opening '{opener}'"})

        # display results and mark in editor
        if not errors:
            self.error_console.setHtml('<span style="color:#9bd39b;">No lint issues found.</span>')
            try:
                editor.setExtraSelections([])
                try:
                    editor.set_lint_error_positions([])
                except Exception:
                    pass
            except Exception:
                pass
            return True

        # build clickable HTML and underline selections
        html = []
        for e in errors:
            ln = e.get('line', 0)
            col = e.get('col', 0)
            msg = e.get('msg', '')
            html.append(f'<a href="pos:{ln}:{col}"><span style="color:#ff9b9b;">[Ln {ln}:Col {col}] {msg}</span></a>')

        self.error_console.setHtml('<br>'.join(html))
        # create extra selections to underline errors
        sels = []
        from PyQt6.QtGui import QTextCharFormat
        for e in errors:
            ln = e.get('line', 0)
            col = e.get('col', 0)
            length = max(1, e.get('len', 1))
            block = editor.document().findBlockByNumber(ln - 1)
            if not block.isValid():
                continue
            start_pos = block.position() + col
            # collect positions for editor-level squiggle drawing
            try:
                pos_list.append((start_pos, length))
            except Exception:
                pass
            try:
                cursor = QTextCursor(editor.document())
                cursor.setPosition(start_pos)
                cursor.setPosition(start_pos + length, QTextCursor.MoveMode.KeepAnchor)
                sel = QPlainTextEdit.ExtraSelection()
                fmt = QTextCharFormat()
                try:
                    # Prefer a wave (squiggly) underline when available for error styling
                    try:
                        fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
                    except Exception:
                        # older/some builds may expose SpellCheckUnderline or not support Wave
                        try:
                            fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
                        except Exception:
                            fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
                    fmt.setUnderlineColor(QColor('#ff5c5c'))
                except Exception:
                    # fallback: set background if underline unsupported
                    fmt.setBackground(QColor('#3a2b2b'))
                sel.format = fmt
                sel.cursor = cursor
                sels.append(sel)
            except Exception:
                continue

            try:
                try:
                    # pass positions to editor for custom squiggle drawing
                    editor.set_lint_error_positions(pos_list)
                except Exception:
                    pass
                editor.setExtraSelections(sels)
            except Exception:
                pass

        return False

    def goto_error(self, url):
        s = url.toString()
        if s.startswith('line:'):
            try:
                ln = int(s.split(':',1)[1])
            except Exception:
                return
            # move cursor to start of line
            editor = self.current_editor()
            if editor is None:
                return
            block = editor.document().findBlockByNumber(ln-1)
            if block.isValid():
                cursor = editor.textCursor()
                cursor.setPosition(block.position())
                editor.setTextCursor(cursor)
                editor.setFocus()
                # highlight the line briefly
                try:
                    from PyQt6.QtGui import QTextCharFormat
                    sel = QPlainTextEdit.ExtraSelection()
                    fmt = QTextCharFormat()
                    fmt.setBackground(QColor('#3a2b2b'))
                    sel.format = fmt
                    sel.cursor = editor.textCursor()
                    editor.setExtraSelections([sel])
                    QTimer.singleShot(1200, lambda: editor.setExtraSelections([]))
                except Exception:
                    pass

    def replace_one(self):
        needle = self.find_input.text()
        repl = self.replace_input.text()
        if not needle:
            return
        editor = self.current_editor()
        if editor is None:
            return
        cursor = editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == needle:
            cursor.insertText(repl)
            editor.setTextCursor(cursor)
        else:
            if editor.find(needle):
                cursor = editor.textCursor()
                cursor.insertText(repl)
                editor.centerCursor()

    
    def update_game_status(self):
        game = TargetGame(self.game_combo.currentIndex())
        running = self.injection_manager.is_game_running(game)
        
        if running:
            self.game_status_label.setText("● Game Running")
            self.game_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.game_status_label.setText("○ Game Not Running")
            self.game_status_label.setStyleSheet("color: #888;")

    def update_plutonium_path(self):
        try:
            plut_path = self.injection_manager.get_plutonium_path()
            if plut_path:
                self.plut_path_label.setText(f"✓ Plutonium detected\n{plut_path}")
                self.plut_path_label.setStyleSheet("color: #4CAF50; padding: 5px;")
            else:
                self.plut_path_label.setText("✗ Plutonium not detected\nExpected: %localappdata%\\Plutonium\\storage")
                self.plut_path_label.setStyleSheet("color: #f44336; padding: 5px;")
        except Exception:
            try:
                self.plut_path_label.setText("✗ Plutonium detection error")
                self.plut_path_label.setStyleSheet("color: #f44336; padding: 5px;")
            except Exception:
                pass

    def is_capslock_on(self):
        try:
            # Windows: GetKeyState(VK_CAPITAL) low-order bit indicates toggle state
            state = ctypes.windll.user32.GetKeyState(0x14)
            return (state & 0x0001) == 1
        except Exception:
            # non-windows or failure
            return False

    def update_caps_lock(self):
        try:
            on = self.is_capslock_on()
            if not self.caps_label:
                return
            # ensure the label is visible in both themes; adapt colors
            theme = getattr(self, 'current_theme', 'dark')
            if on:
                self.caps_label.setText("CAPS ON")
                self.caps_label.setStyleSheet("padding:2px 6px; border-radius:4px; background:#b22222; color:#fff; font-weight:bold;")
            else:
                self.caps_label.setText("CAPS OFF")
                if theme == 'dark':
                    self.caps_label.setStyleSheet("padding:2px 6px; border-radius:4px; background: transparent; color:#fff; font-weight:bold;")
                else:
                    self.caps_label.setStyleSheet("padding:2px 6px; border-radius:4px; background: transparent; color:#000; font-weight:bold;")
        except Exception:
            pass
    
    def new_file(self):
        # create a new tab with default template
        self.new_tab()
    
    def open_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open GSC Script", "", "GSC Files (*.gsc);;All Files (*)"
        )
        if filename:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            self.new_tab(filename=filename, content=content)
            self.log(f"Opened: {filename}")
            self.add_recent_file(filename)
    
    def save_file(self):
        editor = self.current_editor()
        if editor is None:
            return
        cur_path = self.tab_paths.get(editor)
        if cur_path:
            try:
                with open(cur_path, 'w', encoding='utf-8') as f:
                    f.write(editor.toPlainText())
                editor.document().setModified(False)
                self.log(f"Saved: {cur_path}")
                self.add_recent_file(cur_path)
                # update tab label
                idx = self.tab_widget.indexOf(editor)
                if idx >= 0:
                    self.tab_widget.setTabText(idx, os.path.basename(cur_path))
                try:
                    self.remove_autosave_for(editor)
                except Exception:
                    pass
            except Exception as ex:
                QMessageBox.warning(self, "Error", f"Failed to save: {ex}")
        else:
            self.save_file_as()
    
    def save_file_as(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save GSC Script", "", "GSC Files (*.gsc);;All Files (*)"
        )
        if filename:
            editor = self.current_editor()
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(editor.toPlainText())
                self.tab_paths[editor] = filename
                editor.document().setModified(False)
                idx = self.tab_widget.indexOf(editor)
                if idx >= 0:
                    self.tab_widget.setTabText(idx, os.path.basename(filename))
                self.log(f"Saved: {filename}")
                self.add_recent_file(filename)
                # run linter after save
                try:
                    self.lint_script()
                except Exception:
                    pass
            except Exception as ex:
                QMessageBox.warning(self, "Error", f"Failed to save: {ex}")
            try:
                self.remove_autosave_for(editor)
            except Exception:
                pass

    # --- Recent files management ---
    def update_recent_menu(self):
        try:
            self.recent_menu.clear()
        except Exception:
            return

        recent = self.settings.value('recentFiles', []) or []
        if isinstance(recent, str):
            recent = [recent]

        # show newest first
        for path in reversed(recent):
            if not path:
                continue
            action = QAction(path, self)
            try:
                action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
            except Exception:
                pass
            action.setToolTip(path)
            action.triggered.connect(lambda checked, p=path: self.open_recent_file(p))
            self.recent_menu.addAction(action)

        if recent:
            self.recent_menu.addSeparator()
            clear_act = QAction("Clear Recent", self)
            clear_act.triggered.connect(self.clear_recent_files)
            self.recent_menu.addAction(clear_act)
            # make clear recent reachable by shortcut
            try:
                clear_act.setShortcut(QKeySequence("Ctrl+Shift+R"))
                self.addAction(clear_act)
            except Exception:
                pass

    # --- Preferences dialog ---
    def open_preferences(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Preferences")
        layout = QVBoxLayout(dlg)
        form = QFormLayout()

        font_spin = QSpinBox()
        font_spin.setRange(6, 48)
        font_spin.setValue(self.editor.font().pointSize())
        form.addRow("Editor font size:", font_spin)

        theme_combo = QComboBoxWidget()
        theme_combo.addItems(["dark", "light"])
        theme_combo.setCurrentText(getattr(self, 'current_theme', 'dark'))
        form.addRow("Theme:", theme_combo)

        # Live linting toggle
        lint_chk = QCheckBox("Lint as you type")
        try:
            lint_val = self.settings.value('lint_live', True)
            if isinstance(lint_val, str):
                lint_val = lint_val.lower() in ('1', 'true', 'yes', 'on')
            lint_chk.setChecked(bool(lint_val))
        except Exception:
            lint_chk.setChecked(True)
        form.addRow("Live linting:", lint_chk)

        # Per-game overrides
        t6_edit = QLineEdit(self.settings.value('custom_t6_path', ''))
        t5_edit = QLineEdit(self.settings.value('custom_t5_path', ''))
        t4_edit = QLineEdit(self.settings.value('custom_t4_path', ''))
        iw5_edit = QLineEdit(self.settings.value('custom_iw5_path', ''))
        form.addRow('BO2 (t6) scripts base:', t6_edit)
        form.addRow('BO1 (t5) raw/scripts base:', t5_edit)
        form.addRow('T4 (t4) scripts base:', t4_edit)
        form.addRow('IW5 (iw5) scripts base:', iw5_edit)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        def on_save():
            try:
                self.settings.setValue('editor_font_size', font_spin.value())
                self.set_editor_font_size(font_spin.value() - self.editor.font().pointSize())
            except Exception:
                pass
            try:
                self.settings.setValue('theme', theme_combo.currentText())
                self.apply_theme(theme_combo.currentText())
            except Exception:
                pass
            # persist live lint preference
            try:
                self.settings.setValue('lint_live', lint_chk.isChecked())
            except Exception:
                pass

            # save overrides
            try:
                self.settings.setValue('custom_t6_path', t6_edit.text())
                self.settings.setValue('custom_t5_path', t5_edit.text())
                self.settings.setValue('custom_t4_path', t4_edit.text())
                self.settings.setValue('custom_iw5_path', iw5_edit.text())

                # push overrides to injection manager
                overrides = {
                    TargetGame.PLUTONIUM_T6: t6_edit.text(),
                    TargetGame.PLUTONIUM_T5: t5_edit.text(),
                    TargetGame.PLUTONIUM_T4: t4_edit.text(),
                    TargetGame.PLUTONIUM_IW5: iw5_edit.text(),
                }
                try:
                    self.injection_manager.set_custom_paths(overrides)
                except Exception:
                    pass
                # refresh displayed path immediately after applying overrides
                try:
                    self.update_plutonium_path()
                except Exception:
                    pass
            except Exception:
                pass

            # if live lint enabled, run an immediate lint to refresh markers
            try:
                if lint_chk.isChecked():
                    QTimer.singleShot(50, lambda: self.lint_script())
            except Exception:
                pass

            dlg.accept()

        cancel_btn.clicked.connect(dlg.reject)
        save_btn.clicked.connect(on_save)

        dlg.exec()

    def add_recent_file(self, filename):
        if not filename:
            return
        recent = self.settings.value('recentFiles', []) or []
        if isinstance(recent, str):
            recent = [recent]

        # normalize and keep uniqueness
        try:
            recent = [r for r in recent if r != filename]
        except Exception:
            recent = []
        recent.append(filename)
        # keep max 10
        recent = recent[-10:]
        self.settings.setValue('recentFiles', recent)
        self.update_recent_menu()

    def open_recent_file(self, filename):
        if not filename or not os.path.exists(filename):
            QMessageBox.warning(self, "Error", f"File not found: {filename}")
            return
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        self.new_tab(filename=filename, content=content)
        self.log(f"Opened: {filename}")
        self.add_recent_file(filename)

    def clear_recent_files(self):
        self.settings.setValue('recentFiles', [])
        self.update_recent_menu()
    
    def deploy_script(self):
        game = TargetGame(self.game_combo.currentIndex())
        method = InjectionMethod(self.method_combo.currentIndex())
        mode = GameMode(self.mode_combo.currentIndex())
        script_name = self.script_name.text()
        editor = self.current_editor()
        script_content = editor.toPlainText() if editor else ''
        
        success, message = self.injection_manager.inject_script(
            script_content, game, method, mode, script_name
        )
        
        if success:
            self.log(f"✓ {message}", success=True)
            try:
                self.lint_script()
            except Exception:
                pass
            QMessageBox.information(
                self, "Success", 
                f"{message}\n\nRestart Plutonium to load the script."
            )
        else:
            self.log(f"✗ {message}", success=False)
            QMessageBox.warning(self, "Deployment Failed", message)
    
    def open_scripts_folder(self):
        game = TargetGame(self.game_combo.currentIndex())
        mode = GameMode(self.mode_combo.currentIndex())
        path = self.injection_manager.get_script_path(game, mode)
        
        if path and os.path.exists(path):
            os.startfile(path)
        else:
            QMessageBox.warning(self, "Error", "Scripts folder not found")

    # --- Tab management ---
    def new_tab(self, filename: str = None, content: str = None):
        editor = GSCEditor()
        if content is None:
            content = editor.get_default_template()
        editor.setPlainText(content)
        self.tab_paths[editor] = filename
        title = os.path.basename(filename) if filename else "Untitled"
        idx = self.tab_widget.addTab(editor, title)
        self.tab_widget.setCurrentIndex(idx)
        self.attach_editor_signals(editor)
        return editor

    def close_tab(self, index: int):
        try:
            widget = self.tab_widget.widget(index)
            if isinstance(widget, GSCEditor):
                # prompt to save if modified
                try:
                    if widget.document().isModified():
                        resp = QMessageBox.question(self, "Unsaved Changes", "Save changes before closing this tab?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
                        if resp == QMessageBox.StandardButton.Cancel:
                            return
                        if resp == QMessageBox.StandardButton.Yes:
                            # make current and save
                            self.tab_widget.setCurrentIndex(index)
                            self.save_file()
                except Exception:
                    pass
            self.tab_widget.removeTab(index)
        except Exception:
            pass
    
    def show_about(self):
        QMessageBox.about(
            self, "About GSC IDE",
            "GSC IDE v1.0\n\n"
            "Call of Duty Script Editor for Plutonium\n\n"
            "Developed for game modding and speedrunning\n"
            "Supports T6, T5, T4, IW5"
        )
    
    def log(self, message, success=None):
        if success is True:
            color = "#4CAF50"
        elif success is False:
            color = "#f44336"
        else:
            color = "#ffffff"
        
        self.output_console.append(f'<span style="color: {color};">{message}</span>')
        # Show message in the status bar. `statusBar` may be the QMainWindow method
        # (callable) before we assign an attribute with the same name, so handle
        # both cases safely.
        sb_attr = getattr(self, 'statusBar', None)
        sb = None
        if callable(sb_attr):
            try:
                sb = sb_attr()
            except Exception:
                sb = None
        else:
            sb = sb_attr

        if sb:
            try:
                sb.showMessage(message)
            except Exception:
                pass

    # Theme handling
    def apply_theme(self, theme_name: str):
        theme_name = theme_name or 'dark'
        self.current_theme = theme_name
        # simple theme flip: reapply stylesheet with light/dark variants
        if theme_name == 'light':
            light_css = """
            QMainWindow { background-color: #f3f6f8; }
            QLabel { color: #1b1f23; }
            QComboBox, QLineEdit { background-color: #ffffff; color: #1b1f23; border: 1px solid #cfd8dc; }
            QPlainTextEdit, QTextEdit { background-color: #ffffff; color: #1b1f23; border: 1px solid #d0d7db; }
            QGroupBox { color: #1b1f23; border: 1px solid #d0d7db; }
            QStatusBar { background-color: #e0e7ea; color: #1b1f23; }
            """
            self.setStyleSheet(light_css)
        else:
            # dark (default) - restore stored base stylesheet
            try:
                self.setStyleSheet(self.base_css)
            except Exception:
                pass

        # persist
        try:
            self.settings.setValue('theme', theme_name)
        except Exception:
            pass

    def toggle_theme(self):
        new_theme = 'light' if getattr(self, 'current_theme', 'dark') == 'dark' else 'dark'
        self.apply_theme(new_theme)

    def set_editor_font_size(self, delta: int):
        try:
            font = self.editor.font()
            size = font.pointSize()
            if size < 6:
                size = 11
            new_size = max(6, size + delta)
            font.setPointSize(new_size)
            self.editor.setFont(font)
            # update line number metrics
            self.editor.update_line_number_area_width(0)
            try:
                self.settings.setValue('editor_font_size', new_size)
            except Exception:
                pass
        except Exception:
            pass

    def closeEvent(self, event):
        # Persist panel visibility and theme on close
        try:
            self.settings.setValue('panel_injection', self.injection_group.isVisible())
            self.settings.setValue('panel_output', self.output_group.isVisible())
            self.settings.setValue('theme', getattr(self, 'current_theme', 'dark'))
        except Exception:
            pass
        # If there are modified (unsaved) tabs, preserve autosave artifacts
        try:
            preserve_autosave = False
            if getattr(self, 'autosave_dir', None) and os.path.exists(self.autosave_dir):
                for i in range(getattr(self, 'tab_widget').count() if getattr(self, 'tab_widget', None) else 0):
                    w = self.tab_widget.widget(i)
                    try:
                        if not isinstance(w, GSCEditor):
                            continue
                        # Prefer the documented modified flag
                        try:
                            if w.document().isModified():
                                preserve_autosave = True
                                break
                        except Exception:
                            pass
                        # If no path assigned, but content differs from default template, consider unsaved
                        try:
                            assigned = self.tab_paths.get(w)
                            content = w.toPlainText()
                            if assigned is None and content.strip() and content.strip() != w.get_default_template().strip():
                                preserve_autosave = True
                                break
                            # if assigned, compare with on-disk file to detect unsaved changes
                            if assigned and os.path.exists(assigned):
                                try:
                                    with open(assigned, 'r', encoding='utf-8') as f:
                                        disk = f.read()
                                    if disk != content:
                                        preserve_autosave = True
                                        break
                                except Exception:
                                    preserve_autosave = True
                                    break
                        except Exception:
                            pass
                    except Exception:
                        pass

            if preserve_autosave:
                # ensure latest content is saved for recovery
                try:
                    self.autosave_all()
                except Exception:
                    pass
            else:
                # no unsaved edits: remove autosave artifacts
                try:
                    if getattr(self, 'autosave_index', None) and os.path.exists(self.autosave_index):
                        with open(self.autosave_index, 'r', encoding='utf-8') as f:
                            entries = json.load(f)
                        for e in entries:
                            p = os.path.join(self.autosave_dir, e.get('file'))
                            try:
                                if os.path.exists(p):
                                    os.remove(p)
                            except Exception:
                                pass
                        try:
                            os.remove(self.autosave_index)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass
        try:
            super().closeEvent(event)
        except Exception:
            event.accept()

    def eventFilter(self, obj, event):
        # Close the find widget on Escape when editor has focus
        try:
            if event.type() == QEvent.KeyPress:
                key = event.key()
                if key == Qt.Key.Key_Escape and getattr(self, 'find_widget', None) and self.find_widget.isVisible():
                    self.find_widget.setVisible(False)
                    return True
        except Exception:
            pass
        return super().eventFilter(obj, event)

    # --- Autosave and recovery ---
    def autosave_all(self):
        try:
            if not getattr(self, 'autosave_dir', None):
                return
            entries = []
            for i in range(self.tab_widget.count()):
                w = self.tab_widget.widget(i)
                if not isinstance(w, GSCEditor):
                    continue
                # only autosave if modified
                try:
                    if not w.document().isModified():
                        continue
                except Exception:
                    pass
                filename = self.tab_paths.get(w)
                # reuse existing autosave file for this editor when possible
                existing = self.autosave_map.get(w)
                if existing:
                    fname = existing
                else:
                    fname = f"autosave_{uuid.uuid4().hex}.json"
                    self.autosave_map[w] = fname
                path = os.path.join(self.autosave_dir, fname)
                data = {'filename': filename, 'content': w.toPlainText()}
                try:
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump(data, f)
                    entries.append({'file': fname, 'filename': filename})
                except Exception:
                    pass

            # write index
            try:
                if entries:
                    with open(self.autosave_index, 'w', encoding='utf-8') as f:
                        json.dump(entries, f)
                else:
                    # remove index if no entries
                    if os.path.exists(self.autosave_index):
                        os.remove(self.autosave_index)
            except Exception:
                pass
        except Exception:
            pass

    def check_autosave_recovery(self):
        try:
            if not getattr(self, 'autosave_dir', None):
                return
            if not os.path.exists(self.autosave_index):
                return
            with open(self.autosave_index, 'r', encoding='utf-8') as f:
                entries = json.load(f)
            if not entries:
                return
            resp = QMessageBox.question(self, "Recover Autosave", "Autosave data from a previous session was found. Recover tabs?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resp != QMessageBox.StandardButton.Yes:
                return
            # load each autosave as a tab
            for e in entries:
                p = os.path.join(self.autosave_dir, e.get('file'))
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self.new_tab(filename=data.get('filename'), content=data.get('content'))
                except Exception:
                    pass
            # remove autosave artifacts after recovery
            try:
                for e in entries:
                    p = os.path.join(self.autosave_dir, e.get('file'))
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except Exception:
                        pass
                if os.path.exists(self.autosave_index):
                    os.remove(self.autosave_index)
            except Exception:
                pass
        except Exception:
            pass

    def autosave_editor(self, editor: GSCEditor):
        try:
            if not getattr(self, 'autosave_dir', None):
                return
            if not isinstance(editor, GSCEditor):
                return
            # always save current content for this editor
            filename = self.tab_paths.get(editor)
            existing = self.autosave_map.get(editor)
            if existing:
                fname = existing
            else:
                fname = f"autosave_{uuid.uuid4().hex}.json"
                self.autosave_map[editor] = fname
            path = os.path.join(self.autosave_dir, fname)
            data = {'filename': filename, 'content': editor.toPlainText()}
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f)
            except Exception:
                pass
            # update index
            try:
                entries = []
                # include all autosave files currently tracked
                for ed, fname in list(self.autosave_map.items()):
                    entries.append({'file': fname, 'filename': self.tab_paths.get(ed)})
                with open(self.autosave_index, 'w', encoding='utf-8') as f:
                    json.dump(entries, f)
            except Exception:
                pass
        except Exception:
            pass

    def remove_autosave_for(self, editor: GSCEditor):
        try:
            if not getattr(self, 'autosave_dir', None):
                return
            fname = self.autosave_map.pop(editor, None)
            if not fname:
                return
            path = os.path.join(self.autosave_dir, fname)
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
            # rebuild index
            try:
                entries = []
                for ed, f in list(self.autosave_map.items()):
                    entries.append({'file': f, 'filename': self.tab_paths.get(ed)})
                if entries:
                    with open(self.autosave_index, 'w', encoding='utf-8') as f:
                        json.dump(entries, f)
                else:
                    if os.path.exists(self.autosave_index):
                        os.remove(self.autosave_index)
            except Exception:
                pass
        except Exception:
            pass


def main():
    app = QApplication(sys.argv)
    
    window = GSCIDEWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
