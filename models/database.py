import os
import json
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import asyncio

_pool = None
_executor = ThreadPoolExecutor(max_workers=5)


def _get_db_url():
    url = os.getenv("DATABASE_URL", "")
    # Railway даёт postgres://, psycopg2 нужен postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def _init_pool():
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1, maxconn=10,
            dsn=_get_db_url()
        )
    return _pool


def _execute(query, params=None, fetch=None):
    """Синхронное выполнение запроса"""
    p = _init_pool()
    conn = p.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            conn.commit()
            if fetch == "one":
                return cur.fetchone()
            elif fetch == "all":
                return cur.fetchall()
            return None
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        p.putconn(conn)


async def _run(func, *args):
    """Запускаем синхронную функцию в executor"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, func, *args)


# ──────────────────────────────────────────────
# ИНИЦИАЛИЗАЦИЯ
# ──────────────────────────────────────────────

def _create_tables():
    p = _init_pool()
    conn = p.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    user_name_custom TEXT,
                    birth_date TEXT,
                    is_subscribed INTEGER DEFAULT 0,
                    subscription_until TIMESTAMP,
                    messages_this_month INTEGER DEFAULT 0,
                    onboarding_done INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW(),
                    last_active TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_state (
                    user_id BIGINT PRIMARY KEY,
                    current_mode TEXT DEFAULT 'menu',
                    context TEXT DEFAULT '[]',
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dialogs (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    mode TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    bot_response TEXT NOT NULL,
                    emotion TEXT,
                    insight TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    summary TEXT NOT NULL,
                    mode TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS diary (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    entry_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    mood TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
        conn.commit()
        print("✅ PostgreSQL инициализирован")
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        p.putconn(conn)


async def init_db():
    await _run(_create_tables)


# ──────────────────────────────────────────────
# ПОЛЬЗОВАТЕЛИ
# ──────────────────────────────────────────────

def _get_or_create_user_sync(telegram_id, username, first_name):
    p = _init_pool()
    conn = p.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
            user = cur.fetchone()
            if not user:
                cur.execute(
                    "INSERT INTO users (telegram_id, username, first_name) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (telegram_id, username, first_name)
                )
                cur.execute(
                    "INSERT INTO user_state (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
                    (telegram_id,)
                )
                conn.commit()
                cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
                user = cur.fetchone()
            return dict(user) if user else None
    finally:
        p.putconn(conn)


async def get_or_create_user(telegram_id, username=None, first_name=None):
    return await _run(_get_or_create_user_sync, telegram_id, username, first_name)


async def get_user(telegram_id):
    def _get():
        row = _execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,), fetch="one")
        return dict(row) if row else None
    return await _run(_get)


async def update_user(telegram_id, **kwargs):
    if not kwargs:
        return
    def _update():
        fields = ", ".join(f"{k} = %s" for k in kwargs)
        values = list(kwargs.values()) + [telegram_id]
        _execute(f"UPDATE users SET {fields} WHERE telegram_id = %s", values)
    await _run(_update)


async def get_all_users():
    def _get():
        rows = _execute("SELECT * FROM users", fetch="all")
        return [dict(r) for r in rows] if rows else []
    return await _run(_get)


# ──────────────────────────────────────────────
# СОСТОЯНИЕ
# ──────────────────────────────────────────────

async def get_user_state(user_id):
    def _get():
        row = _execute("SELECT * FROM user_state WHERE user_id = %s", (user_id,), fetch="one")
        return dict(row) if row else None
    return await _run(_get)


async def set_user_mode(user_id, mode):
    def _set():
        _execute(
            """INSERT INTO user_state (user_id, current_mode, updated_at)
               VALUES (%s, %s, NOW())
               ON CONFLICT (user_id) DO UPDATE SET current_mode = %s, updated_at = NOW()""",
            (user_id, mode, mode)
        )
    await _run(_set)


async def save_context(user_id, context):
    if len(context) > 20:
        context = context[-20:]
    def _save():
        _execute(
            "UPDATE user_state SET context = %s, updated_at = NOW() WHERE user_id = %s",
            (json.dumps(context, ensure_ascii=False), user_id)
        )
    await _run(_save)


async def get_context(user_id):
    def _get():
        row = _execute("SELECT context FROM user_state WHERE user_id = %s", (user_id,), fetch="one")
        if row and row["context"]:
            return json.loads(row["context"])
        return []
    return await _run(_get)


async def clear_context(user_id):
    def _clear():
        _execute("UPDATE user_state SET context = '[]' WHERE user_id = %s", (user_id,))
    await _run(_clear)


# ──────────────────────────────────────────────
# ДИАЛОГИ
# ──────────────────────────────────────────────

async def save_dialog(user_id, mode, user_msg, bot_response, emotion=None, insight=None):
    def _save():
        _execute(
            "INSERT INTO dialogs (user_id, mode, user_message, bot_response, emotion, insight) VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, mode, user_msg, bot_response, emotion, insight)
        )
    await _run(_save)


async def get_week_dialogs(user_id):
    def _get():
        rows = _execute(
            "SELECT * FROM dialogs WHERE user_id = %s AND created_at >= NOW() - INTERVAL '7 days' ORDER BY created_at ASC",
            (user_id,), fetch="all"
        )
        return [dict(r) for r in rows] if rows else []
    return await _run(_get)


async def get_month_dialogs(user_id):
    def _get():
        rows = _execute(
            "SELECT * FROM dialogs WHERE user_id = %s AND created_at >= NOW() - INTERVAL '30 days' ORDER BY created_at ASC",
            (user_id,), fetch="all"
        )
        return [dict(r) for r in rows] if rows else []
    return await _run(_get)


# ──────────────────────────────────────────────
# ПАМЯТЬ
# ──────────────────────────────────────────────

async def save_memory(user_id, summary, mode=None):
    def _save():
        _execute(
            "INSERT INTO memory (user_id, summary, mode) VALUES (%s, %s, %s)",
            (user_id, summary, mode)
        )
    await _run(_save)


async def get_recent_memories(user_id, limit=5):
    def _get():
        rows = _execute(
            "SELECT summary, mode, created_at FROM memory WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
            (user_id, limit), fetch="all"
        )
        return [dict(r) for r in rows] if rows else []
    return await _run(_get)


async def format_memories_for_prompt(user_id):
    memories = await get_recent_memories(user_id, limit=5)
    if not memories:
        return ""
    lines = []
    for m in reversed(memories):
        date = m["created_at"].strftime("%d.%m") if m.get("created_at") else ""
        lines.append(f"• {date}: {m['summary']}")
    return "Из прошлых разговоров:\n" + "\n".join(lines)


# ──────────────────────────────────────────────
# ДНЕВНИК
# ──────────────────────────────────────────────

async def save_diary_entry(user_id, entry_type, content, mood=None):
    def _save():
        _execute(
            "INSERT INTO diary (user_id, entry_type, content, mood) VALUES (%s, %s, %s, %s)",
            (user_id, entry_type, content, mood)
        )
    await _run(_save)


async def get_month_diary(user_id):
    def _get():
        rows = _execute(
            "SELECT * FROM diary WHERE user_id = %s AND created_at >= NOW() - INTERVAL '30 days' ORDER BY created_at ASC",
            (user_id,), fetch="all"
        )
        return [dict(r) for r in rows] if rows else []
    return await _run(_get)


async def delete_old_diary(user_id):
    def _del():
        _execute("DELETE FROM diary WHERE user_id = %s AND created_at < NOW() - INTERVAL '30 days'", (user_id,))
    await _run(_del)


async def delete_old_dialogs(user_id):
    def _del():
        _execute("DELETE FROM dialogs WHERE user_id = %s AND created_at < NOW() - INTERVAL '30 days'", (user_id,))
    await _run(_del)


# ──────────────────────────────────────────────
# ДОСТУП
# ──────────────────────────────────────────────

async def can_use_bot(user_id):
    user = await get_user(user_id)
    if not user:
        return False, "not_found"
    if user.get("is_subscribed") and user.get("subscription_until"):
        until = user["subscription_until"]
        if isinstance(until, str):
            until = datetime.fromisoformat(until)
        if until > datetime.now():
            return True, "subscribed"
    if user.get("messages_this_month", 0) < 3:
        return True, "trial"
    return False, "limit_reached"


async def increment_message_count(user_id):
    def _inc():
        _execute(
            "UPDATE users SET messages_this_month = messages_this_month + 1, last_active = NOW() WHERE telegram_id = %s",
            (user_id,)
        )
    await _run(_inc)


# ──────────────────────────────────────────────
# РЕФЕРАЛЫ
# ──────────────────────────────────────────────

def _create_referral_tables():
    p = _init_pool()
    conn = p.getconn()
    try:
        with conn.cursor() as cur:
            # Реферальные коды блогеров
            cur.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    id SERIAL PRIMARY KEY,
                    ref_code TEXT UNIQUE NOT NULL,
                    blogger_username TEXT NOT NULL,
                    blogger_telegram_id BIGINT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # Кто от кого пришёл
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ref_conversions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    ref_code TEXT NOT NULL,
                    paid INTEGER DEFAULT 0,
                    amount INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # Добавляем колонку ref_code в users если нет
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS ref_code TEXT
            """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        p.putconn(conn)


