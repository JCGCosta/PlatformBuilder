from pathlib import Path

import ast
import rdflib
from pygments.lexers import PythonLexer, TurtleLexer, JsonLexer
from pygments.token import Token

from PySide6.QtWidgets import QPlainTextEdit, QWidget, QTabWidget, QTextEdit, QMessageBox, QVBoxLayout, QLabel
from PySide6.QtGui import (QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QPainter, QTextFormat, QKeySequence,
                           QShortcut, QTextCursor)
from PySide6.QtCore import Qt, QRect, QSize, Signal

LEXERS = {"py": PythonLexer, "ttl": TurtleLexer, "owl": TurtleLexer, "json": JsonLexer}

# token type -> (color, style); the first token type that matches (walking up the hierarchy) wins
DARK = {
    "bg": "#1e1e1e", "fg": "#d4d4d4", "gutter_bg": "#252526", "gutter_fg": "#858585", "line": "#2a2d2e",
    "tokens": {
        Token.Keyword: ("#c586c0", "bold"), Token.Keyword.Constant: ("#569cd6", ""),
        Token.Name.Function: ("#dcdcaa", ""), Token.Name.Class: ("#4ec9b0", "bold"),
        Token.Name.Decorator: ("#dcdcaa", ""), Token.Name.Builtin: ("#4fc1ff", ""),
        Token.Name.Namespace: ("#4ec9b0", ""), Token.Name.Tag: ("#569cd6", ""),
        Token.Name.Variable: ("#9cdcfe", ""), Token.Name.Attribute: ("#9cdcfe", ""),
        Token.Literal.String: ("#ce9178", ""), Token.Literal.Number: ("#b5cea8", ""),
        Token.Comment: ("#6a9955", "italic"), Token.Operator: ("#d4d4d4", ""),
        Token.Operator.Word: ("#c586c0", "bold"),
    },
}
LIGHT = {
    "bg": "#ffffff", "fg": "#1e1e1e", "gutter_bg": "#f0f0f0", "gutter_fg": "#999999", "line": "#f3f6fa",
    "tokens": {
        Token.Keyword: ("#af00db", "bold"), Token.Keyword.Constant: ("#0000ff", ""),
        Token.Name.Function: ("#795e26", ""), Token.Name.Class: ("#267f99", "bold"),
        Token.Name.Decorator: ("#795e26", ""), Token.Name.Builtin: ("#0070c1", ""),
        Token.Name.Namespace: ("#267f99", ""), Token.Name.Tag: ("#0000ff", ""),
        Token.Name.Variable: ("#001080", ""), Token.Name.Attribute: ("#001080", ""),
        Token.Literal.String: ("#a31515", ""), Token.Literal.Number: ("#098658", ""),
        Token.Comment: ("#008000", "italic"), Token.Operator: ("#1e1e1e", ""),
        Token.Operator.Word: ("#af00db", "bold"),
    },
}


class PygmentsHighlighter(QSyntaxHighlighter):
    """Highlights with the pygments lexer of the file type. Multi-line tokens (docstrings) are handled by lexing the
    whole document once per change and caching the formatted ranges per block."""

    def __init__(self, document, file_type="py", palette=DARK):
        super().__init__(document)
        self.lexer = LEXERS.get(file_type, PythonLexer)(stripnl=False, ensurenl=False)
        self.set_palette(palette, rehighlight=False)
        self._spans = {}
        self._cached_for = None

    def set_palette(self, palette, rehighlight=True):
        self.formats = {}
        for token, (color, style) in palette["tokens"].items():
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if "bold" in style:
                fmt.setFontWeight(QFont.Weight.Bold)
            if "italic" in style:
                fmt.setFontItalic(True)
            self.formats[token] = fmt
        self._cached_for = None
        if rehighlight:
            self.rehighlight()

    def _format_of(self, token):
        while token is not Token:
            if token in self.formats:
                return self.formats[token]
            token = token.parent
        return None

    def _lex_document(self):
        text = self.document().toPlainText()
        self._spans = {}
        block = self.document().begin()
        starts = []
        while block.isValid():
            starts.append(block.position())
            block = block.next()
        line = 0
        for index, token, value in self.lexer.get_tokens_unprocessed(text):
            fmt = self._format_of(token)
            if fmt is None:
                continue
            end = index + len(value)
            # split the token over the blocks it covers
            while line + 1 < len(starts) and starts[line + 1] <= index:
                line += 1
            cur, cur_line = index, line
            while cur < end:
                next_start = starts[cur_line + 1] if cur_line + 1 < len(starts) else end
                seg_end = min(end, next_start)
                self._spans.setdefault(cur_line, []).append((cur - starts[cur_line], seg_end - cur, fmt))
                cur, cur_line = seg_end, cur_line + 1
        self._cached_for = self.document().revision()

    def highlightBlock(self, text):
        if self._cached_for != self.document().revision():
            self._lex_document()
        for start, length, fmt in self._spans.get(self.currentBlock().blockNumber(), []):
            self.setFormat(start, length, fmt)


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.code = editor

    def sizeHint(self):
        return QSize(self.code.gutter_width(), 0)

    def paintEvent(self, event):
        self.code.paint_gutter(event)


