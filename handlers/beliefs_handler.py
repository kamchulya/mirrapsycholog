import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from anthropic import AsyncAnthropic

from models.database import (
    get_user, update_user, get_or_create_user,
    set_user_mode, get_user_state, _execute, _run
)

logger = logging.getLogger(__name__)
router = Router()

async def safe_edit_text(message, text, **kwargs):
    """Безопасный edit_text — игнорирует ошибку 'message is not modified'"""
    try:
        await message.edit_text(text, **kwargs)
    except Exception as e:
        if "message is not modified" not in str(e):
            raise

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ──────────────────────────────────────────────
# КОНСТАНТЫ
# ──────────────────────────────────────────────

SPHERES = {
    "money": "💰 Деньги",
    "relationships": "💞 Отношения",
    "self_realization": "🌟 Самореализация",
    "self_esteem": "🪞 Самооценка",
    "fears": "🌊 Страхи",
}

COURSE_DAYS = 7

BELIEFS_COURSE_PRICE = int(os.getenv("BELIEFS_COURSE_PRICE", "2000"))  # отдельная покупка
BELIEFS_SUB_MONTHS = 6  # при подписке от 6 месяцев — бесплатно

# Промпты для каждого дня курса
DAY_PROMPTS = {
    1: """Ты — Мирра, мягкий и глубокий психолог. Сегодня первый день курса по проработке убеждений в сфере: {sphere}.

Твоя задача — помочь пользователю выявить его главное ограничивающее убеждение в этой сфере.

Задай 3-4 вопроса поочерёдно (не все сразу). Начни с первого вопроса. Слушай ответы внимательно.
После того как пользователь ответит на все вопросы — сформулируй его главное убеждение в одной фразе.

Первый вопрос про сферу "{sphere_name}":
- Деньги: "Когда ты думаешь о деньгах — какая первая мысль приходит?"
- Отношения: "Что первое приходит в голову когда думаешь об отношениях?"
- Самореализация: "Что мешает тебе делать то, что по-настоящему хочется?"
- Самооценка: "Как бы ты описала себя в трёх словах — честно?"
- Страхи: "Чего ты боишься больше всего — даже если это кажется глупым?"

Пиши тепло, без психологического жаргона. Имя пользователя: {name}. История: {history}""",

    2: """Ты — Мирра, психолог. Второй день курса. Сфера: {sphere_name}. Пользователь: {name}.

Вчера было выявлено убеждение: "{belief}"

Сегодня задача — найти субличность, которая стоит за этим убеждением.

Попроси пользователя представить эту часть себя как персонажа или образ. Задай вопросы:
1. "Если бы эта часть тебя, которая говорит '{belief}' — была персонажем, как бы она выглядела?"
2. После ответа: "Сколько ей лет? Как она себя чувствует?"
3. После ответа: "Что она хочет тебе сказать? Зачем она тебя защищает?"

Помоги пользователю увидеть эту субличность с состраданием — она появилась не случайно.
История диалога: {history}""",

    3: """Ты — Мирра, психолог. Третий день курса. Сфера: {sphere_name}. Пользователь: {name}.

Убеждение: "{belief}". Субличность: "{subpersonality}"

Сегодня — диалог с субличностью. Пользователь будет говорить от имени этой части себя, а ты помогаешь ему услышать её послание.

1. Попроси войти в образ субличности и ответить: "Почему ты появилась? Что случилось тогда?"
2. После ответа: "Чего ты боишься, если я перестану в это верить?"
3. После ответа: "Что тебе нужно чтобы успокоиться и отпустить меня?"

Заверши диалог словами благодарности субличности — она долго защищала человека.
История: {history}""",

    4: """Ты — Мирра, психолог. Четвёртый день. Сфера: {sphere_name}. Пользователь: {name}.

Убеждение которое проработали: "{belief}"

Сегодня — переписываем убеждение. 

1. Спроси: "Если бы ты знала, что это убеждение — просто старая программа, а не правда. Как бы звучала новая версия?"
2. Помоги сформулировать новое убеждение — позитивное, реалистичное, в настоящем времени.
3. Предложи аффирмацию под это убеждение — короткую, которую легко повторять.
4. Попроси написать новое убеждение 3 раза — это закрепляет.

История: {history}""",

    5: """Ты — Мирра, психолог. Пятый день. Сфера: {sphere_name}. Пользователь: {name}.

Новое убеждение: "{new_belief}"

Сегодня — телесная практика для закрепления.

1. Дай короткую медитацию (3-4 шага) связанную с новым убеждением. Например для денег — образ изобилия, для самооценки — ощущение своей ценности в теле.
2. Попроси пользователя выполнить и написать что почувствовал.
3. После ответа — дай обратную связь и закрепи ощущение.

Пиши медитацию живо и образно — так чтобы человек действительно погрузился.
История: {history}""",

    6: """Ты — Мирра, психолог. Шестой день. Сфера: {sphere_name}. Пользователь: {name}.

Мы работали с убеждением: "{belief}" → новое: "{new_belief}"

Сегодня — маленький реальный шаг.

1. Предложи одно небольшое конкретное действие которое пользователь может сделать сегодня — в сфере {sphere_name}. Не большое, не страшное. Одно.
2. Когда пользователь напишет что сделал — дай тёплую поддержку и отметь это как победу.
3. Спроси: "Что изменилось внутри когда ты это сделала?"

История: {history}""",

    7: """Ты — Мирра, психолог. Седьмой, последний день курса! Сфера: {sphere_name}. Пользователь: {name}.

Путь: убеждение "{belief}" → новое убеждение "{new_belief}"

Сегодня — подведение итогов и трекер изменений.

1. Поздравь с завершением курса — тепло и искренне.
2. Спроси: "По шкале от 1 до 10 — насколько сильно старое убеждение звучит сейчас?"
3. После ответа: "Что самое важное ты поняла за эти 7 дней?"
4. Дай краткое резюме пути — что было, что изменилось, что взять с собой.
5. Предложи продолжить с другой сферой или углубиться в эту.

История: {history}"""
}


