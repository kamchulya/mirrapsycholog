import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from models.database import (
    get_user_state, set_user_mode, save_context,
    get_context, clear_context, save_dialog,
    can_use_bot, increment_message_count
)
from services.ai_service import (
    interpret_test, get_test_transition,
    chat_auditing, chat_psychologist
)

router = Router()
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# ОПИСАНИЯ ТЕСТОВ
# ──────────────────────────────────────────────

TESTS = {
    "cube": {
        "name": "🏜️ Куб в пустыне",
        "desc": "Классический проективный тест на личность, отношения и жизненные ресурсы",
        "steps": [
            ("cube_1", "Представь пустыню. Бескрайние пески, тишина, горизонт...\n\nТеперь в этой пустыне появляется *куб*.\n\nКакой он? Большой или маленький? Из чего сделан? Где находится — стоит на песке, парит, зарыт? Опиши его подробно 👇"),
            ("cube_2", "Хорошо. Теперь рядом с кубом появляется *лестница*.\n\nКакая она? Где стоит — прислонена к кубу, лежит в стороне, ведёт куда-то? Из чего сделана? Опиши 👇"),
            ("cube_3", "Теперь в пустыне появляется *лошадь*.\n\nГде она находится относительно куба? Что делает? Какая она? Опиши 👇"),
            ("cube_4", "И последнее — в пустыне появляются *цветы*.\n\nСколько их? Где растут? Какие они? Опиши 👇"),
            ("cube_5", "Над пустыней собирается *гроза*.\n\nОна далеко на горизонте или прямо над тобой? Что ты чувствуешь? Куб в безопасности? 👇"),
        ],
        "keys": ["Куб", "Лестница", "Лошадь", "Цветы", "Гроза"],
        "topic": "личность и отношения"
    },
    "house": {
        "name": "🏠 Дом-Дерево-Человек",
        "desc": "Тест на жизненную энергию, границы и открытость миру",
        "steps": [
            ("house_1", "Представь *дом своей мечты*.\n\nКакой он? Большой или маленький? Есть ли забор вокруг? Есть ли окна — большие или маленькие? Есть ли свет в окнах? Опиши подробно 👇"),
            ("house_2", "Рядом с домом растёт *дерево*.\n\nКакое оно? Большое или маленькое? Какие корни — видны или уходят глубоко? Есть ли плоды или листья? Опиши 👇"),
            ("house_3", "Рядом с домом стоит *человек*.\n\nКто это? Как он выглядит? Что делает? Как он относится к дому? Опиши 👇"),
        ],
        "keys": ["Дом", "Дерево", "Человек"],
        "topic": "энергия и границы"
    },
    "money_avatar": {
        "name": "💰 Образ денег",
        "desc": "Тест на внутреннее отношение к деньгам через образ купюры",
        "steps": [
            ("money_1", "Возьми крупную купюру — например 20 000 тенге.\n"
                       "Если нет под рукой — открой её изображение.\n\n"
                       "Смотри на неё внимательно *2-3 минуты*. Рассматривай каждую деталь.\n\n"
                       "Потом закрой глаза и представь что эта купюра *превратилась в человека*.\n\n"
                       "Когда образ появится — напиши:\n\n"
                       "• Это мужчина или женщина?\n"
                       "• Сколько ему/ей лет?\n"
                       "• Как выглядит? Во что одет?\n"
                       "• Какое настроение? Как смотрит на тебя? 👇"),
            ("money_2", "Хорошо. Теперь присмотрись к этому человеку внимательнее:\n\n"
                       "• Он близко или далеко от тебя?\n"
                       "• Он добрый, холодный, строгий, щедрый, опасный?\n"
                       "• Хочет ли он общаться с тобой?\n"
                       "• Что он говорит тебе? 👇"),
            ("money_3", "Последнее и самое важное:\n\n"
                       "• Что ты *чувствуешь* рядом с ним?\n"
                       "• Хочется подойти ближе или отойти?\n"
                       "• Что нужно сделать *тебе*, чтобы отношения с ним стали лучше? 👇"),
        ],
        "keys": ["Внешность и настроение", "Характер и отношение", "Чувства и изменения"],
        "topic": "отношения с деньгами"
    },
    "animal": {
        "name": "🦄 Несуществующее животное",
        "desc": "Тест на скрытые потребности, страхи и внутренние ресурсы",
        "steps": [
            ("animal_1", "У тебя есть 1 минута.\n\nПридумай и опиши *животное которого не существует в природе*. Как оно выглядит? Какое у него тело, цвет, размер? Есть ли у него рога, крылья, когти, мягкая шерсть? 👇"),
            ("animal_2", "Хорошо! Теперь расскажи:\n\n*Где живёт это животное?* Одно или в стае? Как оно защищается? Чего боится? 👇"),
            ("animal_3", "И последнее:\n\n*Как называется это животное?* И что оно больше всего любит делать? 👇"),
        ],
        "keys": ["Внешность животного", "Среда и поведение", "Название и любимое занятие"],
        "topic": "скрытые потребности"
    },
    "wheel": {
        "name": "⭕ Колесо жизни",
        "desc": "Оценка баланса по 8 ключевым сферам жизни",
        "steps": [
            ("wheel_1", "Оцени каждую сферу от 1 до 10, где 1 — совсем плохо, 10 — всё отлично.\n\nНапиши одним сообщением:\n\n💼 *Работа/Карьера:* ?\n💰 *Деньги/Финансы:* ?\n❤️ *Отношения/Семья:* ?\n🏥 *Здоровье:* ?\n🎯 *Личностный рост:* ?\n🎉 *Отдых/Удовольствия:* ?\n👥 *Друзья/Окружение:* ?\n🌟 *Предназначение/Смысл:* ? 👇"),
        ],
        "keys": ["Оценки по сферам"],
        "topic": "баланс жизни"
    },
    "three_images": {
        "name": "🌊 Три образа",
        "desc": "Тест на отношения через метафору — глубокий и точный",
        "steps": [
            ("img_1", "Давай исследуем твои отношения через образы. Это очень точный метод.\n\n*Шаг 1:* Представь ваши отношения как некое пространство или стихию.\n\nЧто это? Например: тихая гавань, выжженное поле, бурлящий котёл, туман... 👇"),
            ("img_2", "Хорошо. *Шаг 2:* Теперь посмотри на партнёра.\n\nНа какой образ он похож в этом пространстве?\n\nНапример: скала, ветер, запертая дверь, огонь, маяк... 👇"),
            ("img_3", "И последнее. *Шаг 3:* Где в этом пространстве *ты*?\n\nКак ты выглядишь? Что делаешь? Как себя чувствуешь? 👇"),
        ],
        "keys": ["Образ отношений", "Образ партнёра", "Образ себя"],
        "topic": "отношения"
    },
    "money_beast": {
        "name": "🐾 Деньги и зверь",
        "desc": "Тест на финансовые блоки и инстинкты — очень мощный",
        "steps": [
            ("beast_1", "Закрой глаза и представь что ты идёшь по дороге...\n\nВдруг ты видишь на земле *деньги* — много денег.\n\n*Как ты их берёшь?* Схватил и спрятал? Спокойно поднял? Долго смотрел? Опиши свои действия 👇"),
            ("beast_2", "Ты взял деньги и идёшь дальше.\n\n*Куда ты хочешь их отнести?* Домой? В банк? Потратить? Вернуть? Что первое пришло в голову? 👇"),
            ("beast_3", "Ты идёшь с деньгами и вдруг на дороге появляется *зверь*.\n\nКакой он? Опиши его — размер, вид, как смотрит на тебя 👇"),
            ("beast_4", "Зверь перед тобой. Деньги в руках.\n\n*Что ты делаешь?* Бросаешь деньги и убегаешь? Прячешь деньги и готовишься защищаться? Пытаешься договориться? Проходишь мимо? Опиши 👇"),
        ],
        "keys": ["Как взял деньги", "Куда несёт", "Образ зверя", "Реакция при звере"],
        "topic": "финансовые блоки"
    },
}


