import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
# Добавили нужные импорты для отлова ошибок:
from aiogram.types import ErrorEvent
from aiogram.exceptions import TelegramBadRequest

from models.database import init_db
from handlers.main_handler import router
from handlers.payment_handler import router as payment_router
from handlers.tests_handler import router as tests_router
from handlers.referral_handler import router as referral_router
from handlers.beliefs_handler import router as beliefs_router, init_beliefs_tables
from services.scheduler import setup_scheduler


async def broadcast_update(bot):
    """Рассылка всем существующим пользователям при деплое"""
    # Проверяем флаг — чтобы не слать при каждом рестарте
    flag_file = "/tmp/broadcast_done.flag"
    if os.path.exists(flag_file):
        logger.info("Рассылка уже была отправлена, пропускаем")
        return

    from models.database import get_all_users
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    try:
        users = await get_all_users()
        logger.info(f"Рассылка обновления для {len(users)} пользователей")

        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="✨ Посмотреть что нового", callback_data="show_updates"))
        keyboard = builder.as_markup()

        text = (
            "🌸 *Привет! У Мирры обновление*\n\n"
            "Появилось кое-что новое и важное:\n\n"
            "🧩 *Проработка убеждений* — новый 7-дневный курс. "
            "Деньги, отношения, самооценка, самореализация, страхи. "
            "Каждый день — шаг глубже. ИИ ведёт тебя лично.\n\n"
            "🗂 *Обновлено меню* — теперь удобнее находить нужный раздел\n\n"
            "Нажми чтобы узнать подробнее 👇"
        )

        sent = 0
        for user in users:
            try:
                await bot.send_message(
                    user["telegram_id"],
                    text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                sent += 1
                await asyncio.sleep(0.05)  # защита от флуда
            except Exception as e:
                logger.warning(f"Не удалось отправить {user['telegram_id']}: {e}")

        logger.info(f"Рассылка отправлена: {sent}/{len(users)}")

        # Ставим флаг чтобы не повторять
        with open(flag_file, "w") as f:
            f.write("done")

    except Exception as e:
        logger.error(f"Ошибка рассылки: {e}")

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        raise ValueError("❌ BOT_TOKEN не задан в .env")

    ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
    if not ANTHROPIC_KEY:
        raise ValueError("❌ ANTHROPIC_API_KEY не задан в .env")

    # Инициализируем базу данных
    await init_db()
    from models.database import init_referral_tables
    await init_referral_tables()
    await init_beliefs_tables()

    # Создаём бота и диспетчер
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher()
    dp.include_router(beliefs_router)
    dp.include_router(payment_router)
    dp.include_router(referral_router)
    dp.include_router(tests_router)
    dp.include_router(router)
    
     # Подключаем роутеры
    dp.include_router(beliefs_router)
    dp.include_router(payment_router)
    dp.include_router(referral_router)
    dp.include_router(tests_router)
    dp.include_router(router)
    # Запускаем планировщик
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("✅ Планировщик запущен")

    # Запускаем бота
    logger.info("🌙 Mirra запускается...")

    # Рассылка старым пользователям при деплое
    await broadcast_update(bot)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Mirra остановлена")


if __name__ == "__main__":
    asyncio.run(main())
