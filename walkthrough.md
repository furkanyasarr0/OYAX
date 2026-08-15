# 🚀 OYAX v1.4 — Yeni Özellikler & Otomatik Güncelleme Sistemi

İstenen 3 geliştirme tamamlandı:

---

## ✨ Eklenen ve Güncellenen Özellikler

### 1. 🗂️ Kategori Scrollbar'ı Gizlendi (Sade & Şık Tasarım)
- Kategori listesindeki kaydırma çubuğu (scrollbar) tamamen kaldırılarak tüm kategoriler ferah ve pürüzsüz bir dikey menüye dönüştürüldü.
- 9 kategori tek bakışta net olarak görülür.

### 2. 😃 Gelişmiş Emoji & Tipografi Desteği
- `Segoe UI` ve `Segoe UI Emoji` font motoru entegre edildi.
- Uygulama içi tüm simgeler, durum rozetleri, kategori butonları ve bildirimler modern Windows renkli emoji standartlarında net olarak görüntülenir.

### 3. 🔄 Başlangıçta Otomatik Güncelleme & Tek Tıkla Doğrudan Güncelleme (In-App Auto-Updater)
- **Açılışta Otomatik Denetim:** Uygulama başlatıldığında arka planda sessizce GitHub Releases API'sini sorgular.
- **Modern Güncelleme Pop-up'ı:** Yeni bir sürüm tespit edildiğinde sürüm notları, yeni versiyon numarası ve **"🚀 Şimdi Güncelle"** butonu içeren şık bir pencere açılır.
- **Tek Tıkla Otomatik Güncelleme:** **"Şimdi Güncelle"** butonuna basıldığında:
  1. GitHub'dan en son sürüm arşivini indirir.
  2. Dosyaları otomatik ayıklar ve mevcut proje dizinine yazar.
  3. İlerleme çubuğunu günceller ve uygulamayı **otomatik olarak yeniden başlatır**.
  4. Hata durumunda ise kullanıcıyı GitHub sürüm sayfasına yönlendirir.

---

## 🚀 Uygulamayı Başlatma
```powershell
python OYAX.py
```
