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

def find_file_path(expected_filename: str, title: str = "", mount_path: str = "/mnt/torbox", on_log: Optional[callable] = None, season: int = None, episode: int = None) -> Optional[str]:
    """
    Busca un archivo en TorBox usando BÚSQUEDA EXACTA del nombre del archivo.
    Prioridad: Raíz > Carpetas por título > Resto de carpetas.
    """
    expected_lower = expected_filename.lower()
    expected_no_ext = os.path.splitext(expected_lower)[0]
    
    # Limpiar el título: remover información de S##E##
    title_clean = re.sub(r'\s*[sS]\d+[eE]\d+\s*', ' ', title).strip()
    
    if not os.path.exists(mount_path):
        log(f"[Watcher] ERROR: Directorio de montaje no existe: {mount_path}", on_log)
        return None

    try:
        raw_items = os.listdir(mount_path)
        log(f"[Watcher] Escaneando {mount_path}: {len(raw_items)} items", on_log)
    except Exception as e:
        log(f"[Watcher] ERROR listando {mount_path}: {e}", on_log)
        return None

    # PASO 1: Búsqueda EXACTA en la raíz
    log(f"[Watcher] PASO 1: Buscando archivo exacto en raíz...", on_log)
    for item in raw_items:
        if item.lower() == expected_lower:
            item_path = os.path.join(mount_path, item)
            if os.path.isfile(item_path):
                log(f"[Watcher] ✓ ENCONTRADO EN RAÍZ: {item_path}", on_log)
                return item_path
            else:
                log(f"[Watcher] {item} es directorio, no archivo", on_log)

    # PASO 2: Búsqueda recursiva desde raíz (todas las subcarpetas, sin límite de profundidad)
    log(f"[Watcher] PASO 2: Buscando recursivamente desde {mount_path}...", on_log)
    try:
        for root, dirs, files in os.walk(mount_path):
            # Limitar profundidad solo si está muy profundo
            current_depth = root[len(mount_path):].count(os.sep)
            if current_depth > 10:
                log(f"[Watcher] Profundidad máxima alcanzada en: {root}", on_log)
                dirs.clear()
                continue
                
            for f in files:
                f_lower = f.lower()
                f_no_ext = os.path.splitext(f_lower)[0]
                
                # Búsqueda exacta: nombre completo o sin extensión
                if f_lower == expected_lower or f_no_ext == expected_no_ext:
                    full_path = os.path.join(root, f)
                    log(f"[Watcher] ✓ ENCONTRADO RECURSIVAMENTE: {full_path}", on_log)
                    return full_path
    except Exception as e:
        log(f"[Watcher] ERROR en búsqueda recursiva: {e}", on_log)

    # PASO 3: Búsqueda por patrón S##E## como último recurso
    if season is not None and episode is not None:
        pattern = f"s{season:02d}e{episode:02d}".lower()
        log(f"[Watcher] PASO 3: Búsqueda flexible por patrón S##E##: {pattern}", on_log)
        
        try:
            for root, dirs, files in os.walk(mount_path):
                current_depth = root[len(mount_path):].count(os.sep)
                if current_depth > 10:
                    dirs.clear()
                    continue
                    
                for f in files:
                    f_lower = f.lower()
                    # Buscar el patrón sin separadores
                    if pattern in f_lower.replace(' ', '').replace('_', '').replace('-', '').replace('.', ''):
                        full_path = os.path.join(root, f)
                        log(f"[Watcher] ✓ ENCONTRADO POR PATRÓN: {full_path}", on_log)
                        return full_path
        except Exception as e:
            log(f"[Watcher] ERROR en búsqueda por patrón: {e}", on_log)

    log(f"[Watcher] ARCHIVO NO ENCONTRADO: '{expected_filename}'", on_log)
    return None

def check_file_exists(expected_filename: str, title: str = "", mount_path: str = "/mnt/torbox", season: int = None, episode: int = None) -> Optional[str]:
    """Versión sincrónica de una sola pasada para checking rápido."""
    return find_file_path(expected_filename, title, mount_path, season=season, episode=episode)

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

    # Esperar un poco inicial para que el archivo sea montado por rclone
    log(f"[Watcher] Esperando que el archivo sea montado en rclone...", on_log)
    time.sleep(5)

    while time.time() - start_time < timeout_seconds:
        if get_status:
            status = get_status()
            if status == "Cancelled":
                log(f"[Watcher] Búsqueda cancelada.", on_log)
                return None
            if status == "Paused":
                time.sleep(5)
                continue

        # Limpiar caché de rclone antes de cada búsqueda
        try:
            subprocess.run(["rclone", "rc", "vfs/forget"], capture_output=True, timeout=3)
            log(f"[Watcher] Caché de rclone limpiado", on_log)
        except Exception as e:
            log(f"[Watcher] Error limpiando caché: {e}", on_log)

        elapsed = int(time.time() - start_time)
        log(f"[Watcher] Ciclo de búsqueda... ({elapsed}s)", on_log)
        if on_status:
            on_status("Searching", f"Buscando '{expected_filename}'... ({elapsed}s)")

        found_path = find_file_path(expected_filename, title, mount_path, on_log, season, episode)
        if found_path:
            return found_path

        log(f"[Watcher] Archivo no encontrado. Esperando...", on_log)
        time.sleep(10)

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
