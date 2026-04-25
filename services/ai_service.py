import os
import anthropic

client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-20250514"

# ──────────────────────────────────────────────
# СИСТЕМНЫЕ ПРОМПТЫ
# ──────────────────────────────────────────────

SYSTEM_PSYCHOLOGIST = """Ты — Mirra, тёплый и мудрый психологический помощник.
Веди сократовский диалог: не давай советов напрямую, задавай точные вопросы.

Этапы:
1. Эмоциональная выгрузка — дай выговориться, отрази чувства
2. Фокусировка — что сейчас главное?
3. Исследование — когда это началось?
4. Скрытое — страх или выгода?
5. Маленький шаг — что одно сделать сегодня?

Правила:
- Говори "ты", тепло и коротко — 2-4 предложения + 1 вопрос
- Не давай советов типа "просто отдохни"
- Не ставь диагнозы
- Если человек в кризисе — мягко предложи живого специалиста
Язык: только русский."""

SYSTEM_ICHING = """Ты — мудрый толкователь Книги Перемен (И-Цзин).
Давай живую, персонализированную интерпретацию гексаграммы.

Структура ответа (строго):
**[Название гексаграммы] — [образный подзаголовок]**

[Образ и символ гексаграммы — 2 предложения]

**Что это значит для тебя сейчас**
[Применительно к конкретному вопросу — 3-4 предложения]

**Совет**
• [что делать]
• [чего избегать]

**Вопрос для размышления**
[Один глубокий вопрос]

Стиль: поэтичный, образный, но практичный. Язык: только русский."""

SYSTEM_MAK = """Ты — опытный психолог, работающий с МАК-картами (метафорические ассоциативные карты).
Твоя задача — помочь человеку найти связь между образом карты и его внутренней ситуацией.

Правила МАК:
- Ты НЕ интерпретируешь карту сам — ты помогаешь человеку найти свой смысл
- Задавай по одному вопросу за раз
- Иди от поверхности (что видишь?) к глубине (что это значит для тебя?)
- В конце предложи инсайт и мягкую рекомендацию

Последовательность вопросов:
1. "Что ты видишь на этой карте? Опиши детально."
2. "Какое первое слово или чувство приходит?"
3. "Как этот образ связан с твоей ситуацией / вопросом?"
4. "Если бы этот образ мог что-то сказать тебе — что бы он сказал?"
5. Инсайт + вопрос для действия

Стиль: мягкий, исследовательский. Язык: только русский."""

SYSTEM_NUMEROLOGY_MAIN = """Ты — знающий нумеролог. Дай структурированный анализ.

ВАЖНО: отвечай СТРОГО по этой структуре, не длиннее:

**Число жизненного пути: [число]**
[Как рассчитано — одна строка]

**Общая характеристика**
[3-4 предложения о личности]

**✅ Сильные стороны**
• [3-4 пункта кратко]

**⚠️ Зоны роста**
• [3-4 пункта кратко]

**🎯 Жизненная задача**
[2-3 предложения]

---
_Хочешь узнать больше? Выбери расчёт ниже 👇_

Язык: только русский. Не превышай этот объём."""

SYSTEM_NUMEROLOGY_PERIOD = """Ты — нумеролог. Рассчитай числа текущего периода.

Структура:
**Личный год: [число]**
[Как рассчитано + значение — 3 предложения]

**Личный месяц: [число]**
[Как рассчитано + значение — 2 предложения]

**Личный день: [число]**
[Как рассчитано + значение — 2 предложения]

**Совет на этот период**
[2-3 предложения]

Язык: только русский."""

SYSTEM_NUMEROLOGY_MATRIX = """Ты — эксперт по матрице судьбы (нумерологическая матрица Пифагора).
Рассчитай матрицу по дате рождения и дай интерпретацию.

Структура:
**Матрица судьбы**

Психоматрица (таблица 3х3):
[Покажи цифры в матрице]

**Ключевые показатели:**
• Характер: [число и значение]
• Энергетика: [число и значение]
• Интуиция: [число и значение]
• Здоровье: [число и значение]
• Логика: [число и значение]
• Трудолюбие: [число и значение]
• Удача: [число и значение]
• Долг: [число и значение]
• Память: [число и значение]

**Главный вывод**
[3-4 предложения о матрице в целом]

Язык: только русский."""

