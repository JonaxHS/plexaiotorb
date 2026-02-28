import os
import re

def clean_title(title: str) -> str:
    """Limpia el título para que sea compatible con Plex.
    
    Plex es muy permisivo pero en algunos casos tiene problemas con:
    - Caracteres especiales: : " ? * < > |
    - Paréntesis anidados
    - Múltiples espacios
    """
    if not title:
        return ""
    
    # 1. Eliminar caracteres inválidos en sistemas de archivos
    clean = re.sub(r'[\\/*?:"<>|]', "", title)
    
    # 2. Reemplazar comillas inteligentes con comillas simples/nada
    clean = clean.replace('"', '').replace('"', '')  # Smart quotes
    clean = clean.replace(''', "'").replace(''', "'")   # Smart singles
    
    # 3. Limpiar espacios múltiples
    clean = re.sub(r'\s+', ' ', clean).strip()
    
    # 4. Evitar que termine con punto (confunde a algunos sistemas)
    clean = clean.rstrip('.')
    
    return clean

def create_plex_symlink(source_file_path: str, media_type: str, title: str, year: str, tmdb_id: int, base_library_path: str = "/Media", season_number: int = None, original_title: str = None, use_original: bool = None):
    """"
    Crea la estructura de carpetas de Plex y el symlink al archivo descargado.
    Expected structure for movies: /Media/Movies/Nombre (Año) {tmdb-ID}/Archivo.ext
    Expected structure for TV: /Media/Shows/Nombre (Año) {tmdb-ID}/Season X/Archivo.ext
    
    Args:
        source_file_path: Ruta del archivo en TorBox
        media_type: 'movie' o 'tv'
        title: Título traducido (puede contener caracteres especiales)
        year: Año de la película/serie
        tmdb_id: ID de TMDB
        base_library_path: Ruta base de la librería Plex
        season_number: Número de temporada (para series)
        original_title: Título original en inglés (ej: "Bad Boys Ride or Die")
        use_original: Si True, usar original_title en lugar de title. Si None, intentar usar config.
    """
    
    # Determinar si usar título original o traducido
    display_title = title
    if use_original is None:
        # Intentar leer de config
        try:
            from config import config
            use_original = config.get("plex", {}).get("use_original_titles", False)
        except:
            use_original = False
    
    if use_original and original_title:
        display_title = original_title
        print(f"[Symlink] Usando título original: '{original_title}' (en lugar de '{title}')")
    elif original_title and title != original_title:
        print(f"[Symlink] Traducción disponible: '{title}' (original: '{original_title}')")
    
    clean_name = clean_title(display_title)
    
    # Validaciones para Plex
    if not clean_name or clean_name.isspace():
        print(f"[Symlink] ⚠️ ADVERTENCIA: Título completamente vacío después de limpiar: '{title}'")
        clean_name = title[:20] if title else "Unknown"
    
    # El año es importante para Plex - always include it
    if year and year != "":
        folder_name = f"{clean_name} ({year}) {{tmdb-{tmdb_id}}}"
        file_year = f" ({year})"
    else:
        folder_name = f"{clean_name} {{tmdb-{tmdb_id}}}"
        file_year = ""
        print(f"[Symlink] ⚠️ ADVERTENCIA: Año no disponible para '{title}' - Plex podría tener dificultades para identificarlo")
    
    # Usamos las carpetas declaradas localmente por el usuario
    sub_folder = "Movies" if media_type == "movie" else "Shows"
    
    target_dir = os.path.join(base_library_path, sub_folder, folder_name)
    
    # Extraer la temporada real del nombre del archivo por si TorBox devolvió un archivo cruzado o un pack
    if media_type == "tv":
        from media_utils import extract_se_info
        filename_for_regex = os.path.basename(source_file_path)
        parsed_season, _ = extract_se_info(filename_for_regex)
        if parsed_season is not None:
            print(f"[Symlink] Detectada temporada real en el archivo ({parsed_season}) (Reemplaza la UI: {season_number})")
            season_number = parsed_season
    
    if media_type == "tv" and season_number is not None:
        target_dir = os.path.join(target_dir, f"Season {season_number:02d}")
        
    try:
        os.makedirs(target_dir, exist_ok=True)
        print(f"Directorio Plex creado o verificado: {target_dir}")
        
        # Extraer la extensión del archivo original
        _, file_ext = os.path.splitext(source_file_path)
        
        # Crear el nombre del archivo según el formato de Plex
        if media_type == "movie":
            # Para películas: Título (Año).ext
            filename = f"{clean_name}{file_year}{file_ext}"
            print(f"[Symlink] Archivo películas: {filename}")
        else:
            # Para series: extraer episodio del archivo original
            from media_utils import extract_se_info
            original_filename = os.path.basename(source_file_path)
            parsed_season, parsed_episode = extract_se_info(original_filename)
            
            if parsed_season and parsed_episode:
                # Formato estándar Plex: S01E01.ext
                filename = f"S{parsed_season:02d}E{parsed_episode:02d}{file_ext}"
                print(f"[Symlink] Episodio S{parsed_season:02d}E{parsed_episode:02d}")
            elif parsed_season:
                # Solo temporada (pack completo): mantener nombre pero limpiar caracteres problemáticos
                filename = clean_title(original_filename)
                if not filename.endswith(file_ext):
                    filename = f"{filename}{file_ext}"
                print(f"[Symlink] Pack temporada (archivo): {filename}")
            else:
                # No se pudo parsear: intentar limpiar y mantener extensión
                name_only = clean_title(os.path.splitext(original_filename)[0])
                filename = f"{name_only}{file_ext}"
                print(f"[Symlink] ⚠️ No se pudo parsear S/E: {filename}")
                
            # Validación final
            if not filename or filename.isspace():
                print(f"[Symlink] ✗ CRÍTICO: Archivo vacío, usando fallback")
                filename = f"episode_{season_number}_{parsed_episode or 0}{file_ext}"
        
        symlink_path = os.path.join(target_dir, filename)
        
        # Si ya existe un symlink allí (por alguna razón), lo eliminamos
        if os.path.lexists(symlink_path):
            os.remove(symlink_path)
            
        os.symlink(source_file_path, symlink_path)
        print(f"✓ Symlink creado exitosamente")
        print(f"  Carpeta: {target_dir}")
        print(f"  Archivo: {filename}")
        print(f"  → {symlink_path}")
        return symlink_path
        
    except Exception as e:
        print(f"✗ Error creando estructura o symlink para Plex: {e}")
        import traceback
        traceback.print_exc()
        return None
