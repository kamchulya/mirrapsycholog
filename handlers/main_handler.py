import random
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from models.database import (
    get_or_create_user, get_user, update_user, get_user_state,
    set_user_mode, save_context, get_context, clear_context,
    save_dialog, get_week_dialogs, can_use_bot, increment_message_count,
    save_diary_entry
)
from services.ai_service import (
    chat_psychologist, get_iching_reading, get_mak_response,
    get_numerology_reading, get_meditation, generate_weekly_report,
    detect_emotion
)
from utils.keyboards import (
    main_menu, meditation_menu, diary_menu, iching_confirm,
    mak_draw, back_to_menu, continue_or_menu, subscribe_keyboard, mood_keyboard
)

router = Router()
logger = logging.getLogger(__name__)

# МАК-карты — набор образных описаний
MAK_CARDS = [
    ("Старый маяк в тумане", "🏮"),
    ("Девочка с воздушными шарами", "🎈"),
    ("Дерево с корнями над обрывом", "🌳"),
    ("Две дороги в лесу", "🛤️"),
    ("Птица, покидающая клетку", "🦅"),
    ("Женщина смотрит в зеркало", "🪞"),
    ("Мост через бурную реку", "🌉"),
    ("Руки, сажающие семя", "🌱"),
    ("Звёздное небо над горами", "🌌"),
    ("Закрытая дверь с ключом", "🚪"),
    ("Танцующая фигура в тени", "💃"),
    ("Лодка без вёсел на озере", "⛵"),
]

MEDITATION_TYPES = {
    "med_anxiety": ("Отпускание тревоги и контроля", "тревога"),
    "med_energy": ("Восстановление энергии", "усталость"),
    "med_anger": ("Трансформация злости в силу", "злость"),
    "med_new_self": ("Создание нового Я по методу Диспензы", "нейтральное"),
    "med_abundance": ("Квантовое изобилие и деньги", "нейтральное"),
    "med_love": ("Исцеление отношений и открытие сердца", "нейтральное"),
    "med_wise": ("Встреча с внутренним мудрецом", "нейтральное"),
    "med_healing": ("Исцеление светом — клеточное обновление", "нейтральное"),
}