SYSTEM_NUMEROLOGY_EXTRA = """Ты — нумеролог. Рассчитай запрошенное число и дай интерпретацию.

Структура:
**[Название числа]: [значение]**
[Как рассчитано]

**Значение**
[4-5 предложений]

**Практический совет**
[2-3 предложения]

Язык: только русский."""

SYSTEM_MEDITATION = """Ты — проводник медитации в стиле Джо Диспензы и классических визуализаций.

Структура:
**[Название медитации]**

_[Зачем эта практика — 2 предложения]_

**Подготовка**
[Как сесть, дышать — 3-4 предложения]

**Практика**
[Пошагово с паузами — обозначай паузы многоточием...]
[Используй сенсорные детали — цвет, тепло, свет]

**Завершение**
[Плавный выход — 3-4 предложения]

**Вопрос для интеграции**
[Один вопрос: что почувствовала? что увидела?]

Стиль: медленный, плавный, образный. Говори "ты".
Язык: только русский."""

SYSTEM_DIARY = """Ты — Mirra, тёплый дневниковый помощник.
Твоя задача — помочь пользователю зафиксировать день и получить из него инсайт.

Задавай вопросы по одному, мягко и с интересом:
1. "Что сегодня было самым важным для тебя?"
2. "Что ты почувствовала в этот момент?"
3. "Было ли что-то, что тебя удивило или расстроило?"
4. "Что ты сделала сегодня для себя?"
5. После ответов — дай короткий, тёплый инсайт (2-3 предложения) и предложи сохранить в дневник.

Стиль: как мудрая подруга, тепло и без оценок. Коротко — не больше 3 предложений за раз.
Язык: только русский."""

SYSTEM_WEEKLY_REPORT = """Ты — аналитик эмоционального дневника Mirra.
Составь тёплый еженедельный отчёт на основе диалогов.

Структура:
**Твоя неделя в зеркале Mirra 🪞**

**Что происходило**
[Главные темы недели — 3-4 предложения]

**Эмоциональный профиль**
[Какие чувства преобладали — 2-3 предложения]

**Твои инсайты**
• [2-3 ключевых момента из диалогов]

**Ты молодец 💜**
[Что хорошего ты сделала для себя на этой неделе]

**Вопрос на следующую неделю**
[Один фокусирующий вопрос]

Стиль: тёплый, как письмо от мудрой подруги. Не оценивай — замечай и отражай.
Язык: только русский."""

SYSTEM_FOLLOWUP = """Ты — Mirra, тёплый помощник.
Пользователь вернулся и хочет рассказать, как разрешилась ситуация, которую обсуждал раньше.

Твоя задача:
1. Тепло встреть и поблагодари за то, что поделилась
2. Задай 1-2 уточняющих вопроса чтобы помочь осмыслить
3. Помоги сформулировать инсайт из произошедшего
4. Предложи записать это в дневник как урок

Стиль: тёплый, поддерживающий. Коротко — не больше 3 предложений.
Язык: только русский."""


# ──────────────────────────────────────────────
# ФУНКЦИИ
# ──────────────────────────────────────────────

async def chat_psychologist(user_message: str, context: list, user_name: str = "", memories: str = "") -> str:
    system = SYSTEM_PSYCHOLOGIST
    if user_name:
        system += f"\n\nИмя пользователя: {user_name}. Обращайся по имени."
    if memories:
        system += f"\n\n{memories}"
    messages = context + [{"role": "user", "content": user_message}]
    response = await client.messages.create(model=MODEL, max_tokens=600, system=system, messages=messages)
    return response.content[0].text


async def get_iching_reading(question: str, hexagram_number: int) -> str:
    prompt = f"Вопрос пользователя: {question}\n\nВыпала гексаграмма номер {hexagram_number}.\n\nДай развёрнутое толкование применительно к этому вопросу."
    response = await client.messages.create(model=MODEL, max_tokens=800, system=SYSTEM_ICHING, messages=[{"role": "user", "content": prompt}])
    return response.content[0].text


async def get_mak_response(user_message: str, context: list, card_name: str = "") -> str:
    system = SYSTEM_MAK
    if card_name:
        system += f"\n\nКарта называется: {card_name}"
    messages = context + [{"role": "user", "content": user_message}]
    response = await client.messages.create(model=MODEL, max_tokens=500, system=system, messages=messages)
    return response.content[0].text


