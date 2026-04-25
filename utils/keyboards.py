from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


# ──────────────────────────────────────────────
# ГЛАВНОЕ МЕНЮ
# ──────────────────────────────────────────────

def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🧠 Поговорить с психологом", callback_data="mode_psychologist"))
    builder.row(InlineKeyboardButton(text="🔮 Гадание И-Цзин", callback_data="mode_iching"))
    builder.row(
        InlineKeyboardButton(text="🃏 МАК-карта", callback_data="mode_mak"),
        InlineKeyboardButton(text="🔢 Нумерология", callback_data="mode_numerology")
    )
    builder.row(InlineKeyboardButton(text="🧘 Медитация дня", callback_data="mode_meditation"))
    builder.row(InlineKeyboardButton(text="📖 Мой дневник", callback_data="mode_diary"))
    return builder.as_markup()


# ──────────────────────────────────────────────
# МЕДИТАЦИИ
# ──────────────────────────────────────────────

def meditation_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="😰 Снять тревогу", callback_data="med_anxiety"))
    builder.row(InlineKeyboardButton(text="😴 Восстановить энергию", callback_data="med_energy"))
    builder.row(InlineKeyboardButton(text="😤 Трансформировать злость", callback_data="med_anger"))
    builder.row(InlineKeyboardButton(text="✨ Создание нового Я", callback_data="med_new_self"))
    builder.row(InlineKeyboardButton(text="💰 Изобилие и деньги", callback_data="med_abundance"))
    builder.row(InlineKeyboardButton(text="💞 Отношения и любовь", callback_data="med_love"))
    builder.row(InlineKeyboardButton(text="🌟 Встреча с мудрецом", callback_data="med_wise"))
    builder.row(InlineKeyboardButton(text="🏥 Исцеление светом", callback_data="med_healing"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_menu"))
    return builder.as_markup()


# ──────────────────────────────────────────────
# ДНЕВНИК
# ──────────────────────────────────────────────

def diary_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📅 Записи за эту неделю", callback_data="diary_week"))
    builder.row(InlineKeyboardButton(text="📊 Еженедельный отчёт", callback_data="diary_report"))
    builder.row(InlineKeyboardButton(text="😊 Как я сейчас?", callback_data="diary_mood"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_menu"))
    return builder.as_markup()


# ──────────────────────────────────────────────
# И-ЦЗИ
# ──────────────────────────────────────────────

def iching_confirm() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🪙 Бросить монеты", callback_data="iching_throw"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_menu"))
    return builder.as_markup()


# ──────────────────────────────────────────────
# МАК-КАРТЫ
# ──────────────────────────────────────────────

def mak_draw() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🃏 Вытянуть карту", callback_data="mak_draw"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_menu"))
    return builder.as_markup()


# ──────────────────────────────────────────────
# НАВИГАЦИЯ
# ──────────────────────────────────────────────

def back_to_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_menu"))
    return builder.as_markup()


def continue_or_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💬 Продолжить", callback_data="continue_dialog"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="back_menu")
    )
    return builder.as_markup()


def subscribe_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💜 Оформить подписку — 3 000 ₸/мес", callback_data="subscribe"))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_menu"))
    return builder.as_markup()


# ──────────────────────────────────────────────
# НАСТРОЕНИЕ
# ──────────────────────────────────────────────

def mood_keyboard() -> InlineKeyboardMarkup:
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
    return builder.as_markup()