class CodeTextEdit(QPlainTextEdit):
    """Plain text editor with line numbers, current line highlight, auto indent and spaces for tabs."""
    INDENT = "    "

    def __init__(self):
        super().__init__()
        self.palette_colors = DARK
        self.gutter = LineNumberArea(self)
        self.error_line = None
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self.cursorPositionChanged.connect(self._highlight_lines)
        self._update_gutter_width()
        self._highlight_lines()

    def apply_font(self, font: QFont):
        font = QFont(font)
        font.setFamilies(["JetBrains Mono", "Fira Code", "DejaVu Sans Mono", "Consolas", "Courier New"])
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self._update_gutter_width()

    def apply_palette(self, palette):
        self.palette_colors = palette
        self.setStyleSheet(f"QPlainTextEdit {{ background-color: {palette['bg']}; color: {palette['fg']}; border: none; }}")
        self._highlight_lines()
        self.gutter.update()

    def set_error_line(self, line):
        self.error_line = line
        self._highlight_lines()

    # -- gutter ------------------------------------------------------------
    def gutter_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 16 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_gutter_width(self, *_):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _update_gutter(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def paint_gutter(self, event):
        painter = QPainter(self.gutter)
        painter.fillRect(event.rect(), QColor(self.palette_colors["gutter_bg"]))
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        current = self.textCursor().blockNumber()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                color = self.palette_colors["fg"] if number == current else self.palette_colors["gutter_fg"]
                if self.error_line == number + 1:
                    color = "#f44747"
                painter.setPen(QColor(color))
                painter.drawText(0, top, self.gutter.width() - 8, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, str(number + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1

    def _highlight_lines(self):
        selections = []
        current = QTextEdit.ExtraSelection()
        current.format.setBackground(QColor(self.palette_colors["line"]))
        current.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        current.cursor = self.textCursor()
        current.cursor.clearSelection()
        selections.append(current)
        if self.error_line:
            err = QTextEdit.ExtraSelection()
            err.format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
            err.format.setUnderlineColor(QColor("#f44747"))
            block = self.document().findBlockByNumber(self.error_line - 1)
            if block.isValid():
                err.cursor = QTextCursor(block)
                err.cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                selections.append(err)
        self.setExtraSelections(selections)
        self.gutter.update()

    # -- editing helpers -----------------------------------------------------
    def keyPressEvent(self, event):
        cursor = self.textCursor()
        key = event.key()
        if key == Qt.Key.Key_Tab and not event.modifiers():
            if cursor.hasSelection():
                self._indent_selection(True)
            else:
                cursor.insertText(self.INDENT)
            return
        if key == Qt.Key.Key_Backtab:
            self._indent_selection(False)
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            line = cursor.block().text()[:cursor.positionInBlock()]
            indent = line[:len(line) - len(line.lstrip())]
            if line.rstrip().endswith(":"):
                indent += self.INDENT
            super().keyPressEvent(event)
            self.insertPlainText(indent)
            return
        if key == Qt.Key.Key_Backspace and not cursor.hasSelection():
            before = cursor.block().text()[:cursor.positionInBlock()]
            if before and not before.strip() and len(before) % 4 == 0:  # delete a whole indent level
                cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, 4)
                cursor.removeSelectedText()
                return
        super().keyPressEvent(event)

    def _indent_selection(self, indent: bool):
        cursor = self.textCursor()
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        doc = self.document()
        first, last = doc.findBlock(start), doc.findBlock(max(start, end - 1) if end > start else start)
        cursor.beginEditBlock()
        block = first
        while block.isValid() and block.blockNumber() <= last.blockNumber():
            c = QTextCursor(block)
            if indent:
                c.insertText(self.INDENT)
            else:
                text = block.text()
                remove = min(len(text) - len(text.lstrip(" ")), 4)
                c.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, remove)
                c.removeSelectedText()
            block = block.next()
        cursor.endEditBlock()


class EditorTab(QWidget):
    """One open file: the text editor plus its highlighter and syntax check."""
    status = Signal(str)
    modified_changed = Signal()

    def __init__(self, path: Path, palette, font):
        super().__init__()
        self.path = path
        self.file_type = path.suffix.lstrip(".").lower()
        self.text = CodeTextEdit()
        self.text.apply_font(font)
        self.text.apply_palette(palette)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text)
        self.text.setPlainText(path.read_text(encoding="utf-8"))
        self.text.document().setModified(False)
        self.highlighter = PygmentsHighlighter(self.text.document(), self.file_type, palette)
        self.text.document().modificationChanged.connect(lambda _: self.modified_changed.emit())
        self.syntax_error = ""
        self.status_text = ""
        self.text.textChanged.connect(self.check_syntax)
        self.text.cursorPositionChanged.connect(self.emit_status)
        self.check_syntax()

    def is_modified(self) -> bool:
        return self.text.document().isModified()

    def save(self):
        self.path.write_text(self.text.toPlainText(), encoding="utf-8")
        self.text.document().setModified(False)

    def set_palette(self, palette):
        self.text.apply_palette(palette)
        self.highlighter.set_palette(palette)

    def check_syntax(self):
        """Sets the error underline and the status message."""
        code = self.text.toPlainText()
        self.syntax_error = ""
        line = None
        try:
            if self.file_type == "py":
                ast.parse(code)
            elif self.file_type in ("ttl", "owl"):
                rdflib.Graph().parse(data=code, format="turtle")
        except SyntaxError as e:
            self.syntax_error, line = f"Python syntax error: {e.msg} (line {e.lineno})", e.lineno
        except Exception as e:
            self.syntax_error = f"Turtle syntax error: {str(e).splitlines()[0] if str(e) else e}"
            line = None
        self.text.set_error_line(line)
        self.emit_status()

    def emit_status(self):
        cursor = self.text.textCursor()
        position = f"Ln {cursor.blockNumber() + 1}, Col {cursor.positionInBlock() + 1}"
        self.status_text = f"{self.syntax_error}    |    {position}" if self.syntax_error else f"{position}    |    No syntax errors"
        self.status.emit(self.status_text)


