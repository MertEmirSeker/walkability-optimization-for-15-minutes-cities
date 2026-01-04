# Nasıl Çalıştırılır? 🚀

Bu projeyi çalıştırmak için aşağıdaki adımları takip edin:

## 1. Virtual Environment'ı Aktifleştirin

```bash
cd /home/seker/workplace/walkability-optimization-for-15-minutes-cities
source venv/bin/activate
```

## 2. Bağımlılıkları Kontrol Edin

Bağımlılıklar zaten yüklü görünüyor. Eğer eksik bir şey varsa:

```bash
pip install -r requirements.txt
```

## 3. PostgreSQL Veritabanını Hazırlayın

**ÖNEMLİ:** Proje PostgreSQL veritabanı gerektirir.

### Veritabanını Oluşturun:

```bash
# Veritabanını oluştur
createdb walkability_center_db

# Schema'yı yükle
psql walkability_center_db < database/schema.sql
```

**Not:** `config.yaml` dosyasında veritabanı adı `walkability_center_db` olarak ayarlanmış. 
Eğer farklı bir isim kullanıyorsanız, `config.yaml` dosyasını düzenleyin.

## 4. Projeyi Çalıştırın

### Temel Kullanım (Tüm Pipeline):

```bash
python src/main.py
```

### Sadece Greedy Algoritması (Hızlı Test):

```bash
python src/main.py --algorithm greedy --k 1
```

### Mevcut Verilerle (Veri Yükleme Atlanır):

```bash
python src/main.py --skip-data-load --skip-distances --skip-baseline
```

### Görselleştirme ile:

```bash
python src/main.py --visualize --evaluate
```

### Tüm Seçenekler:

```bash
python src/main.py --help
```

## 5. Komut Satırı Seçenekleri

- `--skip-data-load`: OSM veri yükleme adımını atla (mevcut verileri kullan)
- `--skip-distances`: Mesafe hesaplama adımını atla
- `--skip-baseline`: Baseline WalkScore hesaplama adımını atla
- `--algorithm {greedy,milp,both}`: Hangi optimizasyon algoritmasını çalıştır (varsayılan: both)
- `--k <sayı>`: Her tesis tipi için kaç tesis yerleştirilecek (varsayılan: 3)
- `--visualize`: Görselleştirme haritaları oluştur
- `--evaluate`: Sonuçları değerlendir ve rapor oluştur

## 6. Örnek Kullanım Senaryoları

### Senaryo 1: İlk Çalıştırma (Tüm Adımlar)

```bash
python src/main.py --visualize --evaluate
```

### Senaryo 2: Hızlı Test (Sadece Greedy, k=1)

```bash
python src/main.py --algorithm greedy --k 1 --visualize
```

### Senaryo 3: Mevcut Verilerle Optimizasyon

```bash
python src/main.py --skip-data-load --skip-distances --skip-baseline --algorithm greedy --k 3 --visualize --evaluate
```

## 7. Çıktılar

- **Görselleştirmeler**: `visualizations/` klasöründe HTML haritalar
- **Raporlar**: `results/` klasöründe değerlendirme raporları
- **Veriler**: PostgreSQL veritabanında saklanır

## 8. Sorun Giderme

### Veritabanı Bağlantı Hatası:

```bash
# PostgreSQL servisinin çalıştığından emin olun
sudo systemctl status postgresql

# Veritabanı bağlantısını test edin
psql -U seker -d walkability_center_db -c "SELECT 1;"
```

### Gurobi Lisans Hatası:

MILP çözücü için Gurobi lisansı gerekir. Eğer lisans yoksa, sadece Greedy algoritmasını kullanın:

```bash
python src/main.py --algorithm greedy
```

### Eksik Modül Hatası:

```bash
pip install -r requirements.txt
```

## 9. Hızlı Başlangıç (Önerilen)

```bash
# 1. Virtual environment'ı aktifleştir
source venv/bin/activate

# 2. Veritabanını hazırla (ilk kez çalıştırıyorsanız)
createdb walkability_center_db
psql walkability_center_db < database/schema.sql

# 3. Projeyi çalıştır (hızlı test için)
python src/main.py --algorithm greedy --k 1 --visualize
```

## Notlar

- İlk çalıştırmada OSM verileri indirileceği için biraz zaman alabilir
- Görselleştirmeler `visualizations/` klasöründe HTML dosyaları olarak oluşturulur
- Browser'da HTML dosyalarını açarak haritaları görüntüleyebilirsiniz

