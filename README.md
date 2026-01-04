# Walkability Optimization for 15-Minute Cities

Bu proje, şehirlerde yürünebilirliği optimize etmek için tesislerin (market, okul, restoran) stratejik konumlandırılmasını sağlayan bir optimizasyon sistemidir.

## Proje Hakkında

Bu implementasyon, **"Walkability Optimization: Formulations, Algorithms, and a Case Study of Toronto"** (AAAI-23) makalesindeki modeli Balıkesir şehir merkezi için uygular.

### Amaç

15 dakikalık şehir konseptini desteklemek için:
- Konut bölgelerinden günlük ihtiyaçlara (market, okul, restoran) yürüme mesafelerini minimize etmek
- WalkScore metriklerini optimize etmek
- Yeni tesislerin optimal konumlarını belirlemek

## Proje Yapısı

```
walkability-optimization/
├── database/
│   └── schema.sql              # PostgreSQL database schema
├── src/
│   ├── data_collection/        # OSM veri çekme modülleri
│   ├── network/                # Graph network ve shortest paths
│   ├── scoring/                # WalkScore hesaplama
│   ├── models/                 # WALKOPT problem formulasyonu
│   ├── algorithms/             # MILP ve Greedy algoritmaları
│   ├── evaluation/             # Metrikler ve değerlendirme
│   ├── visualization/          # Harita görselleştirme
│   └── main.py                 # Ana pipeline
├── config.yaml                 # Konfigürasyon dosyası
├── requirements.txt            # Python bağımlılıkları
└── README.md
```

## Kurulum

### Gereksinimler

- Python 3.9+
- PostgreSQL 12+ (PostGIS extension ile)
- Gurobi Optimizer (MILP için) veya PuLP (alternatif)

### Adımlar

1. **Repository'yi klonlayın:**
```bash
git clone <repository-url>
cd walkability-optimization
```

2. **Virtual environment oluşturun:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# veya
venv\Scripts\activate  # Windows
```

3. **Bağımlılıkları yükleyin:**
```bash
pip install -r requirements.txt
```

4. **PostgreSQL veritabanını kurun:**
```bash
# PostgreSQL'i başlatın ve veritabanı oluşturun
createdb walkability_db
psql walkability_db < database/schema.sql
```

5. **Konfigürasyonu ayarlayın:**
```bash
cp .env.example .env
# .env dosyasını düzenleyin ve database bilgilerini girin
```

## Kullanım

### Veri Toplama

```bash
python src/data_collection/osm_loader.py
```

Bu komut Balıkesir şehir merkezi için OSM'den verileri çeker ve PostgreSQL'e yükler.

### Optimizasyon Çalıştırma

```bash
python src/main.py
```

Bu komut tüm pipeline'ı çalıştırır:
1. Veri yükleme
2. Graph oluşturma
3. Shortest paths hesaplama
4. Baseline WalkScore hesaplama
5. Optimizasyon (MILP/Greedy)
6. Sonuçları değerlendirme
7. Görselleştirme

## Başarı Kriterleri

Proje başarılı sayılır eğer:
- ✅ En az %70 konut bölgesi tüm tesislere 15 dakika içinde erişebiliyor
- ✅ WalkScore ortalama 25 puan artıyor
- ✅ Ortalama yürüme mesafesi %30 azalıyor

## Referanslar

- Huang, W., & Khalil, E. B. (2023). Walkability Optimization: Formulations, Algorithms, and a Case Study of Toronto. AAAI-23.
- [GitHub Repository](https://github.com/khalil-research/walkability)

## Lisans

Bu proje akademik amaçlıdır.

## Yazar

- Mert Emir ŞEKER
- Veysel CEMALOĞLU
- Danışman: Prof. Dr. Didem GÖZÜPEK

