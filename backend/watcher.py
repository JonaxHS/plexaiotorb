from media_utils import clean_name, clean_words, extract_se_info, is_valid_match, get_match_score

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

def watch_for_file(expected_filename: str, title: str = "", year: str = "", season: int = None, episode: int = None, mount_path: str = "/mnt/torbox", timeout_seconds: int = 3600, on_status: Optional[callable] = None, get_status: Optional[callable] = None, original_title: str = "", on_log: Optional[callable] = None) -> Optional[str]:
    """
    Busca un archivo específico dentro del montaje de rclone (TorBox).
    """
    start_time = time.time()
    msg = f"Buscando '{expected_filename}'..."
    if season is not None:
        msg = f"Buscando {title} S{season}E{episode}..."
    
    log(f"[Watcher] {msg}", on_log)
    if on_status: on_status("Searching", msg)
    
    expected_base = os.path.splitext(expected_filename)[0]
    expected_clean = clean_name(expected_base)
    
    # 1. Tomar foto del nivel raíz con sus FECHAS DE MODIFICACIÓN (mtime)
    initial_state = {}
    if os.path.exists(mount_path):
        try:
            for item in os.listdir(mount_path):
                path = os.path.join(mount_path, item)
                initial_state[item] = os.path.getmtime(path)
        except Exception as e:
            log(f"[Watcher] Error listando directorio inicial: {e}", on_log)
                
    VIDEO_EXTS = ('.mkv', '.mp4', '.avi', '.ts', '.webm')
    
    while time.time() - start_time < timeout_seconds:
        # Verificación de cancelación/pausa
        if get_status:
            status = get_status()
            if status == "Cancelled":
                log(f"[Watcher] Abortando búsqueda: {title} (Cancelada por usuario)", on_log)
                return None
            if status == "Paused":
                time.sleep(5)
                continue

        # Esperamos 10 segundos antes del siguiente ciclo para cuidar la API
        time.sleep(10)
        
        # Log de latido (heartbeat) para la interfaz web (evita que parezca congelado)
        elapsed = int(time.time() - start_time)
        log(f"[Watcher] Monitoreando activamente TorBox... ({elapsed}s transcurridos)", on_log)
        if on_status: on_status("Searching", f"Buscando... ({elapsed}s)")
        
        # Forzar limpieza de cache en rclone para detectar nuevas carpetas casi en tiempo real
        if elapsed % 10 == 0:
            try:
                import subprocess
                log(f"[Watcher] Forzando refresco de cache rclone...", on_log)
                subprocess.run(["rclone", "rc", "vfs/forget"], capture_output=True, timeout=3)
            except Exception:
                pass
                
        if not os.path.exists(mount_path):
            continue
            
        try:
            current_state = {}
            raw_items = os.listdir(mount_path)
            
            # Dump periódico completo para debugging profundo (cada 1 minuto aprox)
            if elapsed % 60 == 0:
                log(f"[Watcher Debug] DUMP completo de {mount_path} ({len(raw_items)} items): {raw_items[:20]}...", on_log)
                if any("thrones" in x.lower() for x in raw_items):
                    log(f"[Watcher Debug] !!! GoT ENCONTRADO en listdir !!!", on_log)
                else:
                    log(f"[Watcher Debug] ??? GoT NO esta en listdir ???", on_log)

            log(f"[Watcher] Listados {len(raw_items)} items en {mount_path}", on_log)
            for item in raw_items:
                try:
                    path = os.path.join(mount_path, item)
                    current_state[item] = os.path.getmtime(path)
                except Exception:
                    # Si falla mtime (ej. archivo desaparece), usamos epoch 0 para forzar revisión textual
                    current_state[item] = 0
        except Exception as e:
            log(f"[Watcher] Error listando directorio (posible rate limit): {e}", on_log)
            time.sleep(5)
            continue
            
        # LÓGICA 0 (PRIORITARIA): Búsqueda por nombre exacto del archivo
        # El filename que nos dio AIOStreams es el nombre real del archivo en TorBox.
        # Buscamos exactamente ese nombre (insensible a mayúsculas) en todo el directorio.
        expected_lower = expected_filename.lower()
        found_exact = None
        for item in raw_items:
            item_path = os.path.join(mount_path, item)
            # Archivo directo en raíz
            if os.path.isfile(item_path) and item.lower() == expected_lower:
                log(f"[Watcher] ✓ Match exacto de filename en raíz: {item}", on_log)
                found_exact = item_path
                break
            # Buscar dentro de carpetas
            if os.path.isdir(item_path):
                try:
                    for root, dirs, files in os.walk(item_path):
                        depth = root[len(item_path):].count(os.sep)
                        if depth > 3:
                            dirs.clear()
                            continue
                        for f in files:
                            if f.lower() == expected_lower and f.lower().endswith(VIDEO_EXTS):
                                found_exact = os.path.join(root, f)
                                log(f"[Watcher] ✓ Match exacto de filename: {found_exact}", on_log)
                                break
                        if found_exact:
                            break
                except Exception:
                    pass
            if found_exact:
                break
        
        if found_exact:
            return found_exact
            
        # LOGICA A: Coincidencia textual pura en primer nivel (fallback)
        log(f"[Watcher] Filename exacto no encontrado, usando matching heurístico...", on_log)
        for item, mtime in current_state.items():
            item_path = os.path.join(mount_path, item)
            
            if is_valid_match(item, expected_filename, title, year, season, episode, original_title=original_title):
                log(f"[Watcher] Coincidencia detected: {item}", on_log)
                if os.path.isfile(item_path) and item.lower().endswith(VIDEO_EXTS):
                    log(f"[Watcher] Coincidencia validada: {item}", on_log)
                    return item_path
                elif os.path.isdir(item_path):
                    # Búsqueda profunda en carpeta (soporta subcarpetas ej. Season 1/Ep 1)
                    log(f"[Watcher Debug] Entrando a carpeta validada: {item}", on_log)
                    try:
                        best_sub = None
                        best_score = -1
                        for root, dirs, files in os.walk(item_path):
                            depth = root[len(item_path):].count(os.sep)
                            if depth > 2:
                                dirs.clear() # No profundizar más de 2 niveles
                                continue
                                
                            for file in files:
                                if file.lower().endswith(VIDEO_EXTS):
                                    score = get_match_score(file, expected_filename, title, year, season, episode, original_title=original_title)
                                    log(f"[Watcher Debug]   - Evaluando sub-archivo: {file} | Score: {score}", on_log)
                                    if score > best_score:
                                        best_score = score
                                        best_sub = os.path.relpath(os.path.join(root, file), item_path)
                        
                        if best_sub and best_score >= 30:
                            log(f"[Watcher Debug]   - Éxito! Mejor sub-archivo: {best_sub} ({best_score}%)", on_log)
                            return os.path.join(item_path, best_sub)
                        else:
                            log(f"[Watcher Debug]   - No se encontró un sub-archivo confiable en {item} (Best: {best_score})", on_log)
                    except Exception as e: 
                        log(f"[Watcher Debug] Error listando subdir {item}: {e}", on_log)
                
        # LOGICA B: Detectar cambios mediante análisis de Tiempo de Modificación (mtime)
        for item, current_mtime in current_state.items():
            item_path = os.path.join(mount_path, item)
            is_new = item not in initial_state
            is_updated = (not is_new) and (current_mtime > initial_state[item])
            
            if is_new or is_updated:
                # 1. Si es un archivo directo de video
                if os.path.isfile(item_path) and item.lower().endswith(VIDEO_EXTS):
                    if is_valid_match(item, expected_filename, title, year, season, episode):
                        log(f"[Watcher] Archivo NUEVO validado: {item}", on_log)
                        return item_path
                    
                # 2. Si es una carpeta nueva o modificada
                if os.path.isdir(item_path) and is_valid_match(item, expected_filename, title, year, season, episode):
                    log(f"[Watcher] Carpeta NUEVA/MODIFICADA validada: {item}", on_log)
                    try:
                        best_sub = None
                        best_score = -1
                        for root, dirs, files in os.walk(item_path):
                            depth = root[len(item_path):].count(os.sep)
                            if depth > 2:
                                dirs.clear()
                                continue
                                
                            for file in files:
                                if file.lower().endswith(VIDEO_EXTS):
                                    score = get_match_score(file, expected_filename, title, year, season, episode)
                                    if score > best_score:
                                        best_score = score
                                        best_sub = os.path.relpath(os.path.join(root, file), item_path)
                        
                        if best_sub and best_score >= 30:
                            log(f"[Watcher] Mejor video en carpeta: {best_sub} (Score: {best_score})", on_log)
                            return os.path.join(item_path, best_sub)
                    except Exception:
                        pass
                        
        # Actualizamos el estado para no reprocesar archivos/carpetas
        initial_state = current_state
        
    return None

def start_watcher_thread(expected_filename: str, title: str, year: str, callback, season_number: int = None, episode_number: int = None, on_status: Optional[callable] = None, get_status: Optional[callable] = None, original_title: str = "", on_log: Optional[callable] = None):
    """
    Inicia la búsqueda en segundo plano y llama al callback con la ruta cuando lo encuentra.
    """
    def run_watch():
        log(f"[Watcher] Iniciando hilo para: {title} (S{season_number}E{episode_number})", on_log)
        found_path = watch_for_file(expected_filename, title, year, season_number, episode_number, on_status=on_status, get_status=get_status, original_title=original_title, on_log=on_log)
        if found_path:
            msg = f"Archivo encontrado: {os.path.basename(found_path)}"
            log(f"[Watcher] {msg}", on_log)
            if on_status: on_status("Found", msg)
            callback(found_path, season_number)
        else:
            log(f"Timeout: No se encontró {title} S{season_number}E{episode_number}", on_log)
            if on_status: on_status("Error", "No se encontró el archivo (Timeout)")
            
    thread = threading.Thread(target=run_watch, daemon=True)
    thread.start()
    return thread

