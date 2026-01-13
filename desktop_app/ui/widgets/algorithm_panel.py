
import subprocess
import sys
import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QComboBox, QSpinBox, QPushButton, QMessageBox,
                               QGroupBox, QCheckBox)
from PySide6.QtCore import Signal, QProcess

class AlgorithmPanel(QWidget):
    optimization_started = Signal(str, int)  # algorithm, k
    progress_updated = Signal(float, str, str) # percent, status, eta
    optimization_finished = Signal(int, str)  # exit_code, status
    log_output = Signal(str)  # log text for console
    
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
        
        # Demo Mode Option
        form_layout.addSpacing(10)
        form_layout.addWidget(QLabel("Run Mode:"))
        
        self.demo_mode_cb = QCheckBox("Demo Mode (Fast Replay ~1 min)")
        self.demo_mode_cb.setToolTip("Replay previously recorded optimization instead of full run")
        self.demo_mode_cb.setChecked(False)
        form_layout.addWidget(self.demo_mode_cb)
        
        # Note
        note = QLabel("Note: Full runs auto-record for demos")
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
        
        # Use -u for unbuffered output to get real-time progress
        args.insert(0, "-u")
        
        # Add demo mode arguments
        if self.demo_mode_cb.isChecked():
            args.append("--demo-mode")
            args.append(f"{algo}_k{k}")
        else:
            # Always record during normal runs
            args.append("--record-demo")
        
        print(f"Starting process: {python_exe} {args}")
        
        # Capture output directly instead of redirecting to file
        # We will write to file manually in the handler
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._handle_output)
        
        self.process.start(python_exe, args)
        self.process.finished.connect(self._on_finished)
        
    def _handle_output(self):
        """Read standard output, parse progress, and write to log file."""
        data = self.process.readAllStandardOutput()
        text = data.data().decode('utf-8', errors='ignore')
        
        # Emit log output for console display
        self.log_output.emit(text)
        
        # Write to log file manually
        with open("pipeline_run.log", "a", encoding='utf-8') as f:
            f.write(text)
            
        # Parse output for progress
        # Format: ::PROGRESS::{global_pct:.1f}::Running Optimization::{eta_str}
        for line in text.splitlines():
            if "::PROGRESS::" in line:
                try:
                    parts = line.split("::")  
                    # parts[0] is empty or text before
                    # parts[1] is PROGRESS
                    # parts[2] is pct
                    # parts[3] is status
                    # parts[4] is eta
                    if len(parts) >= 5:
                        pct = float(parts[2])
                        status = parts[3]
                        eta = parts[4]
                        self.progress_updated.emit(pct, status, eta)
                except Exception as e:
                    print(f"Error parsing progress: {e}")

    def _stop_optimization(self):
        if self.process and self.process.state() == QProcess.Running:
            reply = QMessageBox.question(
                self, "Stop Optimization", 
                "Are you sure you want to stop the optimization process?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.process.kill()
                self.stop_btn.setEnabled(False)
                self.run_btn.setEnabled(True)

    def _on_finished(self, exit_code, exit_status):
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        print(f"Process finished with code {exit_code}")
        
        # Emit finished signal so MainWindow can react
        status_str = "success" if exit_code == 0 else "failed"
        self.optimization_finished.emit(exit_code, status_str)
