import os
import yaml

def load_config():
    config_path = os.getenv("CONFIG_PATH", "config.yaml")
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

config = load_config()

def reload_config():
    global config
    config = load_config()
