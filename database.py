import sqlite3
import time
from contextlib import contextmanager
from paths import DB_PATH


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
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                energy INTEGER DEFAULT 0,
                tokens INTEGER DEFAULT 0,
                event_tokens INTEGER DEFAULT 0,
                last_checkin REAL DEFAULT 0,
                last_energy_refresh REAL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS work_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                work_name TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                token_reward INTEGER NOT NULL,
                collected INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                item_name TEXT NOT NULL,
                rarity TEXT NOT NULL,
                obtained_at REAL NOT NULL
            );
        """)
        _migrate(conn)


def _migrate(conn):
    """Handle schema migrations from older versions."""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]

    if "guild_id" not in cols:
        # Legacy single-guild schema -> multi-guild
        conn.executescript("""
            ALTER TABLE users RENAME TO _users_old;
            CREATE TABLE users (
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                energy INTEGER DEFAULT 0,
                tokens INTEGER DEFAULT 0,
                event_tokens INTEGER DEFAULT 0,
                last_checkin REAL DEFAULT 0,
                last_energy_refresh REAL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );
            INSERT INTO users (guild_id, user_id, energy, tokens, event_tokens, last_checkin, last_energy_refresh)
                SELECT 'legacy', user_id, energy, tokens,
                       COALESCE(event_tokens, 0), last_checkin, last_energy_refresh
                FROM _users_old;
            DROP TABLE _users_old;
        """)
        conn.execute("ALTER TABLE work_sessions ADD COLUMN guild_id TEXT NOT NULL DEFAULT 'legacy'")
        conn.execute("ALTER TABLE inventory ADD COLUMN guild_id TEXT NOT NULL DEFAULT 'legacy'")
    elif "event_tokens" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN event_tokens INTEGER DEFAULT 0")


def reassign_legacy_data(new_guild_id: str):
    """Move all 'legacy' guild_id rows to a real guild."""
    with get_conn() as conn:
        for table in ("users", "work_sessions", "inventory"):
            conn.execute(f"UPDATE {table} SET guild_id = ? WHERE guild_id = 'legacy'", (new_guild_id,))


def delete_guild_data(guild_id: str):
    """Delete all data for a guild."""
    with get_conn() as conn:
        for table in ("users", "work_sessions", "inventory"):
            conn.execute(f"DELETE FROM {table} WHERE guild_id = ?", (guild_id,))


# --- Helpers ---

def _token_col(config: dict) -> str:
    if config.get("activity", {}).get("active", False):
        return "event_tokens"
    return "tokens"


def _token_label(config: dict) -> str:
    if config.get("activity", {}).get("active", False):
        return "限時代幣"
    return "代幣"


# --- User ---

def get_user(guild_id: str, user_id: str, config: dict) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchone()
        if row is None:
            now = time.time()
            initial_event = config.get("activity", {}).get("initial_event_tokens", 0) if config.get("activity", {}).get("active", False) else 0
            conn.execute(
                "INSERT INTO users (guild_id, user_id, energy, tokens, event_tokens, last_checkin, last_energy_refresh) VALUES (?, ?, ?, 0, ?, 0, ?)",
                (guild_id, user_id, config["energy"]["daily_amount"], initial_event, now),
            )
            row = conn.execute(
                "SELECT * FROM users WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ).fetchone()
        return dict(row)


def refresh_energy(guild_id: str, user_id: str, config: dict) -> dict:
    user = get_user(guild_id, user_id, config)
    now = time.time()
    elapsed = now - user["last_energy_refresh"]
    if elapsed >= 86400:
        new_energy = min(user["energy"] + config["energy"]["daily_amount"], config["energy"]["max_amount"])
        with get_conn() as conn:
            conn.execute(
                "UPDATE users SET energy = ?, last_energy_refresh = ? WHERE guild_id = ? AND user_id = ?",
                (new_energy, now, guild_id, user_id),
            )
        user["energy"] = new_energy
        user["last_energy_refresh"] = now
    return user


# --- Checkin ---

def checkin(guild_id: str, user_id: str, config: dict) -> tuple[bool, str]:
    user = refresh_energy(guild_id, user_id, config)
    now = time.time()
    reset_seconds = config["tokens"]["checkin_reset_hours"] * 3600
    if now - user["last_checkin"] < reset_seconds:
        remaining = reset_seconds - (now - user["last_checkin"])
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        return False, f"簽到冷卻中，還需等待 {hours} 小時 {minutes} 分鐘"
    reward = config["tokens"]["checkin_reward"]
    col = _token_col(config)
    label = _token_label(config)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE users SET {col} = {col} + ?, last_checkin = ? WHERE guild_id = ? AND user_id = ?",
            (reward, now, guild_id, user_id),
        )
    return True, f"簽到成功！獲得 {reward} {label}"


# --- Work ---

def start_work(guild_id: str, user_id: str, work_cfg: dict, config: dict) -> tuple[bool, str]:
    user = refresh_energy(guild_id, user_id, config)
    label = _token_label(config)
    with get_conn() as conn:
        active = conn.execute(
            "SELECT * FROM work_sessions WHERE guild_id = ? AND user_id = ? AND collected = 0 AND end_time > ?",
            (guild_id, user_id, time.time()),
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
            "UPDATE users SET energy = energy - ? WHERE guild_id = ? AND user_id = ?",
            (work_cfg["energy_cost"], guild_id, user_id),
        )
        conn.execute(
            "INSERT INTO work_sessions (guild_id, user_id, work_name, start_time, end_time, token_reward) VALUES (?, ?, ?, ?, ?, ?)",
            (guild_id, user_id, work_cfg["name"], now, end_time, work_cfg["token_reward"]),
        )
    return True, f"開始在 **{work_cfg['name']}** 打工！需要 {work_cfg['duration_hours']} 小時，完成後可領取 {work_cfg['token_reward']} {label}"


def collect_work(guild_id: str, user_id: str, config: dict) -> tuple[bool, str]:
    now = time.time()
    col = _token_col(config)
    label = _token_label(config)
    with get_conn() as conn:
        session = conn.execute(
            "SELECT * FROM work_sessions WHERE guild_id = ? AND user_id = ? AND collected = 0 AND end_time <= ? ORDER BY end_time DESC LIMIT 1",
            (guild_id, user_id, now),
        ).fetchone()
        if session is None:
            active = conn.execute(
                "SELECT * FROM work_sessions WHERE guild_id = ? AND user_id = ? AND collected = 0 AND end_time > ?",
                (guild_id, user_id, now),
            ).fetchone()
            if active:
                remaining = active["end_time"] - now
                minutes = int(remaining // 60)
                return False, f"打工尚未完成，還需 {minutes} 分鐘"
            return False, "沒有可領取的打工報酬"
        conn.execute(
            f"UPDATE users SET {col} = {col} + ? WHERE guild_id = ? AND user_id = ?",
            (session["token_reward"], guild_id, user_id),
        )
        conn.execute("UPDATE work_sessions SET collected = 1 WHERE id = ?", (session["id"],))
    return True, f"領取成功！從 **{session['work_name']}** 獲得 {session['token_reward']} {label}"


# --- Gacha ---

def _normalize_prize(item: dict) -> dict:
    """Soft-upgrade an old prize record by filling in stock fields with safe defaults."""
    return {
        "limit_enabled": False,
        "stock_limit": None,
        "stock_remaining": None,
        **item,
    }


def _is_depleted(item: dict) -> bool:
    return bool(item.get("limit_enabled")) and (item.get("stock_remaining") or 0) <= 0


def is_pool_empty(config: dict) -> bool:
    """Pool is empty only if every prize has a limit and zero stock."""
    pool = config.get("gacha_pool", [])
    if not pool:
        return True
    return all(_is_depleted(_normalize_prize(p)) for p in pool)


def refill_prize(config: dict, name: str) -> tuple[bool, int]:
    """Reset stock_remaining = stock_limit for a named prize. Returns (found, restored_amount)."""
    for p in config.get("gacha_pool", []):
        if p.get("name") == name:
            if not p.get("limit_enabled"):
                return False, 0
            limit = int(p.get("stock_limit") or 0)
            p["stock_remaining"] = limit
            return True, limit
    return False, 0


def calc_item_probabilities(config: dict, exclude_depleted: bool = False) -> list[dict]:
    rarity_weights = config["rarity_weights"]
    pool = [_normalize_prize(p) for p in config["gacha_pool"]]
    if exclude_depleted:
        pool = [p for p in pool if not _is_depleted(p)]

    secret_items = [p for p in pool if p["rarity"] == "秘藏"]
    standard_items = [p for p in pool if p["rarity"] != "秘藏"]

    rarity_counts: dict[str, int] = {}
    for item in standard_items:
        rarity_counts[item["rarity"]] = rarity_counts.get(item["rarity"], 0) + 1

    active_rarity_weight = sum(
        w for r, w in rarity_weights.items() if rarity_counts.get(r, 0) > 0
    )
    total_weight = active_rarity_weight + sum(p.get("weight", 1) for p in secret_items)

    results = []
    for item in pool:
        if total_weight <= 0:
            prob = 0.0
        elif item["rarity"] == "秘藏":
            prob = item.get("weight", 1) / total_weight
        else:
            count = rarity_counts.get(item["rarity"], 1)
            prob = (rarity_weights.get(item["rarity"], 0) / total_weight) / count
        results.append({**item, "probability": prob})
    return results


def do_gacha(guild_id: str, user_id: str, config: dict) -> tuple[bool, str, dict | None]:
    import random
    user = refresh_energy(guild_id, user_id, config)
    cost = config["tokens"]["gacha_cost"]
    col = _token_col(config)
    label = _token_label(config)
    current = user[col]
    if current < cost:
        return False, f"{label}不足！需要 {cost}，目前只有 {current}", None

    if is_pool_empty(config):
        return False, "獎池所有獎項皆已抽完，無法抽取空的轉蛋機", None

    # Reroll while landing on a depleted prize.
    items_with_prob = calc_item_probabilities(config)
    weights = [item["probability"] for item in items_with_prob]
    if sum(weights) <= 0:
        return False, "獎池所有獎項皆已抽完，無法抽取空的轉蛋機", None

    prize = None
    for _ in range(100):
        candidate = random.choices(items_with_prob, weights=weights, k=1)[0]
        if _is_depleted(candidate):
            continue
        prize = candidate
        break
    if prize is None:
        return False, "獎池所有獎項皆已抽完，無法抽取空的轉蛋機", None

    # Decrement stock on the live config object (caller is responsible for persisting).
    if prize.get("limit_enabled"):
        for p in config["gacha_pool"]:
            if p.get("name") == prize["name"] and p.get("rarity") == prize["rarity"]:
                p["stock_remaining"] = max(0, int(p.get("stock_remaining") or 0) - 1)
                prize = {**prize, "stock_remaining": p["stock_remaining"]}
                break

    now = time.time()
    with get_conn() as conn:
        conn.execute(
            f"UPDATE users SET {col} = {col} - ? WHERE guild_id = ? AND user_id = ?",
            (cost, guild_id, user_id),
        )
        conn.execute(
            "INSERT INTO inventory (guild_id, user_id, item_name, rarity, obtained_at) VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, prize["name"], prize["rarity"], now),
        )
    return True, f"消耗 {cost} {label}", prize


# --- Adventure ---

def do_adventure(guild_id: str, user_id: str, adventure: dict, config: dict) -> dict:
    import random
    user = refresh_energy(guild_id, user_id, config)
    cost_type = adventure["cost_type"]
    cost_amount = adventure["cost_amount"]
    col = _token_col(config)
    label = _token_label(config)

    if cost_type == "energy":
        if user["energy"] < cost_amount:
            return {"ok": False, "msg": f"精力不足！需要 {cost_amount}，目前只有 {user['energy']}"}
    else:
        current = user[col]
        if current < cost_amount:
            return {"ok": False, "msg": f"{label}不足！需要 {cost_amount}，目前只有 {current}"}

    with get_conn() as conn:
        if cost_type == "energy":
            conn.execute(
                "UPDATE users SET energy = energy - ? WHERE guild_id = ? AND user_id = ?",
                (cost_amount, guild_id, user_id),
            )
        else:
            conn.execute(
                f"UPDATE users SET {col} = {col} - ? WHERE guild_id = ? AND user_id = ?",
                (cost_amount, guild_id, user_id),
            )

    success = random.random() < adventure["success_rate"]
    reward_cfg = adventure["success_reward"] if success else adventure["failure_reward"]
    if reward_cfg["type"] == "fixed":
        reward_amount = int(reward_cfg.get("amount", 0))
    else:
        reward_amount = int(cost_amount * reward_cfg.get("value", 0))

    if reward_amount > 0:
        with get_conn() as conn:
            conn.execute(
                f"UPDATE users SET {col} = {col} + ? WHERE guild_id = ? AND user_id = ?",
                (reward_amount, guild_id, user_id),
            )

    cost_label = "精力" if cost_type == "energy" else label
    return {
        "ok": True,
        "success": success,
        "adventure_name": adventure["name"],
        "cost_msg": f"消耗 {cost_amount} {cost_label}",
        "reward_amount": reward_amount,
        "net": reward_amount - (cost_amount if cost_type == "tokens" else 0),
        "cost_type": cost_type,
    }


# --- Inventory & Redeem ---

def redeem_item(guild_id: str, user_id: str, item_name: str, rarity: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM inventory WHERE guild_id = ? AND user_id = ? AND item_name = ? AND rarity = ? LIMIT 1",
            (guild_id, user_id, item_name, rarity),
        ).fetchone()
        if row is None:
            return False
        conn.execute("DELETE FROM inventory WHERE id = ?", (row["id"],))
    return True


def get_inventory(guild_id: str, user_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT item_name, rarity, COUNT(*) as count FROM inventory WHERE guild_id = ? AND user_id = ? GROUP BY item_name, rarity ORDER BY rarity, item_name",
            (guild_id, user_id),
        ).fetchall()
        return [dict(r) for r in rows]


# --- Status ---

def get_status(guild_id: str, user_id: str, config: dict) -> dict:
    user = refresh_energy(guild_id, user_id, config)
    with get_conn() as conn:
        active_work = conn.execute(
            "SELECT * FROM work_sessions WHERE guild_id = ? AND user_id = ? AND collected = 0 AND end_time > ?",
            (guild_id, user_id, time.time()),
        ).fetchone()
        uncollected = conn.execute(
            "SELECT * FROM work_sessions WHERE guild_id = ? AND user_id = ? AND collected = 0 AND end_time <= ?",
            (guild_id, user_id, time.time()),
        ).fetchone()
    return {
        "energy": user["energy"],
        "max_energy": config["energy"]["max_amount"],
        "tokens": user["tokens"],
        "event_tokens": user.get("event_tokens", 0),
        "activity_active": config.get("activity", {}).get("active", False),
        "working": dict(active_work) if active_work else None,
        "uncollected": dict(uncollected) if uncollected else None,
    }


# --- Activity Mode ---

def activate_event(guild_id: str, config: dict):
    initial = config.get("activity", {}).get("initial_event_tokens", 0)
    with get_conn() as conn:
        conn.execute("UPDATE users SET event_tokens = ? WHERE guild_id = ?", (initial, guild_id))


def deactivate_event(guild_id: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET event_tokens = 0 WHERE guild_id = ?", (guild_id,))


# --- User Management ---

def get_all_users(guild_id: str, config: dict) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM users WHERE guild_id = ? ORDER BY user_id",
            (guild_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_user(guild_id: str, user_id: str, data: dict):
    allowed = ("energy", "tokens", "event_tokens")
    sets = []
    vals = []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = ?")
            vals.append(int(data[key]))
    if not sets:
        return
    vals.extend([guild_id, user_id])
    with get_conn() as conn:
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE guild_id = ? AND user_id = ?", vals)
