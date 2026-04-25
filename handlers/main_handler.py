import random
import logging
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, URLInputFile
from aiogram.filters import CommandStart, Command

from models.database import (
    get_or_create_user, get_user, update_user, get_user_state,
    set_user_mode, save_context, get_context, clear_context,
    save_dialog, get_week_dialogs, get_month_dialogs, get_month_diary,
    can_use_bot, increment_message_count, save_diary_entry,
    save_memory, format_memories_for_prompt
)
from services.ai_service import (
    chat_psychologist, get_iching_reading, get_mak_response,
    get_numerology_main, get_numerology_period, get_numerology_matrix,
    get_numerology_extra, get_meditation, chat_diary, chat_followup,
    generate_weekly_report, detect_emotion, generate_diary_summary,
    generate_session_summary
)
from services.pdf_service import generate_diary_pdf
from utils.keyboards import (
    main_menu, iching_intro, iching_confirm, mak_intro, mak_draw,
    mak_after_card, numerology_menu, numerology_other, meditation_menu,
    diary_menu, diary_save_confirm, diary_followup, back_to_menu,
    continue_or_menu, subscribe_keyboard, mood_keyboard
)

router = Router()
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# МАК-КАРТЫ — реальные картинки
# Положи свои jpg/png в папку static/mak/
# Имена файлов = название карты
# ──────────────────────────────────────────────
MAK_CARDS = [
    ("Старый маяк в тумане", "mak_01.jpg"),
    ("Девочка с воздушными шарами", "mak_02.jpg"),
    ("Дерево с корнями над обрывом", "mak_03.jpg"),
    ("Две дороги в лесу", "mak_04.jpg"),
    ("Птица, покидающая клетку", "mak_05.jpg"),
    ("Женщина смотрит в зеркало", "mak_06.jpg"),
    ("Мост через бурную реку", "mak_07.jpg"),
    ("Руки, сажающие семя", "mak_08.jpg"),
    ("Звёздное небо над горами", "mak_09.jpg"),
    ("Закрытая дверь с ключом", "mak_10.jpg"),
    ("Танцующая фигура в тени", "mak_11.jpg"),
    ("Лодка без вёсел на озере", "mak_12.jpg"),
]

# ──────────────────────────────────────────────
# МЕДИТАЦИИ — YouTube ссылки
# ──────────────────────────────────────────────
MEDITATION_YOUTUBE = {
    "med_anxiety": {
        "name": "Снять тревогу и обрести покой",
        "mood": "тревога",
        "url": "https://www.youtube.com/watch?v=HGbeMBsBJas",
        "description": "Медитация Джо Диспензы — отпускание тревоги и страха"
    },
    "med_energy": {
        "name": "Восстановление энергии",
        "mood": "усталость",
        "url": "https://www.youtube.com/watch?v=La9S_wAaAF0",
        "description": "Медитация для восстановления жизненных сил"
    },
    "med_anger": {
        "name": "Трансформация злости в силу",
        "mood": "злость",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "description": "Практика трансформации негативных эмоций"
    },
    "med_new_self": {
        "name": "Создание нового Я",
        "mood": "нейтральное",
        "url": "https://www.youtube.com/watch?v=La9S_wAaAF0",
        "description": "Джо Диспенза — визуализация нового себя"
    },
    "med_abundance": {
        "name": "Квантовое изобилие и деньги",
        "mood": "нейтральное",
        "url": "https://www.youtube.com/watch?v=HGbeMBsBJas",
        "description": "Медитация на открытие потока изобилия"
    },
    "med_love": {
        "name": "Исцеление отношений",
        "mood": "нейтральное",
        "url": "https://www.youtube.com/watch?v=La9S_wAaAF0",
        "description": "Открытие сердца и исцеление в отношениях"
    },
    "med_wise": {
        "name": "Встреча с внутренним мудрецом",
        "mood": "нейтральное",
        "url": "https://www.youtube.com/watch?v=HGbeMBsBJas",
        "description": "Визуализация — диалог с мудрой частью себя"
    },
    "med_healing": {
        "name": "Исцеление светом",
        "mood": "нейтральное",
        "url": "https://www.youtube.com/watch?v=La9S_wAaAF0",
        "description": "Клеточное обновление — практика исцеляющего света"
    },
}


