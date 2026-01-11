
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
        
        self.status_label = QLabel("Status: Idle")
        progress_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        self.time_label = QLabel("ETA: --:--")
        progress_layout.addWidget(self.time_label)
        
        self.progress_group.setLayout(progress_layout)
        self.layout.addWidget(self.progress_group)
        
        # Metrics Section
        self.metrics_group = QGroupBox("Current Metrics")
        metrics_layout = QVBoxLayout()
        
        self.score_label = QLabel("Avg WalkScore: --")
        self.score_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2ecc71;")
        metrics_layout.addWidget(self.score_label)
        
        self.allocations_label = QLabel("Allocated Amenities: 0")
        metrics_layout.addWidget(self.allocations_label)
        
        self.improvement_label = QLabel("Last Improvement: --")
        metrics_layout.addWidget(self.improvement_label)
        
        self.metrics_group.setLayout(metrics_layout)
        self.layout.addWidget(self.metrics_group)
        
        # Actions
        self.view_report_btn = QPushButton("View Full Report")
        self.view_report_btn.setStyleSheet("margin-top: 10px;")
        self.layout.addWidget(self.view_report_btn)
        
        self.layout.addStretch()
        
    def update_progress(self, percent: float, status: str, eta: str):
        self.progress_bar.setValue(int(percent))
        self.status_label.setText(f"Status: {status}")
        self.time_label.setText(f"ETA: {eta}")
        
    def update_metrics(self, score: float, allocations: int, improvement: float):
        self.score_label.setText(f"Avg WalkScore: {score:.2f}")
        self.allocations_label.setText(f"Allocated Amenities: {allocations}")
        if improvement > 0:
            self.improvement_label.setText(f"Last Improvement: +{improvement:.4f}")
            self.improvement_label.setStyleSheet("color: green;")
        else:
            self.improvement_label.setText(f"Last Improvement: {improvement:.4f}")
            self.improvement_label.setStyleSheet("color: black;")
