# Yapılacaklar Listesi (TODO)

## 🔴 Kritik Sorunlar (High Priority)

### 1. Greedy Algoritma Düzeltilmesi
- [ ] Greedy algoritma WalkScore'u azaltıyor (şu anda -15.51 puan düşüş var)
- [ ] `get_all_amenity_locations` mantığını gözden geçir (tüm candidate'ları tüm amenity tipleri için kullanma)
- [ ] Weighted distance hesaplama mantığını kontrol et (D_infinity ve breakpoints kombinasyonu)
- [ ] Objective function'ın doğru çalıştığından emin ol
- [ ] Test senaryoları ile doğrulama yap

### 2. WalkScore Hesaplama İyileştirmesi
- [ ] Breakpoints ve scores parametrelerini Balıkesir ölçeğine göre kalibre et
- [ ] Weighted distance hesaplama formülünü gözden geçir
- [ ] Depth weights'in doğru uygulandığından emin ol
- [ ] 15-minute coverage'ı artır (şu anda %0.16, çok düşük)

### 3. OSM Data Collection İyileştirmesi
- [ ] Residential building extraction'ı iyileştir (daha fazla bina yakalama)
- [ ] Amenity detection'ı genişlet (eksik amenity'ler olabilir)
- [ ] Candidate location seçimini optimize et
- [ ] Data quality kontrolü ekle

## 🟡 Önemli Geliştirmeler (Medium Priority)

### 4. Shortest Path İyileştirmesi
- [ ] Graph connectivity sorunlarını çöz (bazı residential'lar bağlı değil)
- [ ] Dijkstra algoritmasının performansını optimize et
- [ ] Distance matrix caching mekanizması ekle
- [ ] Unreachable node'lar için handling ekle

### 5. CP (Constraint Programming) Solver Implementasyonu
- [ ] CP solver implementasyonu ekle (OR-Tools veya başka bir kütüphane)
- [ ] MILP ile karşılaştırma yap
- [ ] Performans analizi

### 6. Evaluation Metrics İyileştirmesi
- [ ] Success criteria'ları kontrol et ve güncelle
- [ ] Daha detaylı metrikler ekle (median WalkScore, distribution, etc.)
- [ ] Before/after karşılaştırma raporları oluştur
- [ ] Visualization'da metrikleri göster

## 🟢 İyileştirmeler ve Eklemeler (Low Priority)

### 7. Test Coverage
- [ ] Unit testler yaz (pytest)
- [ ] Integration testler ekle
- [ ] Test data setleri oluştur
- [ ] CI/CD pipeline kurulumu

### 8. Documentation
- [ ] API documentation (docstrings)
- [ ] User guide oluştur
- [ ] Architecture diagram'ları ekle
- [ ] Code comments'leri iyileştir

### 9. Visualization İyileştirmeleri
- [ ] Interactive dashboard oluştur
- [ ] Real-time WalkScore heatmap
- [ ] Before/after karşılaştırma görselleştirmeleri
- [ ] 15-minute radius circle'ları daha iyi göster

### 10. Performance Optimizasyonu
- [ ] Database query'lerini optimize et
- [ ] Graph operations'ı hızlandır
- [ ] Memory usage'ı optimize et
- [ ] Parallel processing ekle (multiprocessing)

### 11. Code Quality
- [ ] Code refactoring (DRY principle)
- [ ] Type hints ekle
- [ ] Linting (flake8, black) kurulumu
- [ ] Error handling iyileştir

### 12. Database Schema
- [ ] Index'leri optimize et
- [ ] Foreign key constraint'leri gözden geçir
- [ ] Query performance analizi

## 📝 Notlar

- Greedy algoritma şu anda çalışıyor ancak sonuçlar beklenenin tersi (WalkScore azalıyor)
- Baseline WalkScore: 55.92 (iyileştirme potansiyeli var)
- 15-minute coverage çok düşük (%0.16), bu kritik bir sorun
- Database schema doğru görünüyor, ancak query performansı test edilmeli
- Visualization'lar çalışıyor, ancak daha interaktif hale getirilebilir

## 🎯 Kısa Vadeli Hedefler (1-2 hafta)

1. Greedy algoritmayı düzelt ve WalkScore artışı sağla
2. 15-minute coverage'ı en az %30'a çıkar
3. WalkScore parametrelerini kalibre et
4. Temel test senaryolarını çalıştır

## 🚀 Uzun Vadeli Hedefler (1-2 ay)

1. CP solver implementasyonu
2. Comprehensive test suite
3. Full documentation
4. Performance optimization
5. Interactive dashboard

