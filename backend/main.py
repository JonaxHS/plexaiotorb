from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import yaml
import os
import docker
import subprocess
import time
import asyncio
import threading
import logging
from config import config, reload_config
import config as config_module
from watcher import start_watcher_thread
from symlinks import create_plex_symlink
from health import start_health_monitor

logger = logging.getLogger(__name__)
app = FastAPI(title="PlexAioTorb Backend")
notification_queue = [] # Cola simple para avisos al frontend
job_logs: dict = {}      # Logs detallados por trabajo: {job_id: [str]}
MAX_JOB_LOGS = 500       # Max líneas de log por trabajo

# --- Persistencia de Trabajos ---
JOBS_FILE = os.path.join(os.path.dirname(config_module.config.get("config_path", "/app/config/config.yaml")), "active_jobs.json")
active_jobs = {}      # Seguimiento de procesos en curso

import json

def save_config(new_cfg: dict):
    """Guarda config.yaml y recarga config_module.config en memoria."""
    config_path = os.getenv("CONFIG_PATH", "config.yaml")
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(new_cfg, f, allow_unicode=True, sort_keys=False)
    reload_config()

def append_job_log(job_id: str, msg: str):
    """Agrega una línea de log a la cola del trabajo."""
    from datetime import datetime
    if job_id not in job_logs:
        job_logs[job_id] = []
    ts = datetime.now().strftime("%H:%M:%S")
    job_logs[job_id].append(f"[{ts}] {msg}")
    # Mantener log circular para no usar demasiada RAM
    if len(job_logs[job_id]) > MAX_JOB_LOGS:
        job_logs[job_id] = job_logs[job_id][-MAX_JOB_LOGS:]

def save_jobs():
    try:
        with open(JOBS_FILE, 'w') as f:
            json.dump(active_jobs, f)
    except Exception as e:
        print(f"[Jobs] Error guardando: {e}")

def load_jobs():
    global active_jobs
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE, 'r') as f:
                active_jobs = json.load(f)
        except Exception:
            active_jobs = {}

def is_vfs_fuse_mounted(mount_point: str = "/mnt/torbox") -> bool:
    """Valida que el mount sea realmente FUSE del VFS (no solo un volumen Docker)."""
    try:
        if not os.path.exists(mount_point):
            return False

        with open("/proc/mounts", "r", encoding="utf-8") as mounts_file:
            for line in mounts_file:
                parts = line.split()
                if len(parts) < 3:
                    continue
                source, target, fstype = parts[0], parts[1], parts[2]
                if target == mount_point and (fstype.startswith("fuse") or source == "torbox_vfs"):
                    return True
        return False
    except Exception:
        return False

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    load_jobs()
    start_health_monitor(interval_seconds=3600, base_library_path=config.get("plex", {}).get("library_path", "/Media"))
    
    # Iniciar VFS custom
    from vfs_manager import startup_vfs
    vfs_started = await startup_vfs()
    
    if vfs_started:
        # Esperar a que el VFS esté montado
        print("[Startup] Esperando a que VFS esté montado...")
        mount_point = os.getenv("MOUNT_POINT", "/mnt/torbox")
        for attempt in range(30):  # 30 intentos x 1s = 30s max
            if is_vfs_fuse_mounted(mount_point):
                try:
                    item_count = len(os.listdir(mount_point))
                    print(f"[Startup] ✓ VFS montado y listo ({item_count} items)")
                    break
                except:
                    pass
            print(f"[Startup] Esperando VFS... ({attempt}s)")
            await asyncio.sleep(1)
        else:
            print("[Startup] ⚠️ VFS no se montó después de 30s. Continuando...")
    else:
        print("[Startup] VFS deshabilitado o no disponible. Continuando sin mount FUSE.")
    
    # Reanudar búsquedas pendientes
    pending_jobs = [job_id for job_id, job in active_jobs.items() 
                    if job.get("status") not in ["Completed", "Error"]]
    if pending_jobs:
        print(f"[Jobs] Reanudando {len(pending_jobs)} búsquedas pendientes...")
        for job_id in pending_jobs:
            job = active_jobs[job_id]
            print(f"[Jobs] Reanudando búsqueda para: {job.get('title')}")
            # Re-disparamos la lógica de descarga usando los datos guardados
            if "req" in job:
                try:
                    # Usamos una función interna para evitar loops de red
                    req_data = DownloadRequest(**job["req"])
                    threading.Thread(target=initiate_download_process, args=(req_data, job_id), daemon=True).start()
                except Exception as e:
                    print(f"[Jobs] Error reanudando {job_id}: {e}")

@app.on_event("shutdown")
async def on_shutdown():
    from vfs_manager import shutdown_vfs
    await shutdown_vfs()
    print("[Shutdown] VFS stopped")

TMDB_API_KEY = config.get("tmdb", {}).get("api_key", "")
AIOSTREAMS_URL = config.get("aiostreams", {}).get("url", "")
print(f"[Startup] Config Loaded. TMDB: {'✓' if TMDB_API_KEY else '✗'}, AIOStreams: {AIOSTREAMS_URL or '✗'}")

class DownloadRequest(BaseModel):
    title: str
    original_title: Optional[str] = None
    year: str
    media_type: str
    tmdb_id: int
    filename: str
    season_number: Optional[int] = None
    episode_number: Optional[int] = None

class CacheCheckRequest(BaseModel):
    filename: str
    title: str = ""

class SetupRequest(BaseModel):
    tmdb_api_key: str
    aiostreams_url: str
    torbox_email: str
    torbox_password: str
    plex_server_name: str

class ManualLinkRequest(BaseModel):
    path: str
    tmdb_id: int
    media_type: str
    title: str
    original_title: Optional[str] = None
    year: str
    season_number: Optional[int] = None
    job_id: Optional[str] = None

def is_setup_complete():
    return bool(config_module.config.get("tmdb", {}).get("api_key"))

@app.get("/api/status")
def get_status():
    """"Devuelve si el sistema ya fue configurado por primera vez"""
    return {"configured": is_setup_complete()}

