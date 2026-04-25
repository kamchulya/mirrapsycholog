import aiosqlite
import os
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "mirra.db")


async def init_db():
    """Инициализация базы данных — создаём все таблицы"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        # Пользователи
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                birth_date TEXT,
                is_subscribed INTEGER DEFAULT 0,
                subscription_until TEXT,
                trial_used INTEGER DEFAULT 0,
                messages_this_month INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_active TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Диалоги — каждое сообщение пользователя и ответ бота
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dialogs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                user_message TEXT NOT NULL,
                bot_response TEXT NOT NULL,
                emotion TEXT,
                insight TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            )
        """)

        # Состояние пользователя (текущий режим, история диалога для контекста)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_state (
                user_id INTEGER PRIMARY KEY,
                current_mode TEXT DEFAULT 'menu',
                context TEXT DEFAULT '[]',
                mood TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            )
        """)

        # Дневниковые записи
        await db.execute("""
            CREATE TABLE IF NOT EXISTS diary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                entry_type TEXT NOT NULL,
                content TEXT NOT NULL,
                mood TEXT,
                tags TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            )
        """)

        await db.commit()
    print("✅ База данных инициализирована")


async def get_or_create_user(telegram_id: int, username: str = None, first_name: str = None):
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            user = await cursor.fetchone()

        if not user:
            await db.execute(
                """INSERT INTO users (telegram_id, username, first_name)
                   VALUES (?, ?, ?)""",
                (telegram_id, username, first_name)
            )
            await db.execute(
                "INSERT INTO user_state (user_id) VALUES (?)", (telegram_id,)
            )
            await db.commit()
            async with db.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            ) as cursor:
                user = await cursor.fetchone()

        return dict(user)


async def get_user(telegram_id: int):
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_user(telegram_id: int, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [telegram_id]
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            f"UPDATE users SET {fields} WHERE telegram_id = ?", values
        )
        await db.commit()


async def get_user_state(user_id: int):
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_state WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def set_user_mode(user_id: int, mode: str):
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            """INSERT INTO user_state (user_id, current_mode, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
               current_mode = excluded.current_mode,
               updated_at = excluded.updated_at""",
            (user_id, mode, datetime.now().isoformat())
        )
        await db.commit()


async def save_context(user_id: int, context: list):
    import json
    # Храним последние 10 сообщений для контекста
    if len(context) > 20:
        context = context[-20:]
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            """UPDATE user_state SET context = ?, updated_at = ?
               WHERE user_id = ?""",
            (json.dumps(context, ensure_ascii=False), datetime.now().isoformat(), user_id)
        )
        await db.commit()


async def get_context(user_id: int) -> list:
    import json
    async with aiosqlite.connect(DATABASE_URL) as db:
        async with db.execute(
            "SELECT context FROM user_state WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
            return []


async def clear_context(user_id: int):
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "UPDATE user_state SET context = '[]' WHERE user_id = ?", (user_id,)
        )
        await db.commit()


async def save_dialog(user_id: int, mode: str, user_msg: str, bot_response: str,
                      emotion: str = None, insight: str = None):
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            """INSERT INTO dialogs (user_id, mode, user_message, bot_response, emotion, insight)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, mode, user_msg, bot_response, emotion, insight)
        )
        await db.commit()


async def get_week_dialogs(user_id: int) -> list:
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM dialogs
               WHERE user_id = ?
               AND created_at >= datetime('now', '-7 days')
               ORDER BY created_at ASC""",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def save_diary_entry(user_id: int, entry_type: str, content: str,
                           mood: str = None, tags: str = None):
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            """INSERT INTO diary (user_id, entry_type, content, mood, tags)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, entry_type, content, mood, tags)
        )
        await db.commit()


async def can_use_bot(user_id: int) -> tuple[bool, str]:
    """Проверяем, может ли пользователь использовать бота"""
    user = await get_user(user_id)
    if not user:
        return False, "Пользователь не найден"

    # Если есть активная подписка
    if user.get("is_subscribed") and user.get("subscription_until"):
        until = datetime.fromisoformat(user["subscription_until"])
        if until > datetime.now():
            return True, "subscribed"

    # Бесплатный триал — 3 диалога
    if user.get("messages_this_month", 0) < 3:
        return True, "trial"

    return False, "limit_reached"


async def increment_message_count(user_id: int):
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            """UPDATE users SET messages_this_month = messages_this_month + 1,
               last_active = ? WHERE telegram_id = ?""",
            (datetime.now().isoformat(), user_id)
        )
        await db.commit()


async def get_all_users() -> list:
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