# ──────────────────────────────────────────────
# КЛАВИАТУРЫ
# ──────────────────────────────────────────────

def tests_menu() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏜️ Куб в пустыне", callback_data="test_cube"))
    builder.row(InlineKeyboardButton(text="🏠 Дом-Дерево-Человек", callback_data="test_house"))
    builder.row(
        InlineKeyboardButton(text="💰 Образ денег", callback_data="test_money_avatar"),
        InlineKeyboardButton(text="🐾 Деньги и зверь", callback_data="test_money_beast"),
    )
    builder.row(InlineKeyboardButton(text="🦄 Несуществующее животное", callback_data="test_animal"))
    builder.row(InlineKeyboardButton(text="⭕ Колесо жизни", callback_data="test_wheel"))
    builder.row(InlineKeyboardButton(text="🌊 Три образа (отношения)", callback_data="test_three_images"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_menu"))
    return builder.as_markup()


def after_test_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🧠 Разобраться глубже с психологом",
        callback_data="test_go_psychologist"
    ))
    builder.row(InlineKeyboardButton(
        text="🏠 Главное меню",
        callback_data="back_menu"
    ))
    return builder.as_markup()


# ──────────────────────────────────────────────
# ОТКРЫТИЕ МЕНЮ ТЕСТОВ
# ──────────────────────────────────────────────