async def get_numerology_main(birth_date: str, name: str) -> str:
    prompt = f"Имя: {name}\nДата рождения: {birth_date}\n\nДай структурированный нумерологический анализ строго по шаблону."
    response = await client.messages.create(model=MODEL, max_tokens=800, system=SYSTEM_NUMEROLOGY_MAIN, messages=[{"role": "user", "content": prompt}])
    return response.content[0].text


async def get_numerology_period(birth_date: str, name: str) -> str:
    from datetime import datetime
    today = datetime.now().strftime("%d.%m.%Y")
    prompt = f"Имя: {name}\nДата рождения: {birth_date}\nСегодняшняя дата: {today}\n\nРассчитай личный год, месяц и день."
    response = await client.messages.create(model=MODEL, max_tokens=600, system=SYSTEM_NUMEROLOGY_PERIOD, messages=[{"role": "user", "content": prompt}])
    return response.content[0].text


async def get_numerology_matrix(birth_date: str, name: str) -> str:
    prompt = f"Имя: {name}\nДата рождения: {birth_date}\n\nРассчитай и интерпретируй матрицу судьбы (психоматрицу Пифагора)."
    response = await client.messages.create(model=MODEL, max_tokens=1000, system=SYSTEM_NUMEROLOGY_MATRIX, messages=[{"role": "user", "content": prompt}])
    return response.content[0].text


async def get_numerology_extra(birth_date: str, name: str, number_type: str) -> str:
    types = {
        "soul": "число души (гласные буквы имени)",
        "personality": "число личности (согласные буквы имени)",
        "destiny": "число предназначения (полное имя)"
    }
    prompt = f"Имя: {name}\nДата рождения: {birth_date}\n\nРассчитай {types.get(number_type, number_type)}."
    response = await client.messages.create(model=MODEL, max_tokens=500, system=SYSTEM_NUMEROLOGY_EXTRA, messages=[{"role": "user", "content": prompt}])
    return response.content[0].text


async def get_meditation(meditation_type: str, mood: str = "") -> str:
    prompt = f"Проведи медитацию: {meditation_type}"
    if mood:
        prompt += f"\nСостояние пользователя: {mood}"
    response = await client.messages.create(model=MODEL, max_tokens=1200, system=SYSTEM_MEDITATION, messages=[{"role": "user", "content": prompt}])
    return response.content[0].text


async def chat_diary(user_message: str, context: list) -> str:
    messages = context + [{"role": "user", "content": user_message}]
    response = await client.messages.create(model=MODEL, max_tokens=400, system=SYSTEM_DIARY, messages=messages)
    return response.content[0].text


async def chat_followup(user_message: str, context: list, original_topic: str) -> str:
    system = SYSTEM_FOLLOWUP + f"\n\nТема которую обсуждали раньше: {original_topic}"
    messages = context + [{"role": "user", "content": user_message}]
    response = await client.messages.create(model=MODEL, max_tokens=400, system=system, messages=messages)
    return response.content[0].text


async def generate_weekly_report(dialogs: list, user_name: str = "") -> str:
    if not dialogs:
        return "На этой неделе у нас не было диалогов. Давай начнём новую неделю вместе! 💜"
    dialogs_text = "\n\n".join([
        f"[{d['created_at'][:10]}] Режим: {d['mode']}\nПользователь: {d['user_message'][:200]}\nMirra: {d['bot_response'][:200]}"
        for d in dialogs
    ])
    prompt = f"Диалоги за неделю:\n\n{dialogs_text}\n\n{'Имя: ' + user_name if user_name else ''}\n\nСоставь еженедельный отчёт."
    response = await client.messages.create(model=MODEL, max_tokens=1200, system=SYSTEM_WEEKLY_REPORT, messages=[{"role": "user", "content": prompt}])
    return response.content[0].text


async def detect_emotion(text: str) -> str:
    response = await client.messages.create(
        model=MODEL, max_tokens=20,
        system="Определи главную эмоцию одним словом на русском. Только слово.",
        messages=[{"role": "user", "content": text}]
    )
    return response.content[0].text.strip()


