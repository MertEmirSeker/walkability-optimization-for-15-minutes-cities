
import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTextEdit, QPushButton, 
                               QHBoxLayout, QLabel)

class DetailsDialog(QDialog):
    def __init__(self, parent=None, report_path="results/evaluation_report.txt"):
        super().__init__(parent)
        self.report_path = report_path
        self.setWindowTitle("Optimization Report")
        self.resize(600, 500)
        
        self.layout = QVBoxLayout(self)
        
        # Header
        self.header = QLabel("Optimization Evaluation Report")
        self.header.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.layout.addWidget(self.header)
        
        # Text Area
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("font-family: monospace;")
        self.layout.addWidget(self.text_edit)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_report)
        btn_layout.addWidget(self.refresh_btn)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)
        
        self.layout.addLayout(btn_layout)
        
        self.load_report()
        
    def load_report(self):
        """Load content from the report file."""
        # Resolve path relative to project root if needed
        # Assuming app is run from project root
        
        # If absolute path is not provided and file doesn't exist, try looking in project root
        target_path = self.report_path
        if not os.path.exists(target_path):
             # Try relative to cwd
             target_path = os.path.join(os.getcwd(), self.report_path)
             
        if os.path.exists(target_path):
            with open(target_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.text_edit.setText(content)
        else:
            self.text_edit.setText(f"Report file not found at:\n{target_path}\n\nRun an optimization with --evaluate enabled to generate this report.")
