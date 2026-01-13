
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QLabel,
                               QGroupBox)
from PySide6.QtGui import QTextCursor, QFont
from PySide6.QtCore import Qt

class LogConsole(QWidget):
    """Live log console to display pipeline output in real-time."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        self._setup_ui()
        
    def _setup_ui(self):
        # Header
        header = QLabel("Pipeline Output")
        header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 5px;")
        self.layout.addWidget(header)
        
        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(150)  # Minimum height for bottom dock
        
        # Monospace font for better log readability
        font = QFont("Courier New", 9)
        self.log_text.setFont(font)
        
        # Dark theme for console
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e3e;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        
        self.layout.addWidget(self.log_text)
        
    def append_log(self, text: str):
        """Append text to log console and auto-scroll to bottom."""
        # Handle carriage return (\r) - replace current line instead of appending
        if '\r' in text and '\n' not in text:
            # This is a progress bar update - replace last line
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.select(QTextCursor.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.insertText(text.replace('\r', ''))
        else:
            # Normal text - split by \r and only keep the last part of each line
            lines = text.split('\n')
            for line in lines:
                if '\r' in line:
                    # Take only the last part after \r
                    parts = line.split('\r')
                    line = parts[-1]
                
                if line:  # Don't insert empty lines from split
                    cursor = self.log_text.textCursor()
                    cursor.movePosition(QTextCursor.End)
                    self.log_text.setTextCursor(cursor)
                    
                    # If this is the last line and there are \r characters, replace current line
                    if line == lines[-1] and '\r' in text:
                        cursor.select(QTextCursor.LineUnderCursor)
                        cursor.removeSelectedText()
                        cursor.insertText(line)
                    else:
                        self.log_text.insertPlainText(line + '\n' if line != lines[-1] else line)
        
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def clear(self):
        """Clear log console."""
        self.log_text.clear()
