# 🎯 YAPILACAKLAR LİSTESİ - Walkability Optimization

**Tarih:** Şu an (Greedy çalışıyor, MILP bekliyor)  
**Hedef:** Desktop App + Greedy + MILP karşılaştırması  
**Toplam Süre:** ~25-30 saat

---

## 📊 MEVCUT DURUM

### ✅ TAMAMLANANLAR:
- ✅ Database schema (node_id tutarlılığı düzeltildi)
- ✅ OSM data loading (600x speedup: 2-3h → 20s)
- ✅ Graph construction (26,931 residential buildings)
- ✅ Shortest paths (multiprocessing, 8 core)
- ✅ WalkScore calculator (düzeltildi, baseline: 56.95)
- ✅ Amenity tags (STRICT - Toronto-style)
- ✅ Healthcare amenity (yeni eklendi)
- ✅ Candidate locations (extended strategy)
- ✅ Greedy algorithm (çalışıyor, iteration 2'de)
- ✅ MILP solver (implement edildi, test edilecek)

### ⏳ ŞU ANDA ÇALIŞAN:
- ⏳ **Greedy k=1**: Iteration 2/4 (1443 pairs değerlendiriliyor)
  - Speed: 0.7 eval/s
  - ETA: ~1-2 saat daha
  - Sonra MILP başlayacak

---

## 🔥 ÖNCELİKLİ İŞLER (Sırayla)

### 1. ✅ GREEDY TESTİ TAMAMLA
**Durum:** Çalışıyor (iteration 2/4)  
**Süre:** ~1-2 saat daha  
**Beklenen Sonuç:**
- Baseline: 56.95
- Greedy: ~59-61 (+2-4 puan)
- 4 allocation (her type'tan 1)

**Yapılacak:**
- [ ] Greedy bitmesini bekle
- [ ] Sonuçları kontrol et (WalkScore improvement)
- [ ] Database'e kaydedildiğini doğrula
- [ ] Visualization oluşturulduğunu kontrol et

---

### 2. ⏳ MILP TESTİ
**Durum:** Greedy bitince başlayacak  
**Süre:** ~2-4 saat (config: 5 saat max)  
**Beklenen Sonuç:**
- MILP: ~59.5-61.5 (+2.5-4.5 puan)
- Optimal veya 1% gap içinde
- Greedy'den +0.2-0.5 puan daha iyi olmalı

**Yapılacak:**
- [ ] Greedy bitince MILP otomatik başlayacak (--algorithm both)
- [ ] Eğer hata verirse (Gurobi license), ayrı çalıştır:
  ```bash
  python -m src.main --skip-data-load --skip-distances --skip-baseline \
    --algorithm milp --k 1 --visualize --evaluate
  ```
- [ ] MILP sonuçlarını kontrol et
- [ ] Time limit gerekirse kısalt (config.yaml: time_limit_seconds: 3600)

**Config:**
```yaml
# config.yaml
optimization:
  milp:
    time_limit_seconds: 18000  # 5 saat (test için 3600 yapılabilir)
    threads: 8
    mip_gap: 0.01  # 1% optimality gap
```

---

### 3. 📊 COMPARISON MODULE (2-3 saat)
**Durum:** Henüz yapılmadı  
**Süre:** ~2-3 saat

**Yapılacak:**
- [ ] `src/comparison/compare.py` oluştur
  ```python
  class AlgorithmComparison:
      def compare_algorithms(self, algorithms=['greedy', 'milp'], k=1):
          """
          Compare Greedy vs MILP:
          - Runtime comparison
          - WalkScore improvement
          - Optimality gap
          - Allocated locations
          """
          
      def export_results(self, format='json'):
          """Export to JSON/CSV for UI"""
          
      def plot_comparison(self):
          """Basic matplotlib charts"""
  ```
- [ ] Database'den sonuçları yükle
- [ ] Karşılaştırma metrikleri hesapla:
  - Baseline WalkScore
  - Greedy WalkScore + improvement
  - MILP WalkScore + improvement
  - Runtime comparison
  - Optimality gap (MILP için)
  - Allocated locations (overlap analizi)
- [ ] JSON export (`results/comparison_k1.json`)
- [ ] CSV export (`results/comparison_k1.csv`)
- [ ] Matplotlib charts:
  - WalkScore comparison (bar chart)
  - Runtime comparison (bar chart)
  - Improvement comparison (bar chart)
  - Allocations map (side-by-side)

**Output Format:**
```json
{
  "baseline": {
    "walkscore": 56.95,
    "amenities": {...}
  },
  "greedy": {
    "runtime": 180.5,
    "walkscore": 59.1,
    "improvement": 3.15,
    "improvement_pct": 5.5,
    "allocations": [...]
  },
  "milp": {
    "runtime": 7200.0,
    "walkscore": 59.5,
    "improvement": 3.55,
    "improvement_pct": 6.2,
    "optimality_gap": 0.008,
    "allocations": [...]
  }
}
```

---

### 4. 🖥️ DESKTOP APP - SETUP (1 saat)
**Durum:** Henüz yapılmadı  
**Süre:** ~1 saat

**Yapılacak:**
- [ ] PySide6 install:
  ```bash
  pip install PySide6
  ```
- [ ] Proje yapısı oluştur:
  ```
  desktop_app/
  ├── main.py                    # Entry point
  ├── ui/
  │   ├── main_window.py         # Main QMainWindow
  │   ├── widgets/
  │   │   ├── map_widget.py      # Folium map → QWebEngineView
  │   │   ├── algorithm_panel.py # Algorithm selection + params
  │   │   ├── results_panel.py   # Results display
  │   │   ├── comparison_view.py # Side-by-side comparison
  │   │   └── progress_widget.py # Progress bar + status
  │   └── dialogs/
  │       └── settings_dialog.py # Settings/config
  ├── core/
  │   ├── optimizer.py          # Wrapper for Greedy/MILP
  │   ├── comparison.py          # Algorithm comparison
  │   └── data_manager.py       # Database queries
  └── utils/
      ├── map_generator.py      # Generate Folium HTML
      └── export.py             # Export results
  ```
- [ ] Basic main window oluştur (boş layout)
- [ ] Test: App açılıyor mu?

---

### 5. 🗺️ DESKTOP APP - MAP WIDGET (4 saat)
**Durum:** Henüz yapılmadı  
**Süre:** ~4 saat

**Yapılacak:**
- [ ] `ui/widgets/map_widget.py` oluştur
  ```python
  from PySide6.QtWebEngineWidgets import QWebEngineView
  import folium
  import io
  
  class MapWidget(QWebEngineView):
      def load_baseline_map(self):
          """Load baseline map with residential + existing amenities"""
          
      def load_result_map(self, allocations):
          """Load result map with new allocations"""
          
      def _load_html(self, folium_map):
          """Convert Folium map to HTML and load"""
  ```
- [ ] Baseline map yükleme:
  - Residential buildings (heatmap)
  - Existing amenities (markers)
  - WalkScore heatmap overlay
- [ ] Result map yükleme:
  - Baseline + allocated amenities (NEW markers)
  - 15-minute walking circles
- [ ] Folium → HTML conversion
- [ ] QWebEngineView'da göster
- [ ] Test: Map görünüyor mu?

**Referans:** `src/visualization/map_visualizer.py` kullan

---

### 6. ⚙️ DESKTOP APP - ALGORITHM PANEL (2 saat)
**Durum:** Henüz yapılmadı  
**Süre:** ~2 saat

**Yapılacak:**
- [ ] `ui/widgets/algorithm_panel.py` oluştur
  ```python
  class AlgorithmPanel(QWidget):
      def __init__(self):
          self.greedy_radio = QRadioButton("Greedy")
          self.milp_radio = QRadioButton("MILP")
          self.k_spinbox = QSpinBox(min=1, max=10)
          self.amenity_combo = QComboBox(["grocery", "school", "restaurant", "healthcare"])
          self.time_limit_spinbox = QSpinBox(min=60, max=7200)
          self.run_button = QPushButton("▶ RUN")
  ```
- [ ] Radio buttons (Greedy vs MILP)
- [ ] Parameter inputs:
  - k value (1-10)
  - Amenity type dropdown
  - Time limit (MILP için, 60-7200 sec)
- [ ] RUN button
- [ ] Signal'ler (run_clicked, parameters_changed)
- [ ] Test: Panel görünüyor mu? Signal'ler çalışıyor mu?

---

### 7. 📊 DESKTOP APP - RESULTS PANEL (2 saat)
**Durum:** Henüz yapılmadı  
**Süre:** ~2 saat

**Yapılacak:**
- [ ] `ui/widgets/results_panel.py` oluştur
  ```python
  class ResultsPanel(QWidget):
      def display_results(self, results):
          """Display optimization results"""
          self.baseline_label.setText(f"Baseline: {results['baseline']:.2f}")
          self.new_label.setText(f"New: {results['new']:.2f}")
          self.improvement_label.setText(f"+{results['improvement']:.2f} ({results['improvement_pct']:.1f}%)")
          self.runtime_label.setText(f"Runtime: {results['runtime']:.1f} sec")
  ```
- [ ] WalkScore gösterimi:
  - Baseline WalkScore
  - New WalkScore
  - Improvement (absolute + percentage)
- [ ] Runtime gösterimi
- [ ] Allocations listesi (QListWidget)
- [ ] Buttons:
  - "Show on Map" (map'e allocations ekle)
  - "Export Results" (JSON/CSV)
  - "Compare" (comparison view aç)
- [ ] Test: Sonuçlar görünüyor mu?

---

### 8. 🔧 DESKTOP APP - CORE OPTIMIZER (3 saat)
**Durum:** Henüz yapılmadı  
**Süre:** ~3 saat

**Yapılacak:**
- [ ] `core/optimizer.py` oluştur
  ```python
  from PySide6.QtCore import QObject, pyqtSignal
  from src.algorithms.greedy import GreedyOptimizer
  from src.algorithms.milp import MILPSolver
  
  class Optimizer(QObject):
      progress_updated = pyqtSignal(int, str)  # progress %, status
      finished = pyqtSignal(dict)  # results
      
      def run_greedy(self, k, amenity_type):
          """Run greedy algorithm with progress updates"""
          
      def run_milp(self, k, amenity_type, time_limit):
          """Run MILP with progress updates"""
  ```
- [ ] Threading implementasyonu (UI donmasın):
  - QThread kullan
  - Worker thread'de algoritma çalıştır
  - Progress signal'leri gönder
- [ ] Greedy entegrasyonu:
  - Progress callbacks ekle
  - Signal'ler gönder (iteration, progress %)
- [ ] MILP entegrasyonu:
  - Gurobi callbacks kullan
  - Signal'ler gönder (gap, progress %)
- [ ] Error handling
- [ ] Test: Threading çalışıyor mu? Progress gösteriliyor mu?

**Referans:** 
- `src/algorithms/greedy.py` - GreedyOptimizer
- `src/algorithms/milp.py` - MILPSolver

---

### 9. 📈 DESKTOP APP - PROGRESS BAR (2 saat)
**Durum:** Henüz yapılmadı  
**Süre:** ~2 saat

**Yapılacak:**
- [ ] `ui/widgets/progress_widget.py` oluştur
  ```python
  class ProgressWidget(QWidget):
      def update_progress(self, percentage, status_text):
          """Update progress bar and status label"""
  ```
- [ ] QProgressBar
- [ ] Status label (QLabel)
- [ ] Progress signal'lerini bağla (Optimizer'dan)
- [ ] Test: Progress gösteriliyor mu?

---

### 10. 🔄 DESKTOP APP - COMPARISON VIEW (3 saat)
**Durum:** Henüz yapılmadı  
**Süre:** ~3 saat

**Yapılacak:**
- [ ] `ui/widgets/comparison_view.py` oluştur
  ```python
  class ComparisonView(QWidget):
      def show_comparison(self, greedy_results, milp_results):
          """Show side-by-side comparison"""
  ```
- [ ] Side-by-side layout:
  - Left: Greedy map + stats
  - Right: MILP map + stats
- [ ] Statistics table (QTableWidget):
  - WalkScore comparison
  - Runtime comparison
  - Improvement comparison
  - Allocations comparison
- [ ] Charts (matplotlib):
  - WalkScore bar chart
  - Runtime bar chart
  - Improvement bar chart
- [ ] Test: Comparison görünüyor mu?

---

### 11. 💾 DESKTOP APP - EXPORT FUNCTIONALITY (2 saat)
**Durum:** Henüz yapılmadı  
**Süre:** ~2 saat

**Yapılacak:**
- [ ] `utils/export.py` oluştur
  ```python
  def export_results_json(results, filepath):
      """Export results to JSON"""
      
  def export_results_csv(results, filepath):
      """Export results to CSV"""
  ```
- [ ] JSON export (tüm sonuçlar)
- [ ] CSV export (tablo formatında)
- [ ] File dialog (QFileDialog)
- [ ] Test: Export çalışıyor mu?

---

### 12. 🎨 DESKTOP APP - MAIN WINDOW INTEGRATION (2 saat)
**Durum:** Henüz yapılmadı  
**Süre:** ~2 saat

**Yapılacak:**
- [ ] `ui/main_window.py` tamamla
- [ ] Layout oluştur:
  ```
  ┌─────────────────────────────────────────────────────────────┐
  │  Walkability Optimization Tool                    [⚙️] [❌] │
  ├─────────────────────────────────────────────────────────────┤
  │                                                             │
  │  ┌──────────────────┐  ┌─────────────────────────────────┐ │
  │  │  ALGORITHM       │  │  MAP VIEW                      │ │
  │  │  PANEL           │  │                                │ │
  │  └──────────────────┘  └─────────────────────────────────┘ │
  │                                                             │
  │  ┌─────────────────────────────────────────────────────┐ │
  │  │  RESULTS PANEL                                       │ │
  │  └─────────────────────────────────────────────────────┘ │
  │                                                             │
  │  Status: [████████░░] 80% - Computing distances...         │
  └─────────────────────────────────────────────────────────────┘
  ```
- [ ] Widget'ları bağla:
  - Algorithm Panel → Optimizer
  - Optimizer → Progress Widget
  - Optimizer → Results Panel
  - Results Panel → Map Widget
  - Results Panel → Comparison View
- [ ] Menu bar:
  - File → Export
  - Settings → Config
  - Help → About
- [ ] Test: Tüm widget'lar çalışıyor mu?

---

### 13. 🧪 TESTING & BUG FIXES (4 saat)
**Durum:** Henüz yapılmadı  
**Süre:** ~4 saat

**Yapılacak:**
- [ ] End-to-end test:
  - [ ] Greedy çalıştır (k=1)
  - [ ] MILP çalıştır (k=1, time_limit=3600)
  - [ ] Sonuçları karşılaştır
  - [ ] Map'te göster
  - [ ] Export yap
- [ ] Bug fixes:
  - [ ] Threading sorunları
  - [ ] Memory leaks
  - [ ] UI donması
  - [ ] Progress bar güncellemeleri
- [ ] Performance optimization:
  - [ ] Map loading hızlandır
  - [ ] Database query optimization
  - [ ] Caching

---

### 14. ✨ POLISH & FINAL TOUCHES (2 saat)
**Durum:** Henüz yapılmadı  
**Süre:** ~2 saat

**Yapılacak:**
- [ ] UI polish:
  - [ ] Icons ekle
  - [ ] Colors düzenle
  - [ ] Fonts düzenle
  - [ ] Spacing düzenle
- [ ] Error messages düzenle
- [ ] Tooltips ekle
- [ ] About dialog
- [ ] README güncelle (desktop app için)

---

## 📋 ÖNEMLİ NOTLAR

### Database Yapısı:
```sql
-- Sonuçlar bu tablolarda:
- walkability_scores (scenario: 'baseline', 'greedy_k1', 'milp_k1')
- optimization_results (allocations)
- shortest_paths (distances)
```

### Config Dosyası:
```yaml
# config.yaml
optimization:
  milp:
    time_limit_seconds: 18000  # Test için 3600 yapılabilir
    threads: 8
    mip_gap: 0.01
```

### Referans Dosyalar:
- `src/algorithms/greedy.py` - GreedyOptimizer
- `src/algorithms/milp.py` - MILPSolver
- `src/visualization/map_visualizer.py` - Map generation
- `src/scoring/walkscore.py` - WalkScore calculation

---

## ⏱️ ZAMAN ÇİZELGESİ

```
📅 BUGÜN (Greedy çalışıyor):
  ⏳ Greedy bitir (~1-2 saat)
  ⏳ MILP başlat (~2-4 saat)
  → Toplam: 3-6 saat

📅 YARIN:
  ✅ Comparison module (2-3 saat)
  ✅ Desktop app setup (1 saat)
  ✅ Map widget (4 saat)
  ✅ Algorithm panel (2 saat)
  → Toplam: 9-10 saat

📅 SONRAKİ GÜN:
  ✅ Results panel (2 saat)
  ✅ Core optimizer (3 saat)
  ✅ Progress bar (2 saat)
  ✅ Comparison view (3 saat)
  → Toplam: 10 saat

📅 SON GÜN:
  ✅ Export (2 saat)
  ✅ Main window integration (2 saat)
  ✅ Testing (4 saat)
  ✅ Polish (2 saat)
  → Toplam: 10 saat

📊 TOPLAM: ~30-35 saat
```

---

## 🎯 HEDEF

**FULLY FUNCTIONAL DESKTOP APP:**
- ✅ Greedy ve MILP algoritmaları çalıştırılabilir
- ✅ Sonuçlar görselleştirilebilir (map)
- ✅ Karşılaştırma yapılabilir
- ✅ Export edilebilir
- ✅ Kullanıcı dostu UI

---

## 🚨 ÖNEMLİ HATIRLATMALAR

1. **Greedy şu an çalışıyor** - Bitmesini bekle!
2. **MILP Greedy bitince başlayacak** (--algorithm both)
3. **Gurobi license** gerekli (MILP için)
4. **Database'de sonuçlar** kaydediliyor (scenario: 'greedy_k1', 'milp_k1')
5. **Threading kullan** (UI donmasın)
6. **Progress signal'leri** gönder (kullanıcı bilgilendir)

---

**BAŞARILAR! 🚀**

