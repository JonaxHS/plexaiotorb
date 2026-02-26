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
        filename_for_regex = os.path.basename(source_file_path)
        # Buscar patrones como S01E01, s1e4, S02, etc. o 1x01
        match = re.search(r'[sS](\d+)[eE]\d+', filename_for_regex) or re.search(r'(?<!\d)(\d+)x\d+', filename_for_regex)
        if match:
            parsed_season = int(match.group(1))
            print(f"[Symlink] Detectada temporada real en el archivo ({parsed_season}) (Reemplaza la UI: {season_number})")
            season_number = parsed_season
    
    if media_type == "tv" and season_number is not None:
        target_dir = os.path.join(target_dir, f"Season {season_number:02d}")
        
    try:
        os.makedirs(target_dir, exist_ok=True)
        print(f"Directorio Plex creado o verificado: {target_dir}")
        
        # El nombre del archivo symlink usará el nombre original del archivo fuente
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
