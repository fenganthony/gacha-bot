import asyncio
import json
import os
import shutil
import discord
from discord import app_commands
from discord.ext import commands
from aiohttp import web
import database as db
import guild_config as gc
from dashboard import create_app
from paths import CONFIG_PATH


def load_bot_token() -> str:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["bot_token"]


class GachaCommandTree(app_commands.CommandTree):
    """Command tree that enforces the per-user '抽獎權限' (bot access) switch.

    A disabled user is blocked from every slash command. Server administrators
    always bypass the block so they can never lock themselves out via the dashboard.
    """

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        gid = interaction.guild_id
        if gid is None:
            return True  # DMs / no guild context — nothing to gate
        user = interaction.user
        if isinstance(user, discord.Member) and user.guild_permissions.administrator:
            return True
        enabled = await asyncio.to_thread(db.is_user_enabled, str(gid), str(user.id))
        if not enabled:
            msg = "🚫 你已被管理員停用，無法使用機器人相關指令，請聯絡管理員。"
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
            except discord.HTTPException:
                pass
            return False
        return True

    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # A blocked user already got a message in interaction_check; stay quiet.
        if isinstance(error, app_commands.CheckFailure):
            return
        await super().on_error(interaction, error)


class GachaBot(commands.Bot):
    def __init__(self, bot_token: str):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents, tree_cls=GachaCommandTree)
        self.bot_token_str = bot_token
        self.guild_configs: dict[str, dict] = {}

    def get_guild_config(self, guild_id: str) -> dict:
        return self.guild_configs.get(guild_id, gc.default_guild_config())

    async def setup_hook(self):
        self.guild_configs = gc.load_all_guild_configs()
        await self.load_extension("cogs.gacha")
        await self.load_extension("cogs.admin")

    async def on_ready(self):
        _migrate_legacy_config(self)
        # Register any guilds we're in that aren't registered yet
        for guild in self.guilds:
            gid = str(guild.id)
            if gid not in self.guild_configs:
                cfg = gc.register_guild(gid, guild.name)
                self.guild_configs[gid] = cfg
            else:
                gc.update_guild_name(gid, guild.name)
        # Safety net: always reassign any orphaned 'legacy' data to first guild
        if self.guilds:
            db.reassign_legacy_data(str(self.guilds[0].id))
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        print(f"✅ {self.user} 已上線！")
        print(f"   伺服器數量：{len(self.guilds)}")
        print(f"   已同步 {len(self.tree.get_commands())} 個指令")
        await self.change_presence(activity=discord.Game(name="🎰 扭蛋機"))

    async def on_guild_join(self, guild):
        gid = str(guild.id)
        if gid not in self.guild_configs:
            cfg = gc.register_guild(gid, guild.name)
            self.guild_configs[gid] = cfg
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print(f"📥 已加入伺服器：{guild.name} ({guild.id})")

    async def on_guild_remove(self, guild):
        print(f"📤 已離開伺服器：{guild.name} ({guild.id})")


def _migrate_legacy_config(bot: GachaBot):
    """One-time migration from single-guild config to multi-guild layout."""
    registry = gc.load_registry()
    if registry:
        return  # Already migrated

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        old_config = json.load(f)

    # Check if old config has guild-level keys (legacy format)
    if "energy" not in old_config:
        return  # Already new format (bot_token only)

    if not bot.guilds:
        return

    first_guild = bot.guilds[0]
    gid = str(first_guild.id)

    # Extract guild-level config
    guild_cfg = {k: old_config[k] for k in gc.GUILD_KEYS if k in old_config}
    gc.register_guild(gid, first_guild.name)
    gc.save_guild_config(gid, guild_cfg)
    bot.guild_configs[gid] = guild_cfg

    # Reassign legacy db rows
    db.reassign_legacy_data(gid)

    # Backup then rewrite config.json to bot-token only
    backup = CONFIG_PATH.with_suffix(".pre-migration.json")
    shutil.copy2(CONFIG_PATH, backup)
    print(f"📋 舊設定備份至：{backup}")
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"bot_token": old_config["bot_token"]}, f, ensure_ascii=False, indent=2)

    print(f"📦 已將舊設定遷移至伺服器：{first_guild.name}")


async def main():
    bot_token = load_bot_token()
    db.init_db()

    bot = GachaBot(bot_token)

    # Start dashboard web server
    dashboard = create_app(bot)
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(dashboard)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Dashboard running at http://localhost:{port}")

    # Start Discord bot
    async with bot:
        await bot.start(bot.bot_token_str)


if __name__ == "__main__":
    asyncio.run(main())
