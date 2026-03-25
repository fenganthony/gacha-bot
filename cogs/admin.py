import asyncio
import json
import time
import discord
from discord import app_commands
from discord.ext import commands
from pathlib import Path
import database as db

CONFIG_PATH = Path(__file__).parent.parent / "config.json"


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config

    def save_config(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    admin_group = app_commands.Group(name="設定", description="管理員設定指令")

    @admin_group.command(name="精力上限", description="設定精力上限")
    @app_commands.describe(amount="精力上限數值")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_max_energy(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        self.config["energy"]["max_amount"] = amount
        self.save_config()
        await interaction.followup.send(f"✅ 精力上限已設為 **{amount}**")

    @admin_group.command(name="每日精力", description="設定每日獲得精力")
    @app_commands.describe(amount="每日精力數值")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_daily_energy(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        self.config["energy"]["daily_amount"] = amount
        self.save_config()
        await interaction.followup.send(f"✅ 每日精力已設為 **{amount}**")

    @admin_group.command(name="扭蛋費用", description="設定扭蛋所需代幣")
    @app_commands.describe(amount="代幣數值")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_gacha_cost(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        self.config["tokens"]["gacha_cost"] = amount
        self.save_config()
        await interaction.followup.send(f"✅ 扭蛋費用已設為 **{amount}** 代幣")

    @admin_group.command(name="簽到獎勵", description="設定簽到代幣獎勵")
    @app_commands.describe(amount="代幣數值")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_checkin_reward(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        self.config["tokens"]["checkin_reward"] = amount
        self.save_config()
        await interaction.followup.send(f"✅ 簽到獎勵已設為 **{amount}** 代幣")

    @admin_group.command(name="簽到冷卻", description="設定簽到重置時間（小時）")
    @app_commands.describe(hours="小時數")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_checkin_cooldown(self, interaction: discord.Interaction, hours: int):
        await interaction.response.defer()
        self.config["tokens"]["checkin_reset_hours"] = hours
        self.save_config()
        await interaction.followup.send(f"✅ 簽到冷卻已設為 **{hours}** 小時")

    @admin_group.command(name="新增打工", description="新增打工地點")
    @app_commands.describe(name="地點名稱", hours="工時（小時）", energy="所需精力", reward="代幣報酬")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_work(self, interaction: discord.Interaction, name: str, hours: int, energy: int, reward: int):
        await interaction.response.defer()
        self.config["work"].append({
            "name": name,
            "duration_hours": hours,
            "energy_cost": energy,
            "token_reward": reward,
        })
        self.save_config()
        await interaction.followup.send(f"✅ 已新增打工地點：**{name}**（⏱{hours}h ⚡-{energy} 🪙+{reward}）")

    @admin_group.command(name="刪除打工", description="刪除打工地點")
    @app_commands.describe(name="地點名稱")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_work(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        before = len(self.config["work"])
        self.config["work"] = [w for w in self.config["work"] if w["name"] != name]
        if len(self.config["work"]) == before:
            await interaction.followup.send(f"❌ 找不到打工地點：**{name}**")
            return
        self.save_config()
        await interaction.followup.send(f"✅ 已刪除打工地點：**{name}**")

    @admin_group.command(name="新增獎品", description="新增扭蛋獎品（秘藏需設定權重）")
    @app_commands.describe(name="獎品名稱", rarity="稀有度 (N/R/SR/SSR/秘藏)", weight="權重（僅秘藏需要填寫）")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_prize(self, interaction: discord.Interaction, name: str, rarity: str, weight: int = None):
        await interaction.response.defer()
        valid = ("N", "R", "SR", "SSR", "秘藏")
        if rarity.upper() not in valid and rarity not in valid:
            await interaction.followup.send("❌ 稀有度必須是 N、R、SR、SSR 或 秘藏")
            return
        r = rarity if rarity == "秘藏" else rarity.upper()
        if r == "秘藏" and weight is None:
            await interaction.followup.send("❌ 秘藏獎品必須設定權重")
            return
        item = {"name": name, "rarity": r}
        if r == "秘藏":
            item["weight"] = weight
        self.config["gacha_pool"].append(item)
        self.save_config()
        msg = f"✅ 已新增獎品：`{r}` **{name}**"
        if r == "秘藏":
            msg += f"（權重 {weight}）"
        await interaction.followup.send(msg)

    @admin_group.command(name="稀有度權重", description="設定 N/R/SR/SSR 的統一權重")
    @app_commands.describe(rarity="稀有度 (N/R/SR/SSR)", weight="權重數值")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_rarity_weight(self, interaction: discord.Interaction, rarity: str, weight: int):
        await interaction.response.defer()
        r = rarity.upper()
        if r not in ("N", "R", "SR", "SSR"):
            await interaction.followup.send("❌ 只能設定 N、R、SR、SSR 的權重（秘藏請用 新增獎品 時設定）")
            return
        self.config["rarity_weights"][r] = weight
        self.save_config()
        rw = self.config["rarity_weights"]
        lines = " / ".join(f"{k}={v}" for k, v in rw.items())
        await interaction.followup.send(f"✅ `{r}` 權重已設為 **{weight}**\n目前權重：{lines}")

    @admin_group.command(name="刪除獎品", description="刪除扭蛋獎品")
    @app_commands.describe(name="獎品名稱")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_prize(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        before = len(self.config["gacha_pool"])
        self.config["gacha_pool"] = [p for p in self.config["gacha_pool"] if p["name"] != name]
        if len(self.config["gacha_pool"]) == before:
            await interaction.followup.send(f"❌ 找不到獎品：**{name}**")
            return
        self.save_config()
        await interaction.followup.send(f"✅ 已刪除獎品：**{name}**")

    @admin_group.command(name="管理角色", description="設定可使用管理指令的角色")
    @app_commands.describe(role="伺服器角色")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_admin_role(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer()
        self.config["admin_role"] = str(role.id)
        self.save_config()
        await interaction.followup.send(f"✅ 管理角色已設為 **{role.name}**")

    @app_commands.command(name="查看玩家", description="查看指定玩家的狀態（需要管理角色）")
    @app_commands.describe(member="要查看的玩家")
    async def view_player(self, interaction: discord.Interaction, member: discord.Member):
        admin_role_id = self.config.get("admin_role", "")
        has_admin_role = any(str(r.id) == admin_role_id for r in interaction.user.roles) if admin_role_id else False
        is_admin = interaction.user.guild_permissions.administrator
        if not has_admin_role and not is_admin:
            await interaction.response.send_message("❌ 你沒有權限使用此指令（需要管理角色）", ephemeral=True)
            return

        await interaction.response.defer()
        status = await asyncio.to_thread(db.get_status, str(member.id), self.config)
        embed = discord.Embed(title=f"📊 {member.display_name} 的狀態", color=0x1ABC9C)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="⚡ 精力", value=f"{status['energy']} / {status['max_energy']}", inline=True)
        embed.add_field(name="🪙 代幣", value=str(status["tokens"]), inline=True)
        if status["working"]:
            remaining = status["working"]["end_time"] - time.time()
            minutes = max(0, int(remaining // 60))
            embed.add_field(
                name="💼 打工中",
                value=f"{status['working']['work_name']}（剩餘 {minutes} 分鐘）",
                inline=False,
            )
        if status["uncollected"]:
            embed.add_field(
                name="💰 待領取",
                value=f"{status['uncollected']['work_name']} — 🪙 {status['uncollected']['token_reward']} 代幣",
                inline=False,
            )
        items = await asyncio.to_thread(db.get_inventory, str(member.id))
        if items:
            lines = [f"`{item['rarity']}` {item['item_name']} ×{item['count']}" for item in items]
            embed.add_field(name="🎒 背包", value="\n".join(lines), inline=False)
        await interaction.followup.send(embed=embed)

    @admin_group.command(name="查看", description="查看目前所有設定")
    @app_commands.checks.has_permissions(administrator=True)
    async def view_config(self, interaction: discord.Interaction):
        await interaction.response.defer()
        c = self.config
        work_lines = "\n".join(
            f"  • **{w['name']}** — ⏱{w['duration_hours']}h ⚡-{w['energy_cost']} 🪙+{w['token_reward']}"
            for w in c["work"]
        ) or "  （無）"
        items_with_prob = db.calc_item_probabilities(c)
        prize_lines = "\n".join(
            f"  • `{p['rarity']}` **{p['name']}** — {p['probability']*100:.2f}%"
            + (f"（權重 {p.get('weight', '')}）" if p["rarity"] == "秘藏" else "")
            for p in items_with_prob
        ) or "  （無）"
        embed = discord.Embed(title="⚙️ 目前設定", color=0x9B59B6)
        embed.add_field(
            name="精力",
            value=f"每日：{c['energy']['daily_amount']}\n上限：{c['energy']['max_amount']}",
            inline=True,
        )
        embed.add_field(
            name="代幣",
            value=f"扭蛋費用：{c['tokens']['gacha_cost']}\n簽到獎勵：{c['tokens']['checkin_reward']}\n簽到冷卻：{c['tokens']['checkin_reset_hours']}h",
            inline=True,
        )
        rw = c["rarity_weights"]
        rw_lines = " / ".join(f"{k}={v}" for k, v in rw.items())
        embed.add_field(name="稀有度權重", value=rw_lines, inline=False)
        embed.add_field(name="打工地點", value=work_lines, inline=False)
        embed.add_field(name="獎品池", value=prize_lines, inline=False)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