@router.callback_query(F.data == "mode_tests")
async def open_tests_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔬 *Проективные тесты*\n\n"
        "Проективные тесты работают через образы и метафоры — "
        "они обходят рациональный ум и показывают то, "
        "что скрыто в подсознании.\n\n"
        "Здесь нет правильных и неправильных ответов. "
        "Просто отвечай первое что приходит в голову.\n\n"
        "Выбери тест 👇",
        parse_mode="Markdown",
        reply_markup=tests_menu()
    )
    await callback.answer()


# ──────────────────────────────────────────────
# ЗАПУСК ТЕСТА
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("test_") & ~F.data.startswith("test_go"))
async def start_test(callback: CallbackQuery):
    test_id = callback.data.replace("test_", "")
    test = TESTS.get(test_id)

    if not test:
        await callback.answer("Тест не найден")
        return

    # Сохраняем состояние теста
    await set_user_mode(callback.from_user.id, f"test_{test_id}_0")
    await clear_context(callback.from_user.id)
    await save_context(callback.from_user.id, [
        {"role": "system", "content": f"test_id:{test_id}"},
        {"role": "system", "content": "step:0"},
        {"role": "system", "content": "answers:{}"}
    ])

    first_step = test["steps"][0]

    await callback.message.edit_text(
        f"*{test['name']}*\n\n"
        f"_{test['desc']}_\n\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"{first_step[1]}",
        parse_mode="Markdown",
        reply_markup=_back_keyboard()
    )
    await callback.answer()


def _back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад к тестам", callback_data="mode_tests"))
    return builder.as_markup()


# ──────────────────────────────────────────────
# ОБРАБОТКА ОТВЕТОВ НА ТЕСТ
# ──────────────────────────────────────────────

async def handle_test_answer(message: Message, mode: str, text: str):
    """Обрабатываем ответ пользователя в ходе теста"""
    import json
    user_id = message.from_user.id

    # Достаём test_id и шаг из mode (формат: test_cube_0)
    parts = mode.split("_")
    if len(parts) < 3:
        return False

    # test_id может быть составным (money_avatar, money_beast, three_images)
    step_num = int(parts[-1])
    test_id = "_".join(parts[1:-1])
    test = TESTS.get(test_id)

    if not test:
        return False

    # Загружаем контекст
    context = await get_context(user_id)
    answers = {}
    for msg in context:
        if msg.get("content", "").startswith("answers:"):
            try:
                answers = json.loads(msg["content"].replace("answers:", ""))
            except Exception:
                answers = {}
            break

    # Сохраняем ответ
    key = test["keys"][step_num] if step_num < len(test["keys"]) else f"Шаг {step_num + 1}"
    answers[key] = text

    next_step = step_num + 1
    total_steps = len(test["steps"])

    # Обновляем контекст
    new_context = [
        {"role": "system", "content": f"test_id:{test_id}"},
        {"role": "system", "content": f"step:{next_step}"},
        {"role": "system", "content": f"answers:{json.dumps(answers, ensure_ascii=False)}"},
    ]
    await save_context(user_id, new_context)

    if next_step < total_steps:
        # Следующий вопрос
        await set_user_mode(user_id, f"test_{test_id}_{next_step}")
        next_question = test["steps"][next_step][1]

        await message.answer(
            f"✓ Записала\n\n{next_question}",
            parse_mode="Markdown",
            reply_markup=_back_keyboard()
        )
    else:
        # Тест завершён — интерпретация
        await set_user_mode(user_id, "test_result")
        await message.answer("🔮 _Анализирую твои ответы..._", parse_mode="Markdown")

        interpretation = await interpret_test(test["name"], answers)
        transition = await get_test_transition(test["name"], interpretation[:200])

        # Сохраняем в диалоги
        answers_text = "\n".join([f"{k}: {v}" for k, v in answers.items()])
        await save_dialog(
            user_id=user_id,
            mode="test",
            user_msg=f"Тест: {test['name']}\n{answers_text}",
            bot_response=interpretation
        )

        # Сохраняем тему для следующего шага
        await save_context(user_id, [
            {"role": "system", "content": f"test_topic:{test['topic']}"},
            {"role": "system", "content": f"test_name:{test['name']}"},
        ])

        await message.answer(
            f"*{test['name']} — результат*\n\n{interpretation}",
            parse_mode="Markdown"
        )
        await message.answer(
            f"💜 {transition}",
            reply_markup=after_test_keyboard()
        )

    return True


