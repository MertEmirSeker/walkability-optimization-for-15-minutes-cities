
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox, 
                               QPushButton, QLabel)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Slot
import folium
import io
import os

class MapWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Controls Toolbar
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(5, 5, 5, 5)
        
        controls_layout.addWidget(QLabel("Map View:"))
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Baseline Map", "baseline_map.html")
        self.mode_combo.addItem("Optimized Map", "optimized_map_dynamic") # Logic to find best
        self.mode_combo.addItem("Comparison Map", "comparison_map_dynamic")
        self.mode_combo.currentIndexChanged.connect(self.load_selected_map)
        controls_layout.addWidget(self.mode_combo)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_selected_map)
        controls_layout.addWidget(self.refresh_btn)
        
        controls_layout.addStretch()
        self.layout.addLayout(controls_layout)
        
        # Web View
        from PySide6.QtWebEngineCore import QWebEngineSettings
        self.web_view = QWebEngineView()
        
        # Critical: Enable local files to access remote URLs (CDN scripts)
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        
        self.layout.addWidget(self.web_view)
        
        # Initialize
        self.load_selected_map()
        
    def load_selected_map(self):
        """Load the map corresponding to the selected mode."""
        mode_data = self.mode_combo.currentData()
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, "../../../"))
        viz_dir = os.path.join(project_root, "visualizations")
        
        target_file = None
        
        if mode_data == "baseline_map.html":
            target_file = os.path.join(viz_dir, "baseline_map.html")
            
        elif mode_data == "optimized_map_dynamic":
            # Find latest optimized map
            target_file = self._find_latest_file(viz_dir, "_map.html", exclude="baseline")
            
        elif mode_data == "comparison_map_dynamic":
            # Find latest comparison map
            target_file = self._find_latest_file(viz_dir, "_comparison.html")
            
        if target_file and os.path.exists(target_file):
            print(f"Loading map: {target_file}")
            self.load_html_file(target_file)
        else:
            print(f"Map file not found for mode: {mode_data}")
            # Load default if nothing found
            if mode_data == "baseline_map.html":
                 self.init_default_map()

    def _find_latest_file(self, folder, suffix, exclude=None):
        """Find the most recently modified file ending with suffix."""
        if not os.path.exists(folder):
            return None
            
        candidates = []
        for f in os.listdir(folder):
            if f.endswith(suffix):
                if exclude and exclude in f:
                    continue
                candidates.append(os.path.join(folder, f))
        
        if not candidates:
            return None
            
        # Sort by modification time (newest first)
        candidates.sort(key=os.path.getmtime, reverse=True)
        return candidates[0]

    def init_default_map(self):
        """Initialize a basic Folium map as fallback."""
        m = folium.Map(location=[43.70, -79.40], zoom_start=11)
        self.set_map(m)
            
    def load_html_file(self, file_path):
        """Load a local HTML file into the view."""
        # Now that we enabled LocalContentCanAccessRemoteUrls, we can use load() again
        # This is much more memory efficient for large (50MB+) files
        self.web_view.load(QUrl.fromLocalFile(file_path))

    def set_map(self, m):
        """Render a Folium map in the QWebEngineView."""
        data = io.BytesIO()
        m.save(data, close_file=False)
        html = data.getvalue().decode()
        self.web_view.setHtml(html)
