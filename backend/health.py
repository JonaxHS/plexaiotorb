import os
import threading
import time

def check_symlinks_health(base_library_path: str = "/Media"):
    """"
    Revisa recursivamente los symlinks en el directorio de Plex para asegurar
    que sus archivos fuente en /mnt/torbox (o donde sea) aún existan.
    """
    print("Iniciando revisión de salud de symlinks (Health Check)...")
    if not os.path.exists(base_library_path):
        print(f"Directorio base {base_library_path} no existe aún.")
        return

    broken_links = 0
    total_links = 0

    for root, dirs, files in os.walk(base_library_path):
        for file in files:
            path = os.path.join(root, file)
            if os.path.islink(path):
                total_links += 1
                target = os.readlink(path)
                if not os.path.exists(target):
                    print(f"[ALERTA] Symlink roto detectado: {path} -> {target}")
                    broken_links += 1
                    # Dependiendo de la lógica, aquí podríamos borrar el symlink roto:
                    # os.remove(path)

    print(f"Health Check finalizado. {total_links} symlinks revisados. {broken_links} rotos.")

def start_health_monitor(interval_seconds: int = 3600, base_library_path: str = "/Media"):
    """"
    Ejecuta el chequeo periódicamente en un hilo en background.
    """
    def run_monitor():
        while True:
            time.sleep(interval_seconds)
            check_symlinks_health(base_library_path)
            
    thread = threading.Thread(target=run_monitor, daemon=True)
    thread.start()
    return thread
