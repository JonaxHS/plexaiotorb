from media_utils import clean_name, clean_words, extract_se_info, is_valid_match, get_match_score

import re

import os
import time
import threading
from typing import Optional

def watch_for_file(expected_filename: str, title: str = "", year: str = "", season: int = None, episode: int = None, mount_path: str = "/mnt/torbox", timeout_seconds: int = 3600, on_status: Optional[callable] = None, get_status: Optional[callable] = None, original_title: str = "") -> Optional[str]:
    """
    Busca un archivo específico dentro del montaje de rclone (TorBox).
    """
    start_time = time.time()
    msg = f"Buscando '{expected_filename}'..."
    if season is not None:
        msg = f"Buscando {title} S{season}E{episode}..."
    
    print(f"[Watcher] {msg}")
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
            print(f"[Watcher] Error listando directorio inicial: {e}")
                
    VIDEO_EXTS = ('.mkv', '.mp4', '.avi', '.ts', '.webm')
    
    while time.time() - start_time < timeout_seconds:
        # Verificación de cancelación/pausa
        if get_status:
            status = get_status()
            if status == "Cancelled":
                print(f"[Watcher] Abortando búsqueda: {title} (Cancelada por usuario)")
                return None
            if status == "Paused":
                time.sleep(5)
                continue

        # Esperamos 10 segundos antes del siguiente ciclo para cuidar la API
        time.sleep(10)
        
        # Log de latido (heartbeat) para la interfaz web (evita que parezca congelado)
        elapsed = int(time.time() - start_time)
        print(f"[Watcher] Monitoreando activamente TorBox... ({elapsed}s transcurridos)")
        if on_status: on_status("Searching", f"Buscando... ({elapsed}s)")
        
        # Forzar limpieza de cache en rclone para detectar nuevas carpetas casi en tiempo real
        if elapsed % 10 == 0:
            try:
                import subprocess
                print(f"[Watcher] Forzando refresco de cache rclone...")
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
                print(f"[Watcher Debug] DUMP completo de {mount_path} ({len(raw_items)} items): {raw_items[:20]}...", flush=True)
                if any("thrones" in x.lower() for x in raw_items):
                    print(f"[Watcher Debug] !!! GoT ENCONTRADO en listdir !!!", flush=True)
                else:
                    print(f"[Watcher Debug] ??? GoT NO esta en listdir ???", flush=True)

            print(f"[Watcher] Listados {len(raw_items)} items en {mount_path}", flush=True)
            for item in raw_items:
                try:
                    path = os.path.join(mount_path, item)
                    current_state[item] = os.path.getmtime(path)
                except Exception:
                    # Si falla mtime (ej. archivo desaparece), usamos epoch 0 para forzar revisión textual
                    current_state[item] = 0
        except Exception as e:
            print(f"[Watcher] Error listando directorio (posible rate limit): {e}")
            time.sleep(5)
            continue
            
        # LOGICA A: Coincidencia textual pura en primer nivel
        for item, mtime in current_state.items():
            item_path = os.path.join(mount_path, item)
            
            if is_valid_match(item, expected_filename, title, year, season, episode, original_title=original_title):
                print(f"[Watcher] Coincidencia detected: {item}", flush=True)
                if os.path.isfile(item_path) and item.lower().endswith(VIDEO_EXTS):
                    print(f"[Watcher] Coincidencia validada: {item}")
                    return item_path
                elif os.path.isdir(item_path):
                    # Búsqueda profunda en carpeta (soporta subcarpetas ej. Season 1/Ep 1)
                    print(f"[Watcher Debug] Entrando a carpeta validada: {item}")
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
                                    print(f"[Watcher Debug]   - Evaluando sub-archivo: {file} | Score: {score}")
                                    if score > best_score:
                                        best_score = score
                                        best_sub = os.path.relpath(os.path.join(root, file), item_path)
                        
                        if best_sub and best_score >= 30:
                            print(f"[Watcher Debug]   - Éxito! Mejor sub-archivo: {best_sub} ({best_score}%)")
                            return os.path.join(item_path, best_sub)
                        else:
                            print(f"[Watcher Debug]   - No se encontró un sub-archivo confiable en {item} (Best: {best_score})")
                    except Exception as e: 
                        print(f"[Watcher Debug] Error listando subdir {item}: {e}")
                
        # LOGICA B: Detectar cambios mediante análisis de Tiempo de Modificación (mtime)
        for item, current_mtime in current_state.items():
            item_path = os.path.join(mount_path, item)
            is_new = item not in initial_state
            is_updated = (not is_new) and (current_mtime > initial_state[item])
            
            if is_new or is_updated:
                # 1. Si es un archivo directo de video
                if os.path.isfile(item_path) and item.lower().endswith(VIDEO_EXTS):
                    if is_valid_match(item, expected_filename, title, year, season, episode):
                        print(f"[Watcher] Archivo NUEVO validado: {item}", flush=True)
                        return item_path
                    
                # 2. Si es una carpeta nueva o modificada
                if os.path.isdir(item_path) and is_valid_match(item, expected_filename, title, year, season, episode):
                    print(f"[Watcher] Carpeta NUEVA/MODIFICADA validada: {item}", flush=True)
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
                            print(f"[Watcher] Mejor video en carpeta: {best_sub} (Score: {best_score})", flush=True)
                            return os.path.join(item_path, best_sub)
                    except Exception:
                        pass
                        
        # Actualizamos el estado para no reprocesar archivos/carpetas
        initial_state = current_state
        
    return None

def start_watcher_thread(expected_filename: str, title: str, year: str, callback, season_number: int = None, episode_number: int = None, on_status: Optional[callable] = None, get_status: Optional[callable] = None, original_title: str = ""):
    """
    Inicia la búsqueda en segundo plano y llama al callback con la ruta cuando lo encuentra.
    """
    def run_watch():
        print(f"[Watcher] Iniciando hilo para: {title} (S{season_number}E{episode_number})")
        found_path = watch_for_file(expected_filename, title, year, season_number, episode_number, on_status=on_status, get_status=get_status, original_title=original_title)
        if found_path:
            msg = f"Archivo encontrado: {os.path.basename(found_path)}"
            print(f"[Watcher] {msg}")
            if on_status: on_status("Found", msg)
            callback(found_path, season_number)
        else:
            print(f"Timeout: No se encontró {title} S{season_number}E{episode_number}")
            if on_status: on_status("Error", "No se encontró el archivo (Timeout)")
            
    thread = threading.Thread(target=run_watch, daemon=True)
    thread.start()
    return thread
