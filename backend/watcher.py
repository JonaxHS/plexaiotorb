import os
import time
import threading
from typing import Optional

def clean_name(name: str) -> str:
    """Elimina todo lo que no sea alfanumérico y pasa a minúsculas."""
    if not name: return ""
    return re.sub(r'[^a-zA-Z0-9]', '', name).lower()

def clean_words(name: str):
    """Extrae las palabras limpias (separadas por puntos, espacios, etc)."""
    if not name: return []
    res = re.sub(r'[^a-zA-Z0-9]', ' ', name).lower()
    return res.split()

def get_key_word(words: list) -> str:
    """Extrae la primera palabra clave importante (ignorando artículos/stopwords)."""
    stopwords = {"the", "a", "an", "el", "la", "los", "las", "un", "una", "de", "del", "and", "or"}
    for w in words:
        if w not in stopwords and len(w) >= 3:
            return w
    # Si todo falla, devolver la palabra más larga
    if words: return max(words, key=len)
    return None

import re

def extract_se_info(text: str):
    """Extrae temporada y episodio si existen en el texto."""
    if not text: return None, None
    # S01E01 o s1e1
    match = re.search(r'[sS](\d+)[eE](\d+)', text)
    if match:
        return int(match.group(1)), int(match.group(2))
    # 1x01
    match = re.search(r'(?<!\d)(\d+)x(\d+)', text)
    if match:
        return int(match.group(1)), int(match.group(2))
    # Temporada 1 Capitulo 1
    t_match = re.search(r'Temporada\s*(\d+)', text, re.I)
    c_match = re.search(r'(?:Capitulo|Episodio)\s*(\d+)', text, re.I)
    if t_match and c_match:
        return int(t_match.group(1)), int(c_match.group(1))
    # Solo Temporada (para packs)
    if t_match:
        return int(t_match.group(1)), None
    return None, None

def is_valid_match(item_name: str, expected_filename: str, title: str, year: str, season: int = None, episode: int = None, original_title: str = "") -> bool:
    if not item_name: return False
    
    # 1. Fuerza bruta: Si el S/E existe en el archivo y no coincide con lo esperado, RECHAZAR
    i_s, i_e = extract_se_info(item_name)
    
    # Si el archivo tiene S/E, debe coincidir con el solicitado (si hay uno solicitado)
    if i_s is not None and season is not None:
        if i_s != season:
            return False 
        # Permitir packs de temporada entera (i_e is None)
        if episode is not None and i_e is not None and i_e != episode:
            return False

    # Si el esperado tiene S/E (fallback para películas con números o streams mal nombrados)
    e_s, e_e = extract_se_info(expected_filename)
    if e_s is not None and i_s is not None:
        if e_s != i_s:
            return False
        if e_e is not None and i_e is not None and e_e != i_e:
            return False

    item_clean = clean_name(item_name)
    expected_clean = clean_name(os.path.splitext(expected_filename)[0])
    title_clean = clean_name(title)
    str_year = str(year).strip() if year else ""
    
    # 3. Validación estricta de Año (Sólo para películas)
    # En series el año del archivo suele ser el de la temporada, no el de inicio de serie (ej Broking Bad 2008 vs S02 2009)
    if str_year and season is None:
        years_in_name = re.findall(r'\b(19\d{2}|20\d{2})\b', item_name)
        if years_in_name and str_year not in years_in_name:
            if "thrones" in item_clean or "agatha" in item_clean or "avatar" in item_clean:
                print(f"[Watcher Trace] {item_name} -> Rechazado por mismatch de año (esperado {str_year}, encontrados {years_in_name})", flush=True)
            return False
            
    is_target = "thrones" in item_clean or "agatha" in item_clean or "avatar" in item_clean
    
    # Extraer posible título en inglés original del expected_filename (provisto por AIOStreams)
    expected_base_clean = expected_clean
    if e_s is not None:
        expected_base_clean = re.split(r's\d+e\d+', expected_base_clean)[0]
        expected_base_clean = re.split(r'\d+x\d+', expected_base_clean)[0]
    elif str_year:
        expected_base_clean = expected_base_clean.split(str_year)[0]
        
    expected_base_clean = expected_base_clean.replace("mkv", "").replace("mp4", "")
        
    item_words = clean_words(item_name)
    title_words = clean_words(title)
    expected_words = clean_words(expected_base_clean)
    
    # Extraer primer palabra clave para ser súper tolerantes pero seguros (evitando substring "exter" en "dexter")
    has_title_match = False
    
    # Necesitamos palabras significativas (ignorando "the", "el", etc)
    t_word = get_key_word(title_words)
    e_word = get_key_word(expected_words)
    o_word = get_key_word(clean_words(original_title)) if original_title else None
    
    if t_word and t_word in item_words: has_title_match = True
    elif e_word and e_word in item_words: has_title_match = True
    elif o_word and o_word in item_words: has_title_match = True
    
    # También chequear original_title completo
    original_clean = clean_name(original_title) if original_title else ""
    if original_clean and (original_clean == item_clean or (len(original_clean) >= 6 and original_clean in item_clean)):
        has_title_match = True
    
    # Si de entrada sabemos que el S/E del archivo coincide perfecto con el pedido (ej. S01E02)
    # y además pasa el prefix del título, ¡es un match definitivo para TV!
    if has_title_match and season is not None and i_s == season:
        if episode is not None and i_e == episode:
            if is_target: print(f"[Watcher Trace] {item_name} -> Match perfecto Título + S/E", flush=True)
            return True
        elif i_e is None:
            # Season pack que coincide temporada
            if is_target: print(f"[Watcher Trace] {item_name} -> Match perfecto Título + Temporada (Pack)", flush=True)
            return True
        
    # Prioridad 1: Match exacto
    if expected_clean == item_clean: 
        if is_target: print(f"[Watcher Trace] {item_name} -> Match exacto", flush=True)
        return True
    
    # Prioridad 2: Contenido mutuo largo
    if len(expected_clean) >= 6 and expected_clean in item_clean: 
        return True
    if len(item_clean) >= 6 and item_clean in expected_clean: 
        return True
    
    # Prioridad 3: Fallbacks para casos agresivos donde S/E o año faltan en el nombre de la carpeta raíz
    if has_title_match:
        if season is not None:
            se_pattern = f"s{season:02d}"
            if se_pattern in item_clean:
                if is_target: print(f"[Watcher Trace] {item_name} -> Match Título Prefix + Patrón Season", flush=True)
                return True
            if "integrale" in item_clean or "temporada" in item_clean or "season" in item_clean:
                if is_target: print(f"[Watcher Trace] {item_name} -> Match Título Prefix + Keyword Pack", flush=True)
                return True
                
        # Fallback de año
        if str_year and str_year in item_clean:
            if is_target: print(f"[Watcher Trace] {item_name} -> Match Título Prefix + Año", flush=True)
            return True
            
        # Si no hay forma de validar año o S/E, pero el torrent es suficientemente largo y tiene el prefijo de nuestro título
        if len(item_clean) >= 10:
            if is_target: print(f"[Watcher Trace] {item_name} -> Match Fallback Extremo (Sólo Título Prefix)", flush=True)
            return True

    if is_target: print(f"[Watcher Trace] {item_name} NO matched (is_target=True)", flush=True)
    return False

