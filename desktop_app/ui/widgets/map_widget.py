
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
        self.mode_combo.setMinimumWidth(300)
        self.mode_combo.currentIndexChanged.connect(self.load_selected_map)
        controls_layout.addWidget(self.mode_combo)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_data)
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
        self._refresh_data()
        
    def _refresh_data(self):
        """Scan available maps and refresh UI."""
        self.mode_combo.blockSignals(True)
        current_file = self.mode_combo.currentData()
        self.mode_combo.clear()
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, "../../../"))
        viz_dir = os.path.join(project_root, "visualizations")
        
        if not os.path.exists(viz_dir):
            self.mode_combo.blockSignals(False)
            return

        # 1. Add Static Baselines
        baseline_map = os.path.join(viz_dir, "baseline_map.html")
        if os.path.exists(baseline_map):
            self.mode_combo.addItem("Baseline Map", baseline_map)
            
        baseline_heatmap = os.path.join(viz_dir, "baseline_heatmap.html")
        if os.path.exists(baseline_heatmap):
            self.mode_combo.addItem("Baseline Heatmap", baseline_heatmap)
            
        # 2. Add Dynamic Maps
        # Pattern: {algorithm}_k{k}_{type}.html
        # e.g., greedy_k1_map.html, milp_k5_heatmap.html
        import re
        map_pattern = re.compile(r'(.+)_k(\d+)_(map|heatmap)\.html')
        
        found_maps = []
        
        for f in os.listdir(viz_dir):
            match = map_pattern.search(f)
            if match:
                algo = match.group(1).title()  # greedy -> Greedy
                k = int(match.group(2))
                type_ = match.group(3).title() # map -> Map
                
                display_name = f"{algo} {type_} (k={k})"
                full_path = os.path.join(viz_dir, f)
                found_maps.append((k, algo, type_, display_name, full_path))
                
        # Sort by K, then Algorithm, then Type
        found_maps.sort(key=lambda x: (x[0], x[1], x[2]))
        
        for _, _, _, name, path in found_maps:
            self.mode_combo.addItem(name, path)
            
        # Restore selection
        index = self.mode_combo.findData(current_file)
        if index >= 0:
            self.mode_combo.setCurrentIndex(index)
        else:
            self.mode_combo.setCurrentIndex(0)
            
        self.mode_combo.blockSignals(False)
        self.load_selected_map()

    def load_selected_map(self):
        """Load the map corresponding to the selected mode."""
        target_file = self.mode_combo.currentData()
        
        if target_file and os.path.exists(target_file):
            print(f"Loading map: {target_file}")
            self.load_html_file(target_file)
        else:
            print(f"Map file not found: {target_file}")
            # If baseline, try to regen? No, simply show empty logic for now or default
            if target_file and "baseline" in target_file:
                 self.init_default_map()

    def _find_latest_file(self, folder, suffix, include=None, exclude=None):
        """Find the most recently modified file."""
        if not os.path.exists(folder):
            return None
            
        candidates = []
        for f in os.listdir(folder):
            if not f.endswith(suffix):
                continue
                
            if exclude and exclude in f:
                continue
                
            if include and include not in f:
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
