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
    
    # Verificar que el mount point existe
    if not os.path.exists(mount_path):
        log(f"[Watcher] 🔴 CRÍTICO: Mount point NO EXISTE: {mount_path}", on_log)
        log(f"[Watcher] 🔴 Verifica que rclone está corriendo: sudo systemctl status rclone", on_log)
        log(f"[Watcher] 🔴 O intenta montar: rclone mount remote:/ /mnt/torbox --daemon", on_log)
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
                
                # Buscar items que contengan palabras clave del título
                title_words = title.lower().split()[:2] if title else []
                if title_words:
                    matching = [item for item in root_items if any(word in item.lower() for word in title_words)]
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
    Limpia caché de rclone cada ciclo, con limpieza AGRESIVA cada 5 minutos.
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

        # Limpiar ANTES de buscar para evitar cache stale
        if cycle_count > 0:  # Primera vez ya se limpió arriba
            cleanup_rclone_cache(on_log, aggressive=(cycle_count % 50 == 0))

        found_path = find_file_path(expected_filename, title, mount_path, on_log, season, episode)
        if found_path:
            return found_path

        cycle_count += 1
        
        # Esperar menos entre ciclos (reducido de 3s a 1s) para búsqueda más rápida
        time.sleep(1)

    return None

def cleanup_rclone_cache(on_log: Optional[callable] = None, aggressive: bool = False):
    """
    Limpia el caché de rclone de múltiples formas para asegurar descubrimiento rápido.
    Si aggressive=True, hace limpiezas más profundas.
    """
    try:
        # 1. Forget: limpia metadata cacheada
        result = subprocess.run(["rclone", "rc", "vfs/forget"], capture_output=True, timeout=5, text=True)
        if result.returncode == 0:
            log(f"[Watcher] ✓ vfs/forget ejecutado", on_log)
        else:
            error_msg = result.stderr or result.stdout
            if "connection refused" in error_msg.lower() or "127.0.0.1:5572" in error_msg:
                log(f"[Watcher] 🔴 CRÍTICO: rclone rc NO activo (Puerto 5572 no responde)", on_log)
                log(f"[Watcher] 🔴 Solución: Inicia rclone rc con: rclone rcd --rc-serve &", on_log)
            else:
                log(f"[Watcher] ⚠️ vfs/forget error: {error_msg[:100]}", on_log)
                return
        
        # 2. Clear-cache (si existe)
        result = subprocess.run(["rclone", "rc", "vfs/clear-cache"], capture_output=True, timeout=5, text=True)
        if result.returncode == 0:
            log(f"[Watcher] ✓ vfs/clear-cache ejecutado", on_log)
        
        # 3. Flush writes para sincronizar
        subprocess.run(["rclone", "rc", "vfs/forget", "mount=/mnt/torbox"], capture_output=True, timeout=5)
        
        if aggressive:
            log(f"[Watcher] 🔄 Limpieza AGRESIVA: Flush y reset de stat caches...", on_log)
            subprocess.run(["rclone", "rc", "cache/expire"], capture_output=True, timeout=5)
            
    except subprocess.TimeoutExpired:
        log(f"[Watcher] ⚠️ rclone rc timeout", on_log)
    except Exception as e:
        log(f"[Watcher] ⚠️ Error conectando con rclone rc: {e}", on_log)


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