@app.post("/api/setup")
def run_setup(req: SetupRequest):
    """"Guarda la configuración y reinicia los contenedores afectados"""
    
    # 1. Crear config.yaml
    new_config = {
        "tmdb": {"api_key": req.tmdb_api_key},
        "aiostreams": {"url": req.aiostreams_url},
        "plex": {"library_path": "/Media"},
        "vfs": {
            "torbox_url": "https://webdav.torbox.app/",
            "torbox_user": req.torbox_email,
            "torbox_pass": req.torbox_password
        }
    }
    config_path = os.getenv("CONFIG_PATH", "config.yaml")
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(new_config, f)
        
    reload_config()
    
    # 2. Modificar Preferences.xml de Plex
    pref_path = "/plex_config/Library/Application Support/Plex Media Server/Preferences.xml"
    os.makedirs(os.path.dirname(pref_path), exist_ok=True)
    if os.path.exists(pref_path):
        with open(pref_path, "r", encoding="utf-8") as f:
            content = f.read()
        import re
        if "FriendlyName=" in content:
            content = re.sub(r'FriendlyName="[^"]*"', f'FriendlyName="{req.plex_server_name}"', content)
        else:
            content = content.replace("<Preferences ", f'<Preferences FriendlyName="{req.plex_server_name}" ')
        with open(pref_path, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        with open(pref_path, "w", encoding="utf-8") as f:
            f.write(f'<?xml version="1.0" encoding="utf-8"?>\n<Preferences FriendlyName="{req.plex_server_name}" />')

    # 3. Reiniciar contenedor de plex
    try:
        client = docker.from_env()
        try:
            plex_c = client.containers.get("plex")
            plex_c.restart()
        except: pass
        os.environ["TORBOX_URL"] = "https://webdav.torbox.app/"
        os.environ["TORBOX_USER"] = req.torbox_email
        os.environ["TORBOX_PASS"] = req.torbox_password
    except Exception as e:
        print(f"Error reiniciando contenedores: {e}")

    return {"status": "ok", "message": "Configuración guardada. Servicios reiniciándose."}


@app.get("/api/settings")
def get_settings():
    return {
        "tmdb_api_key": config_module.config.get("tmdb", {}).get("api_key", ""),
        "aiostreams_url": config_module.config.get("aiostreams", {}).get("url", ""),
        "use_original_titles": config_module.config.get("plex", {}).get("use_original_titles", False),
        "torbox_url": config_module.config.get("vfs", {}).get("torbox_url", ""),
        "torbox_user": config_module.config.get("vfs", {}).get("torbox_user", ""),
        "torbox_pass": config_module.config.get("vfs", {}).get("torbox_pass", "")
    }

class SettingsUpdate(BaseModel):
    tmdb_api_key: str
    aiostreams_url: str
    use_original_titles: bool = False
    torbox_url: str = ""
    torbox_user: str = ""
    torbox_pass: str = ""

@app.post("/api/settings")
def update_settings(req: SettingsUpdate):
    """Actualiza configuración crítica sin reiniciar el backend"""
    new_cfg = config_module.config.copy()
    
    if "tmdb" not in new_cfg: new_cfg["tmdb"] = {}
    new_cfg["tmdb"]["api_key"] = req.tmdb_api_key
    
    if "aiostreams" not in new_cfg: new_cfg["aiostreams"] = {}
    new_cfg["aiostreams"]["url"] = req.aiostreams_url.strip().rstrip('/')
    
    if "plex" not in new_cfg: new_cfg["plex"] = {}
    new_cfg["plex"]["use_original_titles"] = req.use_original_titles
    
    # Guardar configuración del VFS custom
    if "vfs" not in new_cfg: new_cfg["vfs"] = {}
    new_cfg["vfs"]["torbox_url"] = req.torbox_url
    new_cfg["vfs"]["torbox_user"] = req.torbox_user
    new_cfg["vfs"]["torbox_pass"] = req.torbox_pass
    
    save_config(new_cfg)
    print(f"[Settings] use_original_titles guardado en: {req.use_original_titles}")
    
    # Actualizar variables de entorno para VFS
    if req.torbox_url:
        os.environ["TORBOX_URL"] = req.torbox_url
    if req.torbox_user:
        os.environ["TORBOX_USER"] = req.torbox_user
    if req.torbox_pass:
        os.environ["TORBOX_PASS"] = req.torbox_pass
    
    print(f"[VFS] Configuración TorBox actualizada")
    
    # Actualizar variables globales pre-cacheadas
    global TMDB_API_KEY
    TMDB_API_KEY = req.tmdb_api_key
    
    return {"status": "ok", "message": "Ajustes almacenados en vivo"}

@app.get("/api/vfs/status")
def vfs_status():
    try:
        mount_point = os.getenv("MOUNT_POINT", "/mnt/torbox")

        if not os.path.exists(mount_point):
            return {"status": "disconnected", "reason": "mount_path_missing"}
        if not is_vfs_fuse_mounted(mount_point):
            return {"status": "degraded", "reason": "vfs_not_mounted"}

        item_count = len(os.listdir(mount_point))
        return {"status": "connected", "items": item_count}
    except Exception as e:
        return {"status": "disconnected", "reason": str(e)}

@app.get("/api/logs")
def get_global_logs():
    """"Devuelve un arreglo combinado con los últimos logs de los contenedores Docker"""
    try:
        client = docker.from_env()
        combined = []
        for c in client.containers.list(all=True):
            if any(n in c.name for n in ["plexaiotorb-backend", "plex"]):
                try:
                    c_logs = c.logs(tail=30).decode("utf-8").split("\n")
                    # Append container name prefix
                    combined.extend([f"[{c.name}] {l}" for l in c_logs if l.strip()])
                except: pass
        # Sort might be tricky without timestamps, but Docker logs usually have no timestamps unless asked.
        # Returning as is.
        return {"logs": combined[-100:]}
    except Exception as e:
        return {"logs": [f"[Error] No se pudieron obtener los logs: {e}"]}


@app.get("/api/tmdb/trending")
def get_trending(media_type: str = "all", time_window: str = "day", page: int = 1):
    """Obtiene tendencias de TMDB (movie, tv, all)"""
    if not TMDB_API_KEY:
        raise HTTPException(status_code=500, detail="TMDB API key no configurada")
    
    url = f"https://api.themoviedb.org/3/trending/{media_type}/{time_window}?api_key={TMDB_API_KEY}&language=es-MX&page={page}"
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("results", []):
            m_type = item.get("media_type") or (media_type if media_type != "all" else "movie")
            if m_type not in ["movie", "tv"]: continue
            
            title = item.get("title") or item.get("name")
            release_date = item.get("release_date") or item.get("first_air_date") or ""
            year = release_date.split("-")[0] if release_date else ""
            
            results.append({
                "id": item.get("id"),
                "title": title,
                "year": year,
                "media_type": m_type,
                "poster_path": f"https://image.tmdb.org/t/p/w200{item.get('poster_path')}" if item.get('poster_path') else None,
                "backdrop_path": f"https://image.tmdb.org/t/p/w500{item.get('backdrop_path')}" if item.get('backdrop_path') else None,
                "vote_average": round(item.get("vote_average", 0), 1)
            })
        return {"results": results, "total_pages": data.get("total_pages", 1)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tmdb/genres")
def get_genres(media_type: str = "movie"):
    """Obtiene lista de géneros de TMDB"""
    if not TMDB_API_KEY:
        raise HTTPException(status_code=500, detail="TMDB API key no configurada")
    
    url = f"https://api.themoviedb.org/3/genre/{media_type}/list?api_key={TMDB_API_KEY}&language=es-MX"
    try:
        r = requests.get(url)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tmdb/discover")
def discover_tmdb(media_type: str = "movie", genre_id: Optional[int] = None, sort_by: str = "popularity.desc", page: int = 1):
    """Descubre contenido basado en filtros"""
    if not TMDB_API_KEY:
        raise HTTPException(status_code=500, detail="TMDB API key no configurada")
    
    url = f"https://api.themoviedb.org/3/discover/{media_type}?api_key={TMDB_API_KEY}&language=es-MX&sort_by={sort_by}&page={page}"
    if genre_id:
        url += f"&with_genres={genre_id}"
        
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("results", []):
            title = item.get("title") or item.get("name")
            release_date = item.get("release_date") or item.get("first_air_date") or ""
            year = release_date.split("-")[0] if release_date else ""
            
            results.append({
                "id": item.get("id"),
                "title": title,
                "year": year,
                "media_type": media_type,
                "poster_path": f"https://image.tmdb.org/t/p/w200{item.get('poster_path')}" if item.get('poster_path') else None,
                "backdrop_path": f"https://image.tmdb.org/t/p/w500{item.get('backdrop_path')}" if item.get('backdrop_path') else None,
                "vote_average": round(item.get("vote_average", 0), 1)
            })
        return {"results": results, "total_pages": data.get("total_pages", 1)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tmdb/person/{person_id}")
def get_person_details(person_id: int):
    """Obtiene detalles bio de un actor"""
    if not TMDB_API_KEY:
        raise HTTPException(status_code=500, detail="TMDB API key no configurada")
    
    url = f"https://api.themoviedb.org/3/person/{person_id}?api_key={TMDB_API_KEY}&language=es-MX"
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "biography": data.get("biography"),
            "birthday": data.get("birthday"),
            "place_of_birth": data.get("place_of_birth"),
            "profile_path": data.get("profile_path"),
            "known_for_department": data.get("known_for_department")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interactuando con TMDB: " + str(e))

@app.get("/api/tmdb/person/{person_id}/credits")
def get_person_credits(person_id: int):
    """Obtiene los creditos (peliculas/series) de un actor"""
    if not TMDB_API_KEY:
        raise HTTPException(status_code=500, detail="TMDB API key no configurada")
    
    url = f"https://api.themoviedb.org/3/person/{person_id}/combined_credits?api_key={TMDB_API_KEY}&language=es-MX"
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        
        results = []
        # Sort by popularity or release date
        cast = sorted(data.get("cast", []), key=lambda x: x.get("popularity", 0), reverse=True)
        
        for item in cast[:20]: # Limit to top 20
            if item.get("media_type") not in ["movie", "tv"]:
                continue
            title = item.get("title") or item.get("name")
            release_date = item.get("release_date") or item.get("first_air_date") or ""
            year = release_date.split("-")[0] if release_date else ""
            results.append({
                "id": item.get("id"),
                "title": title,
                "year": year,
                "media_type": item.get("media_type"),
                "poster_path": item.get('poster_path'),
                "vote_average": round(item.get("vote_average", 0), 1),
                "character": item.get("character")
            })
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interactuando con TMDB: " + str(e))

@app.get("/api/search")
def search_tmdb(q: str, page: int = 1):
    """"Busca películas y series en TMDB"""
    if not TMDB_API_KEY:
        raise HTTPException(status_code=500, detail="TMDB API key no configurada")
    
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={q}&language=es-MX&page={page}"
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("results", []):
            if item.get("media_type") not in ["movie", "tv"]:
                continue
            title = item.get("title") or item.get("name")
            release_date = item.get("release_date") or item.get("first_air_date") or ""
            year = release_date.split("-")[0] if release_date else ""
            results.append({
                "id": item.get("id"),
                "title": title,
                "year": year,
                "media_type": item.get("media_type"),
                "poster_path": f"https://image.tmdb.org/t/p/w200{item.get('poster_path')}" if item.get('poster_path') else None
            })
        return {"results": results, "total_pages": data.get("total_pages", 1)}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interactuando con TMDB: " + str(e))

@app.get("/api/details/{media_type}/{tmdb_id}")
def get_media_details(media_type: str, tmdb_id: int):
    """"Obtiene detalles enriquecidos (sinopsis, cast, temporadas) de TMDB"""
    current_key = config_module.config.get("tmdb", {}).get("api_key", "")
    if not current_key:
        raise HTTPException(status_code=500, detail="TMDB API key no configurada")
        
    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}?api_key={current_key}&language=es-MX&append_to_response=credits"
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        
        # Parse basic info
        release_date = data.get("release_date") or data.get("first_air_date") or ""
        year = release_date.split("-")[0] if release_date else ""
        
        # Parse cast (primeros 10)
        cast = []
        if "credits" in data and "cast" in data["credits"]:
            for c in data["credits"]["cast"][:10]:
                cast.append({
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "character": c.get("character"),
                    "profile_path": f"https://image.tmdb.org/t/p/w200{c.get('profile_path')}" if c.get('profile_path') else None
                })
            
        # Parse Temporadas si es serie
        seasons = []
        if media_type == "tv" and "seasons" in data:
            for s in data["seasons"]:
                # Ignoramos la temporada 0 (Especiales) por simplicidad inicial, a menos que se desee
                if s.get("season_number") > 0:
                    seasons.append({
                        "season_number": s.get("season_number"),
                        "episode_count": s.get("episode_count"),
                        "name": s.get("name"),
                        "poster_path": f"https://image.tmdb.org/t/p/w200{s.get('poster_path')}" if s.get("poster_path") else None
                    })
                    
        return {
            "id": data.get("id"),
            "title": data.get("title") or data.get("name"),
            "original_title": data.get("original_title") or data.get("original_name"),
            "year": year,
            "overview": data.get("overview"),
            "poster_path": f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}" if data.get('poster_path') else None,
            "backdrop_path": f"https://image.tmdb.org/t/p/original{data.get('backdrop_path')}" if data.get('backdrop_path') else None,
            "genres": [g.get("name") for g in data.get("genres", [])],
            "cast": cast,
            "vote_average": round(data.get("vote_average", 0), 1),
            "seasons": seasons
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error obteniendo detalles de TMDB: " + str(e))

@app.get("/api/season/{tmdb_id}/{season_number}")
def get_season_details(tmdb_id: int, season_number: int):
    """"Obtiene los episodios de una temporada específica de una serie en TMDB"""
    current_key = config_module.config.get("tmdb", {}).get("api_key", "")
    if not current_key:
        raise HTTPException(status_code=500, detail="TMDB API key no configurada")
        
    url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{season_number}?api_key={current_key}&language=es-MX"
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        
        episodes = []
        for ep in data.get("episodes", []):
            episodes.append({
                "id": ep.get("id"),
                "episode_number": ep.get("episode_number"),
                "name": ep.get("name"),
                "overview": ep.get("overview"),
                "still_path": f"https://image.tmdb.org/t/p/w200{ep.get('still_path')}" if ep.get('still_path') else None,
                "air_date": ep.get("air_date")
            })
            
        return {"episodes": episodes}
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Temporada no encontrada en TMDB")
        raise HTTPException(status_code=500, detail="Error de TMDB: " + str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error obteniendo episodios: " + str(e))

class SymlinkExistsRequest(BaseModel):
    title: str
    year: str
    media_type: str
    tmdb_id: int
    original_title: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None

@app.post("/api/symlink/exists")
def check_symlink_exists(req: SymlinkExistsRequest):
    """Comprueba súper rápido si el archivo ya existe en el disco"""
    try:
        from symlinks import clean_title as clean_sym_title
        library_base = config_module.config.get("plex", {}).get("library_path", "/Media")
        use_original = config_module.config.get("plex", {}).get("use_original_titles", False)
        
        # Determinar qué título usar
        display_title = req.original_title if (use_original and req.original_title) else req.title
        
        # Consistent cleaning - must match symlinks.py logic
        clean_name = clean_sym_title(display_title)
        
        # Match symlinks.py folder construction
        if req.year and req.year != "":
            folder_name = f"{clean_name} ({req.year}) {{tmdb-{req.tmdb_id}}}"
        else:
            folder_name = f"{clean_name} {{tmdb-{req.tmdb_id}}}"
        
        sub_folder = "Movies" if req.media_type == "movie" else "Shows"
        plex_dir = os.path.join(library_base, sub_folder, folder_name)

        if req.media_type == "tv" and req.season_number is not None:
            plex_dir = os.path.join(plex_dir, f"Season {req.season_number:02d}")

        print(f"[CheckExists] Investigando: {plex_dir}")

        if os.path.isdir(plex_dir):
            if req.media_type == "tv" and req.episode_number is not None:
                from media_utils import extract_se_info
                try:
                    files = os.listdir(plex_dir)
                    for f in files:
                        f_s, f_e = extract_se_info(f)
                        if f_s == req.season_number and f_e == req.episode_number:
                            return {"exists": True}
                except: pass
                return {"exists": False}
            elif req.media_type == "movie":
                # Si la carpeta de la peli existe y tiene un video adentro, es true
                try:
                    files = os.listdir(plex_dir)
                    if any(f.lower().endswith(('.mkv', '.mp4', '.avi', '.ts', '.webm')) for f in files):
                        return {"exists": True}
                except: pass
        
        return {"exists": False}
    except Exception as e:
        print(f"Error checking symlink: {e}")
        return {"exists": False}

@app.get("/api/streams/{media_type}/{tmdb_id}")
def get_streams(media_type: str, tmdb_id: str):
    """"Obtiene los streams de AIOStreams para un TMDB ID dado"""
    current_key = config_module.config.get("tmdb", {}).get("api_key", "")
    current_aio = config_module.config.get("aiostreams", {}).get("url", "")

    if not current_aio:
        raise HTTPException(status_code=500, detail="AIOStreams URL no configurada")
        
    aiostreams_base = current_aio.rstrip('/')
    
    # Extract base TMDB ID if it's a compound ID (e.g., 60574:1:1)
    base_tmdb_id = tmdb_id.split(":")[0] if ":" in tmdb_id else tmdb_id
    
    # 1. Obtener IMDB ID de TMDB (AIOStreams / Stremio funciona mejor con IMDB IDs)
    imdb_id = None
    try:
        tmdb_url = f"https://api.themoviedb.org/3/{media_type}/{base_tmdb_id}/external_ids?api_key={current_key}"
        tmdb_r = requests.get(tmdb_url)
        if tmdb_r.status_code == 200:
            imdb_id = tmdb_r.json().get("imdb_id")
    except Exception as e:
        print(f"Error fetching IMDB ID: {e}")

    # Limpiar URL base en caso de que el usuario haya pegado un link de addon completo terminando en /manifest.json
    aiostreams_base = aiostreams_base.replace("/manifest.json", "")
    
    # Por defecto probamos con el ID de IMDB si está, sino usamos el formato tmdb:id
    # Si habia compuesto devolvemos ese compuesto o le pegamos el season:ep al imdb_id
    if ":" in tmdb_id and imdb_id:
        addon_id = imdb_id + ":" + ":".join(tmdb_id.split(":")[1:])
    else:
        addon_id = imdb_id if imdb_id else f"tmdb:{tmdb_id}"

    stremio_type = "series" if media_type == "tv" else media_type

    if "stream/" in aiostreams_base:
        # El usuario puso una URL extraña que quizás ya contiene stream/
        req_url = f"{aiostreams_base}/{stremio_type}/{addon_id}.json"
    else:
        # Añadimos /stream/media_type/addon_id.json al Stremio Addon Base URL
        req_url = f"{aiostreams_base}/stream/{stremio_type}/{addon_id}.json"
        
    try:
        r = requests.get(req_url)
        r.raise_for_status()
        data = r.json()
        # Filtros adicionales pueden aplicarse aquí si se requiere (e.g. Latino/4K)
        return {"streams": data.get("streams", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interactuando con AIOStreams: " + str(e))

@app.post("/api/download")
def download_item(req: DownloadRequest):
    """Inicia la observación del archivo"""
    job_id = f"{req.tmdb_id}_{req.season_number or 0}_{req.episode_number or 0}"
    
    # Responder inmediatamente sin verificar caché (se verifica en el Watcher)
    return initiate_download_process(req, job_id)

import threading
def initiate_download_process(req: DownloadRequest, job_id: str):
    print(f"[Download] Iniciando proceso para {job_id}: {req.title}")
    
    active_jobs[job_id] = {
        "title": req.title,
        "original_title": req.original_title,
        "media_type": req.media_type,
        "status": "Searching",
        "message": "Buscando en TorBox...",
        "season": req.season_number,
        "episode": req.episode_number,
        "req": req.dict() # Guardamos para persistencia
    }
    save_jobs()

    def on_status_update(status: str, message: str):
        if job_id in active_jobs:
            active_jobs[job_id]["status"] = status
            active_jobs[job_id]["message"] = message
            save_jobs()
            # También lo guardamos en el log detallado
            append_job_log(job_id, f"[STATUS] {status}: {message}")

    def on_found(path: str, season_number: int = None):
        on_status_update("Linking", "Creando Symlink...")
        res = create_plex_symlink(
            source_file_path=path,
            media_type=req.media_type,
            title=req.title,
            original_title=req.original_title,
            year=req.year,
            tmdb_id=req.tmdb_id,
            base_library_path=config_module.config.get("plex", {}).get("library_path", "/Media"),
            season_number=season_number,
            use_original=config_module.config.get("plex", {}).get("use_original_titles", False)
        )
        if res:
            msg = f"¡Listo! {req.title} ya está en Plex."
            if req.media_type == "tv":
                msg = f"¡Listo! {req.title} T{season_number} ya está en Plex."
            notification_queue.append(msg)
            on_status_update("Completed", "Completado")
        else:
            on_status_update("Error", "Error creando enlace")
        
        # Guardar estado final
        save_jobs()
        # Eliminar tras 60 segundos del tracker (más tiempo para que el usuario lo vea)
        threading.Timer(60.0, lambda: (active_jobs.pop(job_id, None), save_jobs())).start()
        
    # Escribir log de inicio
    append_job_log(job_id, f"Iniciando búsqueda: {req.title} ({req.year}) - {req.filename}")
    if req.season_number:
        append_job_log(job_id, f"Buscando S{req.season_number:02d}E{(req.episode_number or 0):02d}")
    
    # Iniciar Watcher en background
    start_watcher_thread(
        expected_filename=req.filename, 
        title=req.title, 
        original_title=req.original_title,
        year=req.year, 
        callback=on_found,
        season_number=req.season_number,
        episode_number=req.episode_number,
        on_status=on_status_update,
        on_log=lambda msg: append_job_log(job_id, msg),
        get_status=lambda: active_jobs.get(job_id, {}).get("status")
    )
    return {"status": "ok", "message": f"Observando descarga de {req.filename}", "job_id": job_id}

@app.delete("/api/downloads/{job_id}")
def delete_job(job_id: str):
    """Cancela y detiene un trabajo de búsqueda"""
    if job_id in active_jobs:
        active_jobs[job_id]["status"] = "Cancelled"
        save_jobs()
        # Dar tiempo al hilo para que lo lea antes de sacarlo de la lista
        threading.Timer(2.0, lambda: (active_jobs.pop(job_id, None), save_jobs())).start()
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Trabajo no encontrado")

@app.delete("/api/downloads/clear/completed")
def clear_completed_jobs():
    """Elimina todos los trabajos completados"""
    completed_ids = [job_id for job_id, job in active_jobs.items() if job.get("status") == "Completed"]
    for job_id in completed_ids:
        active_jobs.pop(job_id, None)
        job_logs.pop(job_id, None)
    save_jobs()
    return {"status": "ok", "deleted": len(completed_ids), "message": f"{len(completed_ids)} trabajos completados eliminados"}

@app.delete("/api/downloads/clear/errors")
def clear_error_jobs():
    """Elimina todos los trabajos con error o cancelados"""
    error_ids = [job_id for job_id, job in active_jobs.items() if job.get("status") in ["Error", "Cancelled"]]
    for job_id in error_ids:
        active_jobs.pop(job_id, None)
        job_logs.pop(job_id, None)
    save_jobs()
    return {"status": "ok", "deleted": len(error_ids), "message": f"{len(error_ids)} trabajos con error eliminados"}

@app.delete("/api/downloads/clear/all")
def clear_all_jobs():
    """Elimina TODOS los trabajos activos"""
    total = len(active_jobs)
    # Cancelar trabajos activos primero
    for job_id in list(active_jobs.keys()):
        if active_jobs[job_id].get("status") not in ["Completed", "Error", "Cancelled"]:
            active_jobs[job_id]["status"] = "Cancelled"
    # Esperar un momento y luego limpiar todo
    time.sleep(1)
    active_jobs.clear()
    job_logs.clear()
    save_jobs()
    return {"status": "ok", "deleted": total, "message": f"Todos los trabajos eliminados ({total})"}

@app.get("/api/jobs/{job_id}/logs")
def get_job_logs(job_id: str, since: int = 0):
    """Devuelve logs detallados de un trabajo específico desde la línea `since`."""
    logs = job_logs.get(job_id, [])
    return {"logs": logs[since:], "total": len(logs)}


@app.post("/api/downloads/{job_id}/pause")
def pause_job(job_id: str):
    """Pausa la búsqueda activa"""
    if job_id in active_jobs:
        active_jobs[job_id]["status"] = "Paused"
        save_jobs()
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Trabajo no encontrado")

@app.post("/api/downloads/{job_id}/resume")
def resume_job(job_id: str):
    """Reanuda una búsqueda pausada"""
    if job_id in active_jobs:
        # Volver al estado de búsqueda si estaba pausado o reanudando
        active_jobs[job_id]["status"] = "Searching"
        save_jobs()
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Trabajo no encontrado")

class SymlinkTestRequest(BaseModel):
    filepath: str

class DeleteSeasonRequest(BaseModel):
    media_type: str
    folder_name: str
    season_number: int

class DeleteSeriesRequest(BaseModel):
    media_type: str
    folder_name: str

class DeleteMovieRequest(BaseModel):
    folder_name: str

@app.get("/api/library")
def get_library():
    """Rastrea el directorio /Media para devolver la lista de películas y series enlazadas localmente con sus IDs."""
    import re
    base_library = config_module.config.get("plex", {}).get("library_path", "/Media")
    movies_dir = os.path.join(base_library, "Movies")
    shows_dir = os.path.join(base_library, "Shows")
    
    library = {
        "movies": [],
        "shows": []
    }
    
    def parse_folder(name: str):
        # Busca {tmdb-12345}
        match = re.search(r'\{tmdb-(\d+)\}', name)
        tmdb_id = int(match.group(1)) if match else None
        return {"name": name, "tmdb_id": tmdb_id}

    if os.path.exists(movies_dir):
        for item in os.listdir(movies_dir):
            if os.path.isdir(os.path.join(movies_dir, item)):
                library["movies"].append(parse_folder(item))
                
    if os.path.exists(shows_dir):
        for item in os.listdir(shows_dir):
            if os.path.isdir(os.path.join(shows_dir, item)):
                library["shows"].append(parse_folder(item))
                
    library["movies"].sort(key=lambda x: x["name"])
    library["shows"].sort(key=lambda x: x["name"])
    
    return library

@app.get("/api/library/structure")
def get_library_structure(media_type: str, folder_name: str):
    """Devuelve el árbol de archivos dentro de una carpeta específica."""
    base_library = config_module.config.get("plex", {}).get("library_path", "/Media")
    sub_folder = "Movies" if media_type == "movie" else "Shows"
    
    # Prevenir path traversal
    safe_folder = os.path.basename(folder_name)
    target_dir = os.path.join(base_library, sub_folder, safe_folder)
    
    if not os.path.isdir(target_dir):
        raise HTTPException(status_code=404, detail="Directorio no encontrado")
        
    tree = []
    
    for root, dirs, files in os.walk(target_dir):
        rel_path = os.path.relpath(root, target_dir)
        if rel_path == ".":
            rel_path = ""
            
        for d in dirs:
            tree.append({
                "type": "directory",
                "name": d,
                "path": os.path.join(rel_path, d).lstrip("/"),
                "full_path": os.path.join(root, d)
            })
            
        for f in files:
            full_path = os.path.join(root, f)
            # os.path.lexists check if symlink is there. exists() checks if target is reachable.
            is_valid = os.path.exists(full_path)
            is_symlink = os.path.islink(full_path)
            
            tree.append({
                "type": "file",
                "name": f,
                "path": os.path.join(rel_path, f).lstrip("/"),
                "full_path": full_path,
                "is_symlink": is_symlink,
                "is_valid": is_valid
            })
            
    # Sort: folders first, then files
    tree.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["path"]))
    return {"structure": tree}

@app.post("/api/library/test_symlink")
def test_symlink(req: SymlinkTestRequest):
    """Prueba si un symlink sigue apuntando a un archivo vivo en TorBox"""
    # exists() hace transparente el symlink. Si retorna True, el target existe.
    if os.path.lexists(req.filepath):
        is_alive = os.path.exists(req.filepath)
        return {"alive": is_alive}
    raise HTTPException(status_code=404, detail="El archivo local se borró")

@app.post("/api/library/symlink_info")
def symlink_info(req: SymlinkTestRequest):
    """Obtiene información detallada de un symlink: origen y nombre convertido"""
    if not os.path.lexists(req.filepath):
        raise HTTPException(status_code=404, detail="El archivo no existe")
    
    try:
        is_symlink = os.path.islink(req.filepath)
        symlink_name = os.path.basename(req.filepath)
        
        if is_symlink:
            # Obtener el archivo origen del symlink
            target_path = os.readlink(req.filepath)
            target_name = os.path.basename(target_path)
            is_alive = os.path.exists(req.filepath)
            
            return {
                "is_symlink": True,
                "symlink_name": symlink_name,
                "original_name": target_name,
                "target_path": target_path,
                "is_alive": is_alive,
                "symlink_full_path": req.filepath
            }
        else:
            # No es symlink, es un archivo normal
            return {
                "is_symlink": False,
                "symlink_name": symlink_name,
                "original_name": symlink_name,
                "target_path": req.filepath,
                "is_alive": True,
                "symlink_full_path": req.filepath
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo información: {str(e)}")

@app.delete("/api/library/symlink")
def delete_symlink(req: SymlinkTestRequest):
    """Elimina el symlink y limpia subcarpetas vacías para no dejar basura en Plex"""
    if not os.path.lexists(req.filepath):
        raise HTTPException(status_code=404, detail="El archivo no existe")
        
    try:
        # 1. Eliminar el archivo symlink o estático
        os.remove(req.filepath)
        
        # 2. Limpiar carpetas vacías hacia arriba (ej. Season -> Titulo (Año))
        parent_dir = os.path.dirname(req.filepath)
        for _ in range(2): # Intenta limpiar hasta 2 niveles (Season, Titulo)
            try:
                if not os.listdir(parent_dir): # Si la carpeta está vacía
                    os.rmdir(parent_dir)
                    parent_dir = os.path.dirname(parent_dir) # Subimos al nivel superior
                else:
                    break # Detener si hay otros archivos
            except Exception:
                break
                
        return {"status": "ok", "message": "Archivo eliminado correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/library/delete-season")
def delete_season(req: DeleteSeasonRequest):
    """Elimina todos los archivos de una temporada completa"""
    base_library = config_module.config.get("plex", {}).get("library_path", "/Media")
    
    if req.media_type != "tv":
        raise HTTPException(status_code=400, detail="Solo se pueden borrar temporadas de series")
    
    safe_folder = os.path.basename(req.folder_name)
    season_dir = os.path.join(base_library, "Shows", safe_folder, f"Season {req.season_number:02d}")
    
    if not os.path.isdir(season_dir):
        raise HTTPException(status_code=404, detail="La temporada no existe")
    
    try:
        import shutil
        # Borrar todo el directorio de la temporada
        shutil.rmtree(season_dir)
        print(f"[Library] Temporada {req.season_number:02d} de {req.folder_name} eliminada completamente")
        return {"status": "ok", "message": f"Temporada {req.season_number:02d} eliminada correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando temporada: {str(e)}")

@app.post("/api/library/delete-entire-series")
def delete_entire_series(req: DeleteSeriesRequest):
    """Elimina todos los archivos de una serie completa (incluido el directorio base)"""
    base_library = config_module.config.get("plex", {}).get("library_path", "/Media")
    
    if req.media_type != "tv":
        raise HTTPException(status_code=400, detail="Solo se pueden borrar series")
    
    safe_folder = os.path.basename(req.folder_name)
    series_dir = os.path.join(base_library, "Shows", safe_folder)
    
    if not os.path.isdir(series_dir):
        raise HTTPException(status_code=404, detail="La serie no existe")
    
    try:
        import shutil
        # Borrar todo el directorio de la serie
        shutil.rmtree(series_dir)
        print(f"[Library] Serie {req.folder_name} eliminada completamente")
        return {"status": "ok", "message": f"Serie {req.folder_name} eliminada correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando serie: {str(e)}")

@app.post("/api/library/delete-entire-movie")
def delete_entire_movie(req: DeleteMovieRequest):
    """Elimina todos los archivos de una película"""
    base_library = config_module.config.get("plex", {}).get("library_path", "/Media")
    
    safe_folder = os.path.basename(req.folder_name)
    movie_dir = os.path.join(base_library, "Movies", safe_folder)
    
    if not os.path.isdir(movie_dir):
        raise HTTPException(status_code=404, detail="La película no existe")
    
    try:
        import shutil
        # Borrar todo el directorio de la película
        shutil.rmtree(movie_dir)
        print(f"[Library] Película {req.folder_name} eliminada completamente")
        return {"status": "ok", "message": f"Película {req.folder_name} eliminada correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando película: {str(e)}")

# ============ SYSTEM RESET ENDPOINTS ============

@app.delete("/api/library/clear-all")
def clear_entire_library():
    """⚠️ OPERACIÓN DESTRUCTIVA: Elimina TODA la biblioteca de Plex"""
    base_library = config_module.config.get("plex", {}).get("library_path", "/Media")
    
    try:
        import shutil
        
        # Eliminar Movies y Shows sin tocar la carpeta /Media misma
        for subfolder in ["Movies", "Shows"]:
            subfolder_path = os.path.join(base_library, subfolder)
            if os.path.isdir(subfolder_path):
                shutil.rmtree(subfolder_path)
                os.makedirs(subfolder_path, exist_ok=True)  # Recrear carpeta vacía
                print(f"[Library] {subfolder} eliminado completamente")
        
        print("[Library] ⚠️ TODA LA BIBLIOTECA HA SIDO ELIMINADA")
        return {"status": "ok", "message": "Biblioteca completamente limpiada"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error limpiando biblioteca: {str(e)}")

@app.post("/api/system/reset-vfs")
async def reset_vfs():
    """Reinicia el mount del VFS custom sin reiniciar el backend."""
    try:
        from vfs_manager import shutdown_vfs, startup_vfs

        print("[System] Iniciando reset de VFS...")
        await shutdown_vfs()
        await asyncio.sleep(1)
        started = await startup_vfs()

        if started:
            print("[System] ✓ VFS reiniciado")
            return {
                "status": "ok",
                "message": "VFS reiniciado correctamente"
            }

        return {
            "status": "warning",
            "message": "VFS no pudo iniciarse (revisa credenciales/dependencias)"
        }
    except Exception as e:
        print(f"[System] ✗ Error en reset de VFS: {e}")
        raise HTTPException(status_code=500, detail=f"Error reseteando VFS: {str(e)}")

@app.post("/api/system/reset-plex")
def reset_plex():
    """Reinicia el contenedor de Plex."""
    try:
        client = docker.from_env()
        container = client.containers.get("plex")
        
        print("[System] Reiniciando contenedor Plex...")
        container.restart()
        print("[System] ✓ Contenedor Plex reiniciado")
        
        return {
            "status": "ok",
            "message": "Contenedor Plex reiniciado exitosamente"
        }
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="Contenedor Plex no encontrado")
    except Exception as e:
        print(f"[System] ✗ Error reiniciando Plex: {e}")
        raise HTTPException(status_code=500, detail=f"Error reiniciando Plex: {str(e)}")

@app.post("/api/system/reset-all")
async def reset_all():
    """Reinicia VFS y Plex."""
    try:
        print("[System] Iniciando reset completo del sistema...")
        results = []
        
        # 1. Reset VFS
        try:
            from vfs_manager import shutdown_vfs, startup_vfs
            await shutdown_vfs()
            await asyncio.sleep(1)
            started = await startup_vfs()

            if started:
                results.append("✓ VFS reiniciado")
                print("[System] ✓ VFS reiniciado")
            else:
                results.append("⚠️ VFS no inició (revisar configuración)")
                print("[System] ⚠️ VFS no inició")
        except Exception as e:
            results.append(f"⚠️ Error VFS: {str(e)}")
            print(f"[System] ⚠️ Error reseteando VFS: {e}")
        
        # 2. Reset Plex
        try:
            client = docker.from_env()
            container = client.containers.get("plex")
            container.restart()
            results.append("✓ Plex reiniciado")
            print("[System] ✓ Plex reiniciado")
        except Exception as e:
            results.append(f"⚠️ Error Plex: {str(e)}")
            print(f"[System] ⚠️ Error reiniciando Plex: {e}")
        
        return {
            "status": "ok",
            "message": "Reset completo del sistema completado",
            "results": results
        }
    except Exception as e:
        print(f"[System] ✗ Error en reset total: {e}")
        raise HTTPException(status_code=500, detail=f"Error en reset total: {str(e)}")

@app.get("/api/notifications")
def get_notifications():
    """Retorna y limpia la cola de avisos pendientes para el frontend"""
    global notification_queue
    msgs = list(notification_queue)
    notification_queue.clear()
    return {"messages": msgs}

@app.get("/api/downloads/active")
def get_active_downloads():
    """Retorna los trabajos de descarga/symlink en curso"""
    return active_jobs

@app.post("/api/torbox/check-cache")
def api_check_cache(req: CacheCheckRequest):
    """Verifica si un archivo ya existe en TorBox"""
    from watcher import check_file_exists
    path = check_file_exists(req.filename, req.title)
    return {"cached": path is not None, "path": path}
@app.get("/api/torbox/list")
def list_torbox_dir(path: str = "/"):
    """Lista el contenido de una carpeta en el montaje de torbox"""
    base = "/mnt/torbox"
    # Evitar path traversal básico
    safe_path = os.path.normpath(os.path.join(base, path.lstrip("/")))
    if not safe_path.startswith(base):
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    if not os.path.exists(safe_path):
        return {"items": [], "error": "Ruta no encontrada"}
        
    items = []
    is_root_level = safe_path == base
    
    try:
        for entry in os.scandir(safe_path):
            # El VFS de TorBox muestra directorios fantasma con permisos d?????????
            # Filtrar elementos inaccesibles intentando hacer stat
            try:
                # Verificar que el archivo/directorio realmente existe
                if not os.path.exists(entry.path):
                    logger.debug(f"[VFS] Skipping non-existent entry: {entry.name}")
                    continue
                
                stat_info = entry.stat()
                is_dir = entry.is_dir()
                
                # Bug del VFS: dentro de carpetas, archivos grandes son reportados como directorios
                # Solo aplicar esta corrección en subdirectorios, no en el root
                if not is_root_level and is_dir and stat_info.st_size > 10_000_000:  # > 10MB
                    is_dir = False
                
                items.append({
                    "name": entry.name,
                    "is_dir": is_dir,
                    "path": os.path.relpath(entry.path, base),
                    "size": stat_info.st_size
                })
            except (PermissionError, OSError) as stat_err:
                # Elemento inaccesible (d?????????), ignorar
                logger.debug(f"[VFS] Skipping inaccessible entry: {entry.name}")
                continue
                
    except Exception as e:
        logger.warning(f"[VFS] Error listing {safe_path}: {e}")
        return {"items": [], "error": str(e)}

        
    # Ordenar: carpetas primero
    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
    return {"items": items}

@app.post("/api/library/manual-link")
def manual_link(req: ManualLinkRequest):
    """Vincula manualmente un archivo de TorBox a Plex"""
    base = "/mnt/torbox"
    full_source_path = os.path.join(base, req.path.lstrip("/"))
    
    if not os.path.exists(full_source_path):
        raise HTTPException(status_code=404, detail="Archivo fuente no encontrado")
        
    use_original = config_module.config.get("plex", {}).get("use_original_titles", False)

    original_title = req.original_title
    if use_original and not original_title and req.tmdb_id and req.media_type in ["movie", "tv"]:
        try:
            current_key = config_module.config.get("tmdb", {}).get("api_key", "")
            if current_key:
                tmdb_url = f"https://api.themoviedb.org/3/{req.media_type}/{req.tmdb_id}?api_key={current_key}&language=es-MX"
                tmdb_r = requests.get(tmdb_url, timeout=10)
                if tmdb_r.status_code == 200:
                    tmdb_data = tmdb_r.json()
                    original_title = tmdb_data.get("original_title") or tmdb_data.get("original_name")
                    if original_title:
                        print(f"[ManualLink] Original title recuperado desde TMDB: {original_title}")
        except Exception as e:
            print(f"[ManualLink] No se pudo recuperar original_title desde TMDB: {e}")

    print(f"[ManualLink] use_original_titles={use_original} | title='{req.title}' | original_title='{original_title}'")

    res = create_plex_symlink(
        source_file_path=full_source_path,
        media_type=req.media_type,
        title=req.title,
        original_title=original_title,
        year=req.year,
        tmdb_id=req.tmdb_id,
        base_library_path=config_module.config.get("plex", {}).get("library_path", "/Media"),
        season_number=req.season_number,
        use_original=use_original
    )
    
    if res:
        # Si logramos el link, marcar el trabajo como completado si existe el job_id
        if req.job_id and req.job_id in active_jobs:
            active_jobs[req.job_id]["status"] = "Completed"
            active_jobs[req.job_id]["message"] = "Vínculo manual completado."
            save_jobs()
            # Programar eliminación del tracker
            threading.Timer(30.0, lambda: (active_jobs.pop(req.job_id, None), save_jobs())).start()
            
        return {"status": "ok", "message": "Vínculo manual creado con éxito", "path": res}
    else:
        raise HTTPException(status_code=500, detail="Error creando el symlink")
