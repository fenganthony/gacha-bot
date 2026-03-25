import json
from pathlib import Path
from aiohttp import web
import database as db

CONFIG_PATH = Path(__file__).parent / "config.json"
STATIC_PATH = Path(__file__).parent / "static"


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

    # --- API: Health check ---
    async def health(request):
        return web.json_response({"status": "ok"})

    app.router.add_get("/", index)
    app.router.add_get("/api/config", get_config)
    app.router.add_post("/api/energy", update_energy)
    app.router.add_post("/api/tokens", update_tokens)
    app.router.add_post("/api/rarity", update_rarity)
    app.router.add_post("/api/work", add_work)
    app.router.add_delete("/api/work", delete_work)
    app.router.add_post("/api/prize", add_prize)
    app.router.add_delete("/api/prize", delete_prize)
    app.router.add_get("/health", health)

    return app
