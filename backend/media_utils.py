import re
import os

def clean_name(name: str) -> str:
    """Elimina todo lo que no sea alfanumérico y pasa a minúsculas."""
    if not name: return ""
    # Normalizar: eliminar acentos básicos si es posible o simplemente limpiar
    name = name.lower()
    return re.sub(r'[^a-z0-9]', '', name)

def clean_words(name: str):
    """Extrae las palabras limpias (separadas por puntos, espacios, etc)."""
    if not name: return []
    res = re.sub(r'[^a-zA-Z0-9]', ' ', name).lower()
    return res.split()

def get_key_words(words: list) -> list:
    """Extrae palabras clave importantes (ignorando artículos/stopwords)."""
    stopwords = {"the", "a", "an", "el", "la", "los", "las", "un", "una", "de", "del", "and", "or", "of"}
    return [w for w in words if w not in stopwords and len(w) >= 3]

def extract_se_info(text: str):
    """Extrae temporada y episodio si existen en el texto con múltiples formatos."""
    if not text: return None, None
    
    # 1. Formato Estándar: S01E01, s1e1, S01.E01, S01_E01
    match = re.search(r'[sS](\d+)\s*[.eE\-_]\s*[eE](\d+)', text)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # 2. Formato Simple: S01E01 sin separador (ya cubierto por el de arriba pero re-aseguramos)
    match = re.search(r'[sS](\d+)[eE](\d+)', text)
    if match:
        return int(match.group(1)), int(match.group(2))

    # 3. Formato 1x01
    match = re.search(r'(?<!\d)(\d{1,2})x(\d{1,3})(?!\d|\w)', text, re.I)
    if match:
        return int(match.group(1)), int(match.group(2))

    # 4. Formato Temporada 1 Capitulo 1 (Soporta Inglés y Español)
    t_match = re.search(r'(?:Temporada|Season|Series)\s*(\d+)', text, re.I)
    c_match = re.search(r'(?:Capitulo|Episodio|Episode|Ep)\s*(\d+)', text, re.I)
    if t_match and c_match:
        return int(t_match.group(1)), int(c_match.group(1))
    
    # 5. Formato Temporada X (Packs / Carpetas)
    if t_match:
        return int(t_match.group(1)), None
    
    # 6. Formato solo S01
    match = re.search(r'(?<!\d)[sS](\d{1,2})(?!\d)', text)
    if match:
        return int(match.group(1)), None

    return None, None

def get_season_range(text: str):
    """
    Detecta si un texto cubre un RANGO de temporadas (ej: S01-S05, S01.S02.S03, Complete).
    Devuelve (min_season, max_season) o (None, None) si no aplica.
    """
    if not text: return None, None
    
    # Rango explícito: S01-S05 o S1-S5
    match = re.search(r'[sS](\d+)[-_\.][sS](\d+)', text)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # Múltiples S sin E: S01.S02.S03 o S04 S05 etc
    seasons = re.findall(r'[sS](\d{1,2})(?![eE\d])', text)
    if len(seasons) >= 2:
        nums = [int(s) for s in seasons]
        return min(nums), max(nums)
    
    # Palabras clave de pack completo - cubren todas las temporadas el nombre principal
    keywords = ['complete', 'integral', 'completa', 'all.seasons', 'temporadas']
    text_lower = text.lower()
    if any(kw in text_lower for kw in keywords):
        # No sabemos el rango exacto, asumimos que cubre cualquier temporada
        return 0, 99
    
    return None, None

