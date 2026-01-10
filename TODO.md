# Yapılacaklar Listesi (TODO) - Kapsamlı Versiyon

## 🔴 Kritik Sorunlar ve Bug'lar (Critical Issues)

### 0. 🚨 PAPER IMPLEMENTASYONU - SIFIRDAN YAZ! (YENİ PRİORİTE!)

**Toronto Paper'ındaki algoritmaları SIFIRDAN implement et - mevcut kod yanlış!**

#### Paper'dan Temel Kavramlar:
- [ ] WalkScore formülasyonunu paper'a göre yeniden yaz (Section 2.1)
- [ ] Piecewise linear function PWL(d) - Equation (1)
- [ ] Weighted walking distance formülü - Equation (2)  
- [ ] Aplain (single nearest) ve Adepth (multiple choices) kategorileri
- [ ] Depth weights (wap) for restaurant - Table 1
- [ ] Category weights (wa) - grocery:1.0, school:0.8, restaurant:0.6

#### Algorithm 1: Greedy Heuristic (Paper Section 3.1)
- [ ] SIFIRDAN YAZ: Greedy algorithm'ı paper'daki pseudocode'a göre implement et
- [ ] Input: G(N,E), R (residential), C (candidates), A (amenity types), ka values
- [ ] Output: Allocation decisions (which amenities to where)
- [ ] Step 1: Initialize empty allocation set
- [ ] Step 2: For each amenity type a, iterate ka times
- [ ] Step 3: For each iteration, find candidate that maximizes objective improvement
- [ ] Step 4: Compute marginal improvement for each candidate
- [ ] Step 5: Allocate to best candidate, update distances
- [ ] Step 6: Return final allocation
- [ ] NOT: Mevcut greedy.py'yi KULLANMA - yanlış! Yeniden yaz!

#### MILP Formulation (Paper Section 3.2)
- [ ] Decision variables: yja (binary) - allocate amenity a to candidate j
- [ ] Objective: Maximize average WalkScore (minimize weighted distance)
- [ ] Constraints: Budget constraint (Σyja ≤ ka for each a)
- [ ] Constraints: Candidate capacity
- [ ] Distance assignment için auxiliary variables
- [ ] Paper'daki Equation (3), (4), (5), (6) formülasyonunu implement et

#### WalkScore Computation (DOĞRU VERSİYON)
- [ ] PWL function: 100 at 0m, linearly decreasing to 0 at max distance
- [ ] Breakpoints: [0, 400, 800, 1600, 2400] meters
- [ ] Scores: [100, 90, 70, 40, 0] at breakpoints
- [ ] For Aplain: Use single nearest amenity distance
- [ ] For Adepth: Use weighted average of top-r nearest (r=10 for restaurant)
- [ ] Aggregate across all amenity types with category weights

### 1. Greedy Algoritma Düzeltilmesi (ESKİ - SİL VE YENİDEN YAZ!)

❌ MEVCUT KOD YANLIŞ - Paper'a göre yeniden yazılacak (Yukarıdaki Section 0'a bak)

