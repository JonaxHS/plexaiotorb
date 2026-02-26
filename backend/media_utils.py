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

    # 4. Formato Temporada 1 Capitulo 1
    t_match = re.search(r'Temporada\s*(\d+)', text, re.I)
    c_match = re.search(r'(?:Capitulo|Episodio)\s*(\d+)', text, re.I)
    if t_match and c_match:
        return int(t_match.group(1)), int(c_match.group(1))
    
    # 5. Formato Temporada X (Packs)
    if t_match:
        return int(t_match.group(1)), None
    
    # 6. Formato solo S01
    match = re.search(r'(?<!\d)[sS](\d{1,2})(?!\d)', text)
    if match:
        return int(match.group(1)), None

    return None, None

def get_match_score(name: str, expected_filename: str = "", title: str = "", year: str = "", season: int = None, episode: int = None, original_title: str = "") -> int:
    """Devuelve un puntaje de 0 a 100 de qué tanto se parece el nombre."""
    n_s, n_e = extract_se_info(name)
    
    # 1. Validación estricta de S/E si se proveen
    if season is not None:
        if n_s is None:
            # Si no hay temporada en el nombre, pero estamos buscando una serie, bajamos puntaje drásticamente 
            # a menos que el nombre del archivo sea muy parecido al título (ej. "Breaking Bad Complete")
            pass
        elif n_s != season:
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
        # Si encuentra años en el archivo y NINGUNO es el esperado, entonces es el objeto equivocado
        if years_in_name and str_year not in years_in_name:
            return 0
            
    n_clean = clean_name(os.path.splitext(name)[0])
    e_clean = clean_name(os.path.splitext(expected_filename)[0]) if expected_filename else ""
    t_clean = clean_name(title)
    o_clean = clean_name(original_title) if original_title else ""
    
    # Match exacto es imbatible
    if e_clean and n_clean == e_clean: return 100
    if t_clean and n_clean == t_clean: return 95
    if o_clean and n_clean == o_clean: return 95
    
    # EVITAR: "Ted" matching "Ted 2" si "2" no está en el título solicitado
    if t_clean and len(t_clean) <= 4:
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

    return min(100, max(0, int(score)))

def is_valid_match(item_name: str, expected_filename: str, title: str, year: str, season: int = None, episode: int = None, original_title: str = "") -> bool:
    score = get_match_score(item_name, expected_filename, title, year, season, episode, original_title)
    # Umbral de coincidencia. 35 es razonable para nombres con ruido
    return score >= 35
