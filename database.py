import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "gacha.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                energy INTEGER DEFAULT 0,
                tokens INTEGER DEFAULT 0,
                last_checkin REAL DEFAULT 0,
                last_energy_refresh REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS work_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                work_name TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                token_reward INTEGER NOT NULL,
                collected INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                item_name TEXT NOT NULL,
                rarity TEXT NOT NULL,
                obtained_at REAL NOT NULL
            );
        """)


def get_user(user_id: str, config: dict) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            now = time.time()
            conn.execute(
                "INSERT INTO users (user_id, energy, tokens, last_checkin, last_energy_refresh) VALUES (?, ?, 0, 0, ?)",
                (user_id, config["energy"]["daily_amount"], now),
            )
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row)


def refresh_energy(user_id: str, config: dict) -> dict:
    """Refresh energy if a new day has started (24h since last refresh)."""
    user = get_user(user_id, config)
    now = time.time()
    elapsed = now - user["last_energy_refresh"]
    if elapsed >= 86400:  # 24 hours
        new_energy = min(user["energy"] + config["energy"]["daily_amount"], config["energy"]["max_amount"])
        with get_conn() as conn:
            conn.execute(
                "UPDATE users SET energy = ?, last_energy_refresh = ? WHERE user_id = ?",
                (new_energy, now, user_id),
            )
        user["energy"] = new_energy
        user["last_energy_refresh"] = now
    return user


def checkin(user_id: str, config: dict) -> tuple[bool, str]:
    user = refresh_energy(user_id, config)
    now = time.time()
    reset_seconds = config["tokens"]["checkin_reset_hours"] * 3600
    if now - user["last_checkin"] < reset_seconds:
        remaining = reset_seconds - (now - user["last_checkin"])
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        return False, f"簽到冷卻中，還需等待 {hours} 小時 {minutes} 分鐘"
    reward = config["tokens"]["checkin_reward"]
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET tokens = tokens + ?, last_checkin = ? WHERE user_id = ?",
            (reward, now, user_id),
        )
    return True, f"簽到成功！獲得 {reward} 代幣"


def start_work(user_id: str, work_cfg: dict, config: dict) -> tuple[bool, str]:
    user = refresh_energy(user_id, config)
    with get_conn() as conn:
        active = conn.execute(
            "SELECT * FROM work_sessions WHERE user_id = ? AND collected = 0 AND end_time > ?",
            (user_id, time.time()),
        ).fetchone()
        if active:
            remaining = active["end_time"] - time.time()
            minutes = int(remaining // 60)
            return False, f"你正在打工中（{active['work_name']}），還需 {minutes} 分鐘完成"
        if user["energy"] < work_cfg["energy_cost"]:
            return False, f"精力不足！需要 {work_cfg['energy_cost']}，目前只有 {user['energy']}"
        now = time.time()
        end_time = now + work_cfg["duration_hours"] * 3600
        conn.execute(
            "UPDATE users SET energy = energy - ? WHERE user_id = ?",
            (work_cfg["energy_cost"], user_id),
        )
        conn.execute(
            "INSERT INTO work_sessions (user_id, work_name, start_time, end_time, token_reward) VALUES (?, ?, ?, ?, ?)",
            (user_id, work_cfg["name"], now, end_time, work_cfg["token_reward"]),
        )
    return True, f"開始在 **{work_cfg['name']}** 打工！需要 {work_cfg['duration_hours']} 小時，完成後可領取 {work_cfg['token_reward']} 代幣"


def collect_work(user_id: str, config: dict) -> tuple[bool, str]:
    now = time.time()
    with get_conn() as conn:
        session = conn.execute(
            "SELECT * FROM work_sessions WHERE user_id = ? AND collected = 0 AND end_time <= ? ORDER BY end_time DESC LIMIT 1",
            (user_id, now),
        ).fetchone()
        if session is None:
            active = conn.execute(
                "SELECT * FROM work_sessions WHERE user_id = ? AND collected = 0 AND end_time > ?",
                (user_id, now),
            ).fetchone()
            if active:
                remaining = active["end_time"] - now
                minutes = int(remaining // 60)
                return False, f"打工尚未完成，還需 {minutes} 分鐘"
            return False, "沒有可領取的打工報酬"
        conn.execute("UPDATE users SET tokens = tokens + ? WHERE user_id = ?", (session["token_reward"], user_id))
        conn.execute("UPDATE work_sessions SET collected = 1 WHERE id = ?", (session["id"],))
    return True, f"領取成功！從 **{session['work_name']}** 獲得 {session['token_reward']} 代幣"


def calc_item_probabilities(config: dict) -> list[dict]:
    """Calculate the probability of each item in the gacha pool."""
    rarity_weights = config["rarity_weights"]
    pool = config["gacha_pool"]

    secret_items = [p for p in pool if p["rarity"] == "秘藏"]
    standard_items = [p for p in pool if p["rarity"] != "秘藏"]

    total_weight = sum(rarity_weights.values()) + sum(p.get("weight", 1) for p in secret_items)

    rarity_counts: dict[str, int] = {}
    for item in standard_items:
        rarity_counts[item["rarity"]] = rarity_counts.get(item["rarity"], 0) + 1

    results = []
    for item in pool:
        if item["rarity"] == "秘藏":
            prob = item.get("weight", 1) / total_weight
        else:
            count = rarity_counts.get(item["rarity"], 1)
            prob = (rarity_weights.get(item["rarity"], 0) / total_weight) / count
        results.append({**item, "probability": prob})
    return results


def do_gacha(user_id: str, config: dict) -> tuple[bool, str, dict | None]:
    import random

    user = refresh_energy(user_id, config)
    cost = config["tokens"]["gacha_cost"]
    if user["tokens"] < cost:
        return False, f"代幣不足！需要 {cost}，目前只有 {user['tokens']}", None

    items_with_prob = calc_item_probabilities(config)
    weights = [item["probability"] for item in items_with_prob]
    prize = random.choices(items_with_prob, weights=weights, k=1)[0]

    now = time.time()
    with get_conn() as conn:
        conn.execute("UPDATE users SET tokens = tokens - ? WHERE user_id = ?", (cost, user_id))
        conn.execute(
            "INSERT INTO inventory (user_id, item_name, rarity, obtained_at) VALUES (?, ?, ?, ?)",
            (user_id, prize["name"], prize["rarity"], now),
        )
    return True, f"消耗 {cost} 代幣", prize


def get_inventory(user_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT item_name, rarity, COUNT(*) as count FROM inventory WHERE user_id = ? GROUP BY item_name, rarity ORDER BY rarity, item_name",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_status(user_id: str, config: dict) -> dict:
    user = refresh_energy(user_id, config)
    with get_conn() as conn:
        active_work = conn.execute(
            "SELECT * FROM work_sessions WHERE user_id = ? AND collected = 0 AND end_time > ?",
            (user_id, time.time()),
        ).fetchone()
        uncollected = conn.execute(
            "SELECT * FROM work_sessions WHERE user_id = ? AND collected = 0 AND end_time <= ?",
            (user_id, time.time()),
        ).fetchone()
    return {
        "energy": user["energy"],
        "max_energy": config["energy"]["max_amount"],
        "tokens": user["tokens"],
        "working": dict(active_work) if active_work else None,
        "uncollected": dict(uncollected) if uncollected else None,
    }
