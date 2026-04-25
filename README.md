# 🌙 Mirra — Telegram бот психолог

Персональный помощник по эмоциональной стабильности.

## Быстрый старт

### 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 2. Настройка окружения
Создай файл `.env` (скопируй из `.env.example`):
```bash
cp .env.example .env
```

Заполни в `.env`:
```
BOT_TOKEN=токен_от_BotFather
ANTHROPIC_API_KEY=твой_ключ_anthropic
ADMIN_ID=твой_telegram_id
```

### 3. Запуск
```bash
python main.py
```

---

## Структура проекта

```
mirra/
├── main.py                  # Точка входа
├── requirements.txt
├── .env.example
├── handlers/
│   └── main_handler.py      # Все обработчики сообщений
├── services/
│   ├── ai_service.py        # Все запросы к Claude API
│   └── scheduler.py         # Утренний чекин + еженедельный отчёт
├── models/
│   └── database.py          # SQLite база данных
└── utils/
    └── keyboards.py         # Все клавиатуры
```

---

## Модули бота

| Модуль | Описание |
|--------|----------|
| 🧠 Психолог | Сократовский диалог, работа с проблемой |
| 🔮 И-Цзин | Гадание, 64 гексаграммы |
| 🃏 МАК-карты | Метафорические ассоциативные карты |
| 🔢 Нумерология | Расчёт по дате рождения |
| 🧘 Медитации | 8 практик по Диспензе + визуализации |
| 📖 Дневник | История, отчёты, настроение |

---

## Деплой на Railway

1. Создай аккаунт на [railway.app](https://railway.app)
2. Подключи GitHub репозиторий
3. Добавь переменные окружения в Railway Dashboard
4. Railway автоматически запустит `python main.py`

---

## Тарифы

- 🆓 Бесплатно: 3 диалога в месяц
- 💜 Pro: 3 000 ₸/месяц — безлимит + все модули

## Добавить пользователю подписку (вручную через SQLite)

```sql
UPDATE users 
SET is_subscribed = 1, subscription_until = '2026-12-31T00:00:00'
WHERE telegram_id = 123456789;
```
