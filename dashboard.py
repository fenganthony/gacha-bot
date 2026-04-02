import json
import copy
import time
from aiohttp import web
import database as db
from paths import CONFIG_PATH, STATIC_PATH, PRESETS_PATH


def save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def create_app(config: dict) -> web.Application:
    app = web.Application()
    app["config"] = config

    # --- Pages ---
    async def index(request):
        return web.FileResponse(STATIC_PATH / "index.html")

    # --- API: Read config ---
    async def get_config(request):
        c = app["config"]
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
        data = await request.json()
        c = app["config"]
        if "daily_amount" in data:
            c["energy"]["daily_amount"] = int(data["daily_amount"])
        if "max_amount" in data:
            c["energy"]["max_amount"] = int(data["max_amount"])
        save_config(c)
        return web.json_response({"ok": True})

    # --- API: Update tokens ---
    async def update_tokens(request):
        data = await request.json()
        c = app["config"]
        if "gacha_cost" in data:
            c["tokens"]["gacha_cost"] = int(data["gacha_cost"])
        if "checkin_reward" in data:
            c["tokens"]["checkin_reward"] = int(data["checkin_reward"])
        if "checkin_reset_hours" in data:
            c["tokens"]["checkin_reset_hours"] = int(data["checkin_reset_hours"])
        save_config(c)
        return web.json_response({"ok": True})

    # --- API: Update rarity weights ---
    async def update_rarity(request):
        data = await request.json()
        c = app["config"]
        for key in ("N", "R", "SR", "SSR"):
            if key in data:
                c["rarity_weights"][key] = int(data[key])
        save_config(c)
        return web.json_response({"ok": True})

    # --- API: Work CRUD ---
    async def add_work(request):
        data = await request.json()
        c = app["config"]
        c["work"].append({
            "name": data["name"],
            "duration_hours": int(data["duration_hours"]),
            "energy_cost": int(data["energy_cost"]),
            "token_reward": int(data["token_reward"]),
        })
        save_config(c)
        return web.json_response({"ok": True})

    async def delete_work(request):
        data = await request.json()
        c = app["config"]
        c["work"] = [w for w in c["work"] if w["name"] != data["name"]]
        save_config(c)
        return web.json_response({"ok": True})

    # --- API: Gacha pool CRUD ---
    async def add_prize(request):
        data = await request.json()
        c = app["config"]
        item = {"name": data["name"], "rarity": data["rarity"]}
        if data["rarity"] == "秘藏":
            item["weight"] = int(data.get("weight", 1))
        c["gacha_pool"].append(item)
        save_config(c)
        return web.json_response({"ok": True})

    async def delete_prize(request):
        data = await request.json()
        c = app["config"]
        c["gacha_pool"] = [p for p in c["gacha_pool"] if p["name"] != data["name"]]
        save_config(c)
        return web.json_response({"ok": True})

    # --- API: Adventure CRUD ---
    async def add_adventure(request):
        data = await request.json()
        c = app["config"]
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
        save_config(c)
        return web.json_response({"ok": True})

    async def delete_adventure(request):
        data = await request.json()
        c = app["config"]
        c["adventures"] = [a for a in c.get("adventures", []) if a["name"] != data["name"]]
        save_config(c)
        return web.json_response({"ok": True})

    # --- API: Channel & notification settings ---
    async def update_redeem(request):
        data = await request.json()
        c = app["config"]
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
        save_config(c)
        return web.json_response({"ok": True})

    # --- API: Presets ---
    SAVEABLE_KEYS = ("energy", "tokens", "rarity_weights", "work", "gacha_pool", "adventures")

    async def list_presets(request):
        PRESETS_PATH.mkdir(exist_ok=True)
        presets = []
        for f in sorted(PRESETS_PATH.glob("*.json")):
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            presets.append({
                "name": data.get("name", f.stem),
                "filename": f.stem,
                "saved_at": data.get("saved_at", ""),
            })
        return web.json_response(presets)

    async def save_preset(request):
        data = await request.json()
        name = data.get("name", "").strip()
        if not name:
            return web.json_response({"ok": False, "msg": "名稱不可為空"}, status=400)
        PRESETS_PATH.mkdir(exist_ok=True)
        c = app["config"]
        preset = {"name": name, "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        for key in SAVEABLE_KEYS:
            if key in c:
                preset[key] = copy.deepcopy(c[key])
        filename = name.replace("/", "_").replace("\\", "_")
        with open(PRESETS_PATH / f"{filename}.json", "w", encoding="utf-8") as f:
            json.dump(preset, f, ensure_ascii=False, indent=2)
        return web.json_response({"ok": True})

    async def load_preset(request):
        data = await request.json()
        filename = data.get("filename", "")
        path = PRESETS_PATH / f"{filename}.json"
        if not path.exists():
            return web.json_response({"ok": False, "msg": "找不到該組合"}, status=404)
        with open(path, "r", encoding="utf-8") as f:
            preset = json.load(f)
        c = app["config"]
        for key in SAVEABLE_KEYS:
            if key in preset:
                c[key] = copy.deepcopy(preset[key])
        save_config(c)
        return web.json_response({"ok": True})

    async def delete_preset(request):
        data = await request.json()
        filename = data.get("filename", "")
        path = PRESETS_PATH / f"{filename}.json"
        if path.exists():
            path.unlink()
        return web.json_response({"ok": True})

    # --- API: Activity Mode ---
    async def get_activity(request):
        c = app["config"]
        return web.json_response(c.get("activity", {"active": False, "name": "", "initial_event_tokens": 0}))

    async def toggle_activity(request):
        data = await request.json()
        c = app["config"]
        if "activity" not in c:
            c["activity"] = {"active": False, "name": "", "initial_event_tokens": 0}
        activate = data.get("active", False)
        if activate and not c["activity"]["active"]:
            # Turning ON
            c["activity"]["active"] = True
            c["activity"]["name"] = data.get("name", "活動")
            c["activity"]["initial_event_tokens"] = int(data.get("initial_event_tokens", 0))
            db.activate_event(c)
        elif not activate and c["activity"]["active"]:
            # Turning OFF
            c["activity"]["active"] = False
            db.deactivate_event()
        save_config(c)
        return web.json_response({"ok": True})

    # --- API: User Management ---
    async def get_users(request):
        users = db.get_all_users(app["config"])
        return web.json_response(users)

    async def update_user_api(request):
        data = await request.json()
        user_id = data.pop("user_id", None)
        if not user_id:
            return web.json_response({"ok": False}, status=400)
        db.update_user(user_id, data)
        return web.json_response({"ok": True})

    async def users_page(request):
        return web.FileResponse(STATIC_PATH / "users.html")

    # --- API: Health check ---
    async def health(request):
        return web.json_response({"status": "ok"})

    app.router.add_get("/", index)
    app.router.add_get("/users", users_page)
    app.router.add_get("/api/config", get_config)
    app.router.add_post("/api/energy", update_energy)
    app.router.add_post("/api/tokens", update_tokens)
    app.router.add_post("/api/rarity", update_rarity)
    app.router.add_post("/api/work", add_work)
    app.router.add_delete("/api/work", delete_work)
    app.router.add_post("/api/prize", add_prize)
    app.router.add_delete("/api/prize", delete_prize)
    app.router.add_post("/api/adventure", add_adventure)
    app.router.add_post("/api/redeem", update_redeem)
    app.router.add_delete("/api/adventure", delete_adventure)
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
