
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QGroupBox, QProgressBar, QPushButton)
from PySide6.QtCore import Qt

class ResultsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        self._setup_ui()
        
    def _setup_ui(self):
        # Header
        header = QLabel("Optimization Results")
        header.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        self.layout.addWidget(header)
        
        # Progress Section
        self.progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(5)
        progress_layout.setContentsMargins(5, 5, 5, 5)
        
        # Status only
        self.status_label = QLabel("Status: Idle")
        progress_layout.addWidget(self.status_label)
        
        self.progress_group.setLayout(progress_layout)
        self.layout.addWidget(self.progress_group)
        
        # Actions
        self.view_report_btn = QPushButton("View Full Report")
        self.view_report_btn.setStyleSheet("margin-top: 10px;")
        self.layout.addWidget(self.view_report_btn)
        
        self.layout.addStretch()
        
    def update_progress(self, percent: float, status: str, eta: str):
        self.status_label.setText(f"Status: {status}")
        
    def update_metrics(self, score: float, allocations: int, improvement: float):
        self.score_label.setText(f"Avg WalkScore: {score:.2f}")
        self.allocations_label.setText(f"Allocated Amenities: {allocations}")
        if improvement > 0:
            self.improvement_label.setText(f"Last Improvement: +{improvement:.4f}")
            self.improvement_label.setStyleSheet("color: green;")
        else:
            self.improvement_label.setText(f"Last Improvement: {improvement:.4f}")
            self.improvement_label.setStyleSheet("color: black;")
