
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QStatusBar, QDockWidget)
from PySide6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("15-Minute City Walkability Optimization")
        self.resize(1200, 800)
        
        # Setup UI
        self._setup_ui()
        
    def _setup_ui(self):
        # Central Widget (Map)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main Layout
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Map Widget
        from desktop_app.ui.widgets.map_widget import MapWidget
        self.map_widget = MapWidget()
        self.main_layout.addWidget(self.map_widget)
        
        # Dock Widget for Controls/Results
        self.dock = QDockWidget("Optimization Controls", self)
        self.dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        # Dock Content
        self.dock_content = QWidget()
        self.dock_layout = QVBoxLayout(self.dock_content)
        
        # Algorithm Panel
        from desktop_app.ui.widgets.algorithm_panel import AlgorithmPanel
        self.algo_panel = AlgorithmPanel()
        self.dock_layout.addWidget(self.algo_panel)
        
        # Separator
        from PySide6.QtWidgets import QFrame
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        self.dock_layout.addWidget(line)

        # Results Panel
        from desktop_app.ui.widgets.results_panel import ResultsPanel
        self.results_panel = ResultsPanel()
        self.results_panel.view_report_btn.clicked.connect(self._show_report)
        self.dock_layout.addWidget(self.results_panel)
        
        self.dock_layout.addStretch()
        
        self.dock.setWidget(self.dock_content)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock)
        
        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Start Status Monitor
        self._start_monitor()
        
    def _start_monitor(self):
        from desktop_app.utils.status_monitor import StatusMonitor
        self.monitor = StatusMonitor()
        self.monitor.progress_updated.connect(self._on_progress_update)
        # self.monitor.metrics_updated.connect(self._on_metrics_update)
        self.monitor.start()
        
    def _on_progress_update(self, percent, status, eta):
        self.results_panel.update_progress(percent, status, eta)
        if percent >= 100:
             self.status_bar.showMessage("Optimization Completed")
        else:
             self.status_bar.showMessage(f"Running... {percent:.1f}%")

    def _show_report(self):
        from desktop_app.ui.dialogs.details_dialog import DetailsDialog
        dlg = DetailsDialog(self)
        dlg.exec()
        
    def closeEvent(self, event):
        if hasattr(self, 'monitor'):
            self.monitor.stop()
        event.accept()
