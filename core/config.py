import os

# AppData yolunu bul ve Oyax klasörü yoksa oluştur
APPDATA_PATH = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'Oyax')
if not os.path.exists(APPDATA_PATH):
    os.makedirs(APPDATA_PATH)

DB_FILE = os.path.join(APPDATA_PATH, "maintenance_logs.db")
APP_VERSION = "1.4"
AUTHOR_NAME = "furkanysrr0"

CATEGORY_ICONS = {
    "Tümü": "📋",
    "Geçici Dosyalar ve Cache": "🧹",
    "Ağ ve DNS": "🌐",
    "Ağ Sıfırlama": "🔄",
    "Sistem Sağlığı": "🛡️",
    "Performans Optimizasyonu": "🚀",
    "Disk Yönetimi": "💾",
    "Güvenlik": "🔒",
    "Sistem Bilgisi": "📊",
}

TASK_CATEGORIES = {
    "Geçici Dosyalar ve Cache": [
        {"name": "Geçici Dosyaları Temizle", "requires_admin": False, "type": "python",
         "description": "Windows ve kullanıcı temp klasörlerindeki geçici dosyaları siler"},
        {
            "name": "Windows Temp Temizliği (powershell)",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "Get-ChildItem -Path C:\\Windows\\Temp -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"],
            "description": "C:\\Windows\\Temp klasöründeki tüm dosya ve klasörleri temizler",
        },
        {
            "name": "Prefetch Temizliği",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "Remove-Item -Path C:\\Windows\\Prefetch\\* -Force -Recurse -ErrorAction SilentlyContinue"],
            "description": "Uygulama önbellek dosyalarını temizler, açılış verisi sıfırlanır",
        },
        {
            "name": "Geri Dönüşüm Kutusu Temizle",
            "requires_admin": False,
            "type": "command",
            "command": ["powershell", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
            "description": "Çöp kutusundaki tüm dosyaları kalıcı olarak siler",
        },
        {
            "name": "Microsoft Store Cache Sıfırla",
            "requires_admin": False,
            "type": "command",
            "command": ["wsreset.exe"],
            "description": "Windows Store uygulamasının önbelleğini sıfırlar",
        },
        {
            "name": "Thumbnail Cache Temizle",
            "requires_admin": False,
            "type": "command",
            "command": ["powershell", "-Command", "Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue; Remove-Item -Path \"$env:LOCALAPPDATA\\Microsoft\\Windows\\Explorer\\thumbcache_*\" -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 2; Start-Process explorer"],
            "description": "Dosya gezginindeki küçük resim önbelleğini yeniden oluşturur",
        },
        {
            "name": "Font Cache Temizle",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "Stop-Service -Name FontCache -Force -ErrorAction SilentlyContinue; Remove-Item -Path \"$env:WinDir\\ServiceProfiles\\LocalService\\AppData\\Local\\FontCache\\*\" -Force -Recurse -ErrorAction SilentlyContinue; Start-Service -Name FontCache -ErrorAction SilentlyContinue"],
            "description": "Yazı tipi önbelleğini temizler, bozuk font sorunlarını çözer",
        },
        {
            "name": "Windows Icon Cache Temizle",
            "requires_admin": False,
            "type": "command",
            "command": ["powershell", "-Command", "Remove-Item -Path \"$env:LOCALAPPDATA\\IconCache.db\" -Force -ErrorAction SilentlyContinue; Remove-Item -Path \"$env:LOCALAPPDATA\\Microsoft\\Windows\\Explorer\\iconcache_*\" -Force -ErrorAction SilentlyContinue"],
            "description": "Simge önbelleğini temizler, bozuk simgeleri düzeltir",
        },
    ],
    "Ağ ve DNS": [
        {"name": "DNS Önbelleğini Temizle (ipconfig /flushdns)", "requires_admin": True, "type": "command", "command": ["ipconfig", "/flushdns"],
         "description": "DNS çözümleme önbelleğini temizler, bağlantı sorunlarını çözer"},
        {"name": "DNS Önbelleğini Görüntüle", "requires_admin": False, "type": "command", "command": ["ipconfig", "/displaydns"],
         "description": "Mevcut DNS önbellek kayıtlarını listeler"},
        {"name": "DNS Yeniden Kaydet (ipconfig /registerdns)", "requires_admin": True, "type": "command", "command": ["ipconfig", "/registerdns"],
         "description": "DNS istemcisini Active Directory'ye yeniden kaydeder"},
        {
            "name": "IP Adresini Yenile (release + renew)",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "ipconfig /release; ipconfig /renew"],
            "description": "DHCP sunucusundan yeni IP adresi alır",
        },
        {"name": "ARP Cache Temizliği", "requires_admin": True, "type": "command", "command": ["arp", "-d", "*"],
         "description": "ARP tablosunu temizler, ağ çakışmalarını giderir"},
        {
            "name": "Aktif Bağlantıları Görüntüle (netstat)",
            "requires_admin": False,
            "type": "command",
            "command": ["netstat", "-ano"],
            "description": "Tüm açık ağ bağlantılarını ve portları listeler",
        },
        {
            "name": "Ağ Adaptörü Bilgilerini Görüntüle",
            "requires_admin": False,
            "type": "command",
            "command": ["powershell", "-Command", "Get-NetAdapter | Select-Object Name, Status, MacAddress, LinkSpeed | Format-Table -AutoSize"],
            "description": "Ağ kartı durumunu, MAC adresi ve hız bilgisini gösterir",
        },
        {
            "name": "IP Konfigürasyonunu Görüntüle (ipconfig /all)",
            "requires_admin": False,
            "type": "command",
            "command": ["ipconfig", "/all"],
            "description": "Tüm ağ adaptörlerinin detaylı IP yapılandırma bilgilerini gösterir",
        },
        {
            "name": "Bağlantı Testi (Ping)",
            "requires_admin": False,
            "type": "command",
            "command": ["ping", "8.8.8.8", "-n", "4"],
            "description": "Google DNS sunucusuna ping atarak internet bağlantısını test eder",
        },
        {
            "name": "DNS Çözümleme Testi",
            "requires_admin": False,
            "type": "command",
            "command": ["nslookup", "google.com"],
            "description": "DNS sunucusunun alan adlarını çözümleyebildiğini kontrol eder",
        },
        {
            "name": "Traceroute Testi",
            "requires_admin": False,
            "type": "command",
            "command": ["tracert", "-d", "-h", "15", "8.8.8.8"],
            "description": "Hedefe giden ağ yolunu ve her düğümdeki gecikmeyi gösterir",
        },
        {
            "name": "Wi-Fi Profilleri Listele",
            "requires_admin": False,
            "type": "command",
            "command": ["netsh", "wlan", "show", "profiles"],
            "description": "Kaydedilmiş tüm kablosuz ağ profillerini listeler",
        },
        {
            "name": "Wi-Fi Şifresini Görüntüle (Bağlı Ağ)",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "$prof = (netsh wlan show interfaces | Select-String 'Profile' | ForEach-Object { ($_ -split ':')[1].Trim() }); if($prof){ netsh wlan show profile name=$prof key=clear } else { Write-Host 'Bağlı Wi-Fi ağı bulunamadı' }"],
            "description": "Şu an bağlı olduğunuz Wi-Fi ağının şifresini gösterir",
        },
        {
            "name": "Route Tablosunu Görüntüle",
            "requires_admin": False,
            "type": "command",
            "command": ["route", "print"],
            "description": "IP yönlendirme tablosunu görüntüler",
        },
        {
            "name": "DNS Sunucu Bilgilerini Görüntüle",
            "requires_admin": False,
            "type": "command",
            "command": ["powershell", "-Command", "Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object { $_.ServerAddresses } | Select-Object InterfaceAlias, ServerAddresses | Format-Table -AutoSize"],
            "description": "Tüm adaptörlerde kullanılan DNS sunucu adreslerini gösterir",
        },
        {
            "name": "Ağ Bant Genişliği Kullanımı",
            "requires_admin": False,
            "type": "command",
            "command": ["powershell", "-Command", "Get-NetAdapterStatistics | Select-Object Name, ReceivedBytes, SentBytes, @{N='Alınan_MB';E={[math]::Round($_.ReceivedBytes/1MB,2)}}, @{N='Gönderilen_MB';E={[math]::Round($_.SentBytes/1MB,2)}} | Format-Table -AutoSize"],
            "description": "Ağ adaptörlerinin gönderilen/alınan veri miktarını gösterir",
        },
    ],
    "Ağ Sıfırlama": [
        {"name": "Winsock Sıfırla (netsh winsock reset)", "requires_admin": True, "type": "command", "command": ["netsh", "winsock", "reset"],
         "description": "Ağ soket kütüphanesini fabrika ayarlarına döndürür"},
        {"name": "TCP/IP Stack Sıfırla", "requires_admin": True, "type": "command", "command": ["netsh", "int", "ip", "reset"],
         "description": "TCP/IP protokol yığınını sıfırlar, bağlantı sorunlarını giderir"},
        {"name": "Windows Güvenlik Duvarını Sıfırla", "requires_admin": True, "type": "command", "command": ["netsh", "advfirewall", "reset"],
         "description": "Güvenlik duvarı kurallarını varsayılan ayarlara döndürür"},
        {
            "name": "DNS İstemci Servisini Yeniden Başlat",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "Restart-Service -Name Dnscache -Force -ErrorAction SilentlyContinue"],
            "description": "DNS çözümleme servisini yeniden başlatır",
        },
        {
            "name": "DHCP İstemci Servisini Yeniden Başlat",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "Restart-Service -Name Dhcp -Force -ErrorAction SilentlyContinue"],
            "description": "IP adresi otomatik alma servisini yeniden başlatır",
        },
        {
            "name": "Ağ Adaptörlerini Yeniden Başlat",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | Restart-NetAdapter -Confirm:$false"],
            "description": "Aktif ağ adaptörlerini devre dışı bırakıp yeniden etkinleştirir",
        },
        {
            "name": "NetBIOS Önbelleğini Temizle",
            "requires_admin": True,
            "type": "command",
            "command": ["nbtstat", "-R"],
            "description": "NetBIOS ad önbelleğini temizler ve LMHOSTS dosyasını yeniden yükler",
        },
    ],
    "Sistem Sağlığı": [
        {"name": "SFC Taraması (sfc /scannow)", "requires_admin": True, "type": "command", "command": ["sfc", "/scannow"],
         "description": "Bozuk sistem dosyalarını tarar ve onarır"},
        {"name": "DISM Health Check", "requires_admin": True, "type": "command", "command": ["DISM", "/Online", "/Cleanup-Image", "/CheckHealth"],
         "description": "Windows imaj deposunun sağlık durumunu kontrol eder"},
        {"name": "DISM Scan Health", "requires_admin": True, "type": "command", "command": ["DISM", "/Online", "/Cleanup-Image", "/ScanHealth"],
         "description": "Bileşen deposunu detaylı tarar, bozulma olup olmadığını raporlar"},
        {"name": "DISM Restore Health", "requires_admin": True, "type": "command", "command": ["DISM", "/Online", "/Cleanup-Image", "/RestoreHealth"],
         "description": "Bozuk bileşen deposunu Windows Update üzerinden onarır"},
        {"name": "Disk Tarama (chkdsk /scan)", "requires_admin": True, "type": "command", "command": ["chkdsk", "/scan"],
         "description": "Diskteki dosya sistemi hatalarını tarar"},
        {
            "name": "Windows Bileşen Deposu Temizliği",
            "requires_admin": True,
            "type": "command",
            "command": ["DISM", "/Online", "/Cleanup-Image", "/StartComponentCleanup"],
            "description": "Eski Windows bileşen sürümlerini kaldırarak disk alanı kazandırır",
        },
    ],
    "Performans Optimizasyonu": [
        {
            "name": "Windows Update Cache Temizle",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "Stop-Service -Name wuauserv -Force -ErrorAction SilentlyContinue; Remove-Item -Path C:\\Windows\\SoftwareDistribution\\Download\\* -Recurse -Force -ErrorAction SilentlyContinue; Start-Service -Name wuauserv -ErrorAction SilentlyContinue"],
            "description": "Windows Update indirme önbelleğini temizler, güncelleme sorunlarını çözer",
        },
        {
            "name": "Yüksek Performans Güç Planını Etkinleştir",
            "requires_admin": True,
            "type": "command",
            "command": ["powercfg", "/setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"],
            "description": "Güç planını Yüksek Performans moduna geçirir",
        },
        {
            "name": "Aktif Güç Planını Görüntüle",
            "requires_admin": False,
            "type": "command",
            "command": ["powercfg", "/getactivescheme"],
            "description": "Şu an aktif olan güç planını gösterir",
        },
        {
            "name": "Hızlı Başlatmayı Etkinleştir",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "Set-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Power' -Name HiberbootEnabled -Value 1 -ErrorAction SilentlyContinue"],
            "description": "Windows hızlı başlatma özelliğini etkinleştirir, açılış süresini kısaltır",
        },
        {
            "name": "Görsel Efektleri Performans İçin Optimize Et",
            "requires_admin": False,
            "type": "command",
            "command": ["powershell", "-Command", "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\VisualEffects' -Name VisualFXSetting -Value 2 -ErrorAction SilentlyContinue"],
            "description": "Animasyonları ve görsel efektleri kapatarak performansı artırır",
        },
    ],
    "Disk Yönetimi": [
        {
            "name": "Disk Optimizasyonu (Defrag/TRIM)",
            "requires_admin": True,
            "type": "command",
            "command": ["defrag", "C:", "/O"],
            "description": "HDD için birleştirme, SSD için TRIM komutu çalıştırır",
        },
        {
            "name": "Compact OS Durumunu Sorgula",
            "requires_admin": True,
            "type": "command",
            "command": ["compact", "/compactos:query"],
            "description": "İşletim sisteminin sıkıştırılmış olup olmadığını kontrol eder",
        },
        {
            "name": "Disk Alanı Raporu",
            "requires_admin": False,
            "type": "command",
            "command": ["powershell", "-Command", "Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='Kullanilan_GB';E={[math]::Round($_.Used/1GB,2)}}, @{N='Bos_GB';E={[math]::Round($_.Free/1GB,2)}}, @{N='Toplam_GB';E={[math]::Round(($_.Used+$_.Free)/1GB,2)}} | Format-Table -AutoSize"],
            "description": "Tüm disklerin kullanım durumunu ve boş alanı raporlar",
        },
        {
            "name": "Büyük Dosya Tarama (500MB+)",
            "requires_admin": False,
            "type": "command",
            "command": ["powershell", "-Command", "Get-ChildItem -Path C:\\ -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Length -gt 500MB } | Sort-Object Length -Descending | Select-Object -First 20 @{N='Boyut_MB';E={[math]::Round($_.Length/1MB,1)}}, FullName | Format-Table -AutoSize"],
            "description": "C: diskinde 500MB üzeri dosyaları bulur ve listeler",
        },
    ],
    "Güvenlik": [
        {
            "name": "Windows Defender Hızlı Tarama",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "Start-MpScan -ScanType QuickScan"],
            "description": "Sistem belleğini ve yaygın tehdit alanlarını hızlıca tarar",
        },
        {
            "name": "Windows Defender Tanım Güncelle",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "Update-MpSignature"],
            "description": "Virüs ve kötü amaçlı yazılım tanımlarını günceller",
        },
        {
            "name": "Güvenlik Duvarı Durumunu Görüntüle",
            "requires_admin": False,
            "type": "command",
            "command": ["netsh", "advfirewall", "show", "allprofiles", "state"],
            "description": "Tüm güvenlik duvarı profillerinin aktif/pasif durumunu gösterir",
        },
        {
            "name": "Windows Defender Durumunu Görüntüle",
            "requires_admin": False,
            "type": "command",
            "command": ["powershell", "-Command", "Get-MpComputerStatus | Select-Object AntivirusEnabled, RealTimeProtectionEnabled, AntispywareEnabled, AntivirusSignatureLastUpdated | Format-List"],
            "description": "Antivirüs, gerçek zamanlı koruma ve tanım güncelleme durumunu gösterir",
        },
    ],
    "Sistem Bilgisi": [
        {
            "name": "Sistem Bilgisi Raporu",
            "requires_admin": False,
            "type": "command",
            "command": ["systeminfo"],
            "description": "İşletim sistemi, donanım ve ağ bilgilerinin tam raporunu verir",
        },
        {
            "name": "Sürücü Listesi",
            "requires_admin": False,
            "type": "command",
            "command": ["driverquery", "/FO", "TABLE"],
            "description": "Sistemde yüklü tüm sürücüleri tablo olarak listeler",
        },
        {
            "name": "Yüklü Güncellemeler (Son 20)",
            "requires_admin": False,
            "type": "command",
            "command": ["powershell", "-Command", "Get-HotFix | Sort-Object InstalledOn -Descending -ErrorAction SilentlyContinue | Select-Object -First 20 HotFixID, Description, InstalledOn | Format-Table -AutoSize"],
            "description": "En son yüklenen 20 Windows güncellemesini gösterir",
        },
        {
            "name": "Başlangıç Programları Listesi",
            "requires_admin": False,
            "type": "command",
            "command": ["powershell", "-Command", "Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location | Format-Table -AutoSize"],
            "description": "Windows başlangıcında otomatik çalışan programları listeler",
        },
        {
            "name": "Çalışan Servisler Listesi",
            "requires_admin": False,
            "type": "command",
            "command": ["powershell", "-Command", "Get-Service | Where-Object {$_.Status -eq 'Running'} | Sort-Object DisplayName | Select-Object DisplayName, Name, Status | Format-Table -AutoSize"],
            "description": "Şu an çalışan tüm Windows servislerini listeler",
        },
        {
            "name": "Donanım Bilgisi Özeti",
            "requires_admin": False,
            "type": "command",
            "command": ["powershell", "-Command", "$cpu = (Get-CimInstance Win32_Processor).Name; $ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1); $os = (Get-CimInstance Win32_OperatingSystem).Caption; Write-Host \"İşlemci: $cpu\"; Write-Host \"RAM: ${ram} GB\"; Write-Host \"İşletim Sistemi: $os\""],
            "description": "İşlemci, RAM ve işletim sistemi bilgilerini özetler",
        },
    ],
}

def build_task_map() -> dict:
    tasks: dict = {}
    for category_name, category_tasks in TASK_CATEGORIES.items():
        for task in category_tasks:
            tasks[task["name"]] = {
                "requires_admin": task["requires_admin"],
                "type": task["type"],
                "command": task.get("command"),
                "category": category_name,
                "description": task.get("description", ""),
            }
    return tasks

TASKS = build_task_map()