- [ ] Greedy algoritma WalkScore'u azaltıyor (şu anda -15.51 puan düşüş var, beklenen: +25 puan artış)
- [ ] `get_all_amenity_locations` mantığını gözden geçir (tüm candidate'ları tüm amenity tipleri için kullanma problemi)
- [ ] Weighted distance hesaplama mantığını kontrol et (D_infinity ve breakpoints kombinasyonu)
- [ ] Objective function'ın doğru çalıştığından emin ol (maksimizasyon yerine minimizasyon yapıyor olabilir)
- [ ] Greedy iteration'da incremental objective calculation'ı kontrol et
- [ ] `compute_objective_increase` fonksiyonunun doğruluğunu test et
- [ ] Candidate selection logic'ini gözden geçir (en iyi candidate seçiliyor mu?)
- [ ] Allocation tracking'i kontrol et (aynı yere birden fazla amenity yerleştiriliyor mu?)
- [ ] Capacity constraint'lerinin doğru uygulandığından emin ol
- [ ] Sampling mekanizmasını kaldır veya düzelt (greedy_sample_size=1 çok küçük)
- [ ] `greedy_max_candidates` limitini kaldır veya artır (şu anda sadece 10 candidate üzerinde arama yapıyor)
- [ ] Test senaryoları ile doğrulama yap (basit case'lerle başla)
- [ ] Paper'daki Algorithm 1 ile implementasyonu karşılaştır

### 2. WalkScore Hesaplama İyileştirmesi

- [ ] Breakpoints ve scores parametrelerini Balıkesir ölçeğine göre kalibre et
- [ ] Weighted distance hesaplama formülünü gözden geçir (paper'daki formülle karşılaştır)
- [ ] Depth weights'in doğru uygulandığından emin ol (restaurant için top 10 seçim)
- [ ] Plain weights'in doğru uygulandığından emin ol (grocery, school için en yakın)
- [ ] D_infinity değerinin doğru hesaplandığından emin ol (unreachable node'lar için)
- [ ] Piecewise linear function'ın doğru implement edildiğini kontrol et
- [ ] Edge case'leri handle et (distance = 0, distance > max_breakpoint)
- [ ] 15-minute coverage'ı artır (şu anda %0.16, hedef: %70)
- [ ] WalkScore distribution'ını analiz et (tüm residential'lar için)
- [ ] Baseline WalkScore'un gerçekçi olduğunu doğrula (55.92 makul mu?)
- [ ] Weighted distance hesaplamasında existing amenities'in doğru kullanıldığından emin ol
- [ ] Allocated amenities eklendiğinde weighted distance'in doğru güncellendiğinden emin ol

### 3. ✅ OSM Data Collection İyileştirmesi (TAMAMLANDI!)

- [x] Residential building extraction'ı iyileştir (daha fazla bina yakalama) - EXCLUSION stratejisi ile 27K bina
- [x] Building tag'lerini genişlet (apartments, residential, house, etc.) - 37 farklı residential type
- [x] Amenity detection'ı genişlet (eksik amenity'ler olabilir) - 217 farklı amenity tag!
- [x] Candidate location seçimini optimize et (parking lots, empty lots, etc.) - 17 tag grubu
- [x] Data quality kontrolü ekle (duplicate detection, validation) - Implemented
- [x] OSM data freshness kontrolü ekle (ne zaman çekildi?) - Timestamp tracking eklendi
- [x] Missing data handling (bazı alanlarda veri eksik olabilir) - Statistics ve reporting eklendi
- [x] Residential snapping mekanizmasını iyileştir (en yakın node'a bağlama) - Improved
- [x] Snapping distance limit'i ekle (çok uzak node'lara bağlanmasın) - 500m max distance
- [x] Original coordinates'i sakla (original_latitude, original_longitude zaten var, kontrol et) - Implemented
- [x] OSM tag mapping'lerini gözden geçir (doğru tag'ler kullanılıyor mu?) - Ultra comprehensive tags
- [x] Network type'ı kontrol et (walk network doğru mu?) - network_type="walk" confirmed
- [x] Graph simplification'ı kontrol et (çok fazla node silinmiş olabilir) - simplify=True with validation
- [x] Okul/hastane binalarını residential'dan çıkar - amenity tag kontrolü eklendi
- [x] Amenity buffer'ını genişlet - 1.5km buffer eklendi
- [x] Türkiye-spesifik tag'ler ekle - Çay ocağı, esnaf, kuruyemişçi, vb. eklendi

**İyileştirme Sonuçları:**
- Residential: 27,147 (önceden 35) - Okul/hastane binaları çıkarıldı
- Grocery: 63 tag ile kapsamlı arama
- Restaurant: 49 tag (çay ocağı, esnaf lokantası dahil)
- School: 40 tag
- Healthcare: 65 tag
- Toplam 217 farklı amenity tag!

### 4. Graph Connectivity ve Network Sorunları

- [ ] Graph connectivity sorunlarını çöz (bazı residential'lar bağlı değil)
- [ ] Unreachable node'lar için handling ekle (D_infinity kullanımı)
- [ ] Largest connected component seçimi yapıldı mı? (yapılmadı, neden?)
- [ ] Disconnected components'leri analiz et
- [ ] Residential'ların graph'a bağlanma oranını hesapla
- [ ] Edge'lerin doğru yönlendirildiğinden emin ol (undirected graph kullanılıyor)
- [ ] Self-loops ve duplicate edges kontrolü yap
- [ ] Graph validation ekle (cycle detection, etc.)
- [ ] Network simplification'ın etkisini analiz et
- [ ] Missing edges için handling (bazı node'lar arasında edge yok)

## 🟡 Önemli Geliştirmeler ve Eksikler (Important Improvements)

### 5. Shortest Path İyileştirmesi

- [ ] Dijkstra algoritmasının performansını optimize et
- [ ] Distance matrix caching mekanizması ekle (tüm mesafeleri sakla)
- [ ] Incremental distance calculation (sadece değişen mesafeleri hesapla)
- [ ] Parallel shortest path computation (multiprocessing)
- [ ] Memory-efficient distance storage (sparse matrix kullan)
- [ ] Distance precomputation (tüm residential-candidate mesafelerini önceden hesapla)
- [ ] Path reconstruction ekle (sadece distance değil, path'i de sakla)
- [ ] Alternative algorithms (A*, bidirectional Dijkstra)
- [ ] Distance calculation'ın doğruluğunu test et (gerçek yürüme mesafeleriyle karşılaştır)
- [ ] Edge weight'lerinin doğru kullanıldığından emin ol (length_meters)

### 6. CP (Constraint Programming) Solver Implementasyonu

- [ ] CP solver implementasyonu ekle (OR-Tools veya başka bir kütüphane)
- [ ] CP model formulasyonu (constraints, variables, objective)
- [ ] CP solver parametrelerini ayarla (time limit, search strategy)
- [ ] MILP ile karşılaştırma yap (çözüm kalitesi, çözüm süresi)
- [ ] Performans analizi (hangi problem boyutlarında daha iyi?)
- [ ] CP-specific optimizations (constraint propagation, etc.)
- [ ] Test senaryoları ile doğrulama

### 7. MILP Solver İyileştirmeleri

- [ ] MILP model'in doğruluğunu kontrol et (constraints, objective)
- [ ] Gurobi license handling'i iyileştir (license yoksa graceful degradation)
- [ ] Alternative MILP solver desteği ekle (PuLP, CPLEX)
- [ ] MILP parametrelerini optimize et (mip_gap, time_limit)
- [ ] Warm start ekle (greedy solution'dan başla)
- [ ] Lazy constraints ekle (gerekirse)
- [ ] Solution pool ekle (birden fazla çözüm)
- [ ] MILP çözüm kalitesini analiz et (optimality gap)

### 8. Evaluation Metrics İyileştirmesi

- [ ] Success criteria'ları kontrol et ve güncelle
- [ ] Daha detaylı metrikler ekle:
  - [ ] Median WalkScore (sadece average değil)
  - [ ] WalkScore distribution (histogram, percentiles)
  - [ ] Minimum WalkScore (en kötü durum)
  - [ ] WalkScore variance
  - [ ] Distance distribution
  - [ ] Coverage by amenity type (her amenity için ayrı coverage)
  - [ ] Geographic distribution of improvements
- [ ] Before/after karşılaştırma raporları oluştur
- [ ] Visualization'da metrikleri göster
- [ ] Statistical significance testleri ekle
- [ ] Sensitivity analysis (parametre değişikliklerinin etkisi)
- [ ] Scenario comparison (farklı k değerleri için karşılaştırma)

### 9. Database Schema ve Query Optimizasyonu

- [ ] Index'leri optimize et (hangi query'ler yavaş?)
- [ ] Foreign key constraint'leri gözden geçir (doğru mu?)
- [ ] Query performance analizi (EXPLAIN ANALYZE)
- [ ] Composite index'ler ekle (sık kullanılan column kombinasyonları)
- [ ] Partitioning düşün (büyük tablolar için)
- [ ] Vacuum ve analyze işlemlerini otomatikleştir
- [ ] Connection pooling iyileştirmesi
- [ ] Transaction management iyileştirmesi
- [ ] Database backup stratejisi
- [ ] Schema migration script'leri
- [ ] Data integrity check'leri ekle

### 10. Configuration Management

- [ ] Config validation ekle (yaml schema validation)
- [ ] Default value'ları dokümante et
- [ ] Environment-specific config'ler (dev, prod)
- [ ] Config hot-reload desteği (restart olmadan)
- [ ] Config versioning
- [ ] Sensitive data handling (password'ler için encryption)

## 🟢 İyileştirmeler ve Eklemeler (Enhancements)

### 11. Test Coverage

- [ ] Unit testler yaz (pytest):
  - [ ] WalkScore calculation tests
  - [ ] Shortest path tests
  - [ ] Greedy algorithm tests
  - [ ] MILP solver tests
  - [ ] Database operations tests
  - [ ] Visualization tests
- [ ] Integration testler ekle:
  - [ ] End-to-end pipeline test
  - [ ] Database integration tests
  - [ ] OSM data loading tests
- [ ] Test data setleri oluştur:
  - [ ] Small synthetic graph (test için)
  - [ ] Known solution test cases
  - [ ] Edge case test data
- [ ] CI/CD pipeline kurulumu (GitHub Actions, GitLab CI)
- [ ] Test coverage reporting (coverage.py)
- [ ] Performance benchmarks
- [ ] Regression tests

### 12. Documentation

- [ ] API documentation (docstrings):
  - [ ] Tüm class'lar için docstring
  - [ ] Tüm method'lar için docstring
  - [ ] Parameter ve return type documentation
  - [ ] Example usage
- [ ] User guide oluştur:
  - [ ] Installation guide
  - [ ] Quick start guide
  - [ ] Configuration guide
  - [ ] Troubleshooting guide
- [ ] Architecture diagram'ları ekle:
  - [ ] System architecture
  - [ ] Data flow diagram
  - [ ] Database schema diagram (zaten var, güncelle)
  - [ ] Algorithm flowcharts
- [ ] Code comments'leri iyileştir:
  - [ ] Complex algorithm explanations
  - [ ] Business logic comments
  - [ ] TODO comments for future work
- [ ] Paper implementation notes (hangi kısımlar paper'dan, hangileri ek)
- [ ] Changelog (version history)
- [ ] Contributing guide

### 13. Visualization İyileştirmeleri

- [ ] Interactive dashboard oluştur (Streamlit, Dash, veya web app)
- [ ] Real-time WalkScore heatmap (daha smooth)
- [ ] Before/after karşılaştırma görselleştirmeleri:
  - [ ] Side-by-side maps
  - [ ] Difference heatmap
  - [ ] Improvement indicators
- [ ] 15-minute radius circle'ları daha iyi göster:
  - [ ] Her residential için circle
  - [ ] Coverage visualization
  - [ ] Overlapping circles
- [ ] Animation ekle (optimization sürecini göster)
- [ ] Filtering ve search (belirli bölgeleri filtrele)
- [ ] Export functionality (PNG, PDF)
- [ ] Print-friendly version
- [ ] Mobile-responsive design
- [ ] Legend ve tooltip'leri iyileştir
- [ ] Color scheme accessibility (colorblind-friendly)
- [ ] Layer control (farklı layer'ları aç/kapa)

### 14. Performance Optimizasyonu

- [ ] Database query'lerini optimize et:
  - [ ] N+1 query problem'lerini çöz
  - [ ] Batch operations kullan
  - [ ] Query result caching
- [ ] Graph operations'ı hızlandır:
  - [ ] Graph preprocessing
  - [ ] Cached graph statistics
  - [ ] Efficient node/edge lookups
- [ ] Memory usage'ı optimize et:
  - [ ] Large data structure'ları optimize et
  - [ ] Garbage collection tuning
  - [ ] Memory profiling
- [ ] Parallel processing ekle:
  - [ ] Multiprocessing for distance calculation
  - [ ] Parallel greedy iterations
  - [ ] Concurrent database operations
- [ ] Algorithmic optimizations:
  - [ ] Early termination conditions
  - [ ] Pruning strategies
  - [ ] Approximation algorithms for large instances
- [ ] Profiling ve benchmarking:
  - [ ] cProfile kullan
  - [ ] Memory profiler
  - [ ] Performance regression tests

### 15. Code Quality ve Refactoring

- [ ] Code refactoring (DRY principle):
  - [ ] Duplicate code'ları extract et
  - [ ] Common utilities oluştur
  - [ ] Shared constants
- [ ] Type hints ekle:
  - [ ] Tüm function signature'larına type hints
  - [ ] mypy ile type checking
- [ ] Linting ve formatting:
  - [ ] flake8 kurulumu ve configuration
  - [ ] black formatter kurulumu
  - [ ] isort import sorter
  - [ ] Pre-commit hooks
- [ ] Error handling iyileştir:
  - [ ] Custom exception classes
  - [ ] Proper error messages
  - [ ] Error logging
  - [ ] Graceful degradation
- [ ] Logging sistemi:
  - [ ] Structured logging (JSON format)
  - [ ] Log levels (DEBUG, INFO, WARNING, ERROR)
  - [ ] Log rotation
  - [ ] Performance logging
- [ ] Code organization:
  - [ ] Module structure iyileştirmesi
  - [ ] Circular dependency'leri çöz
  - [ ] Interface definitions (ABC)

### 16. Data Validation ve Quality Assurance

- [ ] Input validation:
  - [ ] Config file validation
  - [ ] Database data validation
  - [ ] User input validation
- [ ] Data quality checks:
  - [ ] Duplicate detection
  - [ ] Outlier detection
  - [ ] Missing data handling
  - [ ] Data consistency checks
- [ ] Sanity checks:
  - [ ] WalkScore range check (0-100)
  - [ ] Distance range check (positive, reasonable)
  - [ ] Node/edge count checks
- [ ] Data profiling:
  - [ ] Statistics generation
  - [ ] Distribution analysis
  - [ ] Quality metrics

### 17. Feature Eklemeleri

- [ ] Multiple city support (sadece Balıkesir değil)
- [ ] Custom amenity types (kullanıcı tanımlı)
- [ ] Weight customization (kullanıcı weight'leri değiştirebilsin)
- [ ] Scenario comparison tool (farklı çözümleri karşılaştır)
- [ ] Export/import functionality (çözümleri kaydet/yükle)
- [ ] Batch processing (birden fazla şehir için)
- [ ] API endpoint'leri (REST API)
- [ ] Web interface (full web app)
- [ ] Command-line interface iyileştirmesi (click, argparse)
- [ ] Progress tracking (uzun işlemler için progress bar)

### 18. Algorithm İyileştirmeleri

- [ ] Advanced greedy variants:
  - [ ] Stochastic greedy
  - [ ] Adaptive greedy
  - [ ] Multi-start greedy
- [ ] Local search improvements:
  - [ ] 2-opt, 3-opt moves
  - [ ] Simulated annealing
  - [ ] Tabu search
- [ ] Hybrid approaches:
  - [ ] Greedy + MILP hybrid
  - [ ] Decomposition methods
- [ ] Approximation algorithms:
  - [ ] For very large instances
  - [ ] With quality guarantees
- [ ] Algorithm comparison framework:
  - [ ] Standardized evaluation
  - [ ] Performance metrics
  - [ ] Solution quality metrics

### 19. Monitoring ve Observability

- [ ] Application monitoring:
  - [ ] Health checks
  - [ ] Performance metrics
  - [ ] Error tracking
- [ ] Logging infrastructure:
  - [ ] Centralized logging
  - [ ] Log aggregation
  - [ ] Alerting
- [ ] Metrics collection:
  - [ ] Execution time metrics
  - [ ] Memory usage metrics
  - [ ] Database query metrics
- [ ] Dashboard (monitoring için)

### 20. Security ve Best Practices

- [ ] Security audit:
  - [ ] SQL injection prevention (zaten parameterized queries kullanılıyor)
  - [ ] Input sanitization
  - [ ] Authentication/authorization (eğer web app olursa)
- [ ] Secrets management:
  - [ ] Database credentials
  - [ ] API keys
- [ ] Dependency management:
  - [ ] Security vulnerabilities check
  - [ ] Dependency updates
- [ ] Code review process
- [ ] Version control best practices

### 21. Deployment ve DevOps

- [ ] Docker containerization:
  - [ ] Dockerfile
  - [ ] docker-compose.yml
  - [ ] Multi-stage builds
- [ ] Database migration tools:
  - [ ] Alembic veya benzeri
  - [ ] Migration scripts
- [ ] Environment setup automation:
  - [ ] Setup scripts
  - [ ] Dependency installation
- [ ] Deployment automation:
  - [ ] CI/CD pipeline
  - [ ] Automated testing
  - [ ] Deployment scripts
- [ ] Production readiness:
  - [ ] Error handling
  - [ ] Monitoring
  - [ ] Backup strategies

### 22. Research ve Experimentation

- [ ] Parameter sensitivity analysis:
  - [ ] Breakpoints değişikliğinin etkisi
  - [ ] Weight değişikliğinin etkisi
  - [ ] k değerinin etkisi
- [ ] Algorithm comparison:
  - [ ] Greedy vs MILP vs CP
  - [ ] Solution quality comparison
  - [ ] Runtime comparison
- [ ] Case study expansion:
  - [ ] Farklı şehirler için test
  - [ ] Farklı ölçekler için test
- [ ] Paper reproduction:
  - [ ] Toronto case study'yi reproduce et
  - [ ] Sonuçları karşılaştır
- [ ] Novel contributions:
  - [ ] Yeni algoritmalar
  - [ ] İyileştirmeler
  - [ ] Extensions

## 🎯 PAPER IMPLEMENTATION ROADMAP (ÖNCELİK #1!)

### ⚠️ KRİTİK: Mevcut kod YANLIŞ - Sıfırdan yazılacak!

**Toronto Paper Implementation Plan:**

#### Phase 1: WalkScore Module (Yeniden Yaz - 1-2 gün)
- [ ] `src/scoring/walkscore_v2.py` oluştur
- [ ] PWL(d) function - Paper Equation (1)
- [ ] Aplain: Single nearest amenity
- [ ] Adepth: Top-r with depth weights (r=10 for restaurant)
- [ ] Aggregate WalkScore formula
- [ ] Unit tests: PWL function, distance computation

#### Phase 2: Greedy Algorithm (Sıfırdan Yaz - 2-3 gün)
- [ ] `src/algorithms/greedy_v2.py` oluştur
- [ ] Paper Algorithm 1 pseudocode'u takip et
- [ ] Marginal improvement computation
- [ ] Allocation tracking
- [ ] Distance updates after each allocation
- [ ] Test on toy problem (5 nodes, verify it INCREASES WalkScore)

#### Phase 3: Distance Management (Optimize - 1 gün)
- [ ] `src/network/distance_manager.py` oluştur
- [ ] Precompute R×C distances
- [ ] Efficient k-nearest queries
- [ ] Incremental distance updates
- [ ] Cache mechanism

#### Phase 4: MILP Implementation (Paper Section 3.2 - 3-4 gün)
- [ ] `src/algorithms/milp_v2.py` oluştur
- [ ] Binary variables yja (allocate a to j)
- [ ] Objective: minimize weighted distance
- [ ] Budget constraints Σyja ≤ ka
- [ ] Distance assignment constraints
- [ ] Gurobi integration

#### Phase 5: Integration & Testing (2-3 gün)
- [ ] Mevcut pipeline'ı yeni algorithm'larla değiştir
- [ ] Balıkesir data ile test (27K residential)
- [ ] Verify: WalkScore ARTMALI (not decrease!)
- [ ] Verify: 15-minute coverage improvement
- [ ] Performance profiling

#### Phase 6: Validation (1-2 gün)
- [ ] Compare Greedy vs MILP
- [ ] Different k values (k=1,3,5,9)
- [ ] Solution quality metrics
- [ ] Runtime analysis

**Toplam Süre: ~2 hafta**

---

## 📝 Notlar ve Gözlemler

### Mevcut Durum (ESKİ KOD)

- ❌ Baseline WalkScore: 55.92 → Greedy: 40.42 (AZALIYOR - BUG!)
- ❌ Mevcut greedy.py yanlış implement edilmiş
- ❌ 15-minute coverage: %0.16 (hedef: %70, çok düşük)
- ✅ OSM data collection: TAMAMLANDI! 27K residential, 217 amenity tags
- ✅ Database schema: Çalışıyor
- ✅ Visualization: Çalışıyor
- ✅ Network: 19,710 nodes, 58,582 edges

### Yeni Implementation Hedefleri

- ✅ WalkScore ARTACAK (paper'daki gibi +25 puan)
- ✅ 15-minute coverage +70%
- ✅ Paper'daki Algorithm 1 faithful implementation
- ✅ MILP formulation (Equations 3-6)
- ✅ Test coverage %90+

### Teknik Detaylar

- Graph: NetworkX DiGraph, undirected'a çevriliyor
- Shortest path: Dijkstra (single_source_dijkstra_path_length)
- WalkScore: Piecewise linear function ile hesaplanıyor
- Greedy: Sampling kullanıyor (greedy_sample_size=1, çok küçük)
- MILP: Gurobi kullanıyor, license gerekli
- Database: PostgreSQL + PostGIS
- Visualization: Folium

### Bilinen Sorunlar

- Greedy algoritma WalkScore'u azaltıyor (bug var)
- 15-minute coverage çok düşük (parametreler veya data sorunu olabilir)
- Sampling mekanizması çok agresif (sadece 1 residential, 10 candidate)
- Bazı residential'lar graph'a bağlı değil (connectivity sorunu)
- Distance matrix tam olarak cache'lenmiyor (her seferinde hesaplanıyor olabilir)

### Öncelik Sırası Önerisi

1. Greedy algoritma bug'ını düzelt (en kritik)
2. WalkScore hesaplamasını doğrula
3. 15-minute coverage sorununu çöz
4. Graph connectivity sorunlarını çöz
5. Performance optimizasyonları
6. Test coverage
7. Documentation
8. Feature eklemeleri
