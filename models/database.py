import os
import json
import asyncpg
from datetime import datetime, timedelta

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        database_url = os.getenv("DATABASE_URL", "")
        # Railway даёт postgres://, asyncpg нужен postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        _pool = await asyncpg.create_pool(database_url, min_size=1, max_size=10)
    return _pool


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:

        # Пользователи — с памятью
        await conn.execute("""
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

        # Состояние — текущий режим и контекст диалога
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_state (
                user_id BIGINT PRIMARY KEY,
                current_mode TEXT DEFAULT 'menu',
                context TEXT DEFAULT '[]',
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Диалоги — полная история
        await conn.execute("""
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

        # Память — краткие резюме сессий (не весь текст!)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                summary TEXT NOT NULL,
                mode TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Дневник
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS diary (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                entry_type TEXT NOT NULL,
                content TEXT NOT NULL,
                mood TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        print("✅ PostgreSQL инициализирован")


# ──────────────────────────────────────────────
# ПОЛЬЗОВАТЕЛИ
# ──────────────────────────────────────────────

async def get_or_create_user(telegram_id: int, username: str = None, first_name: str = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        if not user:
            await conn.execute(
                """INSERT INTO users (telegram_id, username, first_name)
                   VALUES ($1, $2, $3) ON CONFLICT DO NOTHING""",
                telegram_id, username, first_name
            )
            await conn.execute(
                "INSERT INTO user_state (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
                telegram_id
            )
            user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        return dict(user)


async def get_user(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        return dict(row) if row else None


async def update_user(telegram_id: int, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(kwargs))
    values = [telegram_id] + list(kwargs.values())
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE users SET {fields} WHERE telegram_id = $1", *values
        )


async def get_all_users():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM users")
        return [dict(r) for r in rows]


# ──────────────────────────────────────────────
# СОСТОЯНИЕ
# ──────────────────────────────────────────────

async def get_user_state(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM user_state WHERE user_id = $1", user_id)
        return dict(row) if row else None


async def set_user_mode(user_id: int, mode: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO user_state (user_id, current_mode, updated_at)
               VALUES ($1, $2, NOW())
               ON CONFLICT (user_id) DO UPDATE SET
               current_mode = $2, updated_at = NOW()""",
            user_id, mode
        )


async def save_context(user_id: int, context: list):
    if len(context) > 20:
        context = context[-20:]
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE user_state SET context = $2, updated_at = NOW()
               WHERE user_id = $1""",
            user_id, json.dumps(context, ensure_ascii=False)
        )


async def get_context(user_id: int) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT context FROM user_state WHERE user_id = $1", user_id)
        if row and row["context"]:
            return json.loads(row["context"])
        return []


async def clear_context(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE user_state SET context = '[]' WHERE user_id = $1", user_id
        )


# ──────────────────────────────────────────────
# ДИАЛОГИ
# ──────────────────────────────────────────────

async def save_dialog(user_id: int, mode: str, user_msg: str, bot_response: str,
                      emotion: str = None, insight: str = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO dialogs (user_id, mode, user_message, bot_response, emotion, insight)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            user_id, mode, user_msg, bot_response, emotion, insight
        )


async def get_week_dialogs(user_id: int) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM dialogs
               WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '7 days'
               ORDER BY created_at ASC""",
            user_id
        )
        return [dict(r) for r in rows]


async def get_month_dialogs(user_id: int) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM dialogs
               WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '30 days'
               ORDER BY created_at ASC""",
            user_id
        )
        return [dict(r) for r in rows]


# ──────────────────────────────────────────────
# ПАМЯТЬ — краткие резюме сессий
# ──────────────────────────────────────────────

async def save_memory(user_id: int, summary: str, mode: str = None):
    """Сохраняем краткое резюме сессии — не весь текст"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO memory (user_id, summary, mode) VALUES ($1, $2, $3)",
            user_id, summary, mode
        )


async def get_recent_memories(user_id: int, limit: int = 5) -> list:
    """Последние N резюме для контекста — дёшево и информативно"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT summary, mode, created_at FROM memory
               WHERE user_id = $1
               ORDER BY created_at DESC LIMIT $2""",
            user_id, limit
        )
        return [dict(r) for r in rows]


async def format_memories_for_prompt(user_id: int) -> str:
    """Форматируем память для вставки в системный промпт"""
    memories = await get_recent_memories(user_id, limit=5)
    if not memories:
        return ""
    lines = []
    for m in reversed(memories):
        date = m["created_at"].strftime("%d.%m")
        lines.append(f"• {date}: {m['summary']}")
    return "Из прошлых разговоров:\n" + "\n".join(lines)


# ──────────────────────────────────────────────
# ДНЕВНИК
# ──────────────────────────────────────────────

async def save_diary_entry(user_id: int, entry_type: str, content: str, mood: str = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO diary (user_id, entry_type, content, mood) VALUES ($1, $2, $3, $4)",
            user_id, entry_type, content, mood
        )


async def get_month_diary(user_id: int) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM diary
               WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '30 days'
               ORDER BY created_at ASC""",
            user_id
        )
        return [dict(r) for r in rows]


async def delete_old_diary(user_id: int):
    """Удаляем записи старше 30 дней"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM diary WHERE user_id = $1 AND created_at < NOW() - INTERVAL '30 days'",
            user_id
        )


async def delete_old_dialogs(user_id: int):
    """Удаляем диалоги старше 30 дней (память остаётся)"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM dialogs WHERE user_id = $1 AND created_at < NOW() - INTERVAL '30 days'",
            user_id
        )


# ──────────────────────────────────────────────
# ДОСТУП
# ──────────────────────────────────────────────

async def can_use_bot(user_id: int) -> tuple:
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


async def increment_message_count(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE users SET
               messages_this_month = messages_this_month + 1,
               last_active = NOW()
               WHERE telegram_id = $1""",
            user_id
        )
