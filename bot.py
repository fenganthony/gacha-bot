import asyncio
import json
import os
import discord
from discord.ext import commands
from aiohttp import web
from pathlib import Path
import database as db
from dashboard import create_app

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class GachaBot(commands.Bot):
    def __init__(self, config: dict):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.config = config

    async def setup_hook(self):
        await self.load_extension("cogs.gacha")
        await self.load_extension("cogs.admin")

    async def on_ready(self):
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        print(f"✅ {self.user} 已上線！")
        print(f"   伺服器數量：{len(self.guilds)}")
        print(f"   已同步 {len(self.tree.get_commands())} 個指令")
        await self.change_presence(activity=discord.Game(name="🎰 扭蛋機"))


async def main():
    config = load_config()
    db.init_db()

    # Start dashboard web server
    dashboard = create_app(config)
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(dashboard)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Dashboard running at http://localhost:{port}")

    # Start Discord bot
    bot = GachaBot(config)
    async with bot:
        await bot.start(config["bot_token"])


if __name__ == "__main__":
    asyncio.run(main())