# ──────────────────────────────────────────────
# БАЗА ДАННЫХ — таблица курса убеждений
# ──────────────────────────────────────────────

def _create_beliefs_tables():
    from models.database import _init_pool
    p = _init_pool()
    conn = p.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS beliefs_course (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    sphere TEXT NOT NULL,
                    current_day INTEGER DEFAULT 1,
                    belief TEXT,
                    subpersonality TEXT,
                    new_belief TEXT,
                    context TEXT DEFAULT '[]',
                    started_at TIMESTAMP DEFAULT NOW(),
                    last_day_at TIMESTAMP DEFAULT NOW(),
                    completed INTEGER DEFAULT 0,
                    purchased INTEGER DEFAULT 0
                )
            """)
            # Колонка beliefs_access в users
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS beliefs_access INTEGER DEFAULT 0
            """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        p.putconn(conn)


async def init_beliefs_tables():
    await _run(_create_beliefs_tables)


async def get_active_course(user_id: int):
    def _get():
        row = _execute(
            "SELECT * FROM beliefs_course WHERE user_id = %s AND completed = 0 ORDER BY started_at DESC LIMIT 1",
            (user_id,), fetch="one"
        )
        return dict(row) if row else None
    return await _run(_get)


async def create_course(user_id: int, sphere: str):
    def _create():
        _execute(
            "INSERT INTO beliefs_course (user_id, sphere, current_day) VALUES (%s, %s, 1)",
            (user_id, sphere)
        )
    await _run(_create)


async def update_course(user_id: int, **kwargs):
    if not kwargs:
        return
    def _update():
        fields = ", ".join(f"{k} = %s" for k in kwargs)
        values = list(kwargs.values()) + [user_id]
        _execute(
            f"UPDATE beliefs_course SET {fields} WHERE user_id = %s AND completed = 0",
            values
        )
    await _run(_update)


async def save_beliefs_context(user_id: int, context: list):
    if len(context) > 30:
        context = context[-30:]
    def _save():
        _execute(
            "UPDATE beliefs_course SET context = %s WHERE user_id = %s AND completed = 0",
            (json.dumps(context, ensure_ascii=False), user_id)
        )
    await _run(_save)


async def get_beliefs_context(user_id: int) -> list:
    def _get():
        row = _execute(
            "SELECT context FROM beliefs_course WHERE user_id = %s AND completed = 0",
            (user_id,), fetch="one"
        )
        if row and row["context"]:
            return json.loads(row["context"])
        return []
    return await _run(_get)


async def has_beliefs_access(user_id: int) -> bool:
    """Проверяем доступ: куплен курс ИЛИ подписка 6+ месяцев"""
    user = await get_user(user_id)
    if not user:
        return False
    # Отдельная покупка курса
    if user.get("beliefs_access"):
        return True
    # Подписка 6+ месяцев
    if user.get("is_subscribed") and user.get("subscription_until"):
        until = user["subscription_until"]
        if isinstance(until, str):
            until = datetime.fromisoformat(until)
        # Проверяем что подписка на 6+ месяцев (осталось >= 5 месяцев или куплена давно)
        months_left = (until - datetime.now()).days / 30
        if months_left >= 1:  # любая активная подписка на 6 месяцев даёт доступ
            return True
    return False


