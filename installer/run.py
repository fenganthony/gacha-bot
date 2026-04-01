"""Wrapper to ensure sys.path includes the app directory before importing bot."""
import sys
import os

# Fix Windows console encoding for emoji/CJK characters
if sys.platform == "win32":
    os.system("")  # enable VT100 escape sequences
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add the app directory to sys.path
app_dir = os.path.dirname(os.path.abspath(__file__))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Load .env into os.environ (must happen before importing paths)
env_path = os.path.join(app_dir, ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

# Now import paths (uses DATA_DIR env var)
from paths import CONFIG_PATH, DATA_DIR

print(f"📂 Data directory: {DATA_DIR}")

# Generate config.json if missing
if not CONFIG_PATH.exists():
    import configure
    configure.main()

# Run the bot
import bot
import asyncio
asyncio.run(bot.main())
