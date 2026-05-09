import os
from dotenv import load_dotenv

# Загружаем .env файл если он есть (для локальной разработки)
load_dotenv()

# --- Telegram MTProto (для чтения групп как живой пользователь) ---
API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]

# Строка сессии — генерируется один раз через auth.py
# Позволяет Telethon работать без интерактивного ввода кода
SESSION_STRING = os.environ.get("TG_SESSION_STRING", "")

# --- Telegram Bot (для отправки алертов тебе) ---
BOT_TOKEN = os.environ["BOT_TOKEN"]
ALERT_CHAT_ID = int(os.environ.get("ALERT_CHAT_ID", "1024728900"))

# --- Anthropic (Claude Haiku для квалификации лидов) ---
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

# --- База данных (Railway PostgreSQL) ---
DATABASE_URL = os.environ["DATABASE_URL"]

# --- Настройки квалификации ---
# Лиды с оценкой ниже этого порога не попадают в алерт
MIN_SCORE = int(os.environ.get("MIN_SCORE", "6"))

# --- Список групп для мониторинга ---
# Указывай username группы без @ (например "balinomads")
# Или числовой ID группы (например -1001234567890)
TARGET_GROUPS = [
    # Английские Bali/Ubud сообщества
    "balinomads",
    "baliexpats",
    "digitalnomadsbali",
    "balirealestate",
    "expatsbali",
    # Русскоязычные Bali сообщества  
    "balirussia",
    "balidlyasvoyih",
    # Добавляй сюда любые другие группы
]
