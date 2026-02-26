import re
import os
import time
import threading
import subprocess
from typing import Optional

def log(msg: str, on_log: Optional[callable] = None):
    """Escribe en stdout y en la cola de logs del frontend si está disponible."""
    print(msg, flush=True)
    if on_log:
        try:
            on_log(msg)
        except Exception:
            pass

def find_file_path(expected_filename: str, title: str = "", mount_path: str = "/mnt/torbox", on_log: Optional[callable] = None) -> Optional[str]:
    """
    Busca un archivo en TorBox usando el nombre exacto del archivo.
    Realiza una sola pasada de búsqueda.
    """
    expected_lower = expected_filename.lower()
    
    if not os.path.exists(mount_path):
        log(f"[Watcher] El directorio de montaje no existe: {mount_path}", on_log)
        return None

    try:
        raw_items = os.listdir(mount_path)
    except Exception as e:
        log(f"[Watcher] Error listando {mount_path}: {e}", on_log)
        return None

    # PASO 1: Archivo directo en la raíz
    for item in raw_items:
        if item.lower() == expected_lower:
            item_path = os.path.join(mount_path, item)
            if os.path.isfile(item_path):
                log(f"[Watcher] ✓ Encontrado en raíz: {item}", on_log)
                return item_path

    # PASO 2: Buscar en subcarpetas
    title_words = [w.lower() for w in re.split(r'[\s\.\-_]+', title) if len(w) >= 3] if title else []

    def walk_for_exact(folder_path: str) -> Optional[str]:
        expected_no_ext = os.path.splitext(expected_lower)[0]
        try:
            for root, dirs, files in os.walk(folder_path):
                depth = root[len(folder_path):].count(os.sep)
                if depth > 4:
                    dirs.clear()
                    continue
                for f in files:
                    f_lower = f.lower()
                    if f_lower == expected_lower or os.path.splitext(f_lower)[0] == expected_no_ext:
                        return os.path.join(root, f)
        except Exception:
            pass
        return None

    candidates = []
    others = []
    for item in raw_items:
        item_path = os.path.join(mount_path, item)
        if not os.path.isdir(item_path):
            continue
        item_l = item.lower()
        if title_words and any(w in item_l for w in title_words):
            candidates.append(item_path)
        else:
            others.append(item_path)

    # Primero prioritarias
    for folder in candidates:
        result = walk_for_exact(folder)
        if result:
            return result

    # Luego el resto
    for folder in others:
        result = walk_for_exact(folder)
        if result:
            return result

    return None

def check_file_exists(expected_filename: str, title: str = "", mount_path: str = "/mnt/torbox") -> Optional[str]:
    """Versión sincrónica de una sola pasada para checking rápido."""
    return find_file_path(expected_filename, title, mount_path)

def watch_for_file(
    expected_filename: str,
    title: str = "",
    year: str = "",
    season: int = None,
    episode: int = None,
    mount_path: str = "/mnt/torbox",
    timeout_seconds: int = 3600,
    on_status: Optional[callable] = None,
    get_status: Optional[callable] = None,
    original_title: str = "",
    on_log: Optional[callable] = None
) -> Optional[str]:
    """
    Busca un archivo en TorBox usando el nombre exacto del archivo
    provisto por AIOStreams (o extraído de la URL).
    """
    start_time = time.time()
    msg = f"Buscando archivo: '{expected_filename}'"
    log(f"[Watcher] {msg}", on_log)
    if on_status:
        on_status("Searching", msg)

    while time.time() - start_time < timeout_seconds:
        if get_status:
            status = get_status()
            if status == "Cancelled":
                log(f"[Watcher] Búsqueda cancelada.", on_log)
                return None
            if status == "Paused":
                time.sleep(5)
                continue

        time.sleep(10)
        elapsed = int(time.time() - start_time)
        log(f"[Watcher] Ciclo de búsqueda... ({elapsed}s)", on_log)
        if on_status:
            on_status("Searching", f"Buscando '{expected_filename}'... ({elapsed}s)")

        try:
            subprocess.run(["rclone", "rc", "vfs/forget"], capture_output=True, timeout=3)
        except Exception:
            pass

        found_path = find_file_path(expected_filename, title, mount_path, on_log)
        if found_path:
            return found_path

        log(f"[Watcher] Archivo no encontrado. Esperando...", on_log)

    return None

    log(f"[Watcher] Timeout: '{expected_filename}' no apareció en {timeout_seconds}s.", on_log)
    return None


def start_watcher_thread(
    expected_filename: str,
    title: str,
    year: str,
    callback,
    season_number: int = None,
    episode_number: int = None,
    on_status: Optional[callable] = None,
    get_status: Optional[callable] = None,
    original_title: str = "",
    on_log: Optional[callable] = None
):
    """
    Inicia la búsqueda en segundo plano y llama al callback con la ruta cuando la encuentra.
    """
    def run_watch():
        se_str = f" S{season_number:02d}E{(episode_number or 0):02d}" if season_number else ""
        log(f"[Watcher] Iniciando búsqueda: {title}{se_str} → '{expected_filename}'", on_log)
        found_path = watch_for_file(
            expected_filename, title, year, season_number, episode_number,
            on_status=on_status, get_status=get_status, original_title=original_title, on_log=on_log
        )
        if found_path:
            msg = f"¡Encontrado! {os.path.basename(found_path)}"
            log(f"[Watcher] {msg}", on_log)
            if on_status:
                on_status("Found", msg)
            callback(found_path, season_number)
        else:
            log(f"[Watcher] No se encontró '{expected_filename}' (Timeout).", on_log)
            if on_status:
                on_status("Error", "No se encontró el archivo (Timeout)")

    thread = threading.Thread(target=run_watch, daemon=True)
    thread.start()
    return thread
