import os
import re

def clean_title(title: str) -> str:
    # Remove invalid characters for folder names
    return re.sub(r'[\\/*?:"<>|]', "", title)

def create_plex_symlink(source_file_path: str, media_type: str, title: str, year: str, tmdb_id: int, base_library_path: str = "/Media", season_number: int = None):
    """"
    Crea la estructura de carpetas de Plex y el symlink al archivo descargado.
    Expected structure for movies: /Media/Movies/Nombre (Año) {tmdb-ID}/Archivo.ext
    Expected structure for TV: /Media/Shows/Nombre (Año) {tmdb-ID}/Season X/Archivo.ext
    """
    
    clean_name = clean_title(title)
    if year:
        folder_name = f"{clean_name} ({year}) {{tmdb-{tmdb_id}}}"
    else:
        folder_name = f"{clean_name} {{tmdb-{tmdb_id}}}"
    
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
            filename = f"{clean_name} ({year}){file_ext}"
        else:
            # Para series: extraer episodio del archivo original
            from media_utils import extract_se_info
            original_filename = os.path.basename(source_file_path)
            parsed_season, parsed_episode = extract_se_info(original_filename)
            
            if parsed_season and parsed_episode:
                # Formato: S01E01.ext
                filename = f"S{parsed_season:02d}E{parsed_episode:02d}{file_ext}"
            elif parsed_season:
                # Solo temporada (pack completo): usar nombre original
                filename = os.path.basename(source_file_path)
            else:
                # No se pudo parsear: usar nombre original como fallback
                filename = os.path.basename(source_file_path)
        
        symlink_path = os.path.join(target_dir, filename)
        
        # Si ya existe un symlink allí (por alguna razón), lo eliminamos
        if os.path.lexists(symlink_path):
            os.remove(symlink_path)
            
        os.symlink(source_file_path, symlink_path)
        print(f"Symlink creado exitosamente en: {symlink_path}")
        return symlink_path
        
    except Exception as e:
        print(f"Error creando estructura o symlink para Plex: {e}")
        return None
