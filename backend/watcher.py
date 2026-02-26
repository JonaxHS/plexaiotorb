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
    Busca un archivo en TorBox usando ÚNICAMENTE el nombre exacto del archivo
    provisto por AIOStreams (behaviorHints.filename).
    """
    start_time = time.time()
    expected_lower = expected_filename.lower()

    msg = f"Buscando archivo: '{expected_filename}'"
    log(f"[Watcher] {msg}", on_log)
    if on_status:
        on_status("Searching", msg)

    def walk_for_exact(folder_path: str) -> Optional[str]:
        """Busca el filename exacto dentro de una carpeta, hasta 4 niveles."""
        try:
            for root, dirs, files in os.walk(folder_path):
                depth = root[len(folder_path):].count(os.sep)
                if depth > 4:
                    dirs.clear()
                    continue
                for f in files:
                    if f.lower() == expected_lower:
                        return os.path.join(root, f)
        except Exception as e:
            log(f"[Watcher] Error recorriendo {folder_path}: {e}", on_log)
        return None

    while time.time() - start_time < timeout_seconds:
        # Verificación de cancelación/pausa
        if get_status:
            status = get_status()
            if status == "Cancelled":
                log(f"[Watcher] Búsqueda cancelada por el usuario.", on_log)
                return None
            if status == "Paused":
                time.sleep(5)
                continue

        # Esperamos entre ciclos para no saturar el API de rclone
        time.sleep(10)

        elapsed = int(time.time() - start_time)
        log(f"[Watcher] Ciclo de búsqueda... ({elapsed}s transcurridos)", on_log)
        if on_status:
            on_status("Searching", f"Buscando '{expected_filename}'... ({elapsed}s)")

        # Forzar refresco de caché rclone para detectar archivos nuevos
        try:
            subprocess.run(["rclone", "rc", "vfs/forget"], capture_output=True, timeout=3)
            log(f"[Watcher] Caché rclone refrescado.", on_log)
        except Exception:
            pass

        if not os.path.exists(mount_path):
            log(f"[Watcher] El directorio de montaje no existe: {mount_path}", on_log)
            continue

        try:
            raw_items = os.listdir(mount_path)
        except Exception as e:
            log(f"[Watcher] Error listando {mount_path}: {e}", on_log)
            time.sleep(5)
            continue

        log(f"[Watcher] {len(raw_items)} items en TorBox. Buscando '{expected_filename}'...", on_log)

        # PASO 1: Archivo directo en la raíz
        for item in raw_items:
            if item.lower() == expected_lower:
                item_path = os.path.join(mount_path, item)
                if os.path.isfile(item_path):
                    log(f"[Watcher] ✓ Encontrado en raíz: {item}", on_log)
                    return item_path

        # PASO 2: Buscar en subcarpetas (primero las que coincidan con el título, luego el resto)
        title_words = [w.lower() for w in re.split(r'[\s\.\-_]+', title) if len(w) >= 3] if title else []

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

        log(f"[Watcher] Buscando en {len(candidates)} carpetas prioritarias + {len(others)} restantes...", on_log)

        # Primero busca en carpetas que coincidan con el título (más rápido)
        for folder in candidates:
            result = walk_for_exact(folder)
            if result:
                log(f"[Watcher] ✓ Encontrado: {result}", on_log)
                return result

        # Luego en el resto (por si la carpeta tiene un nombre diferente)
        for folder in others:
            result = walk_for_exact(folder)
            if result:
                log(f"[Watcher] ✓ Encontrado (búsqueda completa): {result}", on_log)
                return result

        log(f"[Watcher] Archivo no encontrado en este ciclo. Esperando próxima descarga...", on_log)

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
