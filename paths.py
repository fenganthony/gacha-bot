"""Centralized path configuration.

Writable data (config.json, gacha.db, presets/) goes to DATA_DIR.
Read-only app files (static/, cogs/) stay in APP_DIR.

DATA_DIR resolution order:
  1. DATA_DIR environment variable
  2. %APPDATA%/GachaBot  (Windows default)
  3. Fallback to APP_DIR (dev / non-Windows)
"""
import os
from pathlib import Path

APP_DIR = Path(__file__).parent

_data = os.environ.get("DATA_DIR", "")
if _data:
    DATA_DIR = Path(_data)
elif os.name == "nt":
    DATA_DIR = Path(os.environ.get("APPDATA", "")) / "GachaBot"
else:
    DATA_DIR = APP_DIR

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = DATA_DIR / "config.json"
EXAMPLE_CONFIG_PATH = APP_DIR / "config.example.json"
DB_PATH = DATA_DIR / "gacha.db"
PRESETS_PATH = DATA_DIR / "presets"
STATIC_PATH = APP_DIR / "static"
