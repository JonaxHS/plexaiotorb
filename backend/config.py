import os
import yaml

def load_config():
    config_path = os.getenv("CONFIG_PATH", "config.yaml")
    if not os.path.exists(config_path):
        print(f"[Config] Warning: {config_path} not found.")
        return {}
    if os.path.isdir(config_path):
        print(f"[Config] Error: {config_path} is a directory, expected a file.")
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[Config] Error loading {config_path}: {e}")
        return {}

config = load_config()

def reload_config():
    global config
    config = load_config()
