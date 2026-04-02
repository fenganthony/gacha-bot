"""Generate config.json with bot_token only. Guild configs are created at runtime."""
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
    config = {"bot_token": os.environ.get("BOT_TOKEN", "YOUR_DISCORD_BOT_TOKEN")}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"Config saved to {CONFIG_PATH}")


if __name__ == "__main__":
    main()
