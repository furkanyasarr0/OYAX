import os

# AppData yolunu bul ve Oyax klasörü yoksa oluştur
APPDATA_PATH = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'Oyax')
if not os.path.exists(APPDATA_PATH):
    os.makedirs(APPDATA_PATH)

DB_FILE = os.path.join(APPDATA_PATH, "maintenance_logs.db")
APP_VERSION = "1.3"
AUTHOR_NAME = "furkanysrr0"

TASK_CATEGORIES = {
    "Geçici Dosyalar ve Cache": [
        {"name": "Geçici Dosyaları Temizle", "requires_admin": False, "type": "python"},
        {
            "name": "Windows Temp Temizliği (powershell)",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "Get-ChildItem -Path C:\\Windows\\Temp -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"],
        },
        {
            "name": "Prefetch Temizliği",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "Remove-Item -Path C:\\Windows\\Prefetch\\* -Force -Recurse -ErrorAction SilentlyContinue"],
        },
        {
            "name": "Geri Dönüşüm Kutusu Temizle",
            "requires_admin": False,
            "type": "command",
            "command": ["powershell", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
        },
        {
            "name": "Microsoft Store Cache Sıfırla",
            "requires_admin": False,
            "type": "command",
            "command": ["wsreset.exe"],
        },
    ],
    "Ağ ve DNS": [
        {"name": "DNS Önbelleğini Temizle (ipconfig /flushdns)", "requires_admin": True, "type": "command", "command": ["ipconfig", "/flushdns"]},
        {"name": "DNS Önbelleğini Görüntüle", "requires_admin": False, "type": "command", "command": ["ipconfig", "/displaydns"]},
        {"name": "DNS Yeniden Kaydet (ipconfig /registerdns)", "requires_admin": True, "type": "command", "command": ["ipconfig", "/registerdns"]},
        {
            "name": "IP Adresini Yenile (release + renew)",
            "requires_admin": True,
            "type": "command",
            "command": ["powershell", "-Command", "ipconfig /release; ipconfig /renew"],
        },
        {"name": "ARP Cache Temizliği", "requires_admin": True, "type": "command", "command": ["arp", "-d", "*"]},
    ],
    "Ağ Sıfırlama": [
        {"name": "Winsock Sıfırla (netsh winsock reset)", "requires_admin": True, "type": "command", "command": ["netsh", "winsock", "reset"]},
        {"name": "TCP/IP Stack Sıfırla", "requires_admin": True, "type": "command", "command": ["netsh", "int", "ip", "reset"]},
        {"name": "Windows Güvenlik Duvarını Sıfırla", "requires_admin": True, "type": "command", "command": ["netsh", "advfirewall", "reset"]},
    ],
    "Sistem Sağlığı": [
        {"name": "SFC Taraması (sfc /scannow)", "requires_admin": True, "type": "command", "command": ["sfc", "/scannow"]},
        {"name": "DISM Health Check", "requires_admin": True, "type": "command", "command": ["DISM", "/Online", "/Cleanup-Image", "/CheckHealth"]},
        {"name": "DISM Scan Health", "requires_admin": True, "type": "command", "command": ["DISM", "/Online", "/Cleanup-Image", "/ScanHealth"]},
        {"name": "DISM Restore Health", "requires_admin": True, "type": "command", "command": ["DISM", "/Online", "/Cleanup-Image", "/RestoreHealth"]},
        {"name": "Disk Tarama (chkdsk /scan)", "requires_admin": True, "type": "command", "command": ["chkdsk", "/scan"]},
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
            }
    return tasks

TASKS = build_task_map()