# ──────────────────────────────────────────────
# СТАРТ И ОНБОРДИНГ
# ──────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message):
    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    await set_user_mode(message.from_user.id, "menu")
    await clear_context(message.from_user.id)

    name = message.from_user.first_name or "дорогая"

    await message.answer(
        f"Привет, {name}! 🌙\n\n"
        f"Я — *Mirra*, твоё личное пространство тишины и честных ответов.\n"
        f"Когда мир вокруг шумит — я помогу услышать себя.\n\n"
        f"*Что я умею:*\n"
        f"🧠 *Психолог* — разобраться в ситуации через вопросы\n"
        f"🔮 *И-Цзин* — мудрость древней книги перемен\n"
        f"🃏 *МАК-карты* — работа с подсознанием через образы\n"
        f"🔢 *Нумерология* — узнать себя глубже\n"
        f"🧘 *Медитации* — практики Диспензы и визуализации\n"
        f"📖 *Дневник* — я помню всё и делаю еженедельный отчёт\n\n"
        f"Что сделаем сегодня? 💜",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await set_user_mode(message.from_user.id, "menu")
    await message.answer("Главное меню 🏠", reply_markup=main_menu())


# ──────────────────────────────────────────────
# ОБРАБОТКА КНОПОК МЕНЮ
# ──────────────────────────────────────────────

@router.callback_query(F.data == "back_menu")
async def back_to_main_menu(callback: CallbackQuery):
    await set_user_mode(callback.from_user.id, "menu")
    await clear_context(callback.from_user.id)
    await callback.message.edit_text(
        "Главное меню 🏠\n\nЧто сделаем сегодня?",
        reply_markup=main_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "mode_psychologist")
async def start_psychologist(callback: CallbackQuery):
    await set_user_mode(callback.from_user.id, "psychologist")
    await clear_context(callback.from_user.id)
    await callback.message.edit_text(
        "🧠 *Режим: Психолог*\n\n"
        "Я здесь, чтобы выслушать тебя и помочь разобраться в ситуации.\n"
        "Я не буду давать готовых советов — только задавать вопросы, "
        "которые помогут тебе найти ответ самой.\n\n"
        "Расскажи — что сейчас происходит? Что тебя беспокоит?",
        parse_mode="Markdown",
        reply_markup=back_to_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "mode_iching")
async def start_iching(callback: CallbackQuery):
    await set_user_mode(callback.from_user.id, "iching_question")
    await callback.message.edit_text(
        "🔮 *Гадание И-Цзин*\n\n"
        "Книга Перемен отвечает на вопросы о жизни, выборе и пути.\n\n"
        "Сформулируй свой вопрос чётко и от первого лица.\n"
        "Например: _«Стоит ли мне сменить работу?»_ или "
        "_«Как развиваются мои отношения с мужем?»_\n\n"
        "Напиши свой вопрос 👇",
        parse_mode="Markdown",
        reply_markup=back_to_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "iching_throw")
async def throw_iching(callback: CallbackQuery):
    user_state = await get_user_state(callback.from_user.id)
    question = user_state.get("context", "[]")

    import json
    ctx = json.loads(question) if question else []
    user_question = ""
    for msg in reversed(ctx):
        if msg.get("role") == "user":
            user_question = msg.get("content", "")
            break

    await callback.message.edit_text("🪙 Бросаю монеты...\n\n_Думай о своём вопросе..._", parse_mode="Markdown")

    hexagram = random.randint(1, 64)

    await callback.message.answer("⏳ Толкую гексаграмму...")

    response = await get_iching_reading(user_question or "Что важно знать мне сейчас?", hexagram)

    await save_dialog(
        user_id=callback.from_user.id,
        mode="iching",
        user_msg=user_question,
        bot_response=response
    )

    await callback.message.answer(
        f"🔮 *Гексаграмма №{hexagram}*\n\n{response}",
        parse_mode="Markdown",
        reply_markup=back_to_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "mode_mak")
async def start_mak(callback: CallbackQuery):
    await set_user_mode(callback.from_user.id, "mak_question")
    await callback.message.edit_text(
        "🃏 *МАК-карты — работа с подсознанием*\n\n"
        "Метафорические карты обращаются напрямую к твоему "
        "внутреннему знанию, минуя логику.\n\n"
        "Сформулируй вопрос или ситуацию, которую хочешь исследовать. "
        "Или просто напиши — и мы вытянем карту.",
        parse_mode="Markdown",
        reply_markup=mak_draw()
    )
    await callback.answer()


@router.callback_query(F.data == "mak_draw")
async def draw_mak_card(callback: CallbackQuery):
    card_name, card_emoji = random.choice(MAK_CARDS)

    await set_user_mode(callback.from_user.id, "mak_dialog")
    await clear_context(callback.from_user.id)

    first_message = f"Расскажи мне — что ты видишь на этой карте? Какой образ, какие детали замечаешь?"
    context = [{"role": "assistant", "content": first_message}]
    await save_context(callback.from_user.id, context)

    await callback.message.edit_text(
        f"🃏 Твоя карта:\n\n"
        f"*{card_emoji} {card_name}*\n\n"
        f"{first_message}",
        parse_mode="Markdown",
        reply_markup=back_to_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "mode_numerology")
async def start_numerology(callback: CallbackQuery):
    await set_user_mode(callback.from_user.id, "numerology_date")
    await callback.message.edit_text(
        "🔢 *Нумерология*\n\n"
        "Числа рассказывают о твоей природе, талантах и жизненных задачах.\n\n"
        "Напиши свою *дату рождения* в формате ДД.ММ.ГГГГ\n"
        "Например: _15.03.1987_",
        parse_mode="Markdown",
        reply_markup=back_to_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "mode_meditation")
async def start_meditation(callback: CallbackQuery):
    await set_user_mode(callback.from_user.id, "meditation")
    await callback.message.edit_text(
        "🧘 *Медитации и визуализации*\n\n"
        "Выбери практику под своё состояние прямо сейчас:",
        parse_mode="Markdown",
        reply_markup=meditation_menu()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("med_"))
async def run_meditation(callback: CallbackQuery):
    med_data = MEDITATION_TYPES.get(callback.data)
    if not med_data:
        await callback.answer("Неизвестная медитация")
        return

    med_name, mood = med_data
    await callback.message.edit_text(
        f"🧘 *{med_name}*\n\n_Подготавливаю практику для тебя..._",
        parse_mode="Markdown"
    )

    response = await get_meditation(med_name, mood)

    await save_dialog(
        user_id=callback.from_user.id,
        mode="meditation",
        user_msg=f"Медитация: {med_name}",
        bot_response=response
    )

    await callback.message.edit_text(
        f"🧘 *{med_name}*\n\n{response}",
        parse_mode="Markdown",
        reply_markup=back_to_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "mode_diary")
async def open_diary(callback: CallbackQuery):
    await callback.message.edit_text(
        "📖 *Мой дневник*\n\n"
        "Здесь хранится всё, о чём мы говорили.\n"
        "Mirra помнит тебя и замечает твой путь 💜",
        parse_mode="Markdown",
        reply_markup=diary_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "diary_mood")
async def ask_mood(callback: CallbackQuery):
    await callback.message.edit_text(
        "😊 Как ты сейчас?",
        reply_markup=mood_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mood_"))
async def save_mood(callback: CallbackQuery):
    mood_map = {
        "mood_good": "😊 Хорошо",
        "mood_normal": "😐 Нормально",
        "mood_sad": "😔 Грустно",
        "mood_anxious": "😰 Тревожно",
        "mood_angry": "😤 Злюсь",
        "mood_tired": "😴 Устала",
    }
    mood = mood_map.get(callback.data, "нейтральное")

    await save_diary_entry(
        user_id=callback.from_user.id,
        entry_type="mood",
        content=mood,
        mood=mood
    )
    await update_user(callback.from_user.id, last_active=__import__('datetime').datetime.now().isoformat())

    responses = {
        "mood_good": "Как здорово! Держи это состояние 🌟 Чем хочешь заняться сегодня?",
        "mood_normal": "Нормально — это тоже хорошо. Иногда ровное состояние — это отдых 🌿",
        "mood_sad": "Грусть — это тоже часть тебя. Хочешь поговорить о том, что происходит? 💙",
        "mood_anxious": "Тревога говорит о том, что что-то важно для тебя. Хочешь разобраться? 🤍",
        "mood_angry": "Злость — это сила, которой пока не нашла применения. Хочешь трансформировать её? 🔥",
        "mood_tired": "Усталость — сигнал тела. Может, медитация на восстановление поможет? 💜",
    }

    text = responses.get(callback.data, "Записала твоё состояние 💜")

    await callback.message.edit_text(
        f"Записала: *{mood}*\n\n{text}",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "diary_week")
async def show_week_entries(callback: CallbackQuery):
    dialogs = await get_week_dialogs(callback.from_user.id)

    if not dialogs:
        await callback.message.edit_text(
            "📖 За эту неделю у нас ещё не было диалогов.\n\n"
            "Давай начнём? Выбери, с чего хочешь начать 💜",
            reply_markup=main_menu()
        )
        await callback.answer()
        return

    mode_names = {
        "psychologist": "🧠 Психолог",
        "iching": "🔮 И-Цзин",
        "mak": "🃏 МАК-карта",
        "numerology": "🔢 Нумерология",
        "meditation": "🧘 Медитация",
    }

    text = "📖 *Твоя неделя в Mirra:*\n\n"
    for d in dialogs[-7:]:
        date = d['created_at'][:10]
        mode = mode_names.get(d['mode'], d['mode'])
        preview = d['user_message'][:80] + ("..." if len(d['user_message']) > 80 else "")
        text += f"*{date}* {mode}\n_{preview}_\n\n"

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=diary_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "diary_report")
async def generate_report(callback: CallbackQuery):
    await callback.message.edit_text("📊 _Составляю твой отчёт за неделю..._", parse_mode="Markdown")

    dialogs = await get_week_dialogs(callback.from_user.id)
    user = await get_user(callback.from_user.id)
    name = user.get("first_name", "") if user else ""

    report = await generate_weekly_report(dialogs, name)

    await callback.message.edit_text(
        f"📊 *Твой еженедельный отчёт*\n\n{report}",
        parse_mode="Markdown",
        reply_markup=diary_menu()
    )
    await callback.answer()


# ──────────────────────────────────────────────
# ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ
# ──────────────────────────────────────────────

@router.message(F.text)
async def handle_message(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    # Проверяем доступ
    can_use, reason = await can_use_bot(user_id)
    if not can_use:
        await message.answer(
            "💜 Твой бесплатный период завершился.\n\n"
            "Оформи подписку, чтобы продолжить наш диалог.\n"
            "Mirra ждёт тебя 🌙",
            reply_markup=subscribe_keyboard()
        )
        return

    state = await get_user_state(user_id)
    mode = state.get("current_mode", "menu") if state else "menu"
    context = await get_context(user_id)

    # ─── ПСИХОЛОГ ───
    if mode == "psychologist":
        await message.chat.do("typing")
        await increment_message_count(user_id)

        user = await get_user(user_id)
        name = user.get("first_name", "") if user else ""

        response = await chat_psychologist(text, context, name)

        new_context = context + [
            {"role": "user", "content": text},
            {"role": "assistant", "content": response}
        ]
        await save_context(user_id, new_context)

        emotion = await detect_emotion(text)
        await save_dialog(user_id, "psychologist", text, response, emotion=emotion)

        await message.answer(response, reply_markup=continue_or_menu())

    # ─── И-ЦЗИ — вопрос ───
    elif mode == "iching_question":
        context = [{"role": "user", "content": text}]
        await save_context(user_id, context)
        await set_user_mode(user_id, "iching_ready")

        await message.answer(
            f"🔮 Твой вопрос принят:\n_«{text}»_\n\n"
            f"Сосредоточься на нём и брось монеты 🪙",
            parse_mode="Markdown",
            reply_markup=iching_confirm()
        )

    # ─── НУМЕРОЛОГИЯ — дата ───
    elif mode == "numerology_date":
        await set_user_mode(user_id, "numerology_name")
        # Сохраняем дату в контексте
        await save_context(user_id, [{"role": "user", "content": f"дата: {text}"}])

        await message.answer(
            f"Записала: *{text}* 📅\n\nТеперь напиши своё *имя* (как тебя зовут):",
            parse_mode="Markdown",
            reply_markup=back_to_menu()
        )

    elif mode == "numerology_name":
        await message.chat.do("typing")
        await increment_message_count(user_id)

        ctx = await get_context(user_id)
        birth_date = ""
        for msg in ctx:
            if "дата:" in msg.get("content", ""):
                birth_date = msg["content"].replace("дата:", "").strip()
                break

        response = await get_numerology_reading(birth_date, text)
        await save_dialog(user_id, "numerology", f"{birth_date} / {text}", response)
        await set_user_mode(user_id, "menu")

        await message.answer(
            f"🔢 *Нумерологический профиль*\n\n{response}",
            parse_mode="Markdown",
            reply_markup=back_to_menu()
        )

    # ─── МАК — диалог ───
    elif mode == "mak_dialog":
        await message.chat.do("typing")
        await increment_message_count(user_id)

        response = await get_mak_response(text, context)

        new_context = context + [
            {"role": "user", "content": text},
            {"role": "assistant", "content": response}
        ]
        await save_context(user_id, new_context)
        await save_dialog(user_id, "mak", text, response)

        await message.answer(response, reply_markup=continue_or_menu())

    # ─── МАК — начало (написали вопрос перед картой) ───
    elif mode == "mak_question":
        await save_context(user_id, [{"role": "user", "content": text}])
        await message.answer(
            f"Хорошо, держи это в уме 🃏\nТеперь вытяни карту:",
            reply_markup=mak_draw()
        )

    # ─── МЕНЮ — просто текст ───
    else:
        await message.answer(
            "Выбери, чем займёмся сегодня 💜",
            reply_markup=main_menu()
        )


@router.callback_query(F.data == "continue_dialog")
async def continue_dialog(callback: CallbackQuery):
    await callback.message.answer("Я слушаю тебя 💜")
    await callback.answer()


@router.callback_query(F.data == "subscribe")
async def handle_subscribe(callback: CallbackQuery):
    await callback.message.answer(
        "💜 *Подписка Mirra Pro — 3 000 ₸/месяц*\n\n"
        "Для оплаты напиши администратору: @mirra_support\n\n"
        "После оплаты тебе откроется полный доступ 🌙",
        parse_mode="Markdown",
        reply_markup=back_to_menu()
    )
    await callback.answer()
