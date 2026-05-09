import asyncpg
import config

# Глобальный пул соединений с базой данных
# Создаётся один раз при старте, переиспользуется для всех запросов
_pool = None

async def get_pool():
    """Возвращает пул соединений, создаёт если ещё не существует."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(config.DATABASE_URL)
    return _pool

async def init_db():
    """
    Создаёт таблицу leads если её ещё нет.
    Вызывается один раз при запуске приложения.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id          SERIAL PRIMARY KEY,
                msg_id      TEXT UNIQUE NOT NULL,   -- уникальный ID сообщения (chat_id + msg_id)
                text        TEXT NOT NULL,           -- оригинальный текст сообщения
                score       INTEGER,                 -- оценка Haiku 1-10
                tier        TEXT,                    -- hot / warm / cold
                intent      TEXT,                    -- rent / buy / info / other
                duration    TEXT,                    -- short / long / unknown
                budget      BOOLEAN,                 -- есть ли сигнал бюджета
                reason      TEXT,                    -- почему такой score
                sender_name TEXT,                    -- имя отправителя
                username    TEXT,                    -- @username если есть
                chat_title  TEXT,                    -- название группы
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)

async def is_duplicate(msg_id: str) -> bool:
    """
    Проверяет, видели ли мы это сообщение раньше.
    Защита от дублей — если бот перезапустился, он не будет слать алерты повторно.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM leads WHERE msg_id = $1", msg_id
        )
        return row is not None

async def save_lead(msg_id: str, text: str, result: dict, sender_name: str, username: str, chat_title: str):
    """Сохраняет лид в базу данных."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO leads (msg_id, text, score, tier, intent, duration, budget, reason, sender_name, username, chat_title)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (msg_id) DO NOTHING
        """,
            msg_id,
            text,
            result.get("score"),
            result.get("tier"),
            result.get("intent"),
            result.get("duration"),
            result.get("budget_signal"),
            result.get("reason"),
            sender_name,
            username,
            chat_title
        )
