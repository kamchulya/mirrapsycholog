import asyncio
import json
import os
import re
import logging
import random
from collections import deque, OrderedDict
from datetime import datetime, timezone

import aiohttp
import asyncpg
import anthropic
from aiohttp import web

from config import (
    ANTHROPIC_API_KEY,
    WAZZUP_API_KEY,
    WAZZUP_CHANNEL_ID,
    ENVY_OPERATOR_KEY,
    ENVY_API_KEY,
    ENVY_CRM_URL,
    DATABASE_URL,
    PORT,
)
from prompt import SYSTEM_PROMPT

REAL_MANAGERS = [
    1165916,  # Расул Ильясов
    1166309,  # Тамирлан Бауржанов
    1109958,  # Джони
    1158023,  # Кайратулы Нурзат
    1164185,  # Жайсангалиева Диляра
    1163510,  # Каирлымова Дамира
    1166645,  # Акбота
    1164143,  # Есполова Мариям
    1164413,  # Искандырова Карина
]

# ---------- States ----------
STATE_NEW     = "new"
STATE_ACTIVE  = "active"
STATE_DONE    = "done"
STATE_MANAGER = "manager"
STATE_REFUSED = "refused"
STATE_SMM     = "smm"

SILENT_STATES = {STATE_DONE, STATE_MANAGER, STATE_REFUSED, STATE_SMM}


CLAUDE_FALLBACK = {
    "ru": "Извините, небольшой сбой. Напишите позже или менеджер свяжется с Вами 😊",
    "kz": "Кешіріңіз, қате болды. Кейінірек жазыңыз 😊",
}

THANKS_MSGS = {
    "ru": "Спасибо! Передала Ваш номер менеджеру — скоро свяжутся 🙌",
    "kz": "Рахмет! Нөміріңізді менеджерімізге бердім, жақын арада байланысады 🙌",
}

FAREWELL_MSGS = {
    "ru": "Хорошо, не буду беспокоить 😊 Если надумаете — всегда рады помочь!",
    "kz": "Жақсы, мазаламаймын 😊 Ойланып қалсаңыз — әрқашан қош келдіңіз!",
}

REFUSE_WORDS = [
    # RU
    "не надо", "не интересно", "нет спасибо", "не хочу", "не нужно",
    # KZ
    "қажет емес", "жоқ рахмет",
    # EN
    "no thanks", "not interested", "don't need",
]

PHONE_RE = re.compile(
    r'(?:\+7|8|\b7)[\s\-\(\)]*\d{3}[\s\-\(\)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}'
    r'|\b\d{10,11}\b'
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

db_pool: asyncpg.Pool | None = None
processed_message_ids: deque = deque(maxlen=1000)
sent_texts: dict[str, dict[str, datetime]] = {}  # chat_id → {text: added_at}
dialog_locks: OrderedDict = OrderedDict()
last_notify: dict[str, datetime] = {}  # chat_id → время последнего notify_manager


def should_notify(chat_id: str, cooldown_seconds: int = 300) -> bool:
    now = datetime.now(timezone.utc)
    last = last_notify.get(chat_id)
    if last and (now - last).total_seconds() < cooldown_seconds:
        return False
    if len(last_notify) >= 10000:
        oldest_key = min(last_notify, key=last_notify.get)
        del last_notify[oldest_key]
    last_notify[chat_id] = now
    return True


def get_lock(chat_id: str) -> asyncio.Lock:
    if chat_id not in dialog_locks:
        if len(dialog_locks) >= 10000:
            dialog_locks.popitem(last=False)
        dialog_locks[chat_id] = asyncio.Lock()
    return dialog_locks[chat_id]


# ---------- DB helpers ----------
async def get_state(chat_id: str) -> tuple[str | None, list, datetime | None, int | None]:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT state, history, updated_at, deal_id FROM dialogs WHERE chat_id=$1", chat_id
        )
    if row:
        history = json.loads(row["history"]) if row["history"] else []
        return row["state"], history, row["updated_at"], row["deal_id"]
    return None, [], None, None