# ──────────────────────────────────────────────
# КЛАВИАТУРЫ
# ──────────────────────────────────────────────

def spheres_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, name in SPHERES.items():
        builder.row(InlineKeyboardButton(
            text=name,
            callback_data=f"beliefs_sphere_{key}"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    return builder.as_markup()


def start_course_keyboard(sphere: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🚀 Начать курс",
        callback_data=f"beliefs_start_{sphere}"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="beliefs_menu"))
    return builder.as_markup()


def next_day_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="➡️ Следующий день",
        callback_data="beliefs_next_day"
    ))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def buy_course_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"💳 Купить курс — {BELIEFS_COURSE_PRICE} ₸",
        callback_data="beliefs_buy"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    return builder.as_markup()


def continue_course_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="▶️ Продолжить курс",
        callback_data="beliefs_continue"
    ))
    builder.row(InlineKeyboardButton(
        text="🔄 Начать новую сферу",
        callback_data="beliefs_menu"
    ))
    builder.row(InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"))
    return builder.as_markup()


# ──────────────────────────────────────────────
# AI ГЕНЕРАЦИЯ
# ──────────────────────────────────────────────

async def generate_day_response(day: int, course: dict, user_name: str, history: list, user_message: str) -> str:
    sphere = course.get("sphere", "money")
    sphere_name = SPHERES.get(sphere, "Деньги")
    belief = course.get("belief") or ""
    subpersonality = course.get("subpersonality") or ""
    new_belief = course.get("new_belief") or ""

    # Форматируем историю
    history_text = ""
    if history:
        lines = []
        for msg in history[-10:]:
            role = "Пользователь" if msg["role"] == "user" else "Мирра"
            lines.append(f"{role}: {msg['content']}")
        history_text = "\n".join(lines)

    system = DAY_PROMPTS[day].format(
        sphere=sphere,
        sphere_name=sphere_name,
        name=user_name,
        belief=belief,
        subpersonality=subpersonality,
        new_belief=new_belief,
        history=history_text or "Начало разговора"
    )

    messages = history[-10:] if history else []
    if user_message:
        messages = messages + [{"role": "user", "content": user_message}]

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=system,
        messages=messages if messages else [{"role": "user", "content": "начнём"}]
    )
    return response.content[0].text


async def extract_belief_from_context(context: list, sphere_name: str) -> str:
    """Извлекаем ключевое убеждение из диалога первого дня"""
    history = "\n".join([
        f"{'Пользователь' if m['role'] == 'user' else 'Мирра'}: {m['content']}"
        for m in context[-15:]
    ])
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": f"Из этого диалога про сферу '{sphere_name}' выдели главное ограничивающее убеждение пользователя. Одна короткая фраза от первого лица. Только фраза, без объяснений.\n\n{history}"
        }]
    )
    return response.content[0].text.strip()


async def extract_subpersonality(context: list) -> str:
    """Извлекаем описание субличности из диалога второго дня"""
    history = "\n".join([
        f"{'Пользователь' if m['role'] == 'user' else 'Мирра'}: {m['content']}"
        for m in context[-15:]
    ])
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": f"Из этого диалога выдели краткое описание субличности которую увидел пользователь. 1-2 предложения. Только описание.\n\n{history}"
        }]
    )
    return response.content[0].text.strip()


async def extract_new_belief(context: list) -> str:
    """Извлекаем новое убеждение из диалога четвёртого дня"""
    history = "\n".join([
        f"{'Пользователь' if m['role'] == 'user' else 'Мирра'}: {m['content']}"
        for m in context[-15:]
    ])
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": f"Из этого диалога выдели новое позитивное убеждение которое сформулировал пользователь. Одна фраза от первого лица. Только фраза.\n\n{history}"
        }]
    )
    return response.content[0].text.strip()


# ──────────────────────────────────────────────
# ХЭНДЛЕРЫ
# ──────────────────────────────────────────────