async def init_referral_tables():
    await _run(_create_referral_tables)


async def create_ref_code(ref_code: str, blogger_username: str, blogger_telegram_id: int = None):
    def _create():
        _execute(
            """INSERT INTO referrals (ref_code, blogger_username, blogger_telegram_id)
               VALUES (%s, %s, %s) ON CONFLICT (ref_code) DO NOTHING""",
            (ref_code, blogger_username, blogger_telegram_id)
        )
    await _run(_create)


async def get_ref_code(ref_code: str):
    def _get():
        row = _execute(
            "SELECT * FROM referrals WHERE ref_code = %s",
            (ref_code,), fetch="one"
        )
        return dict(row) if row else None
    return await _run(_get)


async def save_ref_conversion(user_id: int, ref_code: str):
    def _save():
        _execute(
            """INSERT INTO ref_conversions (user_id, ref_code)
               VALUES (%s, %s) ON CONFLICT DO NOTHING""",
            (user_id, ref_code)
        )
        _execute(
            "UPDATE users SET ref_code = %s WHERE telegram_id = %s",
            (ref_code, user_id)
        )
    await _run(_save)


async def mark_ref_paid(user_id: int, amount: int):
    """Отмечаем что пользователь оплатил — считаем комиссию блогеру"""
    def _mark():
        _execute(
            """UPDATE ref_conversions
               SET paid = 1, amount = %s
               WHERE user_id = %s""",
            (amount, user_id)
        )
    await _run(_mark)