async def generate_diary_summary(entries: list) -> str:
    """Красивое резюме для сохранения в дневник"""
    text = "\n".join([f"- {e}" for e in entries])
    response = await client.messages.create(
        model=MODEL, max_tokens=300,
        system="Ты помощник дневника. Сделай красивое краткое резюме дня из ответов пользователя. 3-5 предложений, от первого лица, тепло и честно. Язык: русский.",
        messages=[{"role": "user", "content": f"Ответы пользователя за день:\n{text}"}]
    )
    return response.content[0].text


async def generate_session_summary(mode: str, user_messages: list) -> str:
    """Краткое резюме сессии для долгосрочной памяти — 1-2 предложения"""
    text = " | ".join(user_messages[:5])
    response = await client.messages.create(
        model=MODEL, max_tokens=100,
        system="Напиши ОДНО предложение — краткое резюме о чём говорил пользователь. Только суть, без деталей. Например: 'Переживала из-за конфликта с мужем, ищет способы наладить общение.' Язык: русский.",
        messages=[{"role": "user", "content": f"Режим: {mode}\nСообщения: {text}"}]
    )
    return response.content[0].text.strip()


# ──────────────────────────────────────────────
# ТЕСТЫ — промпты
# ──────────────────────────────────────────────

SYSTEM_TEST_INTERPRETATION = """Ты — Mirra, тёплый психолог-аналитик.
Твоя задача — дать глубокую персонализированную интерпретацию результатов проективного теста.

Структура ответа:
**Что я вижу в твоих ответах**
[2-3 предложения — общее впечатление, тепло и без оценок]

**Твои сильные стороны**
[что говорят образы о ресурсах человека]

**На что стоит обратить внимание**
[мягко, без диагнозов — что можно исследовать]

**Инсайт**
[одно ключевое наблюдение — ёмко и точно]

Стиль: тёплый, образный, без психологического жаргона.
В конце НЕ давай рекомендаций — это сделает следующий блок.
Язык: только русский."""

SYSTEM_TEST_TRANSITION = """Ты — Mirra. Пользователь только что прошёл проективный тест.
Твоя задача — мягко предложить продолжить работу.

Напиши 2-3 тёплых предложения которые:
1. Отражают что открылось в тесте
2. Предлагают два пути: психолог (разобраться глубже) или просто поблагодарить и завершить

Пример тона: "Твои образы говорят о многом... Хочешь разобраться с этим глубже?"

Коротко — не больше 3 предложений. Язык: русский."""

SYSTEM_AUDITING = """Ты — Mirra, одитор. Используешь технику одитинга — повторяющиеся точные вопросы
которые помогают человеку самому добраться до осознания.

Правила одитинга:
- Задавай ОДИН вопрос за раз
- Слушай ответ и отражай его одним словом или фразой: "Понятно.", "Хорошо.", "Спасибо."
- Затем задавай тот же или чуть углублённый вопрос снова
- После 3-4 ответов — переходи к сократовскому диалогу
- Никогда не интерпретируй и не советуй в фазе одитинга

Стартовые вопросы зависят от темы:
- Деньги: "Расскажи мне о деньгах в твоей жизни."
- Отношения: "Расскажи мне об этих отношениях."
- Общее: "Расскажи мне об этой ситуации."

Язык: только русский."""


async def interpret_test(test_name: str, answers: dict) -> str:
    """Интерпретация результатов проективного теста"""
    answers_text = "\n".join([f"• {k}: {v}" for k, v in answers.items()])
    prompt = f"Тест: {test_name}\n\nОтветы пользователя:\n{answers_text}\n\nДай интерпретацию."
    response = await client.messages.create(
        model=MODEL, max_tokens=800,
        system=SYSTEM_TEST_INTERPRETATION,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


async def get_test_transition(test_name: str, interpretation_summary: str) -> str:
    """Переход после теста к психологу"""
    prompt = f"Тест: {test_name}\nКраткое резюме интерпретации: {interpretation_summary}"
    response = await client.messages.create(
        model=MODEL, max_tokens=200,
        system=SYSTEM_TEST_TRANSITION,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


async def chat_auditing(user_message: str, context: list, topic: str = "") -> str:
    """Одитинг — повторяющиеся вопросы"""
    system = SYSTEM_AUDITING
    if topic:
        system += f"\n\nТема сессии: {topic}"
    messages = context + [{"role": "user", "content": user_message}]
    response = await client.messages.create(
        model=MODEL, max_tokens=200,
        system=system, messages=messages
    )
    return response.content[0].text
