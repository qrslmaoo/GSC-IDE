import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QPushButton, QComboBox, QLabel, 
                              QTextEdit, QFileDialog, QSplitter, QMessageBox,
                              QLineEdit, QGroupBox, QStatusBar, QTextBrowser, QDialog, QFormLayout, QSpinBox, QComboBox as QComboBoxWidget, QStyle, QPlainTextEdit, QCheckBox, QTabWidget,
                              QFrame, QListWidget, QListWidgetItem, QToolButton)
from PyQt6.QtCore import Qt, QTimer, QSettings, QSize, QEvent
import ctypes
from PyQt6.QtGui import (QFont, QAction, QKeySequence, QSyntaxHighlighter, QTextCharFormat, QColor, QTextCursor,
                         QPainter, QPen)
import re
import tempfile
import json
import uuid
import unicodedata
from weakref import WeakKeyDictionary
import traceback

from injection_manager import InjectionManager, TargetGame, InjectionMethod, GameMode


def _handle_suppressed(exc: Exception, self_obj=None):
    try:
        if self_obj is not None and hasattr(self_obj, 'log_exception'):
            try:
                self_obj.log_exception("suppressed exception", exc)
            except Exception:
                traceback.print_exc()
        else:
            traceback.print_exc()
    except Exception:
        try:
            traceback.print_exc()
        except Exception as e:
            _handle_suppressed(e, locals().get('self', None))


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
        font = QFont("Cascadia Code", 11)
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
        self.setObjectName("codeEditor")
        self.setStyleSheet("""
            QPlainTextEdit#codeEditor {
                background-color: #101112;
                color: #e7e2d8;
                border: 1px solid #34373a;
                border-radius: 4px;
                padding: 10px;
                selection-background-color: #4a3a25;
                selection-color: #ffffff;
            }
        """)
        
        # Set initial content
        self.setPlainText(self.get_default_template())
        # storage for lint error ranges as (start_pos, length)
        self.lint_error_positions = []

    def is_modified(self):
        try:
            return self.document().isModified()
        except Exception as e:
            try:
                # avoid noisy UI logs from editor internals; print traceback for debugging
                traceback.print_exc()
            except Exception as e:
                try:
                    if hasattr(self, 'log_exception'):
                        self.log_exception("suppressed exception", e)
                    else:
                        traceback.print_exc()
                except Exception:
                    try:
                        traceback.print_exc()
                    except Exception as e:
                        _handle_suppressed(e, locals().get('self', None))
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
        painter.fillRect(event.rect(), QColor("#121314"))
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#7f858b"))
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
            try:
                traceback.print_exc()
            except Exception as e:
                try:
                    if hasattr(self, 'log_exception'):
                        self.log_exception("suppressed exception", e)
                    else:
                        traceback.print_exc()
                except Exception:
                    try:
                        traceback.print_exc()
                    except Exception as e:
                        _handle_suppressed(e, locals().get('self', None))

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
            try:
                traceback.print_exc()
            except Exception as e:
                try:
                    if hasattr(self, 'log_exception'):
                        self.log_exception("suppressed exception", e)
                    else:
                        traceback.print_exc()
                except Exception:
                    try:
                        traceback.print_exc()
                    except Exception as e:
                        _handle_suppressed(e, locals().get('self', None))