@router.callback_query(F.data == "beliefs_menu")
async def beliefs_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    has_access = await has_beliefs_access(user_id)
    active_course = await get_active_course(user_id)

    if not has_access:
        await safe_edit_text(callback.message, 
            "🧠 *Проработка убеждений*\n\n"
            "7-дневный курс где ты:\n"
            "• выявишь главный блок в нужной сфере\n"
            "• познакомишься с субличностью за ним\n"
            "• перепишешь убеждение на новое\n"
            "• закрепишь через практику и реальный шаг\n\n"
            "Сферы: деньги, отношения, самореализация, самооценка, страхи\n\n"
            f"Стоимость: *{BELIEFS_COURSE_PRICE} ₸*\n"
            "Входит бесплатно в подписку на 6 месяцев 🎁",
            parse_mode="Markdown",
            reply_markup=buy_course_keyboard()
        )
    elif active_course:
        day = active_course["current_day"]
        sphere_name = SPHERES.get(active_course["sphere"], "")
        await safe_edit_text(callback.message, 
            f"🧠 *Проработка убеждений*\n\n"
            f"У тебя активный курс: {sphere_name}\n"
            f"День {day} из {COURSE_DAYS}\n\n"
            f"Продолжим? 👇",
            parse_mode="Markdown",
            reply_markup=continue_course_keyboard()
        )
    else:
        await safe_edit_text(callback.message, 
            "🧠 *Проработка убеждений*\n\n"
            "Выбери сферу для 7-дневного курса 👇\n\n"
            "Каждый день — новый шаг глубже. Бот будет вести тебя сам.",
            parse_mode="Markdown",
            reply_markup=spheres_keyboard()
        )
    await callback.answer()


@router.callback_query(F.data.startswith("beliefs_sphere_"))
async def select_sphere(callback: CallbackQuery):
    sphere = callback.data.replace("beliefs_sphere_", "")
    sphere_name = SPHERES.get(sphere, "")

    descriptions = {
        "money": "Разберём твои убеждения про деньги, достаток, заработок. Найдём что мешает и перепишем.",
        "relationships": "Посмотрим на убеждения про любовь, близость, партнёров. Найдём паттерн и изменим.",
        "self_realization": "Разберём что стоит между тобой и твоим делом, призванием, реализацией.",
        "self_esteem": "Поработаем с образом себя, самоценностью, внутренним критиком.",
        "fears": "Выявим главный страх, найдём его корень и освободимся от его власти.",
    }

    await safe_edit_text(callback.message, 
        f"{sphere_name}\n\n"
        f"{descriptions.get(sphere, '')}\n\n"
        f"Курс — 7 дней. Каждый день новая практика.\n"
        f"Готова начать? 👇",
        reply_markup=start_course_keyboard(sphere)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("beliefs_start_"))
async def start_course(callback: CallbackQuery):
    sphere = callback.data.replace("beliefs_start_", "")
    user_id = callback.from_user.id

    await create_course(user_id, sphere)
    await set_user_mode(user_id, f"beliefs_day_1")

    user = await get_user(user_id)
    name = user.get("user_name_custom") or user.get("first_name") or "дорогая"
    sphere_name = SPHERES.get(sphere, "")

    await safe_edit_text(callback.message, 
        f"🌱 Начинаем курс *{sphere_name}*\n\nДень 1 из 7 — Диагностика\n\n_пишу тебе..._",
        parse_mode="Markdown"
    )

    course = await get_active_course(user_id)
    response = await generate_day_response(1, course, name, [], "начнём")

    context = [{"role": "assistant", "content": response}]
    await save_beliefs_context(user_id, context)

    await safe_edit_text(callback.message, 
        f"🌱 *День 1 из 7 — Диагностика*\n\n{response}",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "beliefs_continue")
async def continue_course(callback: CallbackQuery):
    user_id = callback.from_user.id
    course = await get_active_course(user_id)
    if not course:
        await safe_edit_text(callback.message, 
            "Активного курса нет. Начни новый 👇",
            reply_markup=spheres_keyboard()
        )
        await callback.answer()
        return

    day = course["current_day"]
    await set_user_mode(user_id, f"beliefs_day_{day}")
    sphere_name = SPHERES.get(course["sphere"], "")

    await safe_edit_text(callback.message, 
        f"*День {day} из {COURSE_DAYS}* — {sphere_name}\n\n"
        f"Продолжаем 🌱\n\nЧто хочешь написать?",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "beliefs_next_day")