# ──────────────────────────────────────────────
# ПЕРЕХОД К ПСИХОЛОГУ ПОСЛЕ ТЕСТА
# ──────────────────────────────────────────────

@router.callback_query(F.data == "test_go_psychologist")
async def test_go_to_psychologist(callback: CallbackQuery):
    """После теста — сначала одитинг, потом сократовский диалог"""
    user_id = callback.from_user.id
    context = await get_context(user_id)

    topic = ""
    for msg in context:
        if msg.get("content", "").startswith("test_topic:"):
            topic = msg["content"].replace("test_topic:", "")
            break

    await set_user_mode(user_id, "auditing")

    # Стартовый вопрос одитинга
    topic_questions = {
        "отношения с деньгами": "Расскажи мне о деньгах в твоей жизни.",
        "финансовые блоки": "Расскажи мне о деньгах в твоей жизни.",
        "отношения": "Расскажи мне об этих отношениях.",
        "личность и отношения": "Расскажи мне о том что ты сейчас чувствуешь.",
        "баланс жизни": "Расскажи мне о той сфере которая тебя беспокоит больше всего.",
        "скрытые потребности": "Расскажи мне о том чего тебе сейчас не хватает.",
        "энергия и границы": "Расскажи мне о том как ты себя чувствуешь прямо сейчас.",
    }

    start_question = topic_questions.get(topic, "Расскажи мне об этой ситуации.")

    # Новый контекст для одитинга
    new_ctx = [
        {"role": "system", "content": f"topic:{topic}"},
        {"role": "system", "content": "auditing_count:0"},
        {"role": "assistant", "content": start_question}
    ]
    await save_context(user_id, new_ctx)

    await callback.message.edit_text(
        f"🧠 *Давай разберёмся глубже*\n\n"
        f"Я задам тебе несколько вопросов.\n"
        f"Отвечай первое что приходит — без анализа.\n\n"
        f"_{start_question}_",
        parse_mode="Markdown",
        reply_markup=_back_keyboard()
    )
    await callback.answer()


async def handle_auditing(message: Message, text: str):
    """Одитинг — 3-4 раунда потом переход к сократовскому диалогу"""
    import json
    user_id = message.from_user.id
    context = await get_context(user_id)

    # Считаем раунды
    count = 0
    topic = ""
    for msg in context:
        if msg.get("content", "").startswith("auditing_count:"):
            try:
                count = int(msg["content"].replace("auditing_count:", ""))
            except Exception:
                count = 0
        if msg.get("content", "").startswith("topic:"):
            topic = msg["content"].replace("topic:", "")

    await message.chat.do("typing")

    if count >= 3:
        # Переходим к сократовскому диалогу
        await set_user_mode(user_id, "psychologist")
        user = await get_context(user_id)

        response = await chat_psychologist(text, context, memories="")
        new_ctx = context + [
            {"role": "user", "content": text},
            {"role": "assistant", "content": response}
        ]
        await save_context(user_id, new_ctx)

        await message.answer(
            f"💜 _{response}_",
            parse_mode="Markdown",
            reply_markup=_continue_keyboard()
        )
    else:
        # Продолжаем одитинг
        response = await chat_auditing(text, context, topic)

        new_ctx = [msg for msg in context if not msg.get("content", "").startswith("auditing_count:")]
        new_ctx.append({"role": "system", "content": f"auditing_count:{count + 1}"})
        new_ctx.append({"role": "user", "content": text})
        new_ctx.append({"role": "assistant", "content": response})
        await save_context(user_id, new_ctx)

        await message.answer(response)


def _continue_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💬 Продолжить", callback_data="continue_dialog"))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_menu"))
    return builder.as_markup()
