
import subprocess
import sys
import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QComboBox, QSpinBox, QPushButton, QMessageBox,
                               QGroupBox, QCheckBox)
from PySide6.QtCore import Signal, QProcess

class AlgorithmPanel(QWidget):
    optimization_started = Signal(str, int)  # algorithm, k
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.process = None
        
        self._setup_ui()
        
    def _setup_ui(self):
        # Header
        header = QLabel("Algorithm Control")
        header.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        self.layout.addWidget(header)
        
        # Controls Group
        group = QGroupBox("Configuration")
        form_layout = QVBoxLayout()
        
        # Algorithm Selection
        form_layout.addWidget(QLabel("Algorithm:"))
        self.algo_combo = QComboBox()
        self.algo_combo.addItems(["greedy"])
        form_layout.addWidget(self.algo_combo)
        
        # K Parameter
        form_layout.addWidget(QLabel("Allocations (k):"))
        self.k_spinner = QSpinBox()
        self.k_spinner.setRange(1, 10)
        self.k_spinner.setValue(1)
        form_layout.addWidget(self.k_spinner)
        
        # Data Options
        form_layout.addSpacing(10)
        form_layout.addWidget(QLabel("Data Options:"))
        
        self.reload_data_cb = QCheckBox("Reload OSM Data")
        self.reload_data_cb.setToolTip("Uncheck to use existing database (Faster)")
        self.reload_data_cb.setChecked(False) # Default skip
        form_layout.addWidget(self.reload_data_cb)
        
        self.recalc_dist_cb = QCheckBox("Recalculate Distances")
        self.recalc_dist_cb.setToolTip("Uncheck to use existing distances (Faster)")
        self.recalc_dist_cb.setChecked(False) # Default skip
        form_layout.addWidget(self.recalc_dist_cb)
        
        # Fast Mode Note
        note = QLabel("Note: Using skips for speed")
        note.setStyleSheet("color: gray; font-size: 10px;")
        form_layout.addWidget(note)
        
        group.setLayout(form_layout)
        self.layout.addWidget(group)
        
        # Buttons
        self.run_btn = QPushButton("Run Optimization")
        self.run_btn.setStyleSheet("background-color: #3498db; color: white; padding: 8px;")
        self.run_btn.clicked.connect(self._run_optimization)
        self.layout.addWidget(self.run_btn)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setStyleSheet("background-color: #e74c3c; color: white; padding: 8px;")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_optimization)
        self.layout.addWidget(self.stop_btn)
        
        self.layout.addStretch()

    def _run_optimization(self):
        algo = self.algo_combo.currentText()
        k = self.k_spinner.value()
        
        # Confirm
        # msg = QMessageBox()
        # msg.setIcon(QMessageBox.Information)
        # msg.setText(f"Start {algo} optimization with k={k}?")
        # msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        # if msg.exec() != QMessageBox.Ok:
        #     return
            
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        # Emit signal immediately for UI feedback
        self.optimization_started.emit(algo, k)
        
        # Construct command
        # python -m src.main --skip-data-load --skip-distances --visualize --algorithm {algo} --k {k}
        
        project_root = os.getcwd() # Assumes running from project root
        
        self.process = QProcess(self)
        self.process.setWorkingDirectory(project_root)
        
        # We use the same venv python
        python_exe = sys.executable 
        
        args = [
            "-m", "src.main",
            "--visualize",
            "--evaluate",  # Ensure full report is generated
            "--algorithm", algo,
            "--k", str(k)
        ]
        
        # Add skip flags only if checkboxes are NOT checked
        if not self.reload_data_cb.isChecked():
            args.append("--skip-data-load")
            
        if not self.recalc_dist_cb.isChecked():
            args.append("--skip-distances")
        
        # Clean up old logs so UI doesn't show stale info
        for f in ["pipeline_run.log", "PROGRESS.txt"]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass
        
        print(f"Starting process: {python_exe} {args}")
        
        # Redirect output to file so StatusMonitor can read it
        self.process.setStandardOutputFile("pipeline_run.log")
        self.process.setStandardErrorFile("pipeline_run.log")
        
        self.process.start(python_exe, args)
        self.process.finished.connect(self._on_finished)

    def _stop_optimization(self):
        if self.process and self.process.state() == QProcess.Running:
            self.process.kill()
            self.stop_btn.setEnabled(False)
            self.run_btn.setEnabled(True)

    def _on_finished(self, exit_code, exit_status):
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        print(f"Process finished with code {exit_code}")
