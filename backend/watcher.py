import re
import os
import time
import threading
import requests
from typing import Optional
import config as config_module

def log(msg: str, on_log: Optional[callable] = None):
    """Escribe en stdout y en la cola de logs del frontend si está disponible."""
    print(msg, flush=True)
    if on_log:
        try:
            on_log(msg)
        except Exception:
            pass


def _get_torbox_api_token() -> str:
    return (
        config_module.config.get("torbox", {}).get("api_token", "")
        or os.getenv("TORBOX_API_TOKEN", "")
    )


def _fetch_torbox_torrents(on_log: Optional[callable] = None) -> list:
    token = _get_torbox_api_token()
    if not token:
        log("[Watcher][API] TorBox API token no configurado", on_log)
        return []

    try:
        cache_buster = int(time.time() * 1000)
        resp = requests.get(
            "https://api.torbox.app/v1/api/torrents/mylist",
            headers={
                "Authorization": f"Bearer {token}",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
            params={"_": cache_buster},
            timeout=15,
        )
        if resp.status_code != 200:
            log(f"[Watcher][API] Error HTTP {resp.status_code} consultando TorBox", on_log)
            return []

        data = resp.json()
        torrents = data.get("data", [])
        if not isinstance(torrents, list):
            return []
        return torrents
    except Exception as e:
        log(f"[Watcher][API] Error consultando TorBox: {e}", on_log)
        return []


def _resolve_vfs_path(mount_path: str, torrent_name: str, file_name: str) -> Optional[str]:
    normalized_file_name = (file_name or "").lstrip("/").replace("\\", "/")
    torrent_dir = os.path.join(mount_path, torrent_name)

    file_rel = normalized_file_name
    torrent_prefix = f"{torrent_name}/"
    if file_rel.startswith(torrent_prefix):
        file_rel = file_rel[len(torrent_prefix):]

    basename = os.path.basename(file_rel)

    def _tokenize_name(value: str) -> set:
        clean = re.sub(r"[^a-z0-9]+", " ", (value or "").lower())
        return {t for t in clean.split() if len(t) >= 3}

    candidate_paths = []
    for candidate in [
        os.path.join(torrent_dir, file_rel),
        os.path.join(torrent_dir, basename),
        os.path.join(mount_path, normalized_file_name),
        os.path.join(mount_path, torrent_name),
        os.path.join(mount_path, basename),
    ]:
        norm = os.path.normpath(candidate)
        if norm not in candidate_paths:
            candidate_paths.append(norm)

    # Force VFS cache refresh by listing root directory
    # This ensures new torrent directories appear immediately
    try:
        os.listdir(mount_path)
    except Exception:
        pass

    # Helper function to safely check file existence using listdir (FUSE-friendly)
    def file_exists_via_listdir(path: str) -> bool:
        try:
            parent = os.path.dirname(path)
            name = os.path.basename(path)
            if not parent or not name:
                return False
            try:
                entries = os.listdir(parent)
                return name in entries
            except (OSError, IOError):
                # Parent dir doesn't exist or isn't accessible
                return False
        except Exception:
            return False
    
    # Check candidate paths using listdir-based check
    for candidate in candidate_paths:
        if file_exists_via_listdir(candidate):
            return candidate

    # Fallback: try to recursively find the basename in the torrent directory
    try:
        entries = os.listdir(torrent_dir)
        for entry in entries:
            entry_path = os.path.join(torrent_dir, entry)
            if os.path.basename(entry_path) == basename:
                return entry_path
            
            # If it's a directory, search inside recursively
            try:
                sub_entries = os.listdir(entry_path)
                for sub_entry in sub_entries:
                    if sub_entry == basename:
                        return os.path.join(entry_path, sub_entry)
            except (OSError, IOError):
                pass
    except (OSError, IOError):
        pass

    # Fallback final: buscar entrada raíz con nombre aproximado
    try:
        root_entries = os.listdir(mount_path)
        expected_tokens = _tokenize_name(basename)
        best_entry = None
        best_score = 0.0
        for entry in root_entries:
            entry_tokens = _tokenize_name(entry)
            if not entry_tokens or not expected_tokens:
                continue
            overlap = len(entry_tokens & expected_tokens)
            score = overlap / max(1, len(expected_tokens))
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry and best_score >= 0.45:
            return os.path.join(mount_path, best_entry)
    except (OSError, IOError):
        pass

    return None


def _find_file_path_via_api(
    expected_filename: str,
    title: str = "",
    mount_path: str = "/mnt/torbox",
    on_log: Optional[callable] = None,
    season: int = None,
    episode: int = None,
) -> Optional[str]:
    torrents = _fetch_torbox_torrents(on_log)
    if not torrents:
        return None

    expected_clean = (expected_filename or "").strip().replace("\\", "/")
    expected_basename = os.path.basename(expected_clean).strip().lower()
    if not expected_basename:
        log("[Watcher][API] Filename esperado vacío", on_log)
        return None

    log(f"[Watcher][API] Torrents recibidos: {len(torrents)}", on_log)

    matches = []
    for torrent in torrents:
        if not torrent.get("download_finished", True):
            continue

        torrent_name = torrent.get("name", "")
        files = torrent.get("files", []) or []

        for file in files:
            file_name = (file.get("name") or "").strip().replace("\\", "/")
            basename = os.path.basename(file_name).strip().lower()
            if basename == expected_basename:
                matches.append((torrent_name, file_name))

    if not matches:
        log(f"[Watcher][API] Sin coincidencia exacta para '{expected_basename}'", on_log)
        return None

    log(f"[Watcher][API] Coincidencias exactas encontradas: {len(matches)}", on_log)
    for torrent_name, file_name in matches:
        resolved = _resolve_vfs_path(mount_path, torrent_name, file_name)
        if resolved:
            log(f"[Watcher][API] ✓ ENCONTRADO: {resolved}", on_log)
            return resolved

    log("[Watcher][API] Coincidencias API detectadas, pero ninguna ruta existe aún en VFS", on_log)
    return None


def find_file_path(expected_filename: str, title: str = "", mount_path: str = "/mnt/torbox", on_log: Optional[callable] = None, season: int = None, episode: int = None) -> Optional[str]:
    """
    Busca un archivo en TorBox usando BÚSQUEDA EXACTA ÚNICA del filename.
    No intenta alternativas, solo busca exactamente lo que pide.
    """
    found_api = _find_file_path_via_api(expected_filename, title, mount_path, on_log, season, episode)
    if found_api:
        return found_api

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
    timeout_seconds: int = 7200,  # 2 horas por defecto (era 1 hora)
    on_status: Optional[callable] = None,
    get_status: Optional[callable] = None,
    original_title: str = "",
    on_log: Optional[callable] = None
) -> Optional[str]:
    """
    Busca un archivo en TorBox por filename exacto.
    Fuerza refresco de estado del watcher por ciclo sin usar comandos externos.
    """
    start_time = time.time()
    msg = f"Buscando archivo: '{expected_filename}'"
    log(f"[Watcher] {msg}", on_log)
    if on_status:
        on_status("Searching", msg)

    # Refresco inicial de búsqueda por API
    log(f"[Watcher] Refrescando búsqueda por API...", on_log)
    cleanup_vfs_cache(on_log)
    
    cycle_count = 0

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

        # Limpieza lógica de caché antes de cada consulta API
        cleanup_vfs_cache(on_log)

        found_path = find_file_path(expected_filename, title, mount_path, on_log, season, episode)
        if found_path:
            return found_path

        cycle_count += 1
        
        # Esperar 5 segundos entre ciclos para reducir carga
        time.sleep(5)

    return None

def cleanup_vfs_cache(on_log: Optional[callable] = None, aggressive: bool = False):
    """
    Compatibilidad heredada: usamos nombre histórico, pero ahora solo
    señaliza refresco lógico para búsquedas por API.
    """
    if aggressive:
        log(f"[Watcher][API] 🔄 Refresco agresivo solicitado", on_log)


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
