import json
import copy
import time
from aiohttp import web
import database as db
import guild_config as gc
from paths import STATIC_PATH


def create_app(bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot

    def _get_guild(request) -> tuple[str, dict]:
        """Extract guild_id from query params, return (guild_id, config)."""
        gid = request.query.get("guild", "")
        if not gid or gid not in bot.guild_configs:
            raise web.HTTPBadRequest(text="Missing or invalid guild parameter")
        return gid, bot.guild_configs[gid]

    def _save(gid: str):
        gc.save_guild_config(gid, bot.guild_configs[gid])

    # --- Pages ---
    async def index(request):
        return web.FileResponse(STATIC_PATH / "index.html")

    async def users_page(request):
        return web.FileResponse(STATIC_PATH / "users.html")

    # --- API: Guilds ---
    async def list_guilds(request):
        registry = gc.load_registry()
        guilds = []
        for gid, info in registry.items():
            guilds.append({
                "id": gid,
                "name": info.get("name", gid),
                "joined_at": info.get("joined_at", ""),
            })
        return web.json_response(guilds)

    async def unregister_guild(request):
        data = await request.json()
        gid = data.get("guild_id", "")
        delete_data = data.get("delete_data", False)
        if gid in bot.guild_configs:
            del bot.guild_configs[gid]
        gc.unregister_guild(gid, delete_data=delete_data)
        if delete_data:
            db.delete_guild_data(gid)
        return web.json_response({"ok": True})

    # --- API: Read config ---
    async def get_config(request):
        gid, c = _get_guild(request)
        items = db.calc_item_probabilities(c)
        return web.json_response({
            "energy": c["energy"],
            "tokens": c["tokens"],
            "rarity_weights": c["rarity_weights"],
            "work": c["work"],
            "gacha_pool": items,
            "admin_role": c.get("admin_role", ""),
            "channel_limits": c.get("channel_limits", {"checkin": "", "gacha": "", "adventure": "", "redeem_cmd": ""}),
            "redeem": c.get("redeem", {"channel_id": "", "role_id": "", "message_template": ""}),
            "adventures": c.get("adventures", []),
        })

    # --- API: Update energy ---
    async def update_energy(request):
        gid, c = _get_guild(request)
        data = await request.json()
        if "daily_amount" in data:
            c["energy"]["daily_amount"] = int(data["daily_amount"])
        if "max_amount" in data:
            c["energy"]["max_amount"] = int(data["max_amount"])
        _save(gid)
        return web.json_response({"ok": True})

    # --- API: Update tokens ---
    async def update_tokens(request):
        gid, c = _get_guild(request)
        data = await request.json()
        if "gacha_cost" in data:
            c["tokens"]["gacha_cost"] = int(data["gacha_cost"])
        if "checkin_reward" in data:
            c["tokens"]["checkin_reward"] = int(data["checkin_reward"])
        if "checkin_reset_hours" in data:
            c["tokens"]["checkin_reset_hours"] = int(data["checkin_reset_hours"])
        _save(gid)
        return web.json_response({"ok": True})

    # --- API: Update rarity weights ---
    async def update_rarity(request):
        gid, c = _get_guild(request)
        data = await request.json()
        for key in ("N", "R", "SR", "SSR"):
            if key in data:
                c["rarity_weights"][key] = int(data[key])
        _save(gid)
        return web.json_response({"ok": True})

    # --- API: Work CRUD ---
    async def add_work(request):
        gid, c = _get_guild(request)
        data = await request.json()
        c["work"].append({
            "name": data["name"],
            "duration_hours": int(data["duration_hours"]),
            "energy_cost": int(data["energy_cost"]),
            "token_reward": int(data["token_reward"]),
        })
        _save(gid)
        return web.json_response({"ok": True})

    async def delete_work(request):
        gid, c = _get_guild(request)
        data = await request.json()
        c["work"] = [w for w in c["work"] if w["name"] != data["name"]]
        _save(gid)
        return web.json_response({"ok": True})

    # --- API: Gacha pool CRUD ---
    async def add_prize(request):
        gid, c = _get_guild(request)
        data = await request.json()
        item = {"name": data["name"], "rarity": data["rarity"]}
        if data["rarity"] == "秘藏":
            item["weight"] = int(data.get("weight", 1))
        if data.get("limit_enabled"):
            limit = int(data.get("stock_limit") or 0)
            if limit < 1:
                return web.json_response({"ok": False, "msg": "啟用上限時，數量上限必須 ≥ 1"}, status=400)
            item["limit_enabled"] = True
            item["stock_limit"] = limit
            item["stock_remaining"] = limit
        c["gacha_pool"].append(item)
        _save(gid)
        return web.json_response({"ok": True})

    async def delete_prize(request):
        gid, c = _get_guild(request)
        data = await request.json()
        c["gacha_pool"] = [p for p in c["gacha_pool"] if p["name"] != data["name"]]
        _save(gid)
        return web.json_response({"ok": True})

    async def update_prize_stock(request):
        """Edit an existing prize's stock fields (enable/disable limit, set limit/remaining)."""
        gid, c = _get_guild(request)
        data = await request.json()
        name = data.get("name")
        if not name:
            return web.json_response({"ok": False, "msg": "缺少獎品名稱"}, status=400)
        for p in c.get("gacha_pool", []):
            if p.get("name") == name:
                if "limit_enabled" in data:
                    enabled = bool(data["limit_enabled"])
                    if enabled:
                        limit = int(data.get("stock_limit") or 0)
                        if limit < 1:
                            return web.json_response({"ok": False, "msg": "上限必須 ≥ 1"}, status=400)
                        remaining = data.get("stock_remaining")
                        remaining = int(remaining) if remaining is not None else limit
                        if remaining < 0 or remaining > limit:
                            return web.json_response({"ok": False, "msg": f"剩餘必須在 0~{limit} 之間"}, status=400)
                        p["limit_enabled"] = True
                        p["stock_limit"] = limit
                        p["stock_remaining"] = remaining
                    else:
                        p["limit_enabled"] = False
                        p.pop("stock_limit", None)
                        p.pop("stock_remaining", None)
                else:
                    if not p.get("limit_enabled"):
                        return web.json_response({"ok": False, "msg": "此獎項未啟用上限"}, status=400)
                    if "stock_limit" in data:
                        limit = int(data["stock_limit"])
                        if limit < 1:
                            return web.json_response({"ok": False, "msg": "上限必須 ≥ 1"}, status=400)
                        p["stock_limit"] = limit
                        if int(p.get("stock_remaining") or 0) > limit:
                            p["stock_remaining"] = limit
                    if "stock_remaining" in data:
                        remaining = int(data["stock_remaining"])
                        limit = int(p.get("stock_limit") or 0)
                        if remaining < 0 or remaining > limit:
                            return web.json_response({"ok": False, "msg": f"剩餘必須在 0~{limit} 之間"}, status=400)
                        p["stock_remaining"] = remaining
                _save(gid)
                return web.json_response({"ok": True})
        return web.json_response({"ok": False, "msg": "找不到獎品"}, status=404)

    # --- API: Adventure CRUD ---
    async def add_adventure(request):
        gid, c = _get_guild(request)
        data = await request.json()
        if "adventures" not in c:
            c["adventures"] = []
        sr_type = data.get("success_type", "fixed")
        fr_type = data.get("failure_type", "fixed")
        adv = {
            "name": data["name"],
            "cost_type": data["cost_type"],
            "cost_amount": int(data["cost_amount"]),
            "success_rate": float(data["success_rate"]) / 100,
            "success_reward": {"type": sr_type, "amount" if sr_type == "fixed" else "value": float(data["success_value"])},
            "failure_reward": {"type": fr_type, "amount" if fr_type == "fixed" else "value": float(data["failure_value"])},
        }
        if data["cost_type"] == "custom_tokens":
            adv["min_bet"] = int(data.get("min_bet", 1))
            adv["max_bet"] = int(data.get("max_bet", 9999))
        c["adventures"].append(adv)
        _save(gid)
        return web.json_response({"ok": True})

    async def delete_adventure(request):
        gid, c = _get_guild(request)
        data = await request.json()
        c["adventures"] = [a for a in c.get("adventures", []) if a["name"] != data["name"]]
        _save(gid)
        return web.json_response({"ok": True})

    # --- API: Channel & notification settings ---
    async def update_redeem(request):
        gid, c = _get_guild(request)
        data = await request.json()
        if "channel_limits" in data:
            if "channel_limits" not in c:
                c["channel_limits"] = {}
            for key in ("checkin", "gacha", "adventure", "redeem_cmd"):
                if key in data["channel_limits"]:
                    c["channel_limits"][key] = data["channel_limits"][key]
        if "redeem" not in c:
            c["redeem"] = {}
        for key in ("channel_id", "role_id", "message_template"):
            if key in data:
                c["redeem"][key] = data[key]
        _save(gid)
        return web.json_response({"ok": True})

    # --- API: Presets (per-guild) ---
    SAVEABLE_KEYS = ("energy", "tokens", "rarity_weights", "work", "gacha_pool", "adventures")

    async def list_presets(request):
        gid, c = _get_guild(request)
        presets_path = gc.guild_presets_path(gid)
        presets_path.mkdir(parents=True, exist_ok=True)
        presets = []
        for f in sorted(presets_path.glob("*.json")):
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            presets.append({
                "name": data.get("name", f.stem),
                "filename": f.stem,
                "saved_at": data.get("saved_at", ""),
            })
        return web.json_response(presets)

    async def save_preset(request):
        gid, c = _get_guild(request)
        data = await request.json()
        name = data.get("name", "").strip()
        if not name:
            return web.json_response({"ok": False, "msg": "名稱不可為空"}, status=400)
        presets_path = gc.guild_presets_path(gid)
        presets_path.mkdir(parents=True, exist_ok=True)
        preset = {"name": name, "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        for key in SAVEABLE_KEYS:
            if key in c:
                preset[key] = copy.deepcopy(c[key])
        filename = name.replace("/", "_").replace("\\", "_")
        with open(presets_path / f"{filename}.json", "w", encoding="utf-8") as f:
            json.dump(preset, f, ensure_ascii=False, indent=2)
        return web.json_response({"ok": True})

    async def load_preset(request):
        gid, c = _get_guild(request)
        data = await request.json()
        filename = data.get("filename", "")
        presets_path = gc.guild_presets_path(gid)
        path = presets_path / f"{filename}.json"
        if not path.exists():
            return web.json_response({"ok": False, "msg": "找不到該組合"}, status=404)
        with open(path, "r", encoding="utf-8") as f:
            preset = json.load(f)
        for key in SAVEABLE_KEYS:
            if key in preset:
                c[key] = copy.deepcopy(preset[key])
        _save(gid)
        return web.json_response({"ok": True})

    async def delete_preset(request):
        gid, c = _get_guild(request)
        data = await request.json()
        filename = data.get("filename", "")
        presets_path = gc.guild_presets_path(gid)
        path = presets_path / f"{filename}.json"
        if path.exists():
            path.unlink()
        return web.json_response({"ok": True})

    # --- API: Activity Mode ---
    async def get_activity(request):
        gid, c = _get_guild(request)
        return web.json_response(c.get("activity", {"active": False, "name": "", "initial_event_tokens": 0}))

    async def toggle_activity(request):
        gid, c = _get_guild(request)
        data = await request.json()
        if "activity" not in c:
            c["activity"] = {"active": False, "name": "", "initial_event_tokens": 0}
        activate = data.get("active", False)
        if activate and not c["activity"]["active"]:
            c["activity"]["active"] = True
            c["activity"]["name"] = data.get("name", "活動")
            c["activity"]["initial_event_tokens"] = int(data.get("initial_event_tokens", 0))
            db.activate_event(gid, c)
        elif not activate and c["activity"]["active"]:
            c["activity"]["active"] = False
            db.deactivate_event(gid)
        _save(gid)
        return web.json_response({"ok": True})

    # --- API: User Management ---
    async def get_users(request):
        gid, c = _get_guild(request)
        users = db.get_all_users(gid, c)
        return web.json_response(users)

    async def update_user_api(request):
        gid, c = _get_guild(request)
        data = await request.json()
        user_id = data.pop("user_id", None)
        if not user_id:
            return web.json_response({"ok": False}, status=400)
        db.update_user(gid, user_id, data)
        return web.json_response({"ok": True})

    # --- API: Health check ---
    async def health(request):
        return web.json_response({"status": "ok"})

    app.router.add_get("/", index)
    app.router.add_get("/users", users_page)
    app.router.add_get("/api/guilds", list_guilds)
    app.router.add_delete("/api/guilds", unregister_guild)
    app.router.add_get("/api/config", get_config)
    app.router.add_post("/api/energy", update_energy)
    app.router.add_post("/api/tokens", update_tokens)
    app.router.add_post("/api/rarity", update_rarity)
    app.router.add_post("/api/work", add_work)
    app.router.add_delete("/api/work", delete_work)
    app.router.add_post("/api/prize", add_prize)
    app.router.add_delete("/api/prize", delete_prize)
    app.router.add_post("/api/prize/stock", update_prize_stock)
    app.router.add_post("/api/adventure", add_adventure)
    app.router.add_delete("/api/adventure", delete_adventure)
    app.router.add_post("/api/redeem", update_redeem)
    app.router.add_get("/api/presets", list_presets)
    app.router.add_post("/api/presets", save_preset)
    app.router.add_post("/api/presets/load", load_preset)
    app.router.add_delete("/api/presets", delete_preset)
    app.router.add_get("/api/activity", get_activity)
    app.router.add_post("/api/activity", toggle_activity)
    app.router.add_get("/api/users", get_users)
    app.router.add_post("/api/users", update_user_api)
    app.router.add_get("/health", health)

    return app