class GlassBackground(QWidget):
    """Root widget styled by Qt stylesheets for reliable startup across PyQt builds."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("backgroundRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


class GlassPanel(QFrame):
    def __init__(self, parent=None, raised=True):
        super().__init__(parent)
        self.setObjectName("glassPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)



class StatusPill(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("statusPill")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class GSCIDEWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.injection_manager = InjectionManager()
        self.settings = QSettings("GSC-IDE", "GSCIDE")
        
        self.init_ui()
        self.setup_timer()
        
    def init_ui(self):
        self.setWindowTitle("GSC Studio - Plutonium Script Editor")
        self.setGeometry(100, 100, 1480, 940)

        self.base_css = """
        QMainWindow {
            background: #0e0f11;
            color: #d7dbe0;
            font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
            font-size: 13px;
        }
        QWidget#backgroundRoot {
            background: #0e0f11;
        }
        QFrame#auroraOne, QFrame#auroraTwo, QFrame#auroraThree {
            background: transparent;
            border: 0;
        }
        QLabel {
            color: #d7dbe0;
        }
        QLabel#heroTitle {
            color: #f0f2f4;
            font-size: 14px;
            font-weight: 750;
            letter-spacing: 0;
        }
        QLabel#heroSubtitle {
            color: #969da5;
            font-size: 11px;
        }
        QLabel#sectionTitle {
            color: #f0f2f4;
            font-size: 14px;
            font-weight: 800;
        }
        QLabel#fieldLabel {
            color: #8b929a;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: .7px;
            text-transform: uppercase;
        }
        QLabel#mutedLabel, QLabel#helperText {
            color: #9aa1a9;
            line-height: 140%;
        }
        QLabel#statusPill {
            background-color: #17191c;
            border: 1px solid #34383d;
            border-radius: 4px;
            color: #d3d8de;
            font-size: 11px;
            font-weight: 700;
            padding: 5px 9px;
        }
        QLabel#statusPill[state="ok"] {
            background-color: #10251c;
            border-color: #276648;
            color: #98e0b9;
        }
        QLabel#statusPill[state="error"] {
            background-color: #2a1218;
            border-color: #773141;
            color: #ffabb7;
        }
        QLabel#statusPill[state="idle"] {
            background-color: #16181b;
            color: #969da5;
        }
        QFrame#glassPanel,
        QFrame#heroPanel,
        QFrame#sideCard,
        QFrame#findBar,
        QFrame#editorPanel,
        QFrame#railPanel {
            background-color: #151719;
            border: 1px solid #303337;
            border-radius: 4px;
        }
        QFrame#heroPanel {
            background-color: #131517;
            border-color: #24282d;
        }
        QFrame#editorPanel {
            background-color: #101112;
            border-color: #34373a;
        }
        QFrame#sideCard {
            background-color: #151719;
        }
        QFrame#findBar {
            background-color: #191b1e;
        }
        QFrame#railPanel {
            background-color: #101112;
        }
        QLabel#railBrand {
            background-color: #1d2024;
            border: 1px solid #3e4349;
            border-radius: 4px;
            color: #f0f2f4;
            font-size: 18px;
            font-weight: 900;
            padding: 10px;
        }
        QLabel#railCaption {
            color: #858c94;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: .8px;
        }
        QLabel#deployTitle {
            color: #f0f2f4;
            font-size: 16px;
            font-weight: 850;
        }
        QLabel#miniMetric {
            background-color: #151719;
            border: 1px solid #30343a;
            border-radius: 4px;
            color: #9aa1a9;
            font-size: 10px;
            font-weight: 800;
            padding: 9px;
        }
        QPushButton {
            background-color: #1f2327;
            color: #e0e4e8;
            border: 1px solid #434950;
            border-radius: 4px;
            padding: 8px 12px;
            font-weight: 700;
        }
        QPushButton:hover {
            background-color: #2a2e33;
            border-color: #59616a;
        }
        QPushButton:pressed {
            background-color: #373c42;
        }
        QPushButton#primaryButton {
            background-color: #2f5f7a;
            color: #f3f7fa;
            border: 1px solid #477d9b;
            border-radius: 4px;
            padding: 10px 12px;
            font-size: 13px;
            font-weight: 750;
        }
        QPushButton#primaryButton:hover {
            background-color: #3a6f8d;
        }
        QPushButton#secondaryButton {
            background-color: #16181b;
            color: #d8dde2;
        }
        QPushButton#navButton {
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 4px;
            color: #c4cad0;
            font-size: 12px;
            font-weight: 750;
            padding: 9px 10px;
            min-height: 26px;
            text-align: left;
        }
        QPushButton#navButton:hover {
            background-color: #1d2024;
            border-color: #373c42;
            color: #f0f2f4;
        }
        QComboBox, QLineEdit {
            background-color: #11100f;
            color: #e2e6ea;
            border: 1px solid #3b4046;
            border-radius: 4px;
            padding: 8px 10px;
            min-height: 22px;
        }
        QComboBox:hover, QLineEdit:hover, QComboBox:focus, QLineEdit:focus {
            background-color: #16181b;
            border-color: #66707a;
        }
        QComboBox QAbstractItemView {
            background-color: #16181b;
            color: #e2e6ea;
            border: 1px solid #3e4349;
            selection-background-color: #4d5146;
            outline: 0;
        }
        QListWidget {
            background-color: #11100f;
            color: #d7dbe0;
            border: 1px solid #373c42;
            border-radius: 4px;
            padding: 4px;
            outline: 0;
        }
        QListWidget::item {
            border-radius: 3px;
            padding: 5px 6px;
        }
        QListWidget::item:hover {
            background-color: #1d2024;
        }
        QListWidget::item:selected {
            background-color: #2f3d47;
            color: #ffffff;
        }
        QTabWidget::pane {
            border: 0;
            top: -1px;
        }
        QTabBar::tab {
            background-color: #17191c;
            color: #969da5;
            border: 1px solid #30343a;
            border-bottom: 0;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 6px 4px 5px 10px;
            margin-right: 4px;
            font-weight: 700;
            min-height: 20px;
        }
        QTabBar::tab:selected {
            background-color: #21252a;
            color: #f0f2f4;
            border-color: #4a5158;
        }
        QTabBar::tab:hover:!selected {
            background-color: #1d2024;
            color: #d7dbe0;
            border-color: #3a4047;
        }
        QToolButton#tabCloseButton {
            background-color: transparent;
            border: 0;
            border-radius: 3px;
            color: #8f969e;
            margin-left: 2px;
            margin-right: 4px;
            padding: 0;
            min-width: 14px;
            max-width: 14px;
            min-height: 14px;
            max-height: 14px;
        }
        QToolButton#tabCloseButton:hover {
            background-color: #3a2528;
            color: #ffb7c0;
        }
        QToolButton#tabCloseButton:pressed {
            background-color: #5a2b34;
            color: #ffffff;
        }
        QSplitter::handle {
            background-color: #2a2e33;
            border-radius: 2px;
        }
        QTextEdit, QTextBrowser {
            background-color: #11100f;
            color: #e2e6ea;
            border: 1px solid #373c42;
            border-radius: 4px;
            padding: 9px;
            selection-background-color: #4d5146;
        }
        QTextBrowser#errorConsole {
            background-color: #171010;
            color: #ffccd3;
            border-color: #4a2c32;
        }
        QMenuBar {
            background-color: #131517;
            color: #d7dbe0;
            border-bottom: 1px solid #30343a;
            padding: 3px;
        }
        QMenuBar::item {
            border-radius: 6px;
            padding: 5px 9px;
        }
        QMenuBar::item:selected {
            background-color: #2a2e33;
        }
        QMenu {
            background-color: #16181b;
            color: #d7dbe0;
            border: 1px solid #3e4349;
            border-radius: 4px;
            padding: 6px;
        }
        QMenu::item {
            border-radius: 5px;
            padding: 7px 22px;
        }
        QMenu::item:selected {
            background-color: #32373d;
        }
        QToolBar {
            background-color: #131517;
            border: 0;
            border-bottom: 1px solid #30343a;
            spacing: 6px;
            padding: 6px;
        }
        QToolButton {
            background-color: #1f2327;
            border: 1px solid #3e4349;
            border-radius: 4px;
            padding: 7px 9px;
            color: #d7dbe0;
            font-weight: 700;
        }
        QToolButton:hover {
            background-color: #2a2e33;
        }
        QStatusBar {
            background-color: #131517;
            color: #9aa1a9;
            border-top: 1px solid #30343a;
            padding: 3px;
        }
        QStatusBar::item {
            border: 0;
        }
        QWidget#lineNumberArea {
            background: #121314;
        }
        """

        self.setStyleSheet(self.base_css)
        
        # Menu bar will be created after editor is initialized
        
        # Main widget and layout
        main_widget = GlassBackground()
        self.setCentralWidget(main_widget)
        self.aurora_layers = []
        for name in ("auroraOne", "auroraTwo", "auroraThree"):
            aura = QFrame(main_widget)
            aura.setObjectName(name)
            aura.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            aura.lower()
            self.aurora_layers.append(aura)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(8)

        hero_panel = GlassPanel(raised=True)
        hero_panel.setObjectName("heroPanel")
        hero_layout = QHBoxLayout(hero_panel)
        hero_layout.setContentsMargins(10, 6, 10, 6)
        hero_layout.setSpacing(8)

        hero_copy = QVBoxLayout()
        hero_copy.setContentsMargins(0, 0, 0, 0)
        hero_copy.setSpacing(0)
        hero_title = QLabel("GSC Studio")
        hero_title.setObjectName("heroTitle")
        hero_copy.addWidget(hero_title)
        hero_layout.addLayout(hero_copy, 1)

        self.plut_path_label = StatusPill("Plutonium: checking")
        self.game_status_label = StatusPill("Game: checking")
        hero_layout.addWidget(self.plut_path_label)
        hero_layout.addWidget(self.game_status_label)

        main_layout.addWidget(hero_panel)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Editor
        left_panel = GlassPanel()
        left_panel.setObjectName("editorPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(10)

        # Editor header
        editor_header_layout = QHBoxLayout()
        editor_header = QLabel("Editor")
        editor_header.setObjectName("sectionTitle")
        self.editor_info = StatusPill("Line: 1 | Column: 1")
        editor_header_layout.addWidget(editor_header)
        editor_header_layout.addStretch()
        editor_header_layout.addWidget(self.editor_info)
        left_layout.addLayout(editor_header_layout)

        # Find/Replace bar (hidden by default)
        self.find_widget = GlassPanel(raised=False)
        self.find_widget.setObjectName("findBar")
        find_layout = QHBoxLayout(self.find_widget)
        find_layout.setContentsMargins(10, 8, 10, 8)
        find_layout.setSpacing(8)
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find in current script")
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace with")
        find_prev_btn = QPushButton("Previous")
        find_next_btn = QPushButton("Next")
        replace_btn = QPushButton("Replace")
        close_find_btn = QPushButton("Close")
        close_find_btn.setObjectName("secondaryButton")
        find_layout.addWidget(self.find_input, 2)
        find_layout.addWidget(self.replace_input, 2)
        find_layout.addWidget(find_prev_btn)
        find_layout.addWidget(find_next_btn)
        find_layout.addWidget(replace_btn)
        find_layout.addWidget(close_find_btn)
        self.find_widget.setVisible(False)
        left_layout.addWidget(self.find_widget)

        # Vertical splitter for editor and error console
        vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        vertical_splitter.setObjectName("verticalSplitter")

        # Text editor
        # Tabbed editors
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(False)

        # Autosave state must exist before any editor connects textChanged handlers.
        self.autosave_dir = None
        self.autosave_index = None
        self._autosave_timers = WeakKeyDictionary()
        self.autosave_map = WeakKeyDictionary()
        try:
            self.autosave_dir = os.path.join(tempfile.gettempdir(), 'gscide_autosave')
            os.makedirs(self.autosave_dir, exist_ok=True)
            self.autosave_index = os.path.join(self.autosave_dir, 'index.json')
        except Exception as e:
            try:
                self.log_exception("autosave path setup", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
            self.autosave_dir = None
            self.autosave_index = None

        # create initial editor tab
        self.editor = GSCEditor()
        # map editor widget -> filename (use WeakKeyDictionary to avoid leaking editor objects)
        self.tab_paths = WeakKeyDictionary()
        self.tab_widget.addTab(self.editor, "Untitled")
        self.tab_paths[self.editor] = None
        self.install_tab_close_button(self.editor)
        vertical_splitter.addWidget(self.tab_widget)

        # attach signals for the initial editor
        self.attach_editor_signals(self.editor)

        # autosave setup
        try:
            if self.autosave_dir:
                # check for recovery files
                self.check_autosave_recovery()
                self.autosave_timer = QTimer(self)
                self.autosave_timer.setInterval(10000)  # 10s
                self.autosave_timer.timeout.connect(self.autosave_all)
                self.autosave_timer.start()
        except Exception as e:
            try:
                self.log_exception("autosave setup", e)
            except Exception as e:
                try:
                    if hasattr(self, 'log_exception'):
                        self.log_exception("suppressed exception", e)
                    else:
                        traceback.print_exc()
                except Exception:
                    try:
                        traceback.print_exc()
                    except Exception as e:
                        _handle_suppressed(e, locals().get('self', None))
            self.autosave_dir = None

        self.apply_saved_editor_font_size(self.editor)

        # Error/Debug console under the editor (clickable links)
        self.error_console = QTextBrowser()
        self.error_console.setObjectName("errorConsole")
        self.error_console.setReadOnly(True)
        self.error_console.setMaximumHeight(180)
        self.error_console.setOpenLinks(False)
        self.error_console.setOpenExternalLinks(False)
        self.error_console.anchorClicked.connect(self.goto_error)
        vertical_splitter.addWidget(self.error_console)
        vertical_splitter.setSizes([680, 150])

        left_layout.addWidget(vertical_splitter)
        # cursor updates will be connected per-tab
        try:
            self.tab_widget.currentChanged.connect(lambda idx: self.update_cursor_info())
            self.tab_widget.currentChanged.connect(lambda idx: self.refresh_symbols())
        except Exception as e:
            try:
                self.log_exception("connect currentChanged", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
        # Live linting timer (debounced)
        try:
            self.live_lint_timer = QTimer(self)
            self.live_lint_timer.setSingleShot(True)
            self.live_lint_timer.setInterval(500)  # 500ms debounce
            self.live_lint_timer.timeout.connect(self.lint_script)
        except Exception as e:
            try:
                self.log_exception("live_lint_timer setup", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
        try:
            self.symbol_timer = QTimer(self)
            self.symbol_timer.setSingleShot(True)
            self.symbol_timer.setInterval(250)
            self.symbol_timer.timeout.connect(self.refresh_symbols)
        except Exception as e:
            try:
                self.log_exception("symbol_timer setup", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))

        # Find/Replace button wiring
        try:
            find_prev_btn.clicked.connect(lambda: self.find_previous())
        except Exception as e:
            try:
                self.log_exception("find_prev_btn.connect", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
        find_next_btn.clicked.connect(lambda: self.find_next())
        replace_btn.clicked.connect(lambda: self.replace_one())
        close_find_btn.clicked.connect(lambda: self.find_widget.setVisible(False))

        # Install event filter to catch Escape key to close find widget
        try:
            self.tab_widget.installEventFilter(self)
        except Exception as e:
            try:
                self.log_exception("installEventFilter", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
        
        splitter.addWidget(left_panel)
        
        # Right panel - Controls
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Script intelligence
        self.code_tools_group = GlassPanel(raised=False)
        self.code_tools_group.setObjectName("sideCard")
        code_tools_layout = QVBoxLayout()
        code_tools_layout.setContentsMargins(12, 12, 12, 12)
        code_tools_layout.setSpacing(8)

        symbols_title = QLabel("Symbols")
        symbols_title.setObjectName("sectionTitle")
        code_tools_layout.addWidget(symbols_title)

        self.symbol_list = QListWidget()
        self.symbol_list.setMinimumHeight(150)
        self.symbol_list.setMaximumHeight(240)
        self.symbol_list.itemActivated.connect(self.goto_symbol_item)
        self.symbol_list.itemDoubleClicked.connect(self.goto_symbol_item)
        code_tools_layout.addWidget(self.symbol_list)

        code_tools_layout.addWidget(self.create_field_label("SNIPPET"))
        snippet_row = QHBoxLayout()
        snippet_row.setContentsMargins(0, 0, 0, 0)
        snippet_row.setSpacing(6)
        self.snippets = self.build_gsc_snippets()
        self.snippet_combo = QComboBox()
        self.snippet_combo.addItems(list(self.snippets.keys()))
        snippet_row.addWidget(self.snippet_combo, 1)
        insert_snippet_btn = QPushButton("Insert")
        insert_snippet_btn.clicked.connect(self.insert_snippet)
        snippet_row.addWidget(insert_snippet_btn)
        code_tools_layout.addLayout(snippet_row)

        self.code_tools_group.setLayout(code_tools_layout)
        right_layout.addWidget(self.code_tools_group)
        
        # Injection settings
        self.injection_group = GlassPanel(raised=False)
        self.injection_group.setObjectName("sideCard")
        injection_layout = QVBoxLayout()
        injection_layout.setContentsMargins(12, 12, 12, 12)
        injection_layout.setSpacing(8)
        injection_title = QLabel("Deploy")
        injection_title.setObjectName("deployTitle")
        injection_layout.addWidget(injection_title)
        
        # Info label
        info_label = QLabel("Writes the active tab to the selected Plutonium scripts folder.")
        info_label.setObjectName("helperText")
        info_label.setWordWrap(True)
        injection_layout.addWidget(info_label)
        
        # Game selection
        injection_layout.addWidget(self.create_field_label("TARGET GAME"))
        self.game_combo = QComboBox()
        self.game_combo.addItems([
            "Plutonium T6 (Black Ops 2)",
            "Plutonium T5 (Black Ops 1)", 
            "Plutonium T4 (World at War)",
            "Plutonium IW5 (MW3)"
        ])
        injection_layout.addWidget(self.game_combo)
        
        # Method selection
        injection_layout.addWidget(self.create_field_label("METHOD"))
        self.method_combo = QComboBox()
        self.method_combo.addItems([
            "Plutonium Scripts Folder",
            "Direct Memory (Not Recommended)",
            "Network (Console)"
        ])
        injection_layout.addWidget(self.method_combo)
        
        # Mode selection
        injection_layout.addWidget(self.create_field_label("GAME MODE"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Multiplayer", "Zombies", "Both"])
        injection_layout.addWidget(self.mode_combo)
        
        # Script name
        injection_layout.addWidget(self.create_field_label("SCRIPT NAME"))
        self.script_name = QLineEdit("my_mod")
        injection_layout.addWidget(self.script_name)
        
        self.script_name_label = QLabel("Will be saved as: my_mod.gsc")
        self.script_name_label.setObjectName("mutedLabel")
        injection_layout.addWidget(self.script_name_label)
        self.script_name.textChanged.connect(
            lambda: self.script_name_label.setText(f"Will be saved as: {self.script_name.text()}.gsc")
        )
        
        # Deploy button
        deploy_btn = QPushButton("Deploy Script")
        deploy_btn.setObjectName("primaryButton")
        deploy_btn.clicked.connect(self.deploy_script)
        injection_layout.addWidget(deploy_btn)
        
        # Open folder button
        open_folder_btn = QPushButton("Open Scripts Folder")
        open_folder_btn.setObjectName("secondaryButton")
        open_folder_btn.clicked.connect(self.open_scripts_folder)
        injection_layout.addWidget(open_folder_btn)
        
        injection_layout.addStretch()
        self.injection_group.setLayout(injection_layout)
        right_layout.addWidget(self.injection_group)
        
        # Output console
        self.output_group = GlassPanel(raised=False)
        self.output_group.setObjectName("sideCard")
        output_layout = QVBoxLayout()
        output_layout.setContentsMargins(12, 12, 12, 12)
        output_layout.setSpacing(8)
        output_title = QLabel("Console")
        output_title.setObjectName("sectionTitle")
        output_layout.addWidget(output_title)
        self.output_console = QTextEdit()
        self.output_console.setObjectName("outputConsole")
        self.output_console.setReadOnly(True)
        self.output_console.setMinimumHeight(180)
        self.log("GSC IDE initialized. Ready to deploy scripts.")
        output_layout.addWidget(self.output_console)
        self.output_group.setLayout(output_layout)
        right_layout.addWidget(self.output_group)
        
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([980, 380])

        body_shell = QWidget()
        body_layout = QHBoxLayout(body_shell)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(splitter, 1)
        main_layout.addWidget(body_shell, 1)
        
        # Create menu bar now that editor exists
        self.create_menu_bar()

        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        # persistent small status label on the right
        self.status_label = StatusPill("Ready")
        try:
            self.statusBar.addPermanentWidget(self.status_label)
        except Exception as e:
            try:
                self.log_exception("statusBar.addPermanentWidget", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
        self.statusBar.showMessage("Ready")
        self.refresh_symbols()

        # Keep legacy theme values compatible while presenting the workbench shell.
        self.current_theme = self.settings.value('theme', 'workbench')
        self.apply_theme(self.current_theme)

        # Caps Lock indicator (always show ON/OFF and adapt to theme)
        try:
            self.caps_label = StatusPill("")
            self.statusBar.addPermanentWidget(self.caps_label)
            self.caps_timer = QTimer()
            self.caps_timer.timeout.connect(self.update_caps_lock)
            self.caps_timer.start(300)
            # set initial state
            self.update_caps_lock()
        except Exception as e:
            try:
                self.log_exception("caps_label init", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
            self.caps_label = None
        QTimer.singleShot(0, self.position_aurora_layers)

    def refresh_widget_style(self, widget):
        try:
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
        except Exception as e:
            _handle_suppressed(e, locals().get('self', None))

    def create_field_label(self, text):
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def create_action_rail(self):
        rail = GlassPanel(raised=False)
        rail.setObjectName("railPanel")
        rail.setFixedWidth(118)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(8)

        brand = QLabel("GSC")
        brand.setObjectName("railBrand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand)

        caption = QLabel("WORKBENCH")
        caption.setObjectName("railCaption")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(caption)
        layout.addSpacing(6)

        actions = [
            ("New", QStyle.StandardPixmap.SP_FileIcon, self.new_file),
            ("Open", QStyle.StandardPixmap.SP_DirOpenIcon, self.open_file),
            ("Save", QStyle.StandardPixmap.SP_DialogSaveButton, self.save_file),
            ("Find", QStyle.StandardPixmap.SP_FileDialogContentsView, lambda: self.show_find(True)),
            ("Replace", QStyle.StandardPixmap.SP_FileDialogDetailedView, lambda: self.show_find(False)),
            ("Deploy", QStyle.StandardPixmap.SP_MediaPlay, self.deploy_script),
            ("Prefs", QStyle.StandardPixmap.SP_FileDialogInfoView, self.open_preferences),
        ]
        for text, icon_id, callback in actions:
            button = QPushButton(text)
            button.setObjectName("navButton")
            button.setIcon(self.style().standardIcon(icon_id))
            button.setIconSize(QSize(16, 16))
            button.setToolTip(text)
            button.clicked.connect(callback)
            layout.addWidget(button)

        layout.addStretch()
        build_label = QLabel("LINT ON\nAUTOSAVE")
        build_label.setObjectName("miniMetric")
        build_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(build_label)
        return rail

    def position_aurora_layers(self):
        try:
            layers = getattr(self, 'aurora_layers', [])
            for layer in layers:
                layer.hide()
        except Exception as e:
            _handle_suppressed(e, locals().get('self', None))

    def resizeEvent(self, event):
        try:
            super().resizeEvent(event)
        finally:
            self.position_aurora_layers()
        
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
        undo_action.triggered.connect(lambda: self.current_editor().undo() if self.current_editor() else None)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("Redo", self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.triggered.connect(lambda: self.current_editor().redo() if self.current_editor() else None)
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        copy_action = QAction("Copy", self)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.triggered.connect(lambda: self.current_editor().copy() if self.current_editor() else None)
        edit_menu.addAction(copy_action)
        
        cut_action = QAction("Cut", self)
        cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        cut_action.triggered.connect(lambda: self.current_editor().cut() if self.current_editor() else None)
        edit_menu.addAction(cut_action)
        
        paste_action = QAction("Paste", self)
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        paste_action.triggered.connect(lambda: self.current_editor().paste() if self.current_editor() else None)
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

        # Find Previous action
        try:
            find_prev_action = QAction("Find Previous", self)
            find_prev_action.setShortcut(QKeySequence("Shift+F3"))
            find_prev_action.triggered.connect(lambda: self.find_previous())
            edit_menu.addAction(find_prev_action)
            self.addAction(find_prev_action)
        except Exception as e:
            try:
                self.log_exception("create_menu_bar: find_prev_action", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
        edit_menu.addAction(replace_action)
        self.addAction(replace_action)

        # View menu (toggle panels)
        view_menu = menubar.addMenu("View")
        refresh_symbols_action = QAction("Refresh Symbols", self)
        refresh_symbols_action.setShortcut(QKeySequence("Ctrl+Alt+O"))
        refresh_symbols_action.triggered.connect(self.refresh_symbols)
        view_menu.addAction(refresh_symbols_action)
        self.addAction(refresh_symbols_action)

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
            except Exception as e:
                try:
                    self.log_exception("set panel_injection", e)
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
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
            except Exception as e:
                try:
                    self.log_exception("set panel_output", e)
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
        toggle_output.triggered.connect(_set_output)
        view_menu.addAction(toggle_output)

        # Theme action is kept for shortcut compatibility; the workbench shell is the only visual mode.
        theme_action = QAction("Refresh Workbench Theme", self)
        theme_action.setShortcut(QKeySequence("Ctrl+T"))
        theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(theme_action)

        # Register shortcuts globally so they work regardless of focus
        self.addAction(toggle_injection)
        self.addAction(toggle_output)
        self.addAction(theme_action)

        # Toolbar for quick actions
        toolbar = self.addToolBar("Main")
        self.main_toolbar = toolbar
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
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
        except Exception as e:
            try:
                self.log_exception("toolbar find_action icon", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))

        try:
            replace_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
            replace_action.setToolTip("Replace (Ctrl+H)")
            toolbar.addAction(replace_action)
        except Exception as e:
            try:
                self.log_exception("toolbar replace_action icon", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
        try:
            # Add Find Previous to toolbar for quick access
            if getattr(self, 'find_prev_btn', None) is None:
                find_prev_action = QAction("Find Previous", self)
                find_prev_action.setShortcut(QKeySequence("Shift+F3"))
                find_prev_action.triggered.connect(lambda: self.find_previous())
                find_prev_action.setToolTip("Find Previous (Shift+F3)")
                toolbar.addAction(find_prev_action)
        except Exception as e:
            try:
                self.log_exception("toolbar add find_prev_action", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))

        toolbar.addSeparator()

        deploy_act = QAction("Deploy", self)
        deploy_act.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        deploy_act.setToolTip("Deploy script to Plutonium (F5)")
        deploy_act.setShortcut(QKeySequence("F5"))
        deploy_act.triggered.connect(self.deploy_script)
        toolbar.addAction(deploy_act)

        refresh_symbols_toolbar = QAction("Symbols", self)
        refresh_symbols_toolbar.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogListView))
        refresh_symbols_toolbar.setToolTip("Refresh symbols (Ctrl+Alt+O)")
        refresh_symbols_toolbar.triggered.connect(self.refresh_symbols)
        toolbar.addAction(refresh_symbols_toolbar)

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

    def log_exception(self, context: str, exc: Exception):
        try:
            tb = traceback.format_exc()
            msg = f"{context}: {exc}\n{tb}"
            try:
                # prefer structured log in UI
                self.log(msg, success=False)
            except Exception:
                # fallback to printing
                print(msg)
        except Exception as e:
            try:
                if hasattr(self, 'log_exception'):
                    self.log_exception("suppressed exception", e)
                else:
                    traceback.print_exc()
            except Exception:
                try:
                    traceback.print_exc()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

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
                    self.status_label.setText(f"{file_display} - Ln {line}, Col {column}")
            except Exception as e:
                try:
                    self.log_exception("update_cursor_info: status_label update", e)
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
        except Exception as e:
            try:
                self.log_exception("update_cursor_info", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))

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
        except Exception as e:
            try:
                self.log_exception("schedule_live_lint", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))

    def attach_editor_signals(self, editor: GSCEditor):
        try:
            editor.cursorPositionChanged.connect(self.update_cursor_info)
        except Exception as e:
            try:
                self.log_exception("attach_editor_signals: cursorPositionChanged", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
        try:
            editor.textChanged.connect(self.schedule_live_lint)
        except Exception as e:
            try:
                self.log_exception("attach_editor_signals: textChanged", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
        try:
            editor.textChanged.connect(self.schedule_symbols_refresh)
        except Exception as e:
            try:
                self.log_exception("attach_editor_signals: symbols textChanged", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
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
                    except Exception as e:
                        try:
                            self.log_exception("autosave _on_edit", e)
                        except Exception as e:
                            _handle_suppressed(e, locals().get('self', None))
                editor.textChanged.connect(_on_edit)
        except Exception as e:
            try:
                self.log_exception("attach_editor_signals (autosave setup)", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))

    def current_editor(self) -> GSCEditor:
        try:
            w = self.tab_widget.currentWidget()
            if isinstance(w, GSCEditor):
                return w
        except Exception as e:
            try:
                if hasattr(self, 'log_exception'):
                    self.log_exception("suppressed exception", e)
                else:
                    traceback.print_exc()
            except Exception:
                try:
                    traceback.print_exc()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
        return getattr(self, 'editor', None)

    def apply_saved_editor_font_size(self, editor: GSCEditor):
        try:
            saved_fs = self.settings.value('editor_font_size', None)
            if not saved_fs or editor is None:
                return
            font = editor.font()
            font.setPointSize(int(saved_fs))
            editor.setFont(font)
            editor.update_line_number_area_width(0)
        except Exception as e:
            try:
                self.log_exception("apply_saved_editor_font_size", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))

    # --- Script intelligence ---
    def schedule_symbols_refresh(self):
        try:
            timer = getattr(self, 'symbol_timer', None)
            if timer:
                timer.start()
            else:
                self.refresh_symbols()
        except Exception as e:
            try:
                self.log_exception("schedule_symbols_refresh", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))

    def refresh_symbols(self):
        try:
            symbol_list = getattr(self, 'symbol_list', None)
            if symbol_list is None:
                return
            editor = self.current_editor()
            symbol_list.clear()
            if editor is None:
                return

            for label, line_no, kind in self.extract_symbols(editor.toPlainText()):
                prefix = "#" if kind == "include" else "fn"
                item = QListWidgetItem(f"{prefix}  {label}    :{line_no}")
                item.setData(Qt.ItemDataRole.UserRole, line_no)
                item.setToolTip(f"Go to line {line_no}")
                symbol_list.addItem(item)

            if symbol_list.count() == 0:
                item = QListWidgetItem("No functions found")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                symbol_list.addItem(item)
        except Exception as e:
            try:
                self.log_exception("refresh_symbols", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))

    def extract_symbols(self, text: str):
        symbols = []
        reserved = {
            'if', 'else', 'for', 'while', 'switch', 'case', 'return',
            'wait', 'waittill', 'thread', 'notify', 'endon'
        }
        include_re = re.compile(r'^\s*#include\s+([^;]+);?')
        func_re = re.compile(r'^\s*(?:function\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*(?:\{|$)')
        for idx, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith('//'):
                continue

            include_match = include_re.match(line)
            if include_match:
                symbols.append((include_match.group(1).strip(), idx, "include"))
                continue

            func_match = func_re.match(line)
            if not func_match:
                continue
            name = func_match.group(1)
            if name.lower() in reserved:
                continue
            symbols.append((name, idx, "function"))
        return symbols

    def goto_symbol_item(self, item):
        try:
            line_no = item.data(Qt.ItemDataRole.UserRole)
            if not line_no:
                return
            self.goto_line(int(line_no))
        except Exception as e:
            try:
                self.log_exception("goto_symbol_item", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))

    def goto_line(self, line_no: int, column: int = 0):
        editor = self.current_editor()
        if editor is None:
            return
        block = editor.document().findBlockByNumber(max(0, line_no - 1))
        if not block.isValid():
            return
        cursor = editor.textCursor()
        cursor.setPosition(block.position() + max(0, column))
        editor.setTextCursor(cursor)
        editor.centerCursor()
        editor.setFocus()

    def build_gsc_snippets(self):
        return {
            "init + connect": (
                "init()\n"
                "{\n"
                "    level thread onPlayerConnect();\n"
                "}\n\n"
                "onPlayerConnect()\n"
                "{\n"
                "    for(;;)\n"
                "    {\n"
                "        level waittill(\"connected\", player);\n"
                "        player thread onPlayerSpawned();\n"
                "    }\n"
                "}\n\n"
                "onPlayerSpawned()\n"
                "{\n"
                "    self endon(\"disconnect\");\n"
                "    for(;;)\n"
                "    {\n"
                "        self waittill(\"spawned_player\");\n"
                "    }\n"
                "}\n"
            ),
            "main function": (
                "main()\n"
                "{\n"
                "    // entry point\n"
                "}\n"
            ),
            "empty function": (
                "functionName()\n"
                "{\n"
                "    // code\n"
                "}\n"
            ),
            "player spawned thread": (
                "onPlayerSpawned()\n"
                "{\n"
                "    self endon(\"disconnect\");\n"
                "    for(;;)\n"
                "    {\n"
                "        self waittill(\"spawned_player\");\n"
                "        // spawn logic\n"
                "    }\n"
                "}\n"
            ),
            "player disconnect endon": (
                "self endon(\"disconnect\");\n"
                "self endon(\"death\");\n"
            ),
            "thread block": (
                "self endon(\"disconnect\");\n"
                "for(;;)\n"
                "{\n"
                "    wait 0.05;\n"
                "}\n"
            ),
            "delayed thread": (
                "threadName()\n"
                "{\n"
                "    wait 1;\n"
                "    // delayed work\n"
                "}\n"
            ),
            "wait loop": (
                "for(;;)\n"
                "{\n"
                "    wait 0.05;\n"
                "}\n"
            ),
            "while defined": (
                "while(isDefined(target))\n"
                "{\n"
                "    wait 0.05;\n"
                "}\n"
            ),
            "foreach players": (
                "players = level.players;\n"
                "for(i = 0; i < players.size; i++)\n"
                "{\n"
                "    player = players[i];\n"
                "}\n"
            ),
            "for index loop": (
                "for(i = 0; i < array.size; i++)\n"
                "{\n"
                "    value = array[i];\n"
                "}\n"
            ),
            "switch block": (
                "switch(value)\n"
                "{\n"
                "case \"one\":\n"
                "    break;\n"
                "default:\n"
                "    break;\n"
                "}\n"
            ),
            "spawn print": "self iPrintlnBold(\"Ready\");\n",
            "server print": "iPrintln(\"Message\");\n",
            "bold all players": "iPrintlnBold(\"Message\");\n",
            "notify wait": (
                "self notify(\"event_name\");\n"
                "self waittill(\"event_name\");\n"
            ),
            "level notify wait": (
                "level notify(\"event_name\");\n"
                "level waittill(\"event_name\");\n"
            ),
            "waittill any": (
                "self waittill_any(\"death\", \"disconnect\");\n"
            ),
            "menu notify pattern": (
                "self notify(\"menu_opened\");\n"
                "self waittill(\"menu_closed\");\n"
            ),
            "dvar guard": (
                "if(getDvar(\"dvar_name\") == \"\")\n"
                "{\n"
                "    setDvar(\"dvar_name\", \"1\");\n"
                "}\n"
            ),
            "set dvar": "setDvar(\"dvar_name\", \"value\");\n",
            "get dvar int": "value = getDvarInt(\"dvar_name\");\n",
            "get dvar float": "value = getDvarFloat(\"dvar_name\");\n",
            "toggle dvar": (
                "if(getDvarInt(\"dvar_name\"))\n"
                "{\n"
                "    setDvar(\"dvar_name\", \"0\");\n"
                "}\n"
                "else\n"
                "{\n"
                "    setDvar(\"dvar_name\", \"1\");\n"
                "}\n"
            ),
            "client dvar": "self setClientDvar(\"dvar_name\", \"value\");\n",
            "hud text": (
                "hud = self createFontString(\"objective\", 1.4);\n"
                "hud setPoint(\"CENTER\", \"CENTER\", 0, 0);\n"
                "hud setText(\"Text\");\n"
            ),
            "hud destroy on death": (
                "hud = self createFontString(\"objective\", 1.4);\n"
                "hud setPoint(\"CENTER\", \"CENTER\", 0, 0);\n"
                "hud setText(\"Text\");\n"
                "self waittill(\"death\");\n"
                "hud destroy();\n"
            ),
            "hud fade": (
                "hud fadeOverTime(0.5);\n"
                "hud.alpha = 0;\n"
            ),
            "hud typewriter": (
                "hud = self createFontString(\"objective\", 1.2);\n"
                "hud setPoint(\"TOP\", \"TOP\", 0, 40);\n"
                "hud setText(\"Message\");\n"
            ),
            "progress bar hud": (
                "bar = self createBar((1, 1, 1), 120, 8);\n"
                "bar setPoint(\"CENTER\", \"CENTER\", 0, 80);\n"
                "bar updateBar(0.5);\n"
            ),
            "give weapon": (
                "self giveWeapon(\"weapon_name\");\n"
                "self switchToWeapon(\"weapon_name\");\n"
            ),
            "take weapon": "self takeWeapon(\"weapon_name\");\n",
            "give ammo": "self giveMaxAmmo(\"weapon_name\");\n",
            "weapon check": (
                "if(self hasWeapon(\"weapon_name\"))\n"
                "{\n"
                "    // has weapon\n"
                "}\n"
            ),
            "current weapon": "weapon = self getCurrentWeapon();\n",
            "freeze controls": "self freezeControls(true);\n",
            "unfreeze controls": "self freezeControls(false);\n",
            "player origin": "origin = self.origin;\n",
            "teleport player": "self setOrigin((0, 0, 0));\n",
            "set angles": "self setPlayerAngles((0, 0, 0));\n",
            "trace forward": (
                "start = self getEye();\n"
                "end = start + anglesToForward(self getPlayerAngles()) * 1000000;\n"
                "trace = bulletTrace(start, end, false, self);\n"
            ),
            "distance check": (
                "if(distance(self.origin, target.origin) < 128)\n"
                "{\n"
                "    // close enough\n"
                "}\n"
            ),
            "spawn model": (
                "model = spawn(\"script_model\", origin);\n"
                "model setModel(\"model_name\");\n"
            ),
            "spawn trigger radius": (
                "trigger = spawn(\"trigger_radius\", origin, 0, 96, 64);\n"
                "trigger waittill(\"trigger\", player);\n"
            ),
            "trigger loop": (
                "trigger = spawn(\"trigger_radius\", origin, 0, 96, 64);\n"
                "for(;;)\n"
                "{\n"
                "    trigger waittill(\"trigger\", player);\n"
                "    // touched\n"
                "}\n"
            ),
            "delete entity": (
                "if(isDefined(entity))\n"
                "{\n"
                "    entity delete();\n"
                "}\n"
            ),
            "link entity": (
                "child linkTo(parent);\n"
                "child unlink();\n"
            ),
            "play fx": (
                "fx = loadFx(\"fx/path/name\");\n"
                "playFx(fx, origin);\n"
            ),
            "play fx on tag": (
                "fx = loadFx(\"fx/path/name\");\n"
                "playFxOnTag(fx, entity, \"tag_origin\");\n"
            ),
            "play sound": "self playLocalSound(\"sound_alias\");\n",
            "sound at position": "playSoundAtPosition(\"sound_alias\", origin);\n",
            "earthquake": "earthquake(0.5, 2, self.origin, 512);\n",
            "radius damage": "radiusDamage(origin, 160, 100, 20, self);\n",
            "array add unique": (
                "if(!isDefined(array))\n"
                "{\n"
                "    array = [];\n"
                "}\n"
                "array[array.size] = value;\n"
            ),
            "array remove value": (
                "newArray = [];\n"
                "for(i = 0; i < array.size; i++)\n"
                "{\n"
                "    if(array[i] != value)\n"
                "    {\n"
                "        newArray[newArray.size] = array[i];\n"
                "    }\n"
                "}\n"
            ),
            "struct create": (
                "data = spawnStruct();\n"
                "data.name = \"name\";\n"
                "data.origin = (0, 0, 0);\n"
            ),
            "get ent": "entity = getEnt(\"targetname\", \"targetname\");\n",
            "get ent array": "entities = getEntArray(\"targetname\", \"targetname\");\n",
            "level var init": (
                "if(!isDefined(level.var_name))\n"
                "{\n"
                "    level.var_name = value;\n"
                "}\n"
            ),
            "self var init": (
                "if(!isDefined(self.var_name))\n"
                "{\n"
                "    self.var_name = value;\n"
                "}\n"
            ),
            "is alive guard": (
                "if(!isAlive(self))\n"
                "{\n"
                "    return;\n"
                "}\n"
            ),
            "defined guard": (
                "if(!isDefined(value))\n"
                "{\n"
                "    return;\n"
                "}\n"
            ),
            "team check": (
                "if(self.team == \"allies\")\n"
                "{\n"
                "    // allies\n"
                "}\n"
            ),
            "host check": (
                "if(self isHost())\n"
                "{\n"
                "    // host-only logic\n"
                "}\n"
            ),
            "debug log": "println(\"DEBUG: message\");\n",
            "debug player": "self iPrintln(\"DEBUG: \" + value);\n",
            "assert defined": (
                "if(!isDefined(value))\n"
                "{\n"
                "    iPrintlnBold(\"Missing value\");\n"
                "    return;\n"
                "}\n"
            ),
            "try cleanup": (
                "self endon(\"disconnect\");\n"
                "entity = undefined;\n"
                "for(;;)\n"
                "{\n"
                "    wait 0.05;\n"
                "}\n"
            ),
            "timer seconds": (
                "timeLeft = 10;\n"
                "while(timeLeft > 0)\n"
                "{\n"
                "    self iPrintln(\"Time: \" + timeLeft);\n"
                "    wait 1;\n"
                "    timeLeft--;\n"
                "}\n"
            ),
            "cooldown": (
                "if(isDefined(self.cooldown) && self.cooldown)\n"
                "{\n"
                "    return;\n"
                "}\n"
                "self.cooldown = true;\n"
                "wait 1;\n"
                "self.cooldown = false;\n"
            ),
            "random int": "value = randomInt(10);\n",
            "random range": "value = randomIntRange(1, 10);\n",
            "random float": "value = randomFloat(1.0);\n",
            "vector add": "origin = origin + (0, 0, 64);\n",
            "angles forward": "forward = anglesToForward(self getPlayerAngles());\n",
            "normalize vector": "dir = vectorNormalize(target.origin - self.origin);\n",
            "precache model": "precacheModel(\"model_name\");\n",
            "precache shader": "precacheShader(\"shader_name\");\n",
            "precache fx": "level._effect[\"name\"] = loadFx(\"fx/path/name\");\n",
            "include utility": "#include common_scripts\\utility;\n",
            "include mp utility": "#include maps\\mp\\_utility;\n",
            "comment header": (
                "/*\n"
                " * Name:\n"
                " * Purpose:\n"
                " */\n"
            ),
        }

    def insert_snippet(self):
        try:
            editor = self.current_editor()
            if editor is None:
                return
            name = self.snippet_combo.currentText()
            snippet = self.snippets.get(name, "")
            if not snippet:
                return
            cursor = editor.textCursor()
            cursor.insertText(snippet)
            editor.setTextCursor(cursor)
            editor.setFocus()
            self.schedule_symbols_refresh()
        except Exception as e:
            try:
                self.log_exception("insert_snippet", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))

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
            # Quick checks: control/non-printable characters and suspicious tokens
            try:
                for ci, ch in enumerate(line):
                    if unicodedata.category(ch) == 'Cc' and ch not in ('\t', '\n', '\r'):
                        errors.append({'line': i, 'col': ci, 'len': 1, 'msg': 'Control/non-printable character detected'})
                        break
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
            try:
                # suspicious token heuristic: tokens with length>=4 but zero alphabetic chars
                toks = re.findall(r"\S+", line)
                for t in toks:
                    if len(t) >= 4:
                        alpha_count = sum(1 for c in t if c.isalpha())
                        non_ascii = sum(1 for c in t if ord(c) > 127)
                        if alpha_count == 0 or non_ascii > (len(t) // 2):
                            col = line.find(t)
                            errors.append({'line': i, 'col': col if col >= 0 else 0, 'len': max(1, len(t)), 'msg': 'Suspicious token or non-ASCII text'})
                            break
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
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
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
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
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
            try:
                cursor = QTextCursor(editor.document())
                cursor.setPosition(start_pos)
                cursor.setPosition(start_pos + length, QTextCursor.MoveMode.KeepAnchor)
                sel = QTextEdit.ExtraSelection()
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
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
                editor.setExtraSelections(sels)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))

        return False

    def goto_error(self, url):
        s = url.toString()
        # support both `pos:LINE:COL` anchors (from linter) and legacy `line:LINE`
        ln = None
        col = None
        if s.startswith('pos:'):
            parts = s.split(':')
            if len(parts) >= 3:
                try:
                    ln = int(parts[1])
                    col = int(parts[2])
                except Exception:
                    return
        elif s.startswith('line:'):
            try:
                ln = int(s.split(':', 1)[1])
            except Exception:
                return

        if ln is None:
            return

        # move cursor to the target position (line + optional column)
        editor = self.current_editor()
        if editor is None:
            return
        block = editor.document().findBlockByNumber(ln - 1)
        if not block.isValid():
            return

        target_pos = block.position()
        if col is not None:
            try:
                target_pos += int(col)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))

        cursor = editor.textCursor()
        cursor.setPosition(target_pos)
        editor.setTextCursor(cursor)
        editor.setFocus()
        # highlight the line briefly
        try:
            from PyQt6.QtGui import QTextCharFormat
            sel = QTextEdit.ExtraSelection()
            fmt = QTextCharFormat()
            fmt.setBackground(QColor('#3a2b2b'))
            sel.format = fmt
            sel.cursor = editor.textCursor()
            editor.setExtraSelections([sel])
            QTimer.singleShot(1200, lambda: editor.setExtraSelections([]))
        except Exception as e:
            try:
                if hasattr(self, 'log_exception'):
                    self.log_exception("suppressed exception", e)
                else:
                    traceback.print_exc()
            except Exception:
                try:
                    traceback.print_exc()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

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
    
    def find_next(self):
        try:
            needle = self.find_input.text()
        except Exception:
            return
        if not needle:
            return
        editor = self.current_editor()
        if editor is None:
            return
        try:
            found = False
            try:
                found = editor.find(needle)
            except Exception:
                found = False

            # If not found, try wrapping: move cursor to start and search again
            if not found:
                try:
                    cur = editor.textCursor()
                    cur.setPosition(0)
                    editor.setTextCursor(cur)
                    found = editor.find(needle)
                    if found:
                        # optional: inform user that search wrapped
                        try:
                            if getattr(self, 'error_console', None):
                                self.error_console.append(f"Find: wrapped and found '{needle}'")
                        except Exception as e:
                            _handle_suppressed(e, locals().get('self', None))
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

            if not found:
                try:
                    if getattr(self, 'error_console', None):
                        self.error_console.append(f"Find: '{needle}' not found")
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
            else:
                try:
                    editor.centerCursor()
                    editor.setFocus()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
        except Exception as e:
            try:
                if hasattr(self, 'log_exception'):
                    self.log_exception("suppressed exception", e)
                else:
                    traceback.print_exc()
            except Exception:
                try:
                    traceback.print_exc()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

    def find_previous(self):
        try:
            needle = self.find_input.text()
        except Exception:
            return
        if not needle:
            return
        editor = self.current_editor()
        if editor is None:
            return
        try:
            text = editor.toPlainText()
            cursor = editor.textCursor()
            pos = cursor.selectionEnd() if cursor.hasSelection() else cursor.position()
            # search backwards from just before current position
            if pos > 0:
                idx = text.rfind(needle, 0, max(0, pos-1))
            else:
                idx = -1

            wrapped = False
            if idx == -1:
                # wrap: search from end
                idx = text.rfind(needle)
                wrapped = idx != -1

            if idx == -1:
                try:
                    if getattr(self, 'error_console', None):
                        self.error_console.append(f"Find: '{needle}' not found")
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
                return

            # position cursor at found index
            try:
                cur = editor.textCursor()
                cur.setPosition(idx)
                cur.setPosition(idx + len(needle), QTextCursor.MoveMode.KeepAnchor)
                editor.setTextCursor(cur)
                editor.centerCursor()
                editor.setFocus()
                if wrapped:
                    try:
                        if getattr(self, 'error_console', None):
                            self.error_console.append(f"Find: wrapped and found '{needle}'")
                    except Exception as e:
                        _handle_suppressed(e, locals().get('self', None))
            except Exception as e:
                try:
                    if hasattr(self, 'log_exception'):
                        self.log_exception("suppressed exception", e)
                    else:
                        traceback.print_exc()
                except Exception:
                    try:
                        traceback.print_exc()
                    except Exception as e:
                        _handle_suppressed(e, locals().get('self', None))
        except Exception as e:
            try:
                if hasattr(self, 'log_exception'):
                    self.log_exception("suppressed exception", e)
                else:
                    traceback.print_exc()
            except Exception:
                try:
                    traceback.print_exc()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

    def show_find(self, find_only=True):
        try:
            # if find_only is True we hide the replace input
            if getattr(self, 'replace_input', None) is not None:
                self.replace_input.setVisible(not find_only)
            if getattr(self, 'find_widget', None) is None:
                return
            self.find_widget.setVisible(True)
            try:
                self.find_input.setFocus()
                self.find_input.selectAll()
            except Exception as e:
                try:
                    if hasattr(self, 'log_exception'):
                        self.log_exception("suppressed exception", e)
                    else:
                        traceback.print_exc()
                except Exception:
                    try:
                        traceback.print_exc()
                    except Exception as e:
                        _handle_suppressed(e, locals().get('self', None))
        except Exception as e:
            try:
                if hasattr(self, 'log_exception'):
                    self.log_exception("suppressed exception", e)
                else:
                    traceback.print_exc()
            except Exception:
                try:
                    traceback.print_exc()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

    
    def update_game_status(self):
        try:
            game = TargetGame(self.game_combo.currentIndex())
            running = False
            try:
                running = self.injection_manager.is_game_running(game)
            except Exception as e:
                # log but don't crash the UI
                try:
                    self.log(f"Error checking game status: {e}", success=False)
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

            if running:
                self.game_status_label.setText("Game running")
                self.game_status_label.setProperty("state", "ok")
            else:
                self.game_status_label.setText("Game not running")
                self.game_status_label.setProperty("state", "idle")
            self.refresh_widget_style(self.game_status_label)
        except Exception as e:
            try:
                if hasattr(self, 'log_exception'):
                    self.log_exception("suppressed exception", e)
                else:
                    traceback.print_exc()
            except Exception:
                try:
                    traceback.print_exc()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

    def update_plutonium_path(self):
        try:
            try:
                plut_path = self.injection_manager.get_plutonium_path()
            except Exception as e:
                plut_path = None
                try:
                    self.log(f"Error detecting Plutonium path: {e}", success=False)
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

            if plut_path:
                self.plut_path_label.setText("Plutonium detected")
                self.plut_path_label.setToolTip(plut_path)
                self.plut_path_label.setProperty("state", "ok")
            else:
                self.plut_path_label.setText("Plutonium not detected")
                self.plut_path_label.setToolTip("Expected: %localappdata%\\Plutonium\\storage")
                self.plut_path_label.setProperty("state", "error")
            self.refresh_widget_style(self.plut_path_label)
        except Exception:
            try:
                self.plut_path_label.setText("Plutonium detection error")
                self.plut_path_label.setProperty("state", "error")
                self.refresh_widget_style(self.plut_path_label)
            except Exception as e:
                try:
                    if hasattr(self, 'log_exception'):
                        self.log_exception("suppressed exception", e)
                    else:
                        traceback.print_exc()
                except Exception:
                    try:
                        traceback.print_exc()
                    except Exception as e:
                        _handle_suppressed(e, locals().get('self', None))

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
            if on:
                self.caps_label.setText("CAPS ON")
                self.caps_label.setProperty("state", "error")
            else:
                self.caps_label.setText("CAPS OFF")
                self.caps_label.setProperty("state", "idle")
            self.refresh_widget_style(self.caps_label)
        except Exception as e:
            try:
                if hasattr(self, 'log_exception'):
                    self.log_exception("suppressed exception", e)
                else:
                    traceback.print_exc()
            except Exception:
                try:
                    traceback.print_exc()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
    
    def new_file(self):
        # create a new tab with default template
        self.new_tab()
    
    def open_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open GSC Script", "", "GSC/GSCR Files (*.gsc *.gscr);;GSC Files (*.gsc);;GSCR Files (*.gscr);;All Files (*)"
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
                    self.install_tab_close_button(editor)
                try:
                    self.remove_autosave_for(editor)
                except Exception as e:
                    try:
                        self.log_exception("save_file: remove_autosave_for", e)
                    except Exception as e:
                        _handle_suppressed(e, locals().get('self', None))
            except Exception as ex:
                QMessageBox.warning(self, "Error", f"Failed to save: {ex}")
        else:
            self.save_file_as()
    
    def save_file_as(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save GSC Script", "", "GSC/GSCR Files (*.gsc *.gscr);;GSC Files (*.gsc);;GSCR Files (*.gscr);;All Files (*)"
        )
        if filename:
            editor = self.current_editor()
            try:
                # ensure default extension if user omitted one
                if not os.path.splitext(filename)[1]:
                    filename = f"{filename}.gsc"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(editor.toPlainText())
                self.tab_paths[editor] = filename
                editor.document().setModified(False)
                idx = self.tab_widget.indexOf(editor)
                if idx >= 0:
                    self.tab_widget.setTabText(idx, os.path.basename(filename))
                    self.install_tab_close_button(editor)
                self.log(f"Saved: {filename}")
                self.add_recent_file(filename)
                # run linter after save
                try:
                    self.lint_script()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
            except Exception as ex:
                QMessageBox.warning(self, "Error", f"Failed to save: {ex}")
            try:
                self.remove_autosave_for(editor)
            except Exception as e:
                try:
                    self.log_exception("save_file_as: remove_autosave_for", e)
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

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
            except Exception as e:
                try:
                    self.log_exception("update_recent_menu: set action icon", e)
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
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
            except Exception as e:
                try:
                    self.log_exception("update_recent_menu: clear_act shortcut", e)
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

    # --- Preferences dialog ---
    def open_preferences(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Preferences")
        layout = QVBoxLayout(dlg)
        form = QFormLayout()

        font_spin = QSpinBox()
        font_spin.setRange(6, 48)
        current = self.current_editor() or self.editor
        font_spin.setValue(current.font().pointSize())
        form.addRow("Editor font size:", font_spin)

        style_label = QLabel("Workbench Dark")
        style_label.setObjectName("helperText")
        form.addRow("Visual style:", style_label)

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
                current_editor = self.current_editor() or self.editor
                self.set_editor_font_size(font_spin.value() - current_editor.font().pointSize())
            except Exception as e:
                try:
                    self.log_exception("preferences:on_save editor_font_size", e)
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
            try:
                self.settings.setValue('theme', 'workbench')
                self.apply_theme('workbench')
            except Exception as e:
                try:
                    self.log_exception("preferences:on_save apply_theme", e)
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
            # persist live lint preference
            try:
                self.settings.setValue('lint_live', lint_chk.isChecked())
            except Exception as e:
                try:
                    self.log_exception("preferences:on_save lint_live", e)
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

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
                except Exception as e:
                    try:
                        self.log_exception("preferences:on_save set_custom_paths", e)
                    except Exception as e:
                        _handle_suppressed(e, locals().get('self', None))
                # refresh displayed path immediately after applying overrides
                try:
                    self.update_plutonium_path()
                except Exception as e:
                    try:
                        self.log_exception("preferences:on_save update_plutonium_path", e)
                    except Exception as e:
                        _handle_suppressed(e, locals().get('self', None))
            except Exception as e:
                try:
                    self.log_exception("preferences:on_save save overrides", e)
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

            # if live lint enabled, run an immediate lint to refresh markers
            try:
                if lint_chk.isChecked():
                    QTimer.singleShot(50, lambda: self.lint_script())
            except Exception as e:
                try:
                    self.log_exception("preferences:on_save schedule lint", e)
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

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
        try:
            game = TargetGame(self.game_combo.currentIndex())
            method = InjectionMethod(self.method_combo.currentIndex())
            mode = GameMode(self.mode_combo.currentIndex())
            script_name = self.script_name.text()
            editor = self.current_editor()
            script_content = editor.toPlainText() if editor else ''

            try:
                success, message = self.injection_manager.inject_script(
                    script_content, game, method, mode, script_name
                )
            except Exception as e:
                success = False
                message = f"Injection error: {e}"
                try:
                    self.log(message, success=False)
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

            if success:
                self.log(f"OK: {message}", success=True)
                try:
                    self.lint_script()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
                QMessageBox.information(
                    self, "Success",
                    f"{message}\n\nRestart Plutonium to load the script."
                )
            else:
                self.log(f"ERROR: {message}", success=False)
                QMessageBox.warning(self, "Deployment Failed", message)
        except Exception as e:
            try:
                self.log(f"Unexpected error during deployment: {e}", success=False)
            except Exception as e:
                try:
                    if hasattr(self, 'log_exception'):
                        self.log_exception("suppressed exception", e)
                    else:
                        traceback.print_exc()
                except Exception:
                    try:
                        traceback.print_exc()
                    except Exception as e:
                        _handle_suppressed(e, locals().get('self', None))
    
    def open_scripts_folder(self):
        try:
            game = TargetGame(self.game_combo.currentIndex())
            mode = GameMode(self.mode_combo.currentIndex())
            try:
                path = self.injection_manager.get_script_path(game, mode)
            except Exception as e:
                path = None
                try:
                    self.log(f"Error getting scripts folder: {e}", success=False)
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

            if path and os.path.exists(path):
                try:
                    os.startfile(path)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Unable to open folder: {e}")
            else:
                QMessageBox.warning(self, "Error", "Scripts folder not found")
        except Exception as e:
            try:
                if hasattr(self, 'log_exception'):
                    self.log_exception("suppressed exception", e)
                else:
                    traceback.print_exc()
            except Exception:
                try:
                    traceback.print_exc()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

    # --- Tab management ---
    def install_tab_close_button(self, editor: GSCEditor):
        try:
            idx = self.tab_widget.indexOf(editor)
            if idx < 0:
                return
            close_btn = QToolButton()
            close_btn.setObjectName("tabCloseButton")
            close_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton))
            close_btn.setIconSize(QSize(8, 8))
            close_btn.setFixedSize(14, 14)
            close_btn.setAutoRaise(True)
            close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            close_btn.setToolTip("Close tab")
            close_btn.clicked.connect(lambda checked=False, ed=editor: self.close_tab(self.tab_widget.indexOf(ed)))
            self.tab_widget.tabBar().setTabButton(idx, self.tab_widget.tabBar().ButtonPosition.RightSide, close_btn)
        except Exception as e:
            try:
                self.log_exception("install_tab_close_button", e)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))

    def new_tab(self, filename: str = None, content: str = None):
        editor = GSCEditor()
        if content is None:
            content = editor.get_default_template()
        editor.setPlainText(content)
        self.tab_paths[editor] = filename
        title = os.path.basename(filename) if filename else "Untitled"
        idx = self.tab_widget.addTab(editor, title)
        self.tab_widget.setCurrentIndex(idx)
        self.apply_saved_editor_font_size(editor)
        self.install_tab_close_button(editor)
        self.attach_editor_signals(editor)
        return editor

    def close_tab(self, index: int):
        try:
            if index < 0:
                return
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
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
            self.tab_widget.removeTab(index)
        except Exception as e:
            try:
                if hasattr(self, 'log_exception'):
                    self.log_exception("suppressed exception", e)
                else:
                    traceback.print_exc()
            except Exception:
                try:
                    traceback.print_exc()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
    
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
            except Exception as e:
                try:
                    if hasattr(self, 'log_exception'):
                        self.log_exception("suppressed exception", e)
                    else:
                        traceback.print_exc()
                except Exception:
                    try:
                        traceback.print_exc()
                    except Exception as e:
                        _handle_suppressed(e, locals().get('self', None))

    # Theme handling
    def apply_theme(self, theme_name: str):
        self.current_theme = 'workbench'
        try:
            self.setStyleSheet(self.base_css)
        except Exception as e:
            try:
                if hasattr(self, 'log_exception'):
                    self.log_exception("suppressed exception", e)
                else:
                    traceback.print_exc()
            except Exception:
                try:
                    traceback.print_exc()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

        try:
            self.settings.setValue('theme', 'workbench')
        except Exception as e:
            try:
                if hasattr(self, 'log_exception'):
                    self.log_exception("suppressed exception", e)
                else:
                    traceback.print_exc()
            except Exception:
                try:
                    traceback.print_exc()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

    def toggle_theme(self):
        self.apply_theme('workbench')
        try:
            self.log("Workbench theme refreshed.")
        except Exception as e:
            _handle_suppressed(e, locals().get('self', None))

    def set_editor_font_size(self, delta: int):
        try:
            editor = self.current_editor()
            if editor is None:
                return
            font = editor.font()
            size = font.pointSize()
            if size < 6:
                size = 11
            new_size = max(6, size + delta)
            for i in range(self.tab_widget.count()):
                tab_editor = self.tab_widget.widget(i)
                if not isinstance(tab_editor, GSCEditor):
                    continue
                tab_font = tab_editor.font()
                tab_font.setPointSize(new_size)
                tab_editor.setFont(tab_font)
                tab_editor.update_line_number_area_width(0)
            try:
                self.settings.setValue('editor_font_size', new_size)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
        except Exception as e:
            try:
                if hasattr(self, 'log_exception'):
                    self.log_exception("suppressed exception", e)
                else:
                    traceback.print_exc()
            except Exception:
                try:
                    traceback.print_exc()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

    def closeEvent(self, event):
        # Persist panel visibility and theme on close
        try:
            self.settings.setValue('panel_injection', self.injection_group.isVisible())
            self.settings.setValue('panel_output', self.output_group.isVisible())
            self.settings.setValue('theme', 'workbench')
        except Exception as e:
            try:
                if hasattr(self, 'log_exception'):
                    self.log_exception("suppressed exception", e)
                else:
                    traceback.print_exc()
            except Exception:
                try:
                    traceback.print_exc()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
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
                        except Exception as e:
                            _handle_suppressed(e, locals().get('self', None))
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
                        except Exception as e:
                            _handle_suppressed(e, locals().get('self', None))
                    except Exception as e:
                        _handle_suppressed(e, locals().get('self', None))

            if preserve_autosave:
                # ensure latest content is saved for recovery
                try:
                    self.autosave_all()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
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
                            except Exception as e:
                                _handle_suppressed(e, locals().get('self', None))
                        try:
                            os.remove(self.autosave_index)
                        except Exception as e:
                            _handle_suppressed(e, locals().get('self', None))
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
        except Exception as e:
            try:
                if hasattr(self, 'log_exception'):
                    self.log_exception("suppressed exception", e)
                else:
                    traceback.print_exc()
            except Exception:
                try:
                    traceback.print_exc()
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
        try:
            super().closeEvent(event)
        except Exception:
            event.accept()

    def eventFilter(self, obj, event):
        # Close the find widget on Escape when editor has focus
        try:
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                if key == Qt.Key.Key_Escape and getattr(self, 'find_widget', None) and self.find_widget.isVisible():
                    self.find_widget.setVisible(False)
                    return True
        except Exception as e:
            _handle_suppressed(e, locals().get('self', None))
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
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
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
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))

            # write index
            try:
                if entries:
                    with open(self.autosave_index, 'w', encoding='utf-8') as f:
                        json.dump(entries, f)
                else:
                    # remove index if no entries
                    if os.path.exists(self.autosave_index):
                        os.remove(self.autosave_index)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
        except Exception as e:
            _handle_suppressed(e, locals().get('self', None))

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
                except Exception as e:
                    _handle_suppressed(e, locals().get('self', None))
            # remove autosave artifacts after recovery
            try:
                for e in entries:
                    p = os.path.join(self.autosave_dir, e.get('file'))
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except Exception as e:
                        _handle_suppressed(e, locals().get('self', None))
                if os.path.exists(self.autosave_index):
                    os.remove(self.autosave_index)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
        except Exception as e:
            _handle_suppressed(e, locals().get('self', None))

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
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
            # update index
            try:
                entries = []
                # include all autosave files currently tracked
                for ed, fname in list(self.autosave_map.items()):
                    entries.append({'file': fname, 'filename': self.tab_paths.get(ed)})
                with open(self.autosave_index, 'w', encoding='utf-8') as f:
                    json.dump(entries, f)
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
        except Exception as e:
            _handle_suppressed(e, locals().get('self', None))

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
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
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
            except Exception as e:
                _handle_suppressed(e, locals().get('self', None))
        except Exception as e:
            _handle_suppressed(e, locals().get('self', None))


def main():
    app = QApplication(sys.argv)
    # Ensure the app uses the bundled icon for the taskbar and windows
    try:
        from PyQt6.QtGui import QIcon
        icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.png')
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        else:
            # fall back to a generic icon if not present
            app.setWindowIcon(QIcon())
    except Exception as e:
        _handle_suppressed(e, locals().get('self', None))

    window = GSCIDEWindow()
    try:
        # also set window icon explicitly
        from PyQt6.QtGui import QIcon
        icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.png')
        if os.path.exists(icon_path):
            window.setWindowIcon(QIcon(icon_path))
    except Exception as e:
        _handle_suppressed(e, locals().get('self', None))

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()




