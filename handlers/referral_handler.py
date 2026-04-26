import logging
import os
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from models.database import (
    get_user, update_user, get_all_users,
    create_ref_code, get_ref_code, get_ref_stats,
    save_ref_conversion, mark_ref_paid
)

router = Router()
logger = logging.getLogger(__name__)

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
COMMISSION_PERCENT = 10  # % от оплаты блогеру


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ──────────────────────────────────────────────
# СОЗДАТЬ РЕФ-ССЫЛКУ
# ──────────────────────────────────────────────

@router.message(Command("addref"))
async def cmd_addref(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "Использование:\n"
            "`/addref @username` — создать реф-ссылку для блогера\n\n"
            "Например: `/addref @bloger_aliya`",
            parse_mode="Markdown"
        )
        return

    blogger = parts[1].replace("@", "").lower()
    ref_code = f"ref_{blogger}"

    await create_ref_code(ref_code, blogger)

    bot_username = (await message.bot.get_me()).username

    await message.answer(
        f"✅ *Реф-ссылка создана!*\n\n"
        f"Блогер: @{blogger}\n"
        f"Код: `{ref_code}`\n\n"
        f"*Ссылка для блогера:*\n"
        f"`https://t.me/{bot_username}?start={ref_code}`\n\n"
        f"Скопируй и отправь блогеру 💜",
        parse_mode="Markdown"
    )


# ──────────────────────────────────────────────
# СТАТИСТИКА РЕФЕРАЛОВ
# ──────────────────────────────────────────────

@router.message(Command("refstats"))
async def cmd_refstats(message: Message):
    if not is_admin(message.from_user.id):
        return

    stats = await get_ref_stats()

    if not stats:
        await message.answer(
            "📊 Рефералов пока нет.\n\n"
            "Создай первую ссылку командой `/addref @username`",
            parse_mode="Markdown"
        )
        return

    text = "📊 *Статистика рефералов*\n\n"
    total_debt = 0

    for s in stats:
        blogger = s.get("blogger_username", "—")
        total = s.get("total") or 0
        paid = s.get("paid_count") or 0
        amount = s.get("total_amount") or 0
        commission = int(amount * COMMISSION_PERCENT / 100)
        total_debt += commission

        text += (
            f"👤 *@{blogger}*\n"
            f"   Пришло: {total} чел. | Оплатили: {paid}\n"
            f"   Сумма оплат: {amount:,}₸\n"
            f"   Комиссия ({COMMISSION_PERCENT}%): *{commission:,}₸*\n\n"
        )

    text += f"━━━━━━━━━━━━━━━━━\n"
    text += f"💰 *Итого к выплате: {total_debt:,}₸*"

    await message.answer(text, parse_mode="Markdown")


# ──────────────────────────────────────────────
# МОЯ РЕФ-ССЫЛКА (для блогера)
# ──────────────────────────────────────────────

@router.message(Command("myref"))
async def cmd_myref(message: Message):
    """Блогер может проверить свою статистику"""
    username = message.from_user.username
    if not username:
        await message.answer("У тебя нет username в Telegram 😔")
        return

    ref_code = f"ref_{username.lower()}"
    stats = await get_ref_stats(ref_code)

    if not stats:
        await message.answer(
            "У тебя пока нет реф-ссылки.\n"
            "Обратись к администратору @mirra_support"
        )
        return

    s = stats[0]
    total = s.get("total") or 0
    paid = s.get("paid_count") or 0
    amount = s.get("total_amount") or 0
    commission = int(amount * COMMISSION_PERCENT / 100)

    bot_username = (await message.bot.get_me()).username

    await message.answer(
        f"📊 *Твоя статистика*\n\n"
        f"Перешли по твоей ссылке: *{total}* чел.\n"
        f"Из них оплатили: *{paid}* чел.\n"
        f"Твоя комиссия: *{commission:,}₸*\n\n"
        f"*Твоя ссылка:*\n"
        f"`https://t.me/{bot_username}?start={ref_code}`",
        parse_mode="Markdown"
    )
