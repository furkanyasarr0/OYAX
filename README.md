# <p align="center">🛠️ OYAX - Windows Bakım Aracı</p>

<p align="center">
  <img src="[https://img.shields.io/badge/version-1.0.0-blue.svg](https://img.shields.io/badge/version-1.0.0-blue.svg)" alt="Version">
  <img src="[https://img.shields.io/badge/python-3.10%2B-blue.svg](https://img.shields.io/badge/python-3.10%2B-blue.svg)" alt="Python">
  <img src="[https://img.shields.io/badge/license-Open_Source_%2B_VDS_Auth-green.svg](https://img.shields.io/badge/license-Open_Source_%2B_VDS_Auth-green.svg)" alt="License">
  <img src="[https://img.shields.io/badge/platform-windows-lightgrey.svg](https://img.shields.io/badge/platform-windows-lightgrey.svg)" alt="Platform">
  <img src="[https://img.shields.io/github/stars/furkanyasarr0/OYAX?style=social](https://img.shields.io/github/stars/furkanyasarr0/OYAX?style=social)" alt="Stars">
</p>

---

**OYAX**, Windows işletim sistemi üzerinde performans artırıcı bakım ve kritik onarım işlemlerini tek bir arayüzden yönetmenizi sağlayan, açık kaynak kodlu ancak güvenli lisans doğrulama sistemine sahip bir optimizasyon aracıdır.

## ✨ Öne Çıkan Özellikler

- 🗂️ **Kategorize Edilmiş Menü:** Geçici dosyalar, Ağ/DNS ve Sistem Sağlığı için ayrılmış kontrol panelleri.
- 🧹 **Gelişmiş Temizlik:** 
  - `Temp` ve `Prefetch` dizinleri.
  - Geri Dönüşüm Kutusu (Recycle Bin).
  - Windows Store önbelleği.
- 🌐 **Ağ & DNS Optimizasyonu:** 
  - DNS önbelleği temizleme (Flush DNS).
  - IP yenileme (Release/Renew).
  - Winsock protokolü sıfırlama.
- 🛡️ **Kritik Sistem Onarımı:** 
  - `SFC Scannow` ile dosya doğrulama.
  - `DISM` araçları ile imaj onarımı.
  - `chkdsk` disk hataları taraması.
- 🚀 **Hızlı Bakım Modu:** En kritik görevleri tek tıkla sıralı olarak çalıştırır.
- 📊 **SQLite Kayıt Defteri:** Yapılan işlemlerin geçmişini tutar ve CSV olarak dışa aktarmanıza olanak tanır.
- 🔑 **VDS Lisans Sistemi:** Uygulama güvenliği için VDS tabanlı HWID eşleştirmeli doğrulama.

## 📸 Ekran Görüntüleri

| Ana Kontrol Paneli | Lisans Doğrulama |
| :---: | :---: |
| ![Ana Ekran](https://via.placeholder.com/400x250?text=OYAX+Dashboard) | ![Lisans Kontrol](https://via.placeholder.com/400x250?text=VDS+Auth+System) |

## 🚀 Kurulum ve Kullanım

Projeyi kendi bilgisayarınızda çalıştırmak için aşağıdaki adımları izleyin.

### Ön Gereksinimler
- Python 3.10 veya üzeri bir sürümün yüklü olması gerekmektedir.
- Windows işletim sistemi (Bazı komutlar yönetici yetkisi gerektirir).

### Çalıştırma Adımları
1. Proje reposunu klonlayın veya indirin.
2. Komut satırında proje dizinine gidin.
3. Sanal ortamınızı (venv) oluşturun ve aktif edin:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```
4. Uygulamayı başlatın:
   
```powershell
   python app.py
   ```

> [!IMPORTANT]
> Sistem dosyalarına müdahale eden (SFC/DISM vb.) özelliklerin doğru çalışabilmesi için uygulamayı **Yönetici Olarak Çalıştır** seçeneğiyle açmanız önerilir.

## 🛠️ Teknik Altyapı

- **Programlama Dili:** Python
- **Arayüz (UI):** Tkinter (Modernize edilmiş, kullanıcı dostu tema)
- **Veritabanı:** SQLite3 (İşlem logları için)
- **Güvenlik:** Uzak VDS sunucu üzerinden HWID tabanlı API doğrulaması.

## 🛡️ Lisans ve Kullanım Koşulları

Bu projenin kaynak kodları **Açık Kaynak (Open Source)** olarak paylaşılmıştır. Kod yapısını inceleyebilir ve geliştirmeye katkıda bulunabilirsiniz. 

Ancak, uygulamanın tam fonksiyonel olarak çalışması ve yetkilendirme işlemleri, geliştirici tarafından yönetilen **VDS_License** (Özel VDS Doğrulama) sistemine tabidir. İzinsiz ticari dağıtımı yasaktır.

---
**Geliştirici:** [furkanysrr0](https://github.com/furkanyasarr0)