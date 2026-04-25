import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

from models.database import get_all_users, get_week_dialogs, get_user
from services.ai_service import generate_weekly_report
from utils.keyboards import main_menu, mood_keyboard

logger = logging.getLogger(__name__)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Almaty")

    # Утренний чекин — каждый день в 9:00
    scheduler.add_job(
        morning_checkin,
        CronTrigger(hour=9, minute=0),
        args=[bot],
        id="morning_checkin",
        replace_existing=True
    )

    # Еженедельный отчёт — каждое воскресенье в 18:00
    scheduler.add_job(
        weekly_report_job,
        CronTrigger(day_of_week="sun", hour=18, minute=0),
        args=[bot],
        id="weekly_report",
        replace_existing=True
    )

    return scheduler


async def morning_checkin(bot: Bot):
    """Утреннее сообщение пользователям"""
    users = await get_all_users()
    logger.info(f"Утренний чекин для {len(users)} пользователей")

    messages = [
        "Доброе утро! ☀️\n\nКак ты сегодня? Выбери своё состояние:",
        "Привет! 🌸\n\nНовый день начинается. Как ты сейчас?",
        "Доброе утро 🌿\n\nЯ здесь. Как твоё состояние сегодня?",
        "Привет, солнце! ✨\n\nКак ты встретила это утро?",
    ]

    import random
    for user in users:
        try:
            msg = random.choice(messages)
            await bot.send_message(
                chat_id=user["telegram_id"],
                text=msg,
                reply_markup=mood_keyboard()
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить чекин пользователю {user['telegram_id']}: {e}")


async def weekly_report_job(bot: Bot):
    """Еженедельный отчёт всем пользователям"""
    users = await get_all_users()
    logger.info(f"Еженедельный отчёт для {len(users)} пользователей")

    for user in users:
        try:
            dialogs = await get_week_dialogs(user["telegram_id"])
            if not dialogs:
                continue

            name = user.get("first_name", "")
            report = await generate_weekly_report(dialogs, name)

            await bot.send_message(
                chat_id=user["telegram_id"],
                text=f"📊 *Твой еженедельный отчёт от Mirra*\n\n{report}",
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
        except Exception as e:
            logger.warning(f"Ошибка отчёта для {user['telegram_id']}: {e}")
