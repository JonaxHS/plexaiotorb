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
    Busca un archivo en TorBox usando BÚSQUEDA EXACTA ÚNICA del filename.
    No intenta alternativas, solo busca exactamente lo que pide.
    """
    expected_lower = expected_filename.lower()
    
    if not os.path.exists(mount_path):
        log(f"[Watcher] ERROR: Directorio de montaje no existe: {mount_path}", on_log)
        return None

    try:
        # Listar raíz para diagnóstico
        try:
            root_items = os.listdir(mount_path)
            log(f"[Watcher] Items en {mount_path}: {len(root_items)} elementos", on_log)
            if len(root_items) > 0 and len(root_items) < 10:
                log(f"[Watcher] Contenido: {root_items[:5]}", on_log)
        except Exception as e:
            log(f"[Watcher] No se puede listar {mount_path}: {e}", on_log)
        
        # Búsqueda recursiva exhaustiva por el filename exacto
        for root, dirs, files in os.walk(mount_path):
            for f in files:
                if f.lower() == expected_lower:
                    full_path = os.path.join(root, f)
                    log(f"[Watcher] ✓ ENCONTRADO: {full_path}", on_log)
                    return full_path
    except Exception as e:
        log(f"[Watcher] ERROR en búsqueda: {e}", on_log)

    log(f"[Watcher] ARCHIVO NO ENCONTRADO: '{expected_filename}' en {mount_path}", on_log)
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
    Busca un archivo en TorBox por filename exacto.
    Limpia agresivamente el caché de rclone en cada ciclo.
    """
    start_time = time.time()
    msg = f"Buscando archivo: '{expected_filename}'"
    log(f"[Watcher] {msg}", on_log)
    if on_status:
        on_status("Searching", msg)

    # Esperar a que rclone monte el archivo
    log(f"[Watcher] Aguardando montaje en rclone...", on_log)
    time.sleep(3)
    
    # Limpiar caché inicial agresivamente
    log(f"[Watcher] Limpiando caché de rclone...", on_log)
    cleanup_rclone_cache(on_log)

    while time.time() - start_time < timeout_seconds:
        if get_status:
            status = get_status()
            if status == "Cancelled":
                log(f"[Watcher] Búsqueda cancelada.", on_log)
                return None
            if status == "Paused":
                time.sleep(5)
                continue

        elapsed = int(time.time() - start_time)
        log(f"[Watcher] Ciclo {elapsed}s: Buscando '{expected_filename}'...", on_log)
        if on_status:
            on_status("Searching", f"Buscando '{expected_filename}'... ({elapsed}s)")

        found_path = find_file_path(expected_filename, title, mount_path, on_log, season, episode)
        if found_path:
            return found_path

        # Limpiar caché antes de reintentar
        log(f"[Watcher] No encontrado. Limpiando caché y reintentando...", on_log)
        cleanup_rclone_cache(on_log)
        
        time.sleep(10)

    return None

def cleanup_rclone_cache(on_log: Optional[callable] = None):
    """Limpia el caché de rclone de múltiples formas."""
    commands = [
        (["rclone", "rc", "vfs/forget"], "vfs/forget"),
        (["rclone", "rc", "cache/expire"], "cache/expire"),
        (["rclone", "rc", "vfs/stats"], "vfs/stats (forzar lectura)"),
    ]
    
    for cmd, desc in commands:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=5, text=True)
            if result.returncode == 0:
                log(f"[Watcher] ✓ {desc} ejecutado", on_log)
            else:
                log(f"[Watcher] ⚠ {desc} retornó error: {result.stderr}", on_log)
        except Exception as e:
            log(f"[Watcher] ⚠ Error ejecutando {desc}: {e}", on_log)


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
