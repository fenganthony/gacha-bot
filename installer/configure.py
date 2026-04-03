"""Generate config.json with bot_token only. Guild configs are created at runtime.

On upgrade: preserves existing config.json, only updates bot_token if provided.
"""
import json
import os
import sys

app_dir = os.path.dirname(os.path.abspath(__file__))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from paths import CONFIG_PATH, DATA_DIR


def load_env():
    env_path = os.path.join(app_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())


def main():
    load_env()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    bot_token = os.environ.get("BOT_TOKEN", "")

    if CONFIG_PATH.exists():
        # Upgrade: preserve existing config, only update bot_token if provided
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        if bot_token:
            config["bot_token"] = bot_token
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"Config updated (preserved existing settings)")
    else:
        # Fresh install: create minimal config
        config = {"bot_token": bot_token or "YOUR_DISCORD_BOT_TOKEN"}
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"Config created at {CONFIG_PATH}")


if __name__ == "__main__":
    main()