def get_match_score(name: str, expected_filename: str = "", title: str = "", year: str = "", season: int = None, episode: int = None, original_title: str = "") -> int:
    """Devuelve un puntaje de 0 a 100 de qué tanto se parece el nombre."""
    n_s, n_e = extract_se_info(name)
    
    # 1. Validación estricta de S/E si se proveen
    if season is not None:
        if n_s is None:
            # Verificar si es un pack multi-temporada que cubre esta temporada
            range_min, range_max = get_season_range(name)
            if range_min is not None and not (range_min <= season <= range_max):
                return 0  # Rango de temporadas conocido pero no incluye la buscada
            # Si n_s is None y no es un rango, puede ser una carpeta genérica - dejamos pasar
        elif n_s != season:
            # Antes de rechazar, verificar si es un pack multi-temporada
            range_min, range_max = get_season_range(name)
            if range_min is not None and (range_min <= season <= range_max):
                # Es un pack que incluye la temporada buscada ✓
                pass
            else:
                return 0
        if episode is not None and n_e is not None and n_e != episode:
            return 0
    else:
        # Si buscamos peli pero el archivo tiene S/E, es probable que sea serie
        if n_s is not None:
            return 0
            
    # 2. Validación estricta de Año
    str_year = str(year).strip() if year else ""
    if str_year:
        years_in_name = re.findall(r'\b(19\d{2}|20\d{2})\b', name)
        if years_in_name and str_year not in years_in_name:
            if season is None:
                # Para películas: siempre fatal
                return 0
            elif n_s is None and get_season_range(name) == (None, None):
                # Para series: si el archivo NO tiene marcador de temporada/episodio,
                # es probablemente una película. Aplicar validación estricta de año.
                # Ej: "Ted 2 (2015)" cuando buscamos "Ted S01E07 (2024)"
                return 0
            # Si tiene marcador de temporada (ej: S02), el año puede ser distinto (es el año de esa temporada)
        else:
            # Para series, no es fatal, pero si coincide damos fe
            pass
            
    n_clean = clean_name(os.path.splitext(name)[0])
    e_clean = clean_name(os.path.splitext(expected_filename)[0]) if expected_filename else ""
    t_clean = clean_name(title)
    o_clean = clean_name(original_title) if original_title else ""
    
    # Match exacto es imbatible
    if e_clean and n_clean == e_clean: return 100
    if t_clean and n_clean == t_clean: return 95
    if o_clean and n_clean == o_clean: return 95
    
    # EVITAR: "Ted" matching "Ted 2" si "2" no está en el título solicitado
    # Solo para PELÍCULAS, ya que en series el "2" puede ser la temporada (E.g. Ted 1x01)
    if season is None and t_clean and len(t_clean) <= 4:
        # Si el nombre del archivo tiene un número justo después del título que no está en el título
        if n_clean.startswith(t_clean) and len(n_clean) > len(t_clean):
            next_char = n_clean[len(t_clean)]
            if next_char.isdigit() and next_char not in t_clean:
                return 0

    score = 0
    n_words = set(clean_words(name))
    t_words = set(get_key_words(clean_words(title)))
    o_words = set(get_key_words(clean_words(original_title))) if original_title else set()
    
    # Match por palabras clave del título
    matched_t = n_words.intersection(t_words)
    if t_words and len(matched_t) >= len(t_words) * 0.7:
        score += 50
    elif t_words and len(matched_t) > 0:
        score += 20 * (len(matched_t) / len(t_words))

    # Match por palabras clave del título original
    matched_o = n_words.intersection(o_words)
    if o_words and len(matched_o) >= len(o_words) * 0.7:
        score += 50
    elif o_words and len(matched_o) > 0:
        score += 20 * (len(matched_o) / len(o_words))
        
    if str_year and str_year in name:
        score += 30
        
    # Bonus por SXXEXX si coincide
    if season is not None and episode is not None and n_s == season and n_e == episode:
        score += 40
    elif season is not None and n_s == season:
        score += 20
        # Si buscamos episodio pero el archivo no tiene episodio (y no es carpeta)
        if episode is not None and n_e is None and "." in name:
             score -= 30

    # Penalizaciones
    if "sample" in n_clean or "trailer" in n_clean or "extra" in n_clean:
        score -= 60
        
    # VALIDACIÓN CRÍTICA: Si no hay NINGUNA coincidencia de título, original_title o expected_filename,
    # el puntaje debe ser 0 para evitar que el bonus de SXXEXX (muy común) cause falsos positivos.
    has_any_title_hint = (len(matched_t) > 0) or (len(matched_o) > 0) or (e_clean and (e_clean in n_clean or n_clean in e_clean))
    
    if not has_any_title_hint:
        return 0
    
    # VALIDACIÓN ESTRICTA MULTI-PALABRA:
    # Si el título tiene 2+ palabras clave (ej: "Ted Lasso"), exigir que TODAS coincidan.
    # Esto evita que "ted.S01E01.mkv" matchee "Ted Lasso" solo por la palabra "ted".
    if len(t_words) >= 2:
        match_ratio_t = len(matched_t) / len(t_words)
        # Verificar también si el título original tiene suficiente coincidencia por sí solo
        match_ratio_o = (len(matched_o) / len(o_words)) if o_words else 0
        # El e_clean puede satisfacer el match si el expected_filename contiene el título completo
        has_full_match = (
            match_ratio_t >= 1.0 or           # todas las palabras del título español coinciden
            match_ratio_o >= 0.7 or            # el título original (inglés) coincide >70%
            (e_clean and (e_clean in n_clean or n_clean in e_clean))  # expected filename coincide
        )
        if not has_full_match:
            return 0

    return min(100, max(0, int(score)))

def is_valid_match(item_name: str, expected_filename: str, title: str, year: str, season: int = None, episode: int = None, original_title: str = "") -> bool:
    score = get_match_score(item_name, expected_filename, title, year, season, episode, original_title)
    # Umbral de coincidencia. 35 es razonable para nombres con ruido
    return score >= 35
