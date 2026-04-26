import logging
import os
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    LabeledPrice, PreCheckoutQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from models.database import get_user, update_user, get_all_users, get_or_create_user

router = Router()
logger = logging.getLogger(__name__)

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
STARS_PRICE = 300
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@mirra_support")
TON_WALLET = "kamshat 8458"  # Telegram Wallet для России
RU_PRICE = "$7"
KZ_PRICE = "3 000 ₸"

# ──────────────────────────────────────────────
# КЛАВИАТУРА ОПЛАТЫ
# ──────────────────────────────────────────────

def payment_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="⭐️ Оплатить Telegram Stars",
        callback_data="pay_stars"
    ))
    builder.row(InlineKeyboardButton(
        text="💳 Kaspi / карта (Казахстан)",
        callback_data="pay_manual"
    ))
    builder.row(InlineKeyboardButton(
        text="💎 TON / Telegram Wallet (Россия и др.)",
        callback_data="pay_ton"
    ))
    builder.row(InlineKeyboardButton(
        text="🏠 Главное меню",
        callback_data="back_menu"
    ))
    return builder.as_markup()


def back_to_payment() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад к оплате", callback_data="subscribe"))
    return builder.as_markup()


# ──────────────────────────────────────────────
# ПОДПИСКА — ВЫБОР СПОСОБА
# ──────────────────────────────────────────────

@router.callback_query(F.data == "subscribe")
async def show_payment_options(callback: CallbackQuery):
    await callback.message.edit_text(
        "💜 *Mirra Pro*\n\n"
        "🇰🇿 Казахстан: *3 000 ₸/месяц*\n"
        "🇷🇺 Россия и др.: *$7/месяц* (~650₽)\n\n"
        "Что входит:\n"
        "✅ Безлимитные диалоги с психологом\n"
        "✅ Все 8 проективных тестов\n"
        "✅ И-Цзин, МАК-карты, нумерология\n"
        "✅ Медитации и визуализации\n"
        "✅ Личный дневник + PDF отчёт\n\n"
        "Выбери способ оплаты 👇",
        parse_mode="Markdown",
        reply_markup=payment_keyboard()
    )
    await callback.answer()


# ──────────────────────────────────────────────
# ВАРИАНТ 1 — TELEGRAM STARS
# ──────────────────────────────────────────────

@router.callback_query(F.data == "pay_stars")
async def pay_with_stars(callback: CallbackQuery):
    await callback.message.answer_invoice(
        title="Mirra Pro — подписка на месяц",
        description="Безлимитный доступ ко всем функциям Mirra: психолог, И-Цзин, МАК-карты, нумерология, медитации, дневник.",
        payload=f"subscription_1month_{callback.from_user.id}",
        currency="XTR",  # Telegram Stars
        prices=[LabeledPrice(label="Mirra Pro (1 месяц)", amount=STARS_PRICE)],
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """Telegram спрашивает — подтверждаем оплату"""
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message):
    """Оплата прошла — открываем доступ"""
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload

    # Открываем подписку на 30 дней
    until = (datetime.now() + timedelta(days=30)).isoformat()
    await update_user(user_id, is_subscribed=1, subscription_until=until)

    stars_amount = message.successful_payment.total_amount

    logger.info(f"✅ Оплата Stars от {user_id}: {stars_amount} Stars")

    # Уведомляем администратора
    if ADMIN_ID:
        user = await get_user(user_id)
        name = user.get("first_name", "—") if user else "—"
        username = user.get("username", "—") if user else "—"
        try:
            from aiogram import Bot
            # Получаем bot из контекста — он передаётся через middleware
            pass
        except Exception:
            pass

    await message.answer(
        "🎉 *Оплата прошла успешно!*\n\n"
        "Добро пожаловать в Mirra Pro 💜\n\n"
        "Теперь у тебя безлимитный доступ на 30 дней.\n"
        "Я рядом — в любое время, когда нужна 🌙",
        parse_mode="Markdown"
    )

    # Отправляем главное меню
    from utils.keyboards import main_menu
    await message.answer("Что сделаем сегодня?", reply_markup=main_menu())


# ──────────────────────────────────────────────
# ВАРИАНТ 2 — РУЧНАЯ ОПЛАТА
# ──────────────────────────────────────────────

@router.callback_query(F.data == "pay_ton")
async def pay_ton(callback: CallbackQuery):
    await callback.message.edit_text(
        "💎 *Оплата через Telegram Wallet / TON*\n\n"
        "Стоимость: *$7 в месяц* (~650₽)\n\n"
        "Переведи на Telegram username:\n"
        "*@kamshat8458*\n\n"
        "Или на TON-кошелёк — напиши мне и я пришлю адрес.\n\n"
        "📌 *Важно:* в комментарии к переводу укажи свой "
        "Telegram username чтобы я могла найти тебя и открыть доступ.\n\n"
        "После оплаты напиши администратору 👇",
        parse_mode="Markdown",
        reply_markup=_pay_ton_keyboard()
    )
    await callback.answer()


