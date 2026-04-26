import os
import logging
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
from aiogram.types import FSInputFile

from models.database import (
    get_all_users, get_week_dialogs, get_month_dialogs,
    get_month_diary, delete_old_diary, delete_old_dialogs, get_user
)
from services.ai_service import generate_weekly_report
from services.pdf_service import generate_diary_pdf
from utils.keyboards import main_menu

logger = logging.getLogger(__name__)


async def keepalive_ping():
    """Пингуем базу каждые 4 минуты чтобы не засыпала"""
    try:
        from models.database import _execute
        _execute("SELECT 1", fetch="one")
        logger.debug("✅ DB keepalive ok")
    except Exception as e:
        logger.warning(f"DB keepalive error: {e}")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Almaty")

    # Keep-alive пинг БД — каждые 4 минуты чтобы Postgres не засыпал
    scheduler.add_job(
        keepalive_ping, CronTrigger(minute="*/4"),
        id="keepalive", replace_existing=True
    )

    # Вечерний чекин — каждый день в 20:00
    scheduler.add_job(
        evening_checkin, CronTrigger(hour=20, minute=0),
        args=[bot], id="evening_checkin", replace_existing=True
    )

    # Еженедельный отчёт — воскресенье 18:00
    scheduler.add_job(
        weekly_report_job, CronTrigger(day_of_week="sun", hour=18, minute=0),
        args=[bot], id="weekly_report", replace_existing=True
    )

    # Ежемесячный PDF дневник — 1-го числа каждого месяца в 10:00
    scheduler.add_job(
        monthly_diary_pdf, CronTrigger(day=1, hour=10, minute=0),
        args=[bot], id="monthly_diary", replace_existing=True
    )

    # Очистка старых данных — каждую ночь в 3:00
    scheduler.add_job(
        cleanup_old_data, CronTrigger(hour=3, minute=0),
        args=[bot], id="cleanup", replace_existing=True
    )

    return scheduler


# ──────────────────────────────────────────────
# ВЕЧЕРНИЙ ЧЕКИН
# ──────────────────────────────────────────────

async def evening_checkin(bot: Bot):
    """Вечернее напоминание — для ВСЕХ пользователей бесплатно"""
    users = await get_all_users()
    logger.info(f"Вечерний чекин: {len(users)} пользователей")

    messages = [
        "🌙 Как прошёл твой день?\n\nЗапиши одну эмоцию — бесплатно, 5 секунд 💜",
        "Добрый вечер ✨\n\nОдна эмоция дня — и твой дневник пополнится. Как ты сейчас?",
        "🌙 Стоп. Выдохни.\n\nКак ты сегодня? Одно нажатие — и день зафиксирован 💜",
        "Вечер настал 🌿\n\nЧто осталось от сегодняшнего дня внутри тебя?",
        "🌙 Mirra здесь.\n\nКак одним словом описать твой сегодняшний день?",
    ]

    for user in users:
        try:
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            from aiogram.types import InlineKeyboardButton
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="😊 Хорошо", callback_data="mood_good"),
                InlineKeyboardButton(text="😐 Нормально", callback_data="mood_normal"),
                InlineKeyboardButton(text="😔 Грустно", callback_data="mood_sad")
            )
            builder.row(
                InlineKeyboardButton(text="😰 Тревожно", callback_data="mood_anxious"),
                InlineKeyboardButton(text="😤 Злюсь", callback_data="mood_angry"),
                InlineKeyboardButton(text="😴 Устала", callback_data="mood_tired")
            )

            await bot.send_message(
                chat_id=user["telegram_id"],
                text=random.choice(messages),
                reply_markup=builder.as_markup()
            )
        except Exception as e:
            logger.warning(f"Ошибка чекина для {user['telegram_id']}: {e}")


# ──────────────────────────────────────────────
# ЕЖЕНЕДЕЛЬНЫЙ ОТЧЁТ
# ──────────────────────────────────────────────

async def weekly_report_job(bot: Bot):
    users = await get_all_users()
    logger.info(f"Еженедельный отчёт: {len(users)} пользователей")

    for user in users:
        try:
            dialogs = await get_week_dialogs(user["telegram_id"])
            if not dialogs:
                continue
            name = user.get("user_name_custom") or user.get("first_name", "")
            from services.ai_service import generate_weekly_report
            report = await generate_weekly_report(dialogs, name)
            await bot.send_message(
                chat_id=user["telegram_id"],
                text=f"📊 *Твоя неделя в Mirra*\n\n{report}",
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
        except Exception as e:
            logger.warning(f"Ошибка отчёта для {user['telegram_id']}: {e}")


# ──────────────────────────────────────────────
# ЕЖЕМЕСЯЧНЫЙ PDF ДНЕВНИК
# ──────────────────────────────────────────────

async def monthly_diary_pdf(bot: Bot):
    users = await get_all_users()
    logger.info(f"Ежемесячный PDF: {len(users)} пользователей")

    for user in users:
        user_id = user["telegram_id"]
        try:
            dialogs = await get_month_dialogs(user_id)
            diary_entries = await get_month_diary(user_id)

            if not dialogs and not diary_entries:
                continue

            name = user.get("user_name_custom") or user.get("first_name") or "Дорогая"

            # Генерируем PDF
            pdf_path = f"/tmp/mirra_diary_{user_id}.pdf"
            generate_diary_pdf(name, dialogs, diary_entries, pdf_path)

            # Отправляем
            from datetime import datetime
            month = datetime.now().strftime("%B %Y")

            await bot.send_document(
                chat_id=user_id,
                document=FSInputFile(pdf_path, filename=f"Mirra_Дневник_{month}.pdf"),
                caption=(
                    f"📖 *Твой дневник за {month}*\n\n"
                    f"Здесь собраны все наши разговоры, записи и настроения месяца.\n\n"
                    f"Сохрани этот файл себе 💜\n\n"
                    f"_Записи из базы будут очищены через несколько дней — "
                    f"этот PDF теперь твой архив._"
                ),
                parse_mode="Markdown"
            )

            # Удаляем временный файл
            os.remove(pdf_path)

        except Exception as e:
            logger.warning(f"Ошибка PDF для {user_id}: {e}")


# ──────────────────────────────────────────────
# ОЧИСТКА СТАРЫХ ДАННЫХ
# ──────────────────────────────────────────────

async def cleanup_old_data(bot: Bot):
    """Удаляем диалоги и дневник старше 30 дней"""
    users = await get_all_users()
    logger.info(f"Очистка данных: {len(users)} пользователей")

    for user in users:
        try:
            await delete_old_diary(user["telegram_id"])
            await delete_old_dialogs(user["telegram_id"])
        except Exception as e:
            logger.warning(f"Ошибка очистки для {user['telegram_id']}: {e}")