class CodeEditor(QWidget):
    """Tabbed code editor: .py/.ttl/.owl/.json files with syntax highlight, line numbers, syntax check and Ctrl+S."""
    files_saved = Signal()

    def __init__(self):
        super().__init__()
        self.dark = True
        self.font = QFont()
        self.font.setPointSize(12)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        layout.addWidget(self.tabs)
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        self.tabs.currentChanged.connect(lambda _: self._show_status())
        QShortcut(QKeySequence.StandardKey.Save, self, activated=self.save_current)
        QShortcut(QKeySequence("Ctrl+W"), self, activated=lambda: self.close_tab(self.tabs.currentIndex()))

    @property
    def palette_colors(self):
        return DARK if self.dark else LIGHT

    def _tab_for(self, path):
        for i in range(self.tabs.count()):
            if self.tabs.widget(i).path == path:
                return i
        return -1

    def open_file(self, path):
        path = Path(path).resolve()
        index = self._tab_for(path)
        if index < 0:
            try:
                tab = EditorTab(path, self.palette_colors, self.font)
            except (OSError, UnicodeDecodeError) as e:
                QMessageBox.warning(self, "Could not open the file", f"{path.name}: {e}")
                return
            tab.status.connect(lambda msg, t=tab: self.status_label.setText(msg) if self.tabs.currentWidget() is t else None)
            tab.modified_changed.connect(self._update_titles)
            index = self.tabs.addTab(tab, path.name)
            self.tabs.setTabToolTip(index, str(path))
        self.tabs.setCurrentIndex(index)
        self.tabs.currentWidget().text.setFocus()
        self._update_titles()

    def _update_titles(self):
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            self.tabs.setTabText(i, ("● " if tab.is_modified() else "") + tab.path.name)

    def _show_status(self):
        tab = self.tabs.currentWidget()
        if tab:
            tab.emit_status()
        else:
            self.status_label.setText("")

    def save_current(self):
        tab = self.tabs.currentWidget()
        if tab and tab.is_modified():
            tab.save()
            self.files_saved.emit()

    def save_all(self):
        saved = False
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab.is_modified():
                tab.save()
                saved = True
        if saved:
            self.files_saved.emit()

    def has_unsaved(self) -> bool:
        return any(self.tabs.widget(i).is_modified() for i in range(self.tabs.count()))

    def close_tab(self, index) -> bool:
        if index < 0:
            return True
        tab = self.tabs.widget(index)
        if tab.is_modified():
            answer = QMessageBox.question(self, "Unsaved changes", f"Save the changes to {tab.path.name}?",
                                          QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if answer == QMessageBox.Cancel:
                return False
            if answer == QMessageBox.Save:
                tab.save()
                self.files_saved.emit()
        self.tabs.removeTab(index)
        tab.deleteLater()
        return True

    def close_under(self, folder) -> bool:
        """Closes the tabs of the files inside `folder` (asking about unsaved ones). False if the user cancelled."""
        folder = Path(folder).resolve()
        for i in reversed(range(self.tabs.count())):
            path = self.tabs.widget(i).path
            if path == folder or folder in path.parents:
                if not self.close_tab(i):
                    return False
        return True

    def close_all(self) -> bool:
        """Asks about unsaved files; returns False if the user cancelled."""
        while self.tabs.count():
            if not self.close_tab(self.tabs.count() - 1):
                return False
        return True

    def set_font(self, font: QFont):
        self.font = QFont(font)
        for i in range(self.tabs.count()):
            self.tabs.widget(i).text.apply_font(self.font)

    def set_theme(self, dark: bool):
        self.dark = dark
        for i in range(self.tabs.count()):
            self.tabs.widget(i).set_palette(self.palette_colors)
