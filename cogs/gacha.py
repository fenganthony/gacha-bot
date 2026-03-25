import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import time
import database as db


def _label(config):
    return db._token_label(config)

def _col(config):
    return db._token_col(config)


class Gacha(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config

    @app_commands.command(name="簽到", description="每日簽到領取代幣")
    async def checkin(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        success, msg = await asyncio.to_thread(db.checkin, str(interaction.user.id), self.config)
        color = 0x2ECC71 if success else 0xE74C3C
        embed = discord.Embed(title="📋 每日簽到", description=msg, color=color)
        if success:
            user = await asyncio.to_thread(db.get_user, str(interaction.user.id), self.config)
            embed.add_field(name=f"目前{_label(self.config)}", value=f"🪙 {user[_col(self.config)]}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="打工", description="選擇打工地點賺取代幣")
    async def work(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        work_list = self.config["work"]
        label = _label(self.config)
        if len(work_list) == 1:
            success, msg = await asyncio.to_thread(db.start_work, str(interaction.user.id), work_list[0], self.config)
            color = 0x3498DB if success else 0xE74C3C
            embed = discord.Embed(title="💼 打工", description=msg, color=color)
            await interaction.followup.send(embed=embed)
            return

        view = WorkSelectView(self.config, interaction.user.id)
        embed = discord.Embed(
            title="💼 選擇打工地點",
            description="\n".join(
                f"**{w['name']}** — ⏱ {w['duration_hours']}小時 | ⚡ -{w['energy_cost']}精力 | 🪙 +{w['token_reward']}{label}"
                for w in work_list
            ),
            color=0x3498DB,
        )
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="領取", description="領取打工報酬")
    async def collect(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        success, msg = await asyncio.to_thread(db.collect_work, str(interaction.user.id), self.config)
        color = 0x2ECC71 if success else 0xE74C3C
        embed = discord.Embed(title="💰 領取報酬", description=msg, color=color)
        if success:
            user = await asyncio.to_thread(db.get_user, str(interaction.user.id), self.config)
            embed.add_field(name=f"目前{_label(self.config)}", value=f"🪙 {user[_col(self.config)]}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="扭蛋", description="花費代幣抽扭蛋")
    async def gacha(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        success, msg, prize = await asyncio.to_thread(db.do_gacha, str(interaction.user.id), self.config)
        if not success:
            embed = discord.Embed(title="🎰 扭蛋機", description=msg, color=0xE74C3C)
            await interaction.followup.send(embed=embed)
            return

        rarity_colors = {"N": 0x95A5A6, "R": 0x3498DB, "SR": 0x9B59B6, "SSR": 0xF1C40F, "秘藏": 0xE74C3C}
        color = rarity_colors.get(prize["rarity"], 0xFFFFFF)
        embed = discord.Embed(
            title="🎰 扭蛋機",
            description=f"{msg}\n\n🎉 恭喜獲得：\n# {prize['name']}\n`{prize['rarity']}`",
            color=color,
        )
        user = await asyncio.to_thread(db.get_user, str(interaction.user.id), self.config)
        embed.add_field(name=f"剩餘{_label(self.config)}", value=f"🪙 {user[_col(self.config)]}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="狀態", description="查看你的精力、代幣與打工狀態")
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        status = await asyncio.to_thread(db.get_status, str(interaction.user.id), self.config)
        embed = discord.Embed(title=f"📊 {interaction.user.display_name} 的狀態", color=0x1ABC9C)
        embed.add_field(name="⚡ 精力", value=f"{status['energy']} / {status['max_energy']}", inline=True)
        embed.add_field(name="🪙 代幣", value=str(status["tokens"]), inline=True)
        if status.get("activity_active"):
            embed.add_field(name="🎪 限時代幣", value=str(status.get("event_tokens", 0)), inline=True)
        label = _label(self.config)
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
                value=f"{status['uncollected']['work_name']} — 🪙 {status['uncollected']['token_reward']} {label}",
                inline=False,
            )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="獎品池", description="查看扭蛋獎品池與機率")
    async def pool(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        items = db.calc_item_probabilities(self.config)
        rarity_order = {"N": 0, "R": 1, "SR": 2, "SSR": 3, "秘藏": 4}
        items.sort(key=lambda x: (rarity_order.get(x["rarity"], 99), -x["probability"]))
        lines = []
        for item in items:
            pct = item["probability"] * 100
            if pct >= 1:
                pct_str = f"{pct:.1f}%"
            else:
                pct_str = f"{pct:.2f}%"
            lines.append(f"`{item['rarity']}` **{item['name']}** — {pct_str}")
        embed = discord.Embed(
            title="🎰 獎品池",
            description="\n".join(lines),
            color=0xF39C12,
        )
        label = _label(self.config)
        embed.set_footer(text=f"每次扭蛋消耗 {self.config['tokens']['gacha_cost']} {label}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="冒險", description="投入資源挑戰冒險事件")
    async def adventure(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        adventures = self.config.get("adventures", [])
        if not adventures:
            embed = discord.Embed(title="⚔️ 冒險", description="目前沒有可用的冒險事件", color=0x95A5A6)
            await interaction.followup.send(embed=embed)
            return

        label = _label(self.config)
        view = AdventureSelectView(self.config, interaction.user.id)
        lines = []
        for a in adventures:
            cost_icon = "⚡" if a["cost_type"] == "energy" else "🪙"
            cost_unit = "精力" if a["cost_type"] == "energy" else label
            rate = int(a["success_rate"] * 100)
            sr = a["success_reward"]
            fr = a["failure_reward"]
            sr_str = f"🪙 +{sr.get('amount', sr.get('value', 0))}" if sr["type"] == "fixed" else f"🪙 ×{sr['value']}"
            fr_str = f"🪙 +{fr.get('amount', fr.get('value', 0))}" if fr["type"] == "fixed" else f"🪙 ×{fr['value']}"
            lines.append(f"**{a['name']}** — {cost_icon} -{a['cost_amount']}{cost_unit} | 成功率 {rate}%\n　成功：{sr_str} ｜ 失敗：{fr_str}")
        embed = discord.Embed(
            title="⚔️ 選擇冒險",
            description="\n\n".join(lines),
            color=0xE67E22,
        )
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="背包", description="查看你的扭蛋收藏")
    async def inventory(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        items = await asyncio.to_thread(db.get_inventory, str(interaction.user.id))
        if not items:
            embed = discord.Embed(title="🎒 背包", description="背包是空的，快去扭蛋吧！", color=0x95A5A6)
            await interaction.followup.send(embed=embed)
            return
        lines = [f"`{item['rarity']}` {item['item_name']} ×{item['count']}" for item in items]
        embed = discord.Embed(title="🎒 背包", description="\n".join(lines), color=0xE67E22)
        await interaction.followup.send(embed=embed)


class WorkSelectView(discord.ui.View):
    def __init__(self, config: dict, user_id: int):
        super().__init__(timeout=60)
        self.config = config
        self.user_id = str(user_id)
        label = _label(config)
        select = discord.ui.Select(
            placeholder="選擇打工地點...",
            options=[
                discord.SelectOption(label=w["name"], value=str(i), description=f"⏱{w['duration_hours']}h ⚡-{w['energy_cost']} 🪙+{w['token_reward']}{label}")
                for i, w in enumerate(config["work"])
            ],
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("這不是你的選單！", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        idx = int(interaction.data["values"][0])
        work_cfg = self.config["work"][idx]
        success, msg = await asyncio.to_thread(db.start_work, self.user_id, work_cfg, self.config)
        color = 0x3498DB if success else 0xE74C3C
        embed = discord.Embed(title="💼 打工", description=msg, color=color)
        await interaction.edit_original_response(embed=embed, view=None)


class AdventureSelectView(discord.ui.View):
    def __init__(self, config: dict, user_id: int):
        super().__init__(timeout=60)
        self.config = config
        self.user_id = str(user_id)
        adventures = config.get("adventures", [])
        label = _label(config)
        select = discord.ui.Select(
            placeholder="選擇冒險...",
            options=[
                discord.SelectOption(
                    label=a["name"],
                    value=str(i),
                    description=f"{'⚡' if a['cost_type'] == 'energy' else '🪙'}-{a['cost_amount']}{'精力' if a['cost_type'] == 'energy' else label} | 成功率 {int(a['success_rate']*100)}%",
                )
                for i, a in enumerate(adventures)
            ],
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("這不是你的選單！", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        idx = int(interaction.data["values"][0])
        adventure = self.config["adventures"][idx]
        result = await asyncio.to_thread(db.do_adventure, self.user_id, adventure, self.config)
        label = _label(self.config)

        if not result["ok"]:
            embed = discord.Embed(title="⚔️ 冒險", description=result["msg"], color=0xE74C3C)
            await interaction.edit_original_response(embed=embed, view=None)
            return

        if result["success"]:
            embed = discord.Embed(
                title="⚔️ 冒險成功！",
                description=f"## 🏆 {result['adventure_name']}\n\n{result['cost_msg']}\n\n獲得 **{result['reward_amount']}** {label}！",
                color=0xF1C40F,
            )
        else:
            desc = f"## 💀 {result['adventure_name']}\n\n{result['cost_msg']}"
            if result["reward_amount"] > 0:
                desc += f"\n\n殘留收穫：**{result['reward_amount']}** {label}"
            else:
                desc += "\n\n空手而歸..."
            embed = discord.Embed(title="⚔️ 冒險失敗", description=desc, color=0x95A5A6)

        user = await asyncio.to_thread(db.get_user, self.user_id, self.config)
        col = _col(self.config)
        embed.add_field(name="⚡ 精力", value=str(user["energy"]), inline=True)
        embed.add_field(name=f"🪙 {label}", value=str(user[col]), inline=True)
        await interaction.edit_original_response(embed=embed, view=None)


async def setup(bot: commands.Bot):
    await bot.add_cog(Gacha(bot))
