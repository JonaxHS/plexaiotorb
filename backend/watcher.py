import re
import os
import time
import threading
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
    
    # Verificar que el mount point existe
    if not os.path.exists(mount_path):
        log(f"[Watcher] 🔴 CRÍTICO: Mount point NO EXISTE: {mount_path}", on_log)
        log(f"[Watcher] 🔴 Verifica que el backend VFS esté levantado y /mnt/torbox montado", on_log)
        return None

    try:
        # Listar raíz para diagnóstico
        try:
            root_items = os.listdir(mount_path)
            log(f"[Watcher] ✓ Mount activo. Items en {mount_path}: {len(root_items)} elementos", on_log)
            
            # Si hay pocos items, listarlos todos
            if len(root_items) < 20:
                log(f"[Watcher] Contenido: {root_items}", on_log)
            else:
                # Mostrar primeros 10
                log(f"[Watcher] Primeros 10 items: {root_items[:10]}", on_log)
                
                # Buscar items que contengan TODAS las palabras clave del título
                title_words = [w for w in title.lower().split()[:3] if len(w) > 2] if title else []
                if title_words:
                    matching = [item for item in root_items if all(word in item.lower() for word in title_words)]
                    if matching:
                        log(f"[Watcher] Items que coinciden con '{title}': {matching[:5]}", on_log)
        except PermissionError:
            log(f"[Watcher] 🔴 CRÍTICO: Permiso denegado en {mount_path}. Verifica permisos", on_log)
            return None
        except Exception as e:
            log(f"[Watcher] 🔴 Error listando {mount_path}: {e}", on_log)
            return None
        
        # Búsqueda recursiva exhaustiva por el filename exacto
        found_count = 0
        for root, dirs, files in os.walk(mount_path):
            for f in files:
                found_count += 1
                if f.lower() == expected_lower:
                    full_path = os.path.join(root, f)
                    log(f"[Watcher] ✓ ENCONTRADO: {full_path}", on_log)
                    return full_path
        
        log(f"[Watcher] Se exploraron {found_count} archivos, ninguno coincide con '{expected_filename}'", on_log)
            
    except Exception as e:
        log(f"[Watcher] 🔴 ERROR fatal en búsqueda: {e}", on_log)

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

    # Esperar a que el VFS monte el archivo
    log(f"[Watcher] Aguardando montaje en VFS...", on_log)
    time.sleep(3)
    
    # Refresco inicial (no-op en VFS custom)
    log(f"[Watcher] Refrescando estado de VFS...", on_log)
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

        # Limpiar caché solo cada 60 ciclos (1 minuto) para evitar rate limiting
        if cycle_count > 0 and cycle_count % 60 == 0:
            cleanup_vfs_cache(on_log, aggressive=(cycle_count % 300 == 0))

        found_path = find_file_path(expected_filename, title, mount_path, on_log, season, episode)
        if found_path:
            return found_path

        cycle_count += 1
        
        # Esperar 5 segundos entre ciclos para reducir carga
        time.sleep(5)

    return None

def cleanup_vfs_cache(on_log: Optional[callable] = None, aggressive: bool = False):
    """
    Compatibilidad heredada: en VFS custom no hay rc para limpiar caché externamente.
    """
    if aggressive:
        log(f"[Watcher] 🔄 Refresco agresivo solicitado (VFS TTL gestionado internamente)", on_log)
    else:
        log(f"[Watcher] ✓ Refresco solicitado (VFS custom)", on_log)


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
