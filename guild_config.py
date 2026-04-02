"""Per-guild configuration management.

Each guild gets its own config file at GUILDS_DIR/{guild_id}/config.json.
A registry file (guilds.json) tracks known guilds.
"""
import json
import copy
import time
import shutil
from pathlib import Path
from paths import GUILDS_DIR, GUILDS_REGISTRY, EXAMPLE_CONFIG_PATH

# Keys that belong to guild config (everything except bot_token)
GUILD_KEYS = (
    "energy", "work", "tokens", "channel_limits", "admin_role",
    "rarity_weights", "gacha_pool", "adventures", "redeem", "activity",
)


def load_registry() -> dict:
    """Returns {guild_id: {name, joined_at}} mapping."""
    if GUILDS_REGISTRY.exists():
        with open(GUILDS_REGISTRY, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_registry(registry: dict):
    GUILDS_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    with open(GUILDS_REGISTRY, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def default_guild_config() -> dict:
    """Load guild-level defaults from config.example.json."""
    with open(EXAMPLE_CONFIG_PATH, "r", encoding="utf-8") as f:
        full = json.load(f)
    return {k: copy.deepcopy(full[k]) for k in GUILD_KEYS if k in full}


def guild_config_path(guild_id: str) -> Path:
    return GUILDS_DIR / guild_id / "config.json"


def guild_presets_path(guild_id: str) -> Path:
    return GUILDS_DIR / guild_id / "presets"


def load_guild_config(guild_id: str) -> dict:
    path = guild_config_path(guild_id)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default_guild_config()


def save_guild_config(guild_id: str, config: dict):
    d = GUILDS_DIR / guild_id
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_all_guild_configs() -> dict[str, dict]:
    """Load configs for all registered guilds. Returns {guild_id: config}."""
    registry = load_registry()
    return {gid: load_guild_config(gid) for gid in registry}


def register_guild(guild_id: str, guild_name: str) -> dict:
    """Register a new guild, create default config if needed, return the config."""
    registry = load_registry()
    if guild_id not in registry:
        registry[guild_id] = {
            "name": guild_name,
            "joined_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        save_registry(registry)
    cfg = load_guild_config(guild_id)
    save_guild_config(guild_id, cfg)
    return cfg


def update_guild_name(guild_id: str, guild_name: str):
    """Update the display name for a registered guild."""
    registry = load_registry()
    if guild_id in registry:
        registry[guild_id]["name"] = guild_name
        save_registry(registry)


def unregister_guild(guild_id: str, delete_data: bool = False):
    """Remove a guild from the registry. Optionally delete its config files."""
    registry = load_registry()
    registry.pop(guild_id, None)
    save_registry(registry)
    if delete_data:
        d = GUILDS_DIR / guild_id
        if d.exists():
            shutil.rmtree(d)
