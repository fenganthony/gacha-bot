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
            rate = int(a["success_rate"] * 100)
            sr = a["success_reward"]
            fr = a["failure_reward"]
            sr_str = f"🪙 +{sr.get('amount', sr.get('value', 0))}" if sr["type"] == "fixed" else f"🪙 ×{sr['value']}"
            fr_str = f"🪙 +{fr.get('amount', fr.get('value', 0))}" if fr["type"] == "fixed" else f"🪙 ×{fr['value']}"
            if a["cost_type"] == "custom_tokens":
                cost_str = f"🪙 自選 {a.get('min_bet', 1)}~{a.get('max_bet', 9999)}{label}"
            else:
                cost_icon = "⚡" if a["cost_type"] == "energy" else "🪙"
                cost_unit = "精力" if a["cost_type"] == "energy" else label
                cost_str = f"{cost_icon} -{a['cost_amount']}{cost_unit}"
            lines.append(f"**{a['name']}** — {cost_str} | 成功率 {rate}%\n　成功：{sr_str} ｜ 失敗：{fr_str}")
        embed = discord.Embed(
            title="⚔️ 選擇冒險",
            description="\n\n".join(lines),
            color=0xE67E22,
        )
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="兌換", description="兌換背包中的獎品")
    async def redeem(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        items = await asyncio.to_thread(db.get_inventory, str(interaction.user.id))
        if not items:
            embed = discord.Embed(title="🎁 兌換", description="背包是空的，沒有可兌換的獎品！", color=0x95A5A6)
            await interaction.followup.send(embed=embed)
            return

        view = RedeemSelectView(self.config, self.bot, interaction.user, interaction.channel, items)
        embed = discord.Embed(
            title="🎁 選擇要兌換的獎品",
            description="\n".join(f"`{it['rarity']}` **{it['item_name']}** ×{it['count']}" for it in items),
            color=0xE91E63,
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
        options = []
        for i, a in enumerate(adventures):
            if a["cost_type"] == "custom_tokens":
                desc = f"🪙 自選 {a.get('min_bet',1)}~{a.get('max_bet',9999)}{label} | 成功率 {int(a['success_rate']*100)}%"
            else:
                icon = '⚡' if a['cost_type'] == 'energy' else '🪙'
                unit = '精力' if a['cost_type'] == 'energy' else label
                desc = f"{icon}-{a['cost_amount']}{unit} | 成功率 {int(a['success_rate']*100)}%"
            options.append(discord.SelectOption(label=a["name"], value=str(i), description=desc))
        select = discord.ui.Select(placeholder="選擇冒險...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("這不是你的選單！", ephemeral=True)
            return
        idx = int(interaction.data["values"][0])
        adventure = self.config["adventures"][idx]

        if adventure["cost_type"] == "custom_tokens":
            # Show modal for custom bet amount
            modal = CustomBetModal(self.config, self.user_id, adventure)
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.defer(ephemeral=True)
            await self._run_adventure(interaction, adventure)

    async def _run_adventure(self, interaction, adventure, custom_amount=None):
        adv = adventure
        if custom_amount is not None:
            # Override cost_amount with custom bet
            adv = {**adventure, "cost_type": "tokens", "cost_amount": custom_amount}
        result = await asyncio.to_thread(db.do_adventure, self.user_id, adv, self.config)
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


class CustomBetModal(discord.ui.Modal):
    def __init__(self, config: dict, user_id: str, adventure: dict):
        label = _label(config)
        min_bet = adventure.get("min_bet", 1)
        max_bet = adventure.get("max_bet", 9999)
        super().__init__(title=f"⚔️ {adventure['name']} — 投入{label}")
        self.config = config
        self.user_id = user_id
        self.adventure = adventure
        self.min_bet = min_bet
        self.max_bet = max_bet
        self.amount_input = discord.ui.TextInput(
            label=f"投入數量（{min_bet} ~ {max_bet}）",
            placeholder=f"輸入 {min_bet} 到 {max_bet} 之間的數字",
            required=True,
            min_length=1,
            max_length=10,
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount_input.value)
        except ValueError:
            await interaction.response.send_message("❌ 請輸入有效數字", ephemeral=True)
            return
        if amount < self.min_bet or amount > self.max_bet:
            await interaction.response.send_message(
                f"❌ 投入數量必須在 {self.min_bet} ~ {self.max_bet} 之間", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        # Create a temporary adventure view to run the adventure
        adv = {**self.adventure, "cost_type": "tokens", "cost_amount": amount}
        result = await asyncio.to_thread(db.do_adventure, self.user_id, adv, self.config)
        label = _label(self.config)

        if not result["ok"]:
            embed = discord.Embed(title="⚔️ 冒險", description=result["msg"], color=0xE74C3C)
            await interaction.followup.send(embed=embed, ephemeral=True)
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
        await interaction.followup.send(embed=embed, ephemeral=True)


class RedeemSelectView(discord.ui.View):
    def __init__(self, config: dict, bot, user: discord.Member, channel, items: list[dict]):
        super().__init__(timeout=60)
        self.config = config
        self.bot = bot
        self.user = user
        self.channel = channel
        self.items = items
        options = []
        for i, it in enumerate(items):
            options.append(discord.SelectOption(
                label=it["item_name"],
                value=f"{i}",
                description=f"{it['rarity']} ×{it['count']}",
            ))
            if len(options) >= 25:
                break
        select = discord.ui.Select(placeholder="選擇要兌換的獎品...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("這不是你的選單！", ephemeral=True)
            return
        idx = int(interaction.data["values"][0])
        item = self.items[idx]
        view = RedeemConfirmView(self.config, self.bot, self.user, self.channel, item)
        embed = discord.Embed(
            title="🎁 確認兌換",
            description=f"確定要兌換以下獎品？\n\n`{item['rarity']}` **{item['item_name']}**\n\n兌換後該獎品會從背包移除，並在頻道發送公開通知。",
            color=0xE91E63,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class RedeemConfirmView(discord.ui.View):
    def __init__(self, config: dict, bot, user: discord.Member, channel, item: dict):
        super().__init__(timeout=30)
        self.config = config
        self.bot = bot
        self.user = user
        self.channel = channel
        self.item = item

    @discord.ui.button(label="確認兌換", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("這不是你的按鈕！", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        # Remove item from inventory
        success = await asyncio.to_thread(
            db.redeem_item, str(self.user.id), self.item["item_name"], self.item["rarity"]
        )
        if not success:
            embed = discord.Embed(title="🎁 兌換失敗", description="背包中找不到該獎品", color=0xE74C3C)
            await interaction.edit_original_response(embed=embed, view=None)
            return

        # Update ephemeral message
        embed = discord.Embed(
            title="🎁 兌換成功",
            description=f"`{self.item['rarity']}` **{self.item['item_name']}** 已從背包移除\n\n公開通知已發送！",
            color=0x2ECC71,
        )
        await interaction.edit_original_response(embed=embed, view=None)

        # Send public message to configured channel
        redeem_cfg = self.config.get("redeem", {})
        target_channel = self.channel
        channel_id = redeem_cfg.get("channel_id", "")
        if channel_id:
            ch = self.bot.get_channel(int(channel_id))
            if ch:
                target_channel = ch

        # Build public message
        role_mention = ""
        role_id = redeem_cfg.get("role_id", "")
        if role_id:
            role_mention = f"<@&{role_id}>"

        template = redeem_cfg.get("message_template", "🎁 {user} 兌換了 `{rarity}` **{item}**！")
        msg = template.format(
            user=self.user.mention,
            item=self.item["item_name"],
            rarity=self.item["rarity"],
            role=role_mention,
        )

        public_embed = discord.Embed(
            title="🎁 獎品兌換通知",
            description=msg,
            color=0xE91E63,
        )
        public_embed.set_thumbnail(url=self.user.display_avatar.url)
        await target_channel.send(content=role_mention if role_id else None, embed=public_embed)

    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("這不是你的按鈕！", ephemeral=True)
            return
        embed = discord.Embed(title="🎁 兌換", description="已取消兌換", color=0x95A5A6)
        await interaction.response.edit_message(embed=embed, view=None)


async def setup(bot: commands.Bot):
    await bot.add_cog(Gacha(bot))