def _pay_ton_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="✅ Написать после оплаты",
        url="https://t.me/kamshat8458"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="subscribe"
    ))
    return builder.as_markup()


# ──────────────────────────────────────────────
# АДМИН-КОМАНДЫ
# ──────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return

    # Открываем вечный доступ для самого себя
    until = "2099-01-01T00:00:00"
    await update_user(message.from_user.id, is_subscribed=1, subscription_until=until)

    await message.answer(
        "👑 *Режим администратора*\n\n"
        "✅ Тебе открыт безлимитный доступ навсегда\n\n"
        "*Команды:*\n"
        "`/give_access [user_id]` — дать подписку на 30 дней\n"
        "`/revoke_access [user_id]` — забрать подписку\n"
        "`/stats` — статистика пользователей\n"
        "`/broadcast [текст]` — рассылка всем пользователям",
        parse_mode="Markdown"
    )


@router.message(Command("give_access"))
async def cmd_give_access(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "Использование:\n"
            "`/give_access @username` — по юзернейму\n"
            "`/give_access 123456789` — по ID\n"
            "`/give_access @username 60` — на 60 дней",
            parse_mode="Markdown"
        )
        return

    target = parts[1].replace("@", "")
    days = int(parts[2]) if len(parts) > 2 else 30

    try:
        # Если число — это ID
        if target.isdigit():
            target_id = int(target)
        else:
            # Ищем по username в базе
            pool = None
            from models.database import _init_pool
            import psycopg2.extras
            p = _init_pool()
            conn = p.getconn()
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        "SELECT telegram_id, first_name FROM users WHERE LOWER(username) = LOWER(%s)",
                        (target,)
                    )
                    user = cur.fetchone()
            finally:
                p.putconn(conn)

            if not user:
                await message.answer(
                    f"❌ Пользователь @{target} не найден в базе.\n\n"
                    f"Он должен сначала запустить бота (/start).",
                    parse_mode="Markdown"
                )
                return

            target_id = user["telegram_id"]
            name = user.get("first_name", target)
            await message.answer(f"✅ Нашла: {name} (ID: {target_id})")

        # Даём доступ
        from datetime import datetime, timedelta
        from models.database import update_user
        until = (datetime.now() + timedelta(days=days)).isoformat()
        await update_user(target_id, is_subscribed=1, subscription_until=until)

        # Уведомляем пользователя
        try:
            from utils.keyboards import main_menu
            await message.bot.send_message(
                chat_id=target_id,
                text=f"🎉 *Твоя подписка Mirra Pro активирована!*\n\n"
                     f"Доступ открыт на *{days} дней* 💜\n\n"
                     f"Я рядом — в любое время 🌙",
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить {target_id}: {e}")

        await message.answer(
            f"✅ Подписка выдана на {days} дней\n"
            f"До: {until[:10]}",
            parse_mode="Markdown"
        )

    except ValueError:
        await message.answer("❌ Неверный формат. Используй @username или числовой ID")


@router.message(Command("revoke_access"))
async def cmd_revoke_access(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: `/revoke_access 123456789`", parse_mode="Markdown")
        return

    try:
        target_id = int(parts[1])
        await update_user(target_id, is_subscribed=0, subscription_until=None)
        await message.answer(f"✅ Доступ у пользователя `{target_id}` отозван", parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ Неверный ID", parse_mode="Markdown")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    users = await get_all_users()
    total = len(users)
    subscribed = sum(1 for u in users if u.get("is_subscribed"))
    active_today = sum(1 for u in users if u.get("last_active", "")[:10] == datetime.now().strftime("%Y-%m-%d"))

    await message.answer(
        f"📊 *Статистика Mirra*\n\n"
        f"👥 Всего пользователей: *{total}*\n"
        f"💜 Активных подписок: *{subscribed}*\n"
        f"🟢 Активны сегодня: *{active_today}*\n"
        f"🆓 На бесплатном: *{total - subscribed}*\n\n"
        f"💰 Доход в месяц (потенциал): *{subscribed * 3000:,} ₸*",
        parse_mode="Markdown"
    )


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        return

    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer("Использование: `/broadcast Привет! Новая функция...`", parse_mode="Markdown")
        return

    users = await get_all_users()
    sent = 0
    failed = 0

    await message.answer(f"📤 Начинаю рассылку для {len(users)} пользователей...")

    for user in users:
        try:
            await message.bot.send_message(
                chat_id=user["telegram_id"],
                text=f"📢 *Сообщение от Mirra*\n\n{text}",
                parse_mode="Markdown"
            )
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        f"✅ Рассылка завершена\n"
        f"Отправлено: {sent}\n"
        f"Ошибок: {failed}"
    )
