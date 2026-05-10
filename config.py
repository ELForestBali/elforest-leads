"""
config.py — конфигурация ElForest Lead Monitor
Секреты (API ключи) живут в Railway Variables.
Каналы и ключевые слова живут здесь — в коде.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# СЕКРЕТЫ — берутся из Railway Variables
# ─────────────────────────────────────────────
API_ID              = int(os.environ["TG_API_ID"])
API_HASH            = os.environ["TG_API_HASH"]
SESSION_STRING      = os.environ.get("TG_SESSION_STRING", "")
BOT_TOKEN           = os.environ["BOT_TOKEN"]
ALERT_CHAT_ID       = int(os.environ.get("ALERT_CHAT_ID", "1024728900"))
ANTHROPIC_API_KEY   = os.environ["ANTHROPIC_API_KEY"]
DATABASE_URL        = os.environ["DATABASE_URL"]
EMAIL_FROM          = os.environ.get("EMAIL_FROM", "")
EMAIL_PASSWORD      = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_TO            = "elforestbydsg@gmail.com"

# ─────────────────────────────────────────────
# LAYER A — жилищные чаты, высокий intent
# Порог алерта: score >= 6
# Мало сообщений, но люди именно ищут жильё
# ─────────────────────────────────────────────
GROUPS_LAYER_A = [
    "bali_villa_top",               # Bali Villa Top
    "balichatarenda",               # БалиЧат Аренда
    "Arenda_Zhilya_Baly",           # Аренда Жилья Бали
    "bali_arenda_zhilya_bayk_avto", # Аренда жилья + байки (жильё релевантно)
    "bali_arendaa",                 # Аренда Бали
    "bali_dom",                     # Бали Дом
    "balichatproperty",             # БалиЧат Property
    "balirental",                   # Жильё на Бали | CHATIK
    "balirentapart",                # Bali Rent Apart
    "Belkin_Bali_Rent",             # Belkin Bali Rent
    "island_rental",                # Island Rental
    "onerealestatebali",            # One Real Estate Bali
    "rent_in_bali",                 # Аренда и жилье на Бали
    "villasbali",                   # Аренда жилья и вилл Бали
    "arenda_bali_homeee",           # Аренда Бали. Убуд, Чангу, Улувату
    "topvillasbali",                # Бали Аренда жилья (канал + комменты)
]

# ─────────────────────────────────────────────
# LAYER B — номады, экспаты, полу-релевантные
# Порог алерта: score >= 7
# Люди «созревают» здесь — запросы появляются
# ─────────────────────────────────────────────
GROUPS_LAYER_B = [
    "balichat_ubud",        # БалиЧат Убуд — наш ключевой район
    "bali_ubud_changu",     # Bali Ubud Canggu — общий чат района
    "balichatroommates",    # Ищут сожителей → часто потом берут виллу целиком
    "baraholka_avito_bali", # Барахолка Бали — доска объявлений, жильё бывает
    "businessmenBali",      # Предприниматели на Бали — наша аудитория
    "russians_in_bali",     # Бали | Чат | Форум — большое русское комьюнити
]

# ─────────────────────────────────────────────
# LAYER C — общие географические чаты
# Порог алерта: score >= 8
# Много шума, лиды редкие но иногда горячие
# ─────────────────────────────────────────────
GROUPS_LAYER_C = [
    "balichat",         # БалиФорум — крупнейшее русское комьюнити на Бали
    "balichatik",       # БалиЧатик — общий
    "balichat_bukit",   # БалиЧат Букит
]

# Все группы объединяем в один плоский список для Telethon
# Слой каждой группы определяется при алертинге через get_group_layer()
TARGET_GROUPS = GROUPS_LAYER_A + GROUPS_LAYER_B + GROUPS_LAYER_C

def get_group_layer(chat_username: str) -> str:
    """Определяет слой группы для выбора правильного порога алерта."""
    username = chat_username.lower().lstrip("@")
    if any(g.lower() == username for g in GROUPS_LAYER_A):
        return "A"
    if any(g.lower() == username for g in GROUPS_LAYER_B):
        return "B"
    return "C"

def get_min_score(chat_username: str) -> int:
    """Возвращает минимальный score для алерта в зависимости от слоя."""
    layer = get_group_layer(chat_username)
    return {"A": 6, "B": 7, "C": 8}.get(layer, 7)

# ─────────────────────────────────────────────
# КЛЮЧЕВЫЕ СЛОВА — позитивный фильтр
# Если ни одно не встретилось — Haiku не вызываем
# Экономит ~85% API-вызовов
# ─────────────────────────────────────────────

# Сигналы намерения — человек что-то ищет или планирует
INTENT_KEYWORDS = [
    # Английский
    "looking for", "searching for", "need a", "need place",
    "any recommendations", "can anyone suggest", "anyone know",
    "moving to", "relocating", "planning to stay",
    "my friend is looking", "friend looking", "colleague looking",
    # Русский
    "ищу", "нужна", "нужен", "посоветуйте", "кто знает",
    "переезжаем", "едем", "планируем", "будем жить",
    "друг ищет", "подруга ищет", "подруга приезжает",
    # Французский
    "cherche", "recherche", "quelqu'un connait",
    # Индонезийский
    "cari", "butuh", "mau sewa",
]

# Сигналы объекта — что именно ищут (жильё)
OBJECT_KEYWORDS = [
    # Английский
    "villa", "house", "place", "accommodation",
    "rental", "rent", "stay", "property",
    "2br", "3br", "bedroom", "private pool",
    # Русский
    "виллу", "вилла", "дом", "жильё", "жилье",
    "аренда", "снять", "место", "помещение",
    # Косвенные (тишина, природа — наши УТП)
    "quiet place", "nature", "rice fields", "jungle",
    "тишина", "уединение", "рисовые поля", "джунгли",
    "peaceful", "private", "remote",
    # Французский
    "maison", "logement",
    # Индонезийский
    "rumah", "tempat tinggal",
]

# Обратный intent — хотят УЙТИ откуда-то
# Это скрытый спрос с минимальной конкуренцией
REVERSE_INTENT_KEYWORDS = [
    "tired of canggu", "tired of seminyak", "tired of noise",
    "too loud", "too crowded", "want quieter", "need more peace",
    "leave canggu", "leave seminyak", "escape the crowds",
    "hotel too noisy", "need more privacy",
    "надоел чангу", "надоел семиньяк", "надоело", "хочу тишины",
    "слишком шумно", "слишком много людей",
]

# Контекстные сигналы — срок, формат, ситуация
CONTEXT_KEYWORDS = [
    # Срок
    "monthly", "long term", "long-term", "3 months", "6 months",
    "yearly", "annual", "per month", "a month",
    "на месяц", "на два месяца", "на три месяца",
    "долгосрок", "помесячно", "на длительный срок",
    "mensuel", "par mois",  # Французский
    "bulanan", "tahunan",   # Индонезийский
    # Формат и аудитория
    "digital nomad", "remote work", "work from home", "coworking",
    "цифровой номад", "удалёнка", "удалённо", "работаю онлайн",
    "couple", "with my partner", "two of us", "family",
    "вдвоём", "с партнёром", "с женой", "с мужем", "семья",
]

# ─────────────────────────────────────────────
# КЛЮЧЕВЫЕ СЛОВА — негативный фильтр
# Если есть хотя бы одно — пропускаем БЕЗ вызова Haiku
# ─────────────────────────────────────────────
NEGATIVE_KEYWORDS = [
    # Продажа (не аренда)
    "for sale", "selling", "продаю", "продам", "на продажу",
    # Крипто и инвестиции
    "crypto", "bitcoin", "investment", "инвестиции", "токен",
    # Работа и персонал
    "job", "vacancy", "hiring", "вакансия", "работа",
    "cleaner", "driver", "staff", "персонал", "уборщица",
    # Мебель и техника
    "furniture", "мебель", "equipment", "appliance",
    # Агентства и маркетинг
    "agency", "broker", "агентство", "брокер", "листинг",
    "marketing", "commission", "комиссия",
    # Вечеринки и мероприятия
    "party", "event", "мероприятие", "вечеринка",
    # Транспорт
    "bike rental", "car rental", "scooter", "байк аренда",
]

# Объединяем все позитивные keywords в один список для быстрой проверки
ALL_POSITIVE_KEYWORDS = (
    INTENT_KEYWORDS + OBJECT_KEYWORDS +
    REVERSE_INTENT_KEYWORDS + CONTEXT_KEYWORDS
)