async def set_state(
    chat_id: str,
    state: str,
    history: list | None = None,
    deal_id: int | None = None,
) -> None:
    history_json = json.dumps(history, ensure_ascii=False) if history is not None else None
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO dialogs (chat_id, state, history, deal_id, updated_at)
            VALUES ($1, $2, $3::jsonb, $4, NOW())
            ON CONFLICT (chat_id) DO UPDATE
                SET state      = EXCLUDED.state,
                    history    = COALESCE(EXCLUDED.history, dialogs.history),
                    deal_id    = COALESCE(EXCLUDED.deal_id, dialogs.deal_id),
                    updated_at = NOW()
            """,
            chat_id, state, history_json, deal_id,
        )


async def save_deal_id(chat_id: str, deal_id: int) -> None:
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE dialogs SET deal_id = $1 WHERE chat_id = $2",
            deal_id, chat_id,
        )


# ---------- Wazzup API (3 попытки: 0 / 2 / 4 сек) ----------
async def send_wazzup(chat_id: str, text: str) -> None:
    url = "https://api.wazzup24.com/v3/message"
    headers = {
        "Authorization": f"Bearer {WAZZUP_API_KEY}",
        "Content-Type": "application/json",
    }
    # chatId — всегда username как есть (строка), никогда не конвертировать
    body = {
        "channelId": WAZZUP_CHANNEL_ID,
        "chatId": chat_id,
        "chatType": "instagram",
        "text": text,
    }
    delays = [0, 2, 4]
    for attempt, delay in enumerate(delays):
        if delay:
            await asyncio.sleep(delay)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=body, headers=headers) as resp:
                    result = await resp.text()
                    log.info(
                        f"📤 Wazzup → {chat_id} attempt={attempt + 1} "
                        f"[{resp.status}]: {result[:200]}"
                    )
                    if resp.status < 500:
                        now = datetime.now(timezone.utc)
                        bucket = sent_texts.setdefault(chat_id, {})
                        expired = [t for t, ts in bucket.items() if (now - ts).total_seconds() > 3600]
                        for t in expired:
                            del bucket[t]
                        if len(bucket) >= 1000:
                            oldest = sorted(bucket, key=lambda t: bucket[t])[:len(bucket) - 999]
                            for t in oldest:
                                del bucket[t]
                        bucket[text] = now
                        return
                    log.warning(f"⚠️ Wazzup attempt {attempt + 1} status={resp.status}")
        except Exception as e:
            log.warning(f"⚠️ Wazzup attempt {attempt + 1} error: {e}")
    log.error(f"❌ Wazzup: все 3 попытки провалились для {chat_id}")


# ---------- EnvyCRM API ----------
async def find_lead(username: str, phone: str | None = None, retries: int = 3, delay: float = 3.0) -> int | None:
    url = f"{ENVY_CRM_URL}/openapi/v1/lead/list?api_key={ENVY_API_KEY}"
    headers = {"Content-Type": "application/json"}
    body = {"limit": 1, "inputs": {"phone": phone}} if phone else {"limit": 1, "keyword": username}
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=body, headers=headers) as resp:
                    raw = await resp.text()
                    log.info(f"🔍 find_lead attempt={attempt+1} raw [{resp.status}]: {raw[:300]}")
                    data = json.loads(raw) if raw else {}
                    leads_data = data.get("leads") or {}
                    result = leads_data.get("result") or []
                    if result:
                        lead_id = result[0]["id"]
                        log.info(f"🔍 find_lead username={username} phone={phone} → lead_id={lead_id}")
                        return lead_id
                    all_ids = leads_data.get("all_ids") or []
                    if all_ids and attempt == retries - 1:
                        log.warning(f"⚠️ find_lead: result пуст, но all_ids есть ({all_ids[0]}), используем как fallback")
                        return all_ids[0]
        except Exception as e:
            log.error(f"❌ find_lead error attempt={attempt+1}: {e}")
        if attempt < retries - 1:
            await asyncio.sleep(delay)
    log.warning(f"⚠️ find_lead: лид не найден после {retries} попыток для username={username}")
    return None


async def create_lead_log(lead_id: int, comment: str) -> None:
    try:
        url = f"{ENVY_CRM_URL}/openapi/v1/lead/log/create?api_key={ENVY_API_KEY}"
        headers = {"Content-Type": "application/json"}
        body = {"lead_id": lead_id, "type_id": 10, "data": {"comment": comment}}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=headers) as resp:
                result = await resp.text()
                log.info(f"📝 create_lead_log lead_id={lead_id} [{resp.status}]: {result[:200]}")
    except Exception as e:
        log.error(f"❌ create_lead_log error: {e}")


async def lead_to_inbox(lead_id: int, chat_id: str, known_deal_id: int | None = None) -> None:
    try:
        headers = {"Content-Type": "application/json"}
        deal_id = known_deal_id

        if not deal_id:
            url1 = f"{ENVY_CRM_URL}/openapi/v1/lead/get?api_key={ENVY_API_KEY}"
            body1 = {"lead_id": lead_id}
            async with aiohttp.ClientSession() as session:
                async with session.post(url1, json=body1, headers=headers) as resp:
                    data = await resp.json()
                    log.info(f"🔎 lead/get [{resp.status}]: {json.dumps(data, ensure_ascii=False)[:1000]}")
                    deals = data.get("result", {}).get("deals") or []
                    if deals:
                        deal_id = deals[0]
                        log.info(f"✅ lead/get извлечён deal_id={deal_id}")
                        await save_deal_id(chat_id, deal_id)

        if not deal_id:
            random_employee_id = random.choice(REAL_MANAGERS)
            url_start = f"{ENVY_CRM_URL}/openapi/v1/lead/start?api_key={ENVY_API_KEY}"
            body_start = {"lead_id": lead_id, "user_id": 346511, "employee_id": random_employee_id}
            log.info(f"🎲 Случайный менеджер для lead/start: {random_employee_id}")
            async with aiohttp.ClientSession() as session:
                async with session.post(url_start, json=body_start, headers=headers) as resp:
                    data = await resp.json()
                    log.info(f"🚀 lead/start [{resp.status}]: {json.dumps(data, ensure_ascii=False)[:500]}")
                    new_deal_id = (data.get("result") or {}).get("deal_id")
                    if new_deal_id:
                        deal_id = new_deal_id
                        log.info(f"✅ lead/start deal_id={deal_id}")
                        await save_deal_id(chat_id, deal_id)

        if not deal_id:
            log.warning(f"⚠️ lead_to_inbox: нет deal_id для lead_id={lead_id}, пропускаем toInbox")
            return

        url2 = f"{ENVY_CRM_URL}/openapi/v1/deal/toInbox?api_key={ENVY_API_KEY}"
        body2 = {"deal_id": deal_id}
        async with aiohttp.ClientSession() as session:
            async with session.post(url2, json=body2, headers=headers) as resp:
                result = await resp.text()
                log.info(f"📥 deal/toInbox deal_id={deal_id} [{resp.status}]: {result[:200]}")
    except Exception as e:
        log.error(f"❌ lead_to_inbox error: {e}")


async def notify_manager(chat_id: str, username: str, phone: str | None = None, known_deal_id: int | None = None) -> None:
    try:
        lead_id = await find_lead(username, phone)
        if lead_id is None:
            log.warning(f"⚠️ notify_manager: лид не найден для username={username} phone={phone}")
            return
        if phone:
            await create_lead_log(lead_id, f"🤖 Лола: клиент {username} оставил номер {phone}. Позвонить!")
        else:
            await create_lead_log(lead_id, f"🤖 Лола: новый клиент {username} написал в Instagram. Проверить диалог.")
        asyncio.create_task(lead_to_inbox(lead_id, chat_id, known_deal_id))
    except Exception as e:
        log.error(f"❌ notify_manager error: {e}")


# ---------- Helpers ----------
def extract_phone(text: str) -> str | None:
    m = PHONE_RE.search(text)
    if m:
        if len(re.sub(r"\D", "", m.group())) >= 10:
            return m.group()
    return None


def is_refusal(text: str) -> bool:
    lower = text.lower()
    for phrase in REFUSE_WORDS:
        pattern = r'\b' + re.escape(phrase) + r'\b'
        if re.search(pattern, lower):
            return True
    return False


def detect_lang(text: str) -> str:
    """Простое определение языка по символам и доле ASCII-букв."""
    kz_chars = set("әіңғүұқөһ")
    kz_words = [
        "керек", "емес", "жоқ", "бар", "барып", "журсек",
        "болмаима", "сурап", "озимиз", "қайда", "қалай",
        "рахмет", "сәлем", "жақсы", "бұл", "мен", "сен",
    ]
    lower_text = text.lower()
    if any(c in kz_chars for c in lower_text):
        return "kz"
    if any(word in lower_text for word in kz_words):
        return "kz"
    return "ru"


async def claude_reply(messages: list[dict]) -> str:
    while messages and messages[0].get("role") == "assistant":
        messages = messages[1:]
    cleaned = []
    for msg in messages:
        if cleaned and cleaned[-1]["role"] == msg["role"]:
            continue
        cleaned.append(msg)
    messages = cleaned
    while messages and messages[0].get("role") == "assistant":
        messages = messages[1:]
    if not messages:
        messages = [{"role": "user", "content": "Здравствуйте"}]
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    msg = await client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        temperature=0.5,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=messages,
    )
    return msg.content[0].text


MAX_HISTORY = 20


# ---------- Основная логика диалога ----------
async def handle_incoming(chat_id: str, text: str | None) -> None:
    async with get_lock(chat_id):
        await _handle_incoming(chat_id, text)


async def _handle_incoming(chat_id: str, text: str | None) -> None:
    state, history, updated_at, deal_id = await get_state(chat_id)

    if state == STATE_NEW and history and history[0].get("content") == text:
        log.info(f"♻️ Дубль сообщения в STATE_NEW {chat_id}, пропускаем")
        return

    if state == STATE_SMM:
        log.info(f"🔇 {chat_id} state=smm, молчим навсегда")
        return

    if state in SILENT_STATES:
        now = datetime.now(timezone.utc)
        if updated_at:
            elapsed = (now - updated_at).total_seconds()
            if state == STATE_MANAGER and elapsed >= 3600:  # 1 час
                log.info(f"🔄 {chat_id} state=manager устарел (>1ч), сбрасываем")
                state = None
            elif state in {STATE_DONE, STATE_REFUSED} and elapsed >= 3600:  # 1 час
                log.info(f"🔄 {chat_id} state={state} устарел (>1 часа), сбрасываем")
                state = None
            else:
                log.info(f"🔇 {chat_id} state={state}, молчим")
                return
        else:
            log.info(f"🔇 {chat_id} state={state}, молчим")
            return

    # Новый диалог — передаём первое сообщение клиента в Claude
    if state is None:
        if history is None:
            history = []
        is_truly_new = len(history) == 0
        if text:
            history.append({"role": "user", "content": text})
        else:
            history.append({"role": "user", "content": "Здравствуйте"})
        try:
            reply = await claude_reply(history)
            if not reply or not reply.strip():
                raise ValueError("пустой ответ")
        except Exception as e:
            log.error(f"❌ Claude error on greeting: {e}")
            lang = detect_lang(text or "")
            reply = CLAUDE_FALLBACK.get(lang, CLAUDE_FALLBACK["ru"])
        history.append({"role": "assistant", "content": reply})
        await send_wazzup(chat_id, reply)
        new_state = STATE_NEW if is_truly_new else STATE_ACTIVE
        await set_state(chat_id, new_state, history=history)
        if should_notify(chat_id):
            asyncio.create_task(notify_manager(chat_id, chat_id, known_deal_id=deal_id))
        log.info(f"👋 {'Новый' if is_truly_new else 'Возобновлённый'} диалог {chat_id} → {new_state}")
        return

    # state = "new" или "active" — нужен текст клиента
    if not text:
        return

    phone = extract_phone(text)
    if phone:
        lang = detect_lang(text)
        thanks = THANKS_MSGS.get(lang, THANKS_MSGS["ru"])
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": thanks})
        await send_wazzup(chat_id, thanks)
        asyncio.create_task(notify_manager(chat_id, chat_id, phone, known_deal_id=deal_id))
        await set_state(chat_id, STATE_DONE, history=history)
        log.info(f"📞 {chat_id} дал телефон={phone} lang={lang} → STATE_DONE")
        return

    if is_refusal(text):
        lang = detect_lang(text)
        farewell = FAREWELL_MSGS.get(lang, FAREWELL_MSGS["ru"])
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": farewell})
        await send_wazzup(chat_id, farewell)
        await set_state(chat_id, STATE_REFUSED, history=history)
        log.info(f"🚫 {chat_id} отказался lang={lang} → STATE_REFUSED")
        return

    # Добавляем сообщение клиента, обрезаем до MAX_HISTORY перед отправкой в Claude
    history.append({"role": "user", "content": text})
    history = history[-MAX_HISTORY:]

    try:
        reply = await claude_reply(history)
        if not reply or not reply.strip():
            raise ValueError("пустой ответ")
    except Exception as e:
        log.error(f"❌ Claude error: {e}")
        reply = CLAUDE_FALLBACK.get(detect_lang(text or ""), CLAUDE_FALLBACK["ru"])

    # Добавляем ответ Лолы и сохраняем
    history.append({"role": "assistant", "content": reply})
    history = history[-MAX_HISTORY:]

    await send_wazzup(chat_id, reply)
    await set_state(chat_id, STATE_ACTIVE, history=history)
    if should_notify(chat_id):
        asyncio.create_task(notify_manager(chat_id, chat_id, known_deal_id=deal_id))
    log.info(f"🤖 {chat_id} ответ Claude → STATE_ACTIVE (history={len(history)})")


# ---------- Эндпоинты ----------
async def envy_hook_handler(request: web.Request) -> web.Response:
    if os.getenv("BOT_PAUSED", "false").lower() == "true":
        log.info("⏸️ Бот на паузе, игнорируем")
        return web.Response(text="ok")

    try:
        payload = await request.json()
    except Exception:
        return web.Response(text="ok")

    log.info(f"📨 envy_hook payload: {json.dumps(payload, ensure_ascii=False)[:1000]}")

    event_type = payload.get("event_type")

    if event_type == "message_reply":
        message_text = (payload.get("message_data") or {}).get("text") or ""
        contact_check = payload.get("contact") or {}
        chat_id_check = str(contact_check.get("external_id") or "").strip()
        if chat_id_check.startswith("inst-"):
            chat_id_check = chat_id_check[5:]
        if message_text and chat_id_check in sent_texts and message_text in sent_texts[chat_id_check]:
            log.info(f"🔄 Эхо Лолы text={message_text[:50]!r}, игнорируем")
            return web.Response(text="ok")
        SMM_KEYWORDS = ["штат моделей", "съёмк", "съемк", "смм менеджер", "сотрудничеств", "исходник", "модел"]
        if any(kw in message_text.lower() for kw in SMM_KEYWORDS):
            if chat_id_check:
                await set_state(chat_id_check, STATE_SMM)
                log.info(f"📸 SMM-рассылка → {chat_id_check} STATE_SMM (навсегда)")
            return web.Response(text="ok")
        from_user = payload.get("from_user") or {}
        crm_employee_id = from_user.get("crm_employee_id")
        if crm_employee_id and crm_employee_id != 0 and crm_employee_id > 100000:
            contact = payload.get("contact") or {}
            chat_id = str(contact.get("external_id") or "").strip()
            if chat_id.startswith("inst-"):
                chat_id = chat_id[5:]
            if chat_id:
                await set_state(chat_id, STATE_MANAGER)
                log.info(f"👨‍💼 Менеджер (crm_employee_id={crm_employee_id}) взял {chat_id} → STATE_MANAGER")
        else:
            log.info("⏭️ message_reply от системы, игнорируем")
        return web.Response(text="ok")

    if event_type != "message":
        log.info(f"⏭️ event_type={event_type!r}, игнорируем")
        return web.Response(text="ok")

    # Дедупликация по message_id
    message_id = payload.get("message_id")
    if message_id is not None:
        if message_id in processed_message_ids:
            log.info(f"♻️ Дубль message_id={message_id}, пропускаем")
            return web.Response(text="ok")
        processed_message_ids.append(message_id)

    contact = payload.get("contact") or {}
    chat_id = str(contact.get("external_id") or "").strip()
    if chat_id.startswith("inst-"):
        chat_id = chat_id[5:]
    if not chat_id:
        log.warning("⚠️ Нет contact.external_id в payload, пропускаем")
        return web.Response(text="ok")
    log.info(f"📌 chat_id={chat_id}")

    from_user = payload.get("from_user") or {}
    crm_employee_id = from_user.get("crm_employee_id")

    if crm_employee_id is not None and crm_employee_id != 0 and crm_employee_id > 100000:
        await set_state(chat_id, STATE_MANAGER)
        log.info(f"👨‍💼 Менеджер (crm_employee_id={crm_employee_id}) взял {chat_id} → STATE_MANAGER")
        return web.Response(text="ok")

    # Сообщение от клиента
    message_data = payload.get("message_data") or {}
    raw_text = message_data.get("text") or ""
    attachments = message_data.get("attachments") or []
    if raw_text.strip() == "You mentioned in the story":
        log.info("⏭️ Отметка в сторис, игнорируем")
        return web.Response(text="ok")
    if any(a.get("type") in ("story", "video") and not raw_text.strip() for a in attachments):
        log.info("⏭️ Вложение сторис без текста, игнорируем")
        return web.Response(text="ok")
    if any(a.get("type") in ("audio", "voice") and not raw_text.strip() for a in attachments):
        log.info(f"🎤 Голосовое сообщение без текста от {chat_id}, передаём как маркер")
        text = "[клиент отправил голосовое сообщение]"
    else:
        text: str | None = raw_text.strip() if raw_text else None

    try:
        await handle_incoming(chat_id, text)
    except Exception as e:
        log.error(f"❌ handle_incoming error {chat_id}: {e}", exc_info=True)

    return web.Response(text="ok")


async def webhook_handler(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def wazzup_handler(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "bot_enabled": True})



# ---------- DB ----------
async def init_db(app: web.Application) -> None:
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS dialogs (
                chat_id    TEXT PRIMARY KEY,
                state      TEXT NOT NULL DEFAULT 'new',
                lead_id    TEXT,
                history    JSONB NOT NULL DEFAULT '[]',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            ALTER TABLE dialogs
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()
        """)
        await conn.execute("""
            ALTER TABLE dialogs
            ADD COLUMN IF NOT EXISTS history JSONB NOT NULL DEFAULT '[]'
        """)
        await conn.execute("""
            ALTER TABLE dialogs
            ADD COLUMN IF NOT EXISTS deal_id BIGINT
        """)
    log.info("✅ DB готова")


async def close_db(app: web.Application) -> None:
    if db_pool:
        await db_pool.close()


# ---------- App factory ----------
def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/webhook",   webhook_handler)
    app.router.add_get( "/webhook",   lambda r: web.Response(text="ok"))
    app.router.add_post("/envy_hook", envy_hook_handler)
    app.router.add_post("/wazzup",    wazzup_handler)
    app.router.add_get( "/health",    health_handler)
    app.on_startup.append(init_db)
    app.on_cleanup.append(close_db)
    return app


if __name__ == "__main__":
    app = create_app()
    log.info("🚀 Champion Bot запущен")
    web.run_app(app, host="0.0.0.0", port=PORT)
