import asyncio
import json
import time
import discord
from discord import app_commands
from discord.ext import commands
import database as db
import guild_config as gc


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _cfg(self, interaction: discord.Interaction) -> dict:
        return self.bot.get_guild_config(str(interaction.guild_id))

    def _gid(self, interaction: discord.Interaction) -> str:
        return str(interaction.guild_id)

    def _save(self, interaction: discord.Interaction):
        gid = self._gid(interaction)
        gc.save_guild_config(gid, self.bot.guild_configs[gid])

    admin_group = app_commands.Group(name="設定", description="管理員設定指令")

    @admin_group.command(name="精力上限", description="設定精力上限")
    @app_commands.describe(amount="精力上限數值")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_max_energy(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        config = self._cfg(interaction)
        config["energy"]["max_amount"] = amount
        self._save(interaction)
        await interaction.followup.send(f"✅ 精力上限已設為 **{amount}**")

    @admin_group.command(name="每日精力", description="設定每日獲得精力")
    @app_commands.describe(amount="每日精力數值")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_daily_energy(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        config = self._cfg(interaction)
        config["energy"]["daily_amount"] = amount
        self._save(interaction)
        await interaction.followup.send(f"✅ 每日精力已設為 **{amount}**")

    @admin_group.command(name="扭蛋費用", description="設定扭蛋所需代幣")
    @app_commands.describe(amount="代幣數值")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_gacha_cost(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        config = self._cfg(interaction)
        config["tokens"]["gacha_cost"] = amount
        self._save(interaction)
        await interaction.followup.send(f"✅ 扭蛋費用已設為 **{amount}** 代幣")

    @admin_group.command(name="簽到獎勵", description="設定簽到代幣獎勵")
    @app_commands.describe(amount="代幣數值")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_checkin_reward(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        config = self._cfg(interaction)
        config["tokens"]["checkin_reward"] = amount
        self._save(interaction)
        await interaction.followup.send(f"✅ 簽到獎勵已設為 **{amount}** 代幣")

    @admin_group.command(name="簽到冷卻", description="設定簽到重置時間（小時）")
    @app_commands.describe(hours="小時數")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_checkin_cooldown(self, interaction: discord.Interaction, hours: int):
        await interaction.response.defer()
        config = self._cfg(interaction)
        config["tokens"]["checkin_reset_hours"] = hours
        self._save(interaction)
        await interaction.followup.send(f"✅ 簽到冷卻已設為 **{hours}** 小時")

    @admin_group.command(name="新增打工", description="新增打工地點")
    @app_commands.describe(name="地點名稱", hours="工時（小時）", energy="所需精力", reward="代幣報酬")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_work(self, interaction: discord.Interaction, name: str, hours: int, energy: int, reward: int):
        await interaction.response.defer()
        config = self._cfg(interaction)
        config["work"].append({
            "name": name,
            "duration_hours": hours,
            "energy_cost": energy,
            "token_reward": reward,
        })
        self._save(interaction)
        await interaction.followup.send(f"✅ 已新增打工地點：**{name}**（⏱{hours}h ⚡-{energy} 🪙+{reward}）")

    @admin_group.command(name="刪除打工", description="刪除打工地點")
    @app_commands.describe(name="地點名稱")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_work(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        config = self._cfg(interaction)
        before = len(config["work"])
        config["work"] = [w for w in config["work"] if w["name"] != name]
        if len(config["work"]) == before:
            await interaction.followup.send(f"❌ 找不到打工地點：**{name}**")
            return
        self._save(interaction)
        await interaction.followup.send(f"✅ 已刪除打工地點：**{name}**")

    @admin_group.command(name="新增獎品", description="新增扭蛋獎品（秘藏需設定權重；可選擇啟用數量上限）")
    @app_commands.describe(
        name="獎品名稱",
        rarity="稀有度 (N/R/SR/SSR/秘藏)",
        weight="權重（僅秘藏需要填寫）",
        limit_enabled="是否限制此獎項可被抽中的次數",
        stock_limit="若啟用上限，可被抽中的總次數",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def add_prize(
        self,
        interaction: discord.Interaction,
        name: str,
        rarity: str,
        weight: int = None,
        limit_enabled: bool = False,
        stock_limit: int = None,
    ):
        await interaction.response.defer()
        config = self._cfg(interaction)
        valid = ("N", "R", "SR", "SSR", "秘藏")
        if rarity.upper() not in valid and rarity not in valid:
            await interaction.followup.send("❌ 稀有度必須是 N、R、SR、SSR 或 秘藏")
            return
        r = rarity if rarity == "秘藏" else rarity.upper()
        if r == "秘藏" and weight is None:
            await interaction.followup.send("❌ 秘藏獎品必須設定權重")
            return
        if limit_enabled and (stock_limit is None or stock_limit < 1):
            await interaction.followup.send("❌ 啟用數量上限時，stock_limit 必須是 ≥ 1 的整數")
            return
        item = {"name": name, "rarity": r}
        if r == "秘藏":
            item["weight"] = weight
        if limit_enabled:
            item["limit_enabled"] = True
            item["stock_limit"] = int(stock_limit)
            item["stock_remaining"] = int(stock_limit)
        config["gacha_pool"].append(item)
        self._save(interaction)
        msg = f"✅ 已新增獎品：`{r}` **{name}**"
        if r == "秘藏":
            msg += f"（權重 {weight}）"
        if limit_enabled:
            msg += f"｜剩餘 {stock_limit}/{stock_limit}"
        await interaction.followup.send(msg)

    @admin_group.command(name="補滿", description="將指定獎項的剩餘數量補滿到上限")
    @app_commands.describe(name="獎品名稱")
    @app_commands.checks.has_permissions(administrator=True)
    async def refill_prize(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        config = self._cfg(interaction)
        ok, amount = db.refill_prize(config, name)
        if not ok:
            await interaction.followup.send(f"❌ 找不到獎品「{name}」，或該獎項未啟用數量上限")
            return
        self._save(interaction)
        await interaction.followup.send(f"✅ 已將 **{name}** 補滿至 {amount}/{amount}")

    @admin_group.command(name="設定剩餘", description="精準設定獎項的剩餘數量（不變更上限）")
    @app_commands.describe(name="獎品名稱", remaining="新的剩餘數量（≥ 0，不可超過上限）")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_prize_remaining(self, interaction: discord.Interaction, name: str, remaining: int):
        await interaction.response.defer()
        config = self._cfg(interaction)
        for p in config.get("gacha_pool", []):
            if p.get("name") == name:
                if not p.get("limit_enabled"):
                    await interaction.followup.send(f"❌ 獎品「{name}」未啟用數量上限")
                    return
                limit = int(p.get("stock_limit") or 0)
                if remaining < 0 or remaining > limit:
                    await interaction.followup.send(f"❌ 剩餘數量必須在 0 ~ {limit} 之間")
                    return
                p["stock_remaining"] = int(remaining)
                self._save(interaction)
                await interaction.followup.send(f"✅ **{name}** 剩餘數量已設為 {remaining}/{limit}")
                return
        await interaction.followup.send(f"❌ 找不到獎品「{name}」")

    @admin_group.command(name="稀有度權重", description="設定 N/R/SR/SSR 的統一權重")
    @app_commands.describe(rarity="稀有度 (N/R/SR/SSR)", weight="權重數值")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_rarity_weight(self, interaction: discord.Interaction, rarity: str, weight: int):
        await interaction.response.defer()
        config = self._cfg(interaction)
        r = rarity.upper()
        if r not in ("N", "R", "SR", "SSR"):
            await interaction.followup.send("❌ 只能設定 N、R、SR、SSR 的權重（秘藏請用 新增獎品 時設定）")
            return
        config["rarity_weights"][r] = weight
        self._save(interaction)
        rw = config["rarity_weights"]
        lines = " / ".join(f"{k}={v}" for k, v in rw.items())
        await interaction.followup.send(f"✅ `{r}` 權重已設為 **{weight}**\n目前權重：{lines}")

    @admin_group.command(name="刪除獎品", description="刪除扭蛋獎品")
    @app_commands.describe(name="獎品名稱")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_prize(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        config = self._cfg(interaction)
        before = len(config["gacha_pool"])
        config["gacha_pool"] = [p for p in config["gacha_pool"] if p["name"] != name]
        if len(config["gacha_pool"]) == before:
            await interaction.followup.send(f"❌ 找不到獎品：**{name}**")
            return
        self._save(interaction)
        await interaction.followup.send(f"✅ 已刪除獎品：**{name}**")

    @admin_group.command(name="新增冒險", description="新增冒險事件")
    @app_commands.describe(
        name="冒險名稱",
        cost_type="消耗類型 (energy/tokens/custom_tokens)",
        cost_amount="消耗數量（custom_tokens 填 0）",
        success_rate="成功率 (0-100)",
        success_type="成功獎勵類型 (fixed/multiplier)",
        success_value="成功獎勵數值（fixed=代幣數, multiplier=倍率）",
        failure_type="失敗獎勵類型 (fixed/multiplier)",
        failure_value="失敗獎勵數值",
        min_bet="自選最小投入（僅 custom_tokens）",
        max_bet="自選最大投入（僅 custom_tokens）",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def add_adventure(
        self, interaction: discord.Interaction,
        name: str, cost_type: str, cost_amount: int, success_rate: int,
        success_type: str, success_value: float,
        failure_type: str, failure_value: float,
        min_bet: int = None, max_bet: int = None,
    ):
        await interaction.response.defer()
        config = self._cfg(interaction)
        if cost_type not in ("energy", "tokens", "custom_tokens"):
            await interaction.followup.send("❌ cost_type 必須是 energy、tokens 或 custom_tokens")
            return
        if success_type not in ("fixed", "multiplier") or failure_type not in ("fixed", "multiplier"):
            await interaction.followup.send("❌ 獎勵類型必須是 fixed 或 multiplier")
            return
        if not (0 <= success_rate <= 100):
            await interaction.followup.send("❌ 成功率必須在 0-100 之間")
            return
        if cost_type == "custom_tokens":
            if min_bet is None or max_bet is None:
                await interaction.followup.send("❌ custom_tokens 類型必須設定 min_bet 和 max_bet")
                return
            if min_bet < 1 or max_bet < min_bet:
                await interaction.followup.send("❌ min_bet 必須 ≥ 1，max_bet 必須 ≥ min_bet")
                return
        if "adventures" not in config:
            config["adventures"] = []
        adv = {
            "name": name,
            "cost_type": cost_type,
            "cost_amount": cost_amount,
            "success_rate": success_rate / 100,
            "success_reward": {"type": success_type, "amount" if success_type == "fixed" else "value": success_value},
            "failure_reward": {"type": failure_type, "amount" if failure_type == "fixed" else "value": failure_value},
        }
        if cost_type == "custom_tokens":
            adv["min_bet"] = min_bet
            adv["max_bet"] = max_bet
        config["adventures"].append(adv)
        self._save(interaction)
        if cost_type == "custom_tokens":
            await interaction.followup.send(f"✅ 已新增冒險：**{name}**（自選 {min_bet}~{max_bet} 代幣, 成功率 {success_rate}%）")
        else:
            cost_label = "精力" if cost_type == "energy" else "代幣"
            await interaction.followup.send(f"✅ 已新增冒險：**{name}**（{cost_label} -{cost_amount}, 成功率 {success_rate}%）")

    @admin_group.command(name="刪除冒險", description="刪除冒險事件")
    @app_commands.describe(name="冒險名稱")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_adventure(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        config = self._cfg(interaction)
        adventures = config.get("adventures", [])
        before = len(adventures)
        config["adventures"] = [a for a in adventures if a["name"] != name]
        if len(config["adventures"]) == before:
            await interaction.followup.send(f"❌ 找不到冒險：**{name}**")
            return
        self._save(interaction)
        await interaction.followup.send(f"✅ 已刪除冒險：**{name}**")

    @admin_group.command(name="管理角色", description="設定可使用管理指令的角色")
    @app_commands.describe(role="伺服器角色")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_admin_role(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer()
        config = self._cfg(interaction)
        config["admin_role"] = str(role.id)
        self._save(interaction)
        await interaction.followup.send(f"✅ 管理角色已設為 **{role.name}**")

    @app_commands.command(name="查看玩家", description="查看指定玩家的狀態（需要管理角色）")
    @app_commands.describe(member="要查看的玩家")
    async def view_player(self, interaction: discord.Interaction, member: discord.Member):
        config = self._cfg(interaction)
        gid = self._gid(interaction)
        admin_role_id = config.get("admin_role", "")
        has_admin_role = any(str(r.id) == admin_role_id for r in interaction.user.roles) if admin_role_id else False
        is_admin = interaction.user.guild_permissions.administrator
        if not has_admin_role and not is_admin:
            await interaction.response.send_message("❌ 你沒有權限使用此指令（需要管理角色）", ephemeral=True)
            return

        await interaction.response.defer()
        status = await asyncio.to_thread(db.get_status, gid, str(member.id), config)
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
        items = await asyncio.to_thread(db.get_inventory, gid, str(member.id))
        if items:
            lines = [f"`{item['rarity']}` {item['item_name']} ×{item['count']}" for item in items]
            embed.add_field(name="🎒 背包", value="\n".join(lines), inline=False)
        await interaction.followup.send(embed=embed)

    @admin_group.command(name="查看", description="查看目前所有設定")
    @app_commands.checks.has_permissions(administrator=True)
    async def view_config(self, interaction: discord.Interaction):
        await interaction.response.defer()
        c = self._cfg(interaction)
        work_lines = "\n".join(
            f"  • **{w['name']}** — ⏱{w['duration_hours']}h ⚡-{w['energy_cost']} 🪙+{w['token_reward']}"
            for w in c["work"]
        ) or "  （無）"
        items_with_prob = db.calc_item_probabilities(c)
        def _prize_line(p):
            line = f"  • `{p['rarity']}` **{p['name']}** — {p['probability']*100:.2f}%"
            if p["rarity"] == "秘藏":
                line += f"（權重 {p.get('weight', '')}）"
            if p.get("limit_enabled"):
                rem = int(p.get("stock_remaining") or 0)
                lim = int(p.get("stock_limit") or 0)
                tag = "已抽完" if rem <= 0 else f"剩餘 {rem}/{lim}"
                line += f"｜{tag}"
            return line
        prize_lines = "\n".join(_prize_line(p) for p in items_with_prob) or "  （無）"
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
        adventures = c.get("adventures", [])
        if adventures:
            adv_lines = []
            for a in adventures:
                cost_label = "⚡" if a["cost_type"] == "energy" else "🪙"
                rate = int(a["success_rate"] * 100)
                sr = a["success_reward"]
                fr = a["failure_reward"]
                sr_str = f"+{sr.get('amount', sr.get('value', 0))}" if sr["type"] == "fixed" else f"×{sr['value']}"
                fr_str = f"+{fr.get('amount', fr.get('value', 0))}" if fr["type"] == "fixed" else f"×{fr['value']}"
                adv_lines.append(f"  • **{a['name']}** — {cost_label}-{a['cost_amount']} | {rate}% | 成功{sr_str} 失敗{fr_str}")
            embed.add_field(name="冒險事件", value="\n".join(adv_lines), inline=False)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