def get_match_score(name: str, expected: str, title: str = "", year: str = "", season: int = None, episode: int = None, original_title: str = "") -> int:
    """Devuelve un puntaje de 0 a 100 de qué tanto se parece el nombre."""
    n_s, n_e = extract_se_info(name)
    
    # 1. Validación estricta de S/E si se proveen
    if season is not None and n_s is not None:
        if n_s != season:
            return 0
        if episode is not None and n_e is not None and n_e != episode:
            return 0
            
    # 2. Validación estricta de Año (Sólo para películas)
    str_year = str(year).strip() if year else ""
    if str_year and season is None:
        years_in_name = re.findall(r'\b(19\d{2}|20\d{2})\b', name)
        # Si encuentra años en el archivo y NINGUNO es el esperado, entonces es la peli equivocada
        if years_in_name and str_year not in years_in_name:
            return 0
            
    n_clean = clean_name(os.path.splitext(name)[0])
    e_clean = clean_name(os.path.splitext(expected)[0])
    
    if n_clean == e_clean: return 100
    
    # Bonus por match de patrón SXXEXX
    if season is not None and episode is not None:
        se_pattern = f"s{season:02d}e{episode:02d}"
        if se_pattern in n_clean: return 90

    if e_clean in n_clean: return 85
    if n_clean in e_clean: return 65
    
    # Fallback relaxado usando validación de la primera palabra clave
    score = 0
    t_words = clean_words(title)
    n_words = clean_words(name)
    
    t_word = get_key_word(t_words)
    if t_word and t_word in n_words:
        score += 40
    
    # Chequeo extra con título original
    if original_title:
        o_words = clean_words(original_title)
        o_word = get_key_word(o_words)
        if o_word and o_word in n_words:
            score += 45
        if clean_name(original_title) in n_clean:
            score += 20
            
    if year and str(year) in n_clean:
        score += 30
        
    # Bonificación si es el archivo más grande o si no tiene palabras como "sample", "trailer"
    if "sample" in n_clean or "trailer" in n_clean or "extra" in n_clean:
        score -= 50
        
    # Si de milagro el file tiene S01E02 de forma explícita y coincide
    if season is not None and episode is not None and n_s == season and n_e == episode:
        score += 80
        
    # LOG FINAL de Score para debugging
    if score > 0:
        print(f"[Watcher Debug]     Score Detail for {name}: {score} (OriginalTitle: {original_title})")
        
    return score

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