# ──────────────────────────────────────────────
# СТАРТ
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

    # Если онбординг уже пройден — просто меню
    if user.get("onboarding_done"):
        name = user.get("user_name_custom") or user.get("first_name") or "дорогая"
        await message.answer(
            f"С возвращением, {name}! 🌙\n\nЧто сделаем сегодня?",
            reply_markup=main_menu()
        )
        return

    # Новый пользователь — онбординг
    await set_user_mode(message.from_user.id, "onboarding_name")
    await message.answer(
        "Привет! 🌙\n\n"
        "Я — *Mirra*, твоё личное пространство тишины и честных ответов.\n"
        "Когда мир вокруг шумит — я помогу услышать себя.\n\n"
        "*Как тебя зовут?* Напиши своё имя 👇",
        parse_mode="Markdown"
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await set_user_mode(message.from_user.id, "menu")
    await message.answer("Главное меню 🏠", reply_markup=main_menu())


# ──────────────────────────────────────────────
# ОНБОРДИНГ — имя
# ──────────────────────────────────────────────

async def finish_onboarding(message: Message, name: str):
    """Завершаем онбординг — показываем возможности и предупреждение"""
    await update_user(
        message.from_user.id,
        user_name_custom=name,
        onboarding_done=1
    )
    await set_user_mode(message.from_user.id, "menu")

    await message.answer(
        f"Очень приятно, *{name}*! 💜\n\n"
        f"*Что я умею:*\n"
        f"🧠 *Психолог* — разобраться в ситуации через вопросы\n"
        f"🔮 *И-Цзин* — мудрость древней книги перемен\n"
        f"🃏 *МАК-карты* — работа с подсознанием через образы\n"
        f"🔢 *Нумерология* — узнать себя глубже\n"
        f"🧘 *Медитации* — практики Диспензы и визуализации\n"
        f"📖 *Дневник* — я запоминаю наши разговоры\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📌 *Важно про дневник*\n\n"
        f"Все записи и наши диалоги хранятся *30 дней*.\n"
        f"1-го числа каждого месяца я автоматически отправлю тебе "
        f"красивый PDF со всем, что было — сохрани его себе как личный архив.\n\n"
        f"Что сделаем сегодня? 💜",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )


@router.callback_query(F.data == "back_menu")
async def back_to_main_menu(callback: CallbackQuery):
    await set_user_mode(callback.from_user.id, "menu")
    await clear_context(callback.from_user.id)
    await callback.message.edit_text("Главное меню 🏠\n\nЧто сделаем сегодня?", reply_markup=main_menu())
    await callback.answer()


# ──────────────────────────────────────────────
# ПСИХОЛОГ
# ──────────────────────────────────────────────

@router.callback_query(F.data == "mode_psychologist")
async def start_psychologist(callback: CallbackQuery):
    await set_user_mode(callback.from_user.id, "psychologist")
    await clear_context(callback.from_user.id)
    await callback.message.edit_text(
        "🧠 *Режим: Психолог*\n\n"
        "Я здесь, чтобы выслушать тебя. Буду не советовать, "
        "а задавать вопросы — чтобы ты сама нашла ответ.\n\n"
        "Расскажи — что сейчас происходит?",
        parse_mode="Markdown",
        reply_markup=back_to_menu()
    )
    await callback.answer()


# ──────────────────────────────────────────────
# И-ЦЗИ
# ──────────────────────────────────────────────

@router.callback_query(F.data == "mode_iching")
async def start_iching_intro(callback: CallbackQuery):
    await set_user_mode(callback.from_user.id, "menu")
    await callback.message.edit_text(
        "🔮 *Гадание И-Цзин*\n\n"
        "Книга Перемен — древнейший памятник китайской мысли (более 3000 лет). "
        "Это одновременно философский трактат и система предсказания.\n\n"
        "В основе И-Цзин лежит идея о том, что *всё в мире находится в постоянном движении*. "
        "Зная законы этих перемен, можно понять — в какой точке пути ты сейчас "
        "и куда дует «ветер судьбы».\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "📌 *Как формулировать вопрос*\n\n"
        "Вопрос должен быть *открытым*. Не «да или нет?», а:\n"
        "• «Каков характер текущей ситуации?»\n"
        "• «На что обратить внимание в отношениях с...?»\n"
        "• «Каковы перспективы моего проекта?»\n"
        "• «Что важно понять мне прямо сейчас?»\n\n"
        "Сосредоточься на своём вопросе — и нажми кнопку ниже 👇",
        parse_mode="Markdown",
        reply_markup=iching_intro()
    )
    await callback.answer()


@router.callback_query(F.data == "iching_start")
async def iching_ask_question(callback: CallbackQuery):
    await set_user_mode(callback.from_user.id, "iching_question")
    await callback.message.edit_text(
        "🔮 Напиши свой вопрос к Книге Перемен 👇\n\n"
        "_Помни: открытый вопрос даёт глубокий ответ_",
        parse_mode="Markdown",
        reply_markup=back_to_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "iching_throw")
async def throw_iching(callback: CallbackQuery):
    import json
    ctx = await get_context(callback.from_user.id)
    user_question = ""
    for msg in reversed(ctx):
        if msg.get("role") == "user":
            user_question = msg.get("content", "")
            break

    await callback.message.edit_text(
        "🪙 *Бросаю монеты...*\n\n_Думай о своём вопросе..._",
        parse_mode="Markdown"
    )

    hexagram = random.randint(1, 64)
    await callback.message.answer("⏳ _Толкую гексаграмму..._", parse_mode="Markdown")

    response = await get_iching_reading(user_question or "Что важно знать мне сейчас?", hexagram)
    await save_dialog(user_id=callback.from_user.id, mode="iching", user_msg=user_question, bot_response=response)

    await callback.message.answer(
        f"🔮 *Гексаграмма №{hexagram}*\n\n{response}",
        parse_mode="Markdown",
        reply_markup=back_to_menu()
    )
    await callback.answer()


# ──────────────────────────────────────────────
# МАК-КАРТЫ
# ──────────────────────────────────────────────

@router.callback_query(F.data == "mode_mak")
async def start_mak_intro(callback: CallbackQuery):
    await callback.message.edit_text(
        "🃏 *МАК-карты — работа с подсознанием*\n\n"
        "МАК (Метафорические Ассоциативные Карты) — это инструмент психологов "
        "и коучей для работы с подсознанием. Это не гадание и не магия.\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "🧠 *Как это работает*\n\n"
        "Когда мы смотрим на неоднозначную картинку, мозг интерпретирует её "
        "через *актуальное внутреннее состояние*.\n\n"
        "Если ты в стрессе — на картинке с морем увидишь угрозу.\n"
        "Если в предвкушении — увидишь энергию и мощь.\n\n"
        "Это позволяет обойти внутреннего критика и вытащить "
        "истинные чувства из подсознания.\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "📌 *Три закона МАК*\n\n"
        "1. *Ты — автор смысла.* Никто не может сказать, что значит твоя карта.\n"
        "2. *Неправильных ответов нет.* Всё что приходит — правильно.\n"
        "3. *Вытягивай под конкретный запрос.* Сформулируй вопрос перед картой.\n\n"
        "Готова? 👇",
        parse_mode="Markdown",
        reply_markup=mak_intro()
    )
    await callback.answer()


@router.callback_query(F.data == "mak_go")
async def mak_ask_question(callback: CallbackQuery):
    await set_user_mode(callback.from_user.id, "mak_question")
    await callback.message.edit_text(
        "🃏 Сформулируй свой вопрос или ситуацию.\n\n"
        "Например: _«Что мешает мне двигаться вперёд?»_ "
        "или _«Как мне улучшить отношения с...?»_\n\n"
        "Или просто нажми «Вытянуть карту» без вопроса 👇",
        parse_mode="Markdown",
        reply_markup=mak_draw()
    )
    await callback.answer()


@router.callback_query(F.data == "mak_draw")
async def draw_mak_card(callback: CallbackQuery):
    card_name, card_file = random.choice(MAK_CARDS)

    await set_user_mode(callback.from_user.id, "mak_dialog")
    await clear_context(callback.from_user.id)

    # Сохраняем название карты в контексте
    await save_context(callback.from_user.id, [
        {"role": "assistant", "content": f"[Карта: {card_name}]"}
    ])

    # Пробуем отправить картинку
    card_path = f"/home/claude/mirra/static/mak/{card_file}"

    caption = (
        f"🃏 *Твоя карта:*\n\n"
        f"*{card_name}*\n\n"
        f"Посмотри внимательно на эту карту...\n"
        f"Дай себе момент просто _почувствовать_ её.\n\n"
        f"Когда будешь готова — нажми кнопку ниже 👇"
    )

    try:
        if os.path.exists(card_path):
            photo = FSInputFile(card_path)
            await callback.message.answer_photo(
                photo=photo,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=mak_after_card()
            )
        else:
            # Картинка не загружена — отправляем текстом с инструкцией
            await callback.message.edit_text(
                f"🃏 *Твоя карта:*\n\n"
                f"*{card_name}*\n\n"
                f"_(Представь этот образ перед собой — "
                f"закрой глаза и визуализируй его несколько секунд)_\n\n"
                f"Когда будешь готова — нажми кнопку ниже 👇",
                parse_mode="Markdown",
                reply_markup=mak_after_card()
            )
    except Exception as e:
        logger.error(f"Ошибка отправки карты: {e}")
        await callback.message.edit_text(
            f"🃏 *Твоя карта: {card_name}*\n\n"
            f"Посмотри на этот образ...\n\n"
            f"Готова рассказать что чувствуешь? 👇",
            parse_mode="Markdown",
            reply_markup=mak_after_card()
        )

    await callback.answer()


@router.callback_query(F.data == "mak_ready_talk")
async def mak_start_dialog(callback: CallbackQuery):
    ctx = await get_context(callback.from_user.id)
    card_name = ""
    for msg in ctx:
        if "[Карта:" in msg.get("content", ""):
            card_name = msg["content"].replace("[Карта:", "").replace("]", "").strip()
            break

    first_question = "Расскажи мне — что ты видишь на этой карте? Опиши детально: что происходит, кто или что изображено, какие детали замечаешь?"

    new_ctx = ctx + [{"role": "assistant", "content": first_question}]
    await save_context(callback.from_user.id, new_ctx)

    await callback.message.answer(
        first_question,
        reply_markup=back_to_menu()
    )
    await callback.answer()


# ──────────────────────────────────────────────
# НУМЕРОЛОГИЯ
# ──────────────────────────────────────────────

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


@router.callback_query(F.data == "num_period")
async def numerology_period(callback: CallbackQuery):
    ctx = await get_context(callback.from_user.id)
    birth_date, name = _get_num_data_from_context(ctx)
    if not birth_date:
        await callback.answer("Сначала сделай основной расчёт 🔢")
        return

    await callback.message.answer("📅 _Рассчитываю числа текущего периода..._", parse_mode="Markdown")
    response = await get_numerology_period(birth_date, name)
    await callback.message.answer(response, parse_mode="Markdown", reply_markup=numerology_menu())
    await callback.answer()


@router.callback_query(F.data == "num_matrix")
async def numerology_matrix(callback: CallbackQuery):
    ctx = await get_context(callback.from_user.id)
    birth_date, name = _get_num_data_from_context(ctx)
    if not birth_date:
        await callback.answer("Сначала сделай основной расчёт 🔢")
        return

    await callback.message.answer("🔢 _Строю матрицу судьбы..._", parse_mode="Markdown")
    response = await get_numerology_matrix(birth_date, name)
    await callback.message.answer(response, parse_mode="Markdown", reply_markup=numerology_menu())
    await callback.answer()


@router.callback_query(F.data == "num_other")
async def numerology_other_menu(callback: CallbackQuery):
    await callback.message.answer(
        "🔄 *Другие числа* — выбери что рассчитать:",
        parse_mode="Markdown",
        reply_markup=numerology_other()
    )
    await callback.answer()


@router.callback_query(F.data.in_({"num_soul", "num_personality", "num_destiny"}))
async def numerology_extra(callback: CallbackQuery):
    ctx = await get_context(callback.from_user.id)
    birth_date, name = _get_num_data_from_context(ctx)
    if not birth_date:
        await callback.answer("Сначала сделай основной расчёт 🔢")
        return

    type_map = {"num_soul": "soul", "num_personality": "personality", "num_destiny": "destiny"}
    await callback.message.answer("✨ _Рассчитываю..._", parse_mode="Markdown")
    response = await get_numerology_extra(birth_date, name, type_map[callback.data])
    await callback.message.answer(response, parse_mode="Markdown", reply_markup=numerology_menu())
    await callback.answer()


@router.callback_query(F.data == "num_back")
async def num_back(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔢 Что ещё рассчитаем?",
        reply_markup=numerology_menu()
    )
    await callback.answer()


def _get_num_data_from_context(ctx: list) -> tuple:
    """Достаём дату и имя из контекста нумерологии"""
    birth_date = ""
    name = ""
    for msg in ctx:
        content = msg.get("content", "")
        if "дата:" in content:
            birth_date = content.replace("дата:", "").strip()
        if "имя:" in content:
            name = content.replace("имя:", "").strip()
    return birth_date, name


# ──────────────────────────────────────────────
# МЕДИТАЦИИ
# ──────────────────────────────────────────────

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
    med_data = MEDITATION_YOUTUBE.get(callback.data)
    if not med_data:
        await callback.answer("Неизвестная медитация")
        return

    await callback.message.edit_text(
        f"🧘 *{med_data['name']}*\n\n_Подготавливаю практику..._",
        parse_mode="Markdown"
    )

    # Генерируем текстовую медитацию
    response = await get_meditation(med_data['name'], med_data['mood'])

    await save_dialog(
        user_id=callback.from_user.id,
        mode="meditation",
        user_msg=f"Медитация: {med_data['name']}",
        bot_response=response
    )

    # Отправляем текст медитации
    await callback.message.edit_text(
        f"🧘 *{med_data['name']}*\n\n{response}",
        parse_mode="Markdown"
    )

    # Отдельным сообщением — ссылка на YouTube
    await callback.message.answer(
        f"🎧 *Хочешь погрузиться глубже?*\n\n"
        f"{med_data['description']}\n\n"
        f"👉 [Слушать медитацию на YouTube]({med_data['url']})",
        parse_mode="Markdown",
        reply_markup=back_to_menu()
    )
    await callback.answer()


# ──────────────────────────────────────────────
# ДНЕВНИК
# ──────────────────────────────────────────────

@router.callback_query(F.data == "mode_diary")
async def open_diary(callback: CallbackQuery):
    user_id = callback.from_user.id

    # Проверяем — есть ли незакрытая тема из прошлых диалогов
    dialogs = await get_week_dialogs(user_id)
    last_topic = None
    for d in reversed(dialogs):
        if d['mode'] == 'psychologist' and d.get('user_message'):
            last_topic = d['user_message'][:80]
            break

    if last_topic:
        await callback.message.edit_text(
            f"📖 *Мой дневник*\n\n"
            f"Кстати, недавно ты говорила о:\n"
            f"_«{last_topic}...»_\n\n"
            f"Хочешь зафиксировать как всё прошло? "
            f"Или просто открой дневник 👇",
            parse_mode="Markdown",
            reply_markup=diary_followup()
        )
    else:
        await callback.message.edit_text(
            "📖 *Мой дневник*\n\nЗдесь хранится всё, о чём мы говорили.\nMirra помнит тебя 💜",
            parse_mode="Markdown",
            reply_markup=diary_menu()
        )
    await callback.answer()


@router.callback_query(F.data == "diary_followup_yes")
async def diary_followup_start(callback: CallbackQuery):
    dialogs = await get_week_dialogs(callback.from_user.id)
    last_topic = ""
    for d in reversed(dialogs):
        if d['mode'] == 'psychologist':
            last_topic = d['user_message'][:100]
            break

    await set_user_mode(callback.from_user.id, "diary_followup")
    await save_context(callback.from_user.id, [
        {"role": "system", "content": f"topic:{last_topic}"}
    ])

    await callback.message.edit_text(
        f"💬 Расскажи — как в итоге разрешилась ситуация?\n\n"
        f"_Мне интересно всё — и что случилось, и как ты себя чувствуешь сейчас._",
        parse_mode="Markdown",
        reply_markup=back_to_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "diary_write")
async def diary_write_start(callback: CallbackQuery):
    await set_user_mode(callback.from_user.id, "diary_dialog")
    await clear_context(callback.from_user.id)

    await callback.message.edit_text(
        "📝 *Записываем твой день*\n\n"
        "Что сегодня было самым важным для тебя?\n\n"
        "_Можешь написать всё что угодно — я здесь._",
        parse_mode="Markdown",
        reply_markup=back_to_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "diary_save_yes")
async def diary_save(callback: CallbackQuery):
    ctx = await get_context(callback.from_user.id)
    entries = [m["content"] for m in ctx if m.get("role") == "user"]

    if entries:
        summary = await generate_diary_summary(entries)
        await save_diary_entry(
            user_id=callback.from_user.id,
            entry_type="day",
            content=summary
        )
        await callback.message.edit_text(
            f"✅ *Сохранено в дневник!*\n\n_{summary}_\n\n"
            f"Хорошего вечера 💜",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
    await clear_context(callback.from_user.id)
    await set_user_mode(callback.from_user.id, "menu")
    await callback.answer()


@router.callback_query(F.data == "diary_add_more")
async def diary_add_more(callback: CallbackQuery):
    await callback.message.edit_text(
        "Продолжай — я слушаю 💜",
        reply_markup=back_to_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "diary_mood")
async def ask_mood(callback: CallbackQuery):
    await callback.message.edit_text("😊 Как ты сейчас?", reply_markup=mood_keyboard())
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
    await save_diary_entry(user_id=callback.from_user.id, entry_type="mood", content=mood, mood=mood)

    responses = {
        "mood_good": "Как здорово! Держи это состояние 🌟",
        "mood_normal": "Нормально — это тоже хорошо. Ровное состояние — это отдых 🌿",
        "mood_sad": "Грусть — это тоже часть тебя. Хочешь поговорить? 💙",
        "mood_anxious": "Тревога говорит о том, что что-то важно для тебя. Разберёмся? 🤍",
        "mood_angry": "Злость — это сила без применения. Трансформируем? 🔥",
        "mood_tired": "Усталость — сигнал тела. Может, медитация на восстановление? 💜",
    }
    await callback.message.edit_text(
        f"Записала: *{mood}*\n\n{responses.get(callback.data, '💜')}",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "diary_week")
async def show_week_entries(callback: CallbackQuery):
    dialogs = await get_week_dialogs(callback.from_user.id)
    if not dialogs:
        await callback.message.edit_text(
            "📖 За эту неделю у нас ещё не было диалогов.\n\nДавай начнём? 💜",
            reply_markup=main_menu()
        )
        await callback.answer()
        return

    mode_names = {
        "psychologist": "🧠", "iching": "🔮",
        "mak": "🃏", "numerology": "🔢", "meditation": "🧘"
    }
    text = "📖 *Твоя неделя в Mirra:*\n\n"
    for d in dialogs[-7:]:
        date = d['created_at'][:10]
        icon = mode_names.get(d['mode'], "💬")
        preview = d['user_message'][:70] + ("..." if len(d['user_message']) > 70 else "")
        text += f"*{date}* {icon}\n_{preview}_\n\n"

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=diary_menu())
    await callback.answer()


@router.callback_query(F.data == "diary_report")
async def generate_report(callback: CallbackQuery):
    await callback.message.edit_text("📊 _Составляю твой отчёт за неделю..._", parse_mode="Markdown")
    dialogs = await get_week_dialogs(callback.from_user.id)
    user = await get_user(callback.from_user.id)
    name = user.get("first_name", "") if user else ""
    report = await generate_weekly_report(dialogs, name)
    await callback.message.edit_text(
        f"📊 *Твоя неделя в Mirra*\n\n{report}",
        parse_mode="Markdown",
        reply_markup=diary_menu()
    )
    await callback.answer()


# ──────────────────────────────────────────────
# ТЕКСТОВЫЕ СООБЩЕНИЯ
# ──────────────────────────────────────────────

@router.message(F.text)
async def handle_message(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    can_use, reason = await can_use_bot(user_id)
    if not can_use:
        await message.answer(
            "💜 Твой бесплатный период завершился.\n\n"
            "Оформи подписку, чтобы продолжить 🌙",
            reply_markup=subscribe_keyboard()
        )
        return

    state = await get_user_state(user_id)
    mode = state.get("current_mode", "menu") if state else "menu"
    context = await get_context(user_id)

    # ОНБОРДИНГ — принимаем имя
    if mode == "onboarding_name":
        await finish_onboarding(message, text)
        return

    # ПСИХОЛОГ
    if mode == "psychologist":
        await message.chat.do("typing")
        await increment_message_count(user_id)
        user = await get_user(user_id)
        name = user.get("user_name_custom") or user.get("first_name", "") if user else ""

        # Подгружаем память — краткие резюме прошлых сессий
        memories = await format_memories_for_prompt(user_id)

        response = await chat_psychologist(text, context, name, memories)
        new_ctx = context + [{"role": "user", "content": text}, {"role": "assistant", "content": response}]
        await save_context(user_id, new_ctx)
        emotion = await detect_emotion(text)
        await save_dialog(user_id, "psychologist", text, response, emotion=emotion)

        # После 3+ сообщений — сохраняем резюме сессии в память
        user_msgs = [m["content"] for m in new_ctx if m.get("role") == "user"]
        if len(user_msgs) == 3:
            summary = await generate_session_summary("psychologist", user_msgs)
            await save_memory(user_id, summary, "psychologist")

        await message.answer(response, reply_markup=continue_or_menu())

    # И-ЦЗИ — принимаем вопрос
    elif mode == "iching_question":
        await save_context(user_id, [{"role": "user", "content": text}])
        await set_user_mode(user_id, "iching_ready")
        await message.answer(
            f"🔮 Твой вопрос:\n_«{text}»_\n\nСосредоточься на нём и брось монеты 🪙",
            parse_mode="Markdown",
            reply_markup=iching_confirm()
        )

    # НУМЕРОЛОГИЯ — дата
    elif mode == "numerology_date":
        await set_user_mode(user_id, "numerology_name")
        await save_context(user_id, [{"role": "user", "content": f"дата:{text}"}])
        await message.answer(
            f"Записала: *{text}* 📅\n\nТеперь напиши своё *имя*:",
            parse_mode="Markdown",
            reply_markup=back_to_menu()
        )

    # НУМЕРОЛОГИЯ — имя → основной расчёт
    elif mode == "numerology_name":
        await message.chat.do("typing")
        await increment_message_count(user_id)
        birth_date = ""
        for msg in context:
            if "дата:" in msg.get("content", ""):
                birth_date = msg["content"].replace("дата:", "").strip()
                break

        response = await get_numerology_main(birth_date, text)

        # Сохраняем данные для дальнейших расчётов
        new_ctx = context + [{"role": "user", "content": f"имя:{text}"}]
        await save_context(user_id, new_ctx)
        await save_dialog(user_id, "numerology", f"{birth_date} / {text}", response)
        await set_user_mode(user_id, "numerology_done")

        await message.answer(
            f"🔢 *Нумерологический анализ*\n\n{response}",
            parse_mode="Markdown",
            reply_markup=numerology_menu()
        )

    # МАК — вопрос перед картой
    elif mode == "mak_question":
        await save_context(user_id, [{"role": "user", "content": text}])
        await message.answer(
            f"Хорошо, держи это в уме 🃏\nТеперь вытяни карту:",
            reply_markup=mak_draw()
        )

    # МАК — диалог вокруг карты
    elif mode == "mak_dialog":
        await message.chat.do("typing")
        await increment_message_count(user_id)
        card_name = ""
        for msg in context:
            if "[Карта:" in msg.get("content", ""):
                card_name = msg["content"].replace("[Карта:", "").replace("]", "").strip()
                break
        response = await get_mak_response(text, context, card_name)
        new_ctx = context + [{"role": "user", "content": text}, {"role": "assistant", "content": response}]
        await save_context(user_id, new_ctx)
        await save_dialog(user_id, "mak", text, response)
        await message.answer(response, reply_markup=continue_or_menu())

    # ДНЕВНИК — диалог
    elif mode == "diary_dialog":
        await message.chat.do("typing")
        response = await chat_diary(text, context)
        new_ctx = context + [{"role": "user", "content": text}, {"role": "assistant", "content": response}]
        await save_context(user_id, new_ctx)

        # Если контекст достаточно большой — предлагаем сохранить
        if len([m for m in new_ctx if m.get("role") == "user"]) >= 3:
            await message.answer(response, reply_markup=diary_save_confirm())
        else:
            await message.answer(response, reply_markup=back_to_menu())

    # ДНЕВНИК — фолоу-ап по старой теме
    elif mode == "diary_followup":
        await message.chat.do("typing")
        topic = ""
        for msg in context:
            if "topic:" in msg.get("content", ""):
                topic = msg["content"].replace("topic:", "").strip()
                break
        response = await chat_followup(text, context, topic)
        new_ctx = context + [{"role": "user", "content": text}, {"role": "assistant", "content": response}]
        await save_context(user_id, new_ctx)
        await save_dialog(user_id, "diary_followup", text, response)

        if len([m for m in new_ctx if m.get("role") == "user"]) >= 2:
            await message.answer(response, reply_markup=diary_save_confirm())
        else:
            await message.answer(response, reply_markup=back_to_menu())

    else:
        await message.answer("Выбери, чем займёмся сегодня 💜", reply_markup=main_menu())


@router.callback_query(F.data == "continue_dialog")
async def continue_dialog(callback: CallbackQuery):
    await callback.message.answer("Я слушаю тебя 💜")
    await callback.answer()


@router.callback_query(F.data == "subscribe")
async def handle_subscribe(callback: CallbackQuery):
    await callback.message.answer(
        "💜 *Подписка Mirra Pro — 3 000 ₸/месяц*\n\n"
        "Для оплаты напиши администратору: @mirra_support\n\n"
        "После оплаты откроется полный доступ 🌙",
        parse_mode="Markdown",
        reply_markup=back_to_menu()
    )
    await callback.answer()
