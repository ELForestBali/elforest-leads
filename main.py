"""
ElForest TG Lead Monitor
------------------------
Основной процесс: слушает Telegram-группы через Telethon (MTProto),
фильтрует сообщения, квалифицирует через Claude Haiku, сохраняет в БД,
отправляет алерты о горячих лидах.
"""

import asyncio
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession

import config
from db import init_db, is_duplicate, save_lead
from scorer import score_lead
from alerter import send_alert
from emailer import send_email_alert
from bot_commands import poll_commands

# Настраиваем логи — будут видны в Railway Console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

def passes_keyword_filter(text: str) -> bool:
    """
    Двухступенчатый фильтр: сначала негативные слова (быстрый отсев),
    затем хотя бы одно позитивное. Haiku не вызываем если не прошло.
    Экономит ~85-90% API-вызовов.
    """
    text_lower = text.lower()
    if any(kw in text_lower for kw in config.NEGATIVE_KEYWORDS):
        return False
    return any(kw in text_lower for kw in config.ALL_POSITIVE_KEYWORDS)

async def main():
    log.info("🌿 ElForest Lead Monitor запускается...")

    # Инициализируем базу данных (создаём таблицу если нет)
    await init_db()
    log.info("✅ База данных готова")

    # Создаём Telethon-клиент
    # StringSession — это сохранённая авторизация в виде строки
    # Если SESSION_STRING пустой — будет обычный интерактивный вход (только для auth.py)
    session = StringSession(config.SESSION_STRING) if config.SESSION_STRING else StringSession()
    client = TelegramClient(session, config.API_ID, config.API_HASH)

    async def handle_new_message(event):
        """Обработчик каждого нового сообщения в отслеживаемых группах."""
        msg_text = event.message.message

        # Пропускаем пустые или слишком короткие сообщения
        if not msg_text or len(msg_text) < 25:
            return

        # Шаг 1: быстрый keyword-фильтр (бесплатно)
        if not passes_keyword_filter(msg_text):
            return

        # Шаг 2: дедупликация — не обрабатываем одно сообщение дважды
        msg_id = f"{event.chat_id}_{event.id}"
        if await is_duplicate(msg_id):
            return

        # Получаем данные отправителя
        try:
            sender = await event.get_sender()
            sender_name = getattr(sender, "first_name", "") or "Unknown"
            username = getattr(sender, "username", None) or ""
        except Exception:
            sender_name = "Unknown"
            username = ""

        # Получаем название группы
        try:
            chat = await event.get_chat()
            chat_title = getattr(chat, "title", "Unknown group")
        except Exception:
            chat = None
            chat_title = "Unknown group"

        log.info(f"🔍 Анализируем сообщение от {sender_name} в '{chat_title}'")

        # Шаг 3: квалификация через Claude Haiku
        result = await score_lead(msg_text)
        score = result.get("score", 0)

        log.info(f"   Score: {score}/10 ({result.get('tier')}) — {result.get('reason')}")

        # Шаг 4: сохраняем в базу данных (все сообщения прошедшие keyword-фильтр)
        await save_lead(msg_id, msg_text, result, sender_name, username, chat_title)

        # Шаг 5: отправляем алерт только если score выше порога слоя группы
        chat_username = getattr(chat, "username", "") or ""
        min_score = config.get_min_score(chat_username)
        if score >= min_score:
            log.info(f"   🔥 АЛЕРТ! Отправляем уведомление.")
            await send_alert(msg_text, result, sender_name, username, chat_title)
            await send_email_alert(msg_text, result, sender_name, username, chat_title)

    # Запускаем бот-команды в фоне (отвечает на /stats)
    asyncio.create_task(poll_commands())

    # Запускаем клиент и держим соединение
    await client.start()

    # Резолвим группы в числовые ID — пропускаем несуществующие
    valid_chats = []
    for group in config.TARGET_GROUPS:
        try:
            entity = await client.get_entity(group)
            valid_chats.append(entity.id)
        except Exception as e:
            log.warning(f"⚠️  Группа '{group}' не найдена, пропускаем: {e}")

    if not valid_chats:
        log.error("Нет ни одной валидной группы — выходим.")
        return

    # Регистрируем обработчик только для валидных групп
    client.add_event_handler(
        handle_new_message,
        events.NewMessage(chats=valid_chats)
    )

    log.info(f"✅ Telethon подключён. Слушаем {len(valid_chats)}/{len(config.TARGET_GROUPS)} групп(ы)...")
    log.info(f"   Валидных групп: {len(valid_chats)}")

    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
