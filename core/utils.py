import os
import sys
import shutil
import tempfile
from pathlib import Path

def apply_dpi_scaling() -> None:
    """Windows DPI Scaling (Bulanık görünümü ve laptop ölçekleme sorunlarını çözer)"""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

def is_admin() -> bool:
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def cleanup_temp_directories() -> tuple:
    deleted_count = 0
    errors = []
    temp_paths = [
        Path(tempfile.gettempdir()),
        Path(os.environ.get("TEMP", "")),
        Path(os.environ.get("TMP", "")),
        Path("C:/Windows/Temp"),
    ]
    unique_paths = []
    for path in temp_paths:
        if str(path) and path.exists() and path not in unique_paths:
            unique_paths.append(path)

    for folder in unique_paths:
        try:
            for item in folder.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                    deleted_count += 1
                except Exception as ex:
                    errors.append(f"{item}: {ex}")
        except Exception as ex:
            errors.append(f"{folder}: {ex}")

    details = f"Silinen öğe sayısı: {deleted_count}"
    if errors:
        details += f"\nAtlanan/Hatalı öğe sayısı: {len(errors)}"
    return details, len(errors)

def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)