async def next_day(callback: CallbackQuery):
    user_id = callback.from_user.id
    course = await get_active_course(user_id)
    if not course:
        await callback.answer("Курс не найден")
        return

    current_day = course["current_day"]
    next_day_num = current_day + 1

    if next_day_num > COURSE_DAYS:
        await update_course(user_id, completed=1)
        await set_user_mode(user_id, "menu")
        await safe_edit_text(callback.message, 
            "🎉 *Курс завершён!*\n\nТы прошла все 7 дней. Это большая работа.\n\n"
            "Хочешь начать курс по другой сфере?",
            parse_mode="Markdown",
            reply_markup=spheres_keyboard()
        )
        await callback.answer()
        return

    # Сохраняем ключевые данные перед переходом на новый день
    context = await get_beliefs_context(user_id)
    sphere_name = SPHERES.get(course["sphere"], "")

    if current_day == 1 and not course.get("belief"):
        belief = await extract_belief_from_context(context, sphere_name)
        await update_course(user_id, belief=belief, current_day=next_day_num, context="[]", last_day_at=datetime.now())
    elif current_day == 2 and not course.get("subpersonality"):
        subpersonality = await extract_subpersonality(context)
        await update_course(user_id, subpersonality=subpersonality, current_day=next_day_num, context="[]", last_day_at=datetime.now())
    elif current_day == 4 and not course.get("new_belief"):
        new_belief = await extract_new_belief(context)
        await update_course(user_id, new_belief=new_belief, current_day=next_day_num, context="[]", last_day_at=datetime.now())
    else:
        await update_course(user_id, current_day=next_day_num, context="[]", last_day_at=datetime.now())

    await set_user_mode(user_id, f"beliefs_day_{next_day_num}")

    course = await get_active_course(user_id)
    user = await get_user(user_id)
    name = user.get("user_name_custom") or user.get("first_name") or "дорогая"

    day_titles = {
        1: "Диагностика",
        2: "Знакомство с субличностью",
        3: "Диалог с субличностью",
        4: "Переписываем убеждение",
        5: "Телесная практика",
        6: "Реальный шаг",
        7: "Итоги и трекер"
    }

    await safe_edit_text(callback.message, 
        f"*День {next_day_num} из {COURSE_DAYS}* — {day_titles.get(next_day_num, '')}\n\n_пишу тебе..._",
        parse_mode="Markdown"
    )

    response = await generate_day_response(next_day_num, course, name, [], "начнём")
    new_context = [{"role": "assistant", "content": response}]
    await save_beliefs_context(user_id, new_context)

    await safe_edit_text(callback.message, 
        f"*День {next_day_num} из {COURSE_DAYS}* — {day_titles.get(next_day_num, '')}\n\n{response}",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "beliefs_buy")
async def buy_beliefs(callback: CallbackQuery):
    kaspi_phone = os.getenv("KASPI_PHONE", "+7 XXX XXX XX XX")
    await safe_edit_text(callback.message, 
        f"💳 *Оплата курса «Проработка убеждений»*\n\n"
        f"Стоимость: *{BELIEFS_COURSE_PRICE} ₸*\n\n"
        f"Переведи на Kaspi:\n*{kaspi_phone}*\n\n"
        f"В комментарии напиши: *убеждения*\n\n"
        f"После оплаты напиши мне:\n"
        f"💬 WhatsApp: +77053458458\n"
        f"Открою доступ в течение часа 🙏",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Назад", callback_data="beliefs_menu")
        ]])
    )
    await callback.answer()


# ──────────────────────────────────────────────
# ОСНОВНОЙ ХЭНДЛЕР СООБЩЕНИЙ В КУРСЕ
# ──────────────────────────────────────────────

async def handle_beliefs_message(message: Message, mode: str):
    """Вызывается из main_handler когда mode начинается с 'beliefs_day_'"""
    user_id = message.from_user.id

    try:
        day = int(mode.replace("beliefs_day_", ""))
    except ValueError:
        return

    course = await get_active_course(user_id)
    if not course:
        await message.answer("Курс не найден. Начни заново 👇", reply_markup=spheres_keyboard())
        return

    user = await get_user(user_id)
    name = user.get("user_name_custom") or user.get("first_name") or "дорогая"

    context = await get_beliefs_context(user_id)
    context.append({"role": "user", "content": message.text})

    await message.answer("_думаю..._", parse_mode="Markdown")

    response = await generate_day_response(day, course, name, context, message.text)

    context.append({"role": "assistant", "content": response})
    await save_beliefs_context(user_id, context)

    # Проверяем достаточно ли диалога для перехода на следующий день
    user_messages_today = sum(1 for m in context if m["role"] == "user")
    show_next = user_messages_today >= 3  # после 3 сообщений предлагаем перейти дальше

    if show_next and day < COURSE_DAYS:
        await message.answer(
            response,
            reply_markup=next_day_keyboard()
        )
    elif day == COURSE_DAYS and show_next:
        await update_course(user_id, completed=1)
        await set_user_mode(user_id, "menu")
        await message.answer(
            response + "\n\n🎉 *Курс завершён! Ты молодец.*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔄 Новая сфера", callback_data="beliefs_menu"),
                InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu")
            ]])
        )
    else:
        await message.answer(response)