async def get_ref_stats(ref_code: str = None) -> list:
    """Статистика по рефералам"""
    def _get():
        if ref_code:
            rows = _execute(
                """SELECT r.blogger_username, r.ref_code,
                   COUNT(rc.id) as total,
                   SUM(rc.paid) as paid_count,
                   SUM(rc.amount) as total_amount
                   FROM referrals r
                   LEFT JOIN ref_conversions rc ON r.ref_code = rc.ref_code
                   WHERE r.ref_code = %s
                   GROUP BY r.blogger_username, r.ref_code""",
                (ref_code,), fetch="all"
            )
        else:
            rows = _execute(
                """SELECT r.blogger_username, r.ref_code,
                   COUNT(rc.id) as total,
                   SUM(COALESCE(rc.paid, 0)) as paid_count,
                   SUM(COALESCE(rc.amount, 0)) as total_amount
                   FROM referrals r
                   LEFT JOIN ref_conversions rc ON r.ref_code = rc.ref_code
                   GROUP BY r.blogger_username, r.ref_code
                   ORDER BY paid_count DESC""",
                fetch="all"
            )
        return [dict(r) for r in rows] if rows else []
    return await _run(_get)


async def get_user_ref_code(user_id: int) -> str:
    """Получаем реф-код пользователя"""
    def _get():
        row = _execute(
            "SELECT ref_code FROM users WHERE telegram_id = %s",
            (user_id,), fetch="one"
        )
        return row["ref_code"] if row and row["ref_code"] else None
    return await _run(_get)
