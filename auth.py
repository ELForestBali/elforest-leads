"""
auth.py — ЗАПУСКАЕТСЯ ТОЛЬКО ОДИН РАЗ для получения строки сессии.

Этот скрипт нужно запустить в Railway Console командой:
    python auth.py

Он попросит ввести код из Telegram, после чего выдаст SESSION_STRING —
длинную строку, которую ты сохранишь как переменную окружения на Railway.
После этого main.py будет работать без интерактивного ввода навсегда.
"""

import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]

async def generate_session():
    print("\n🔐 Генерация строки сессии Telethon")
    print("=" * 50)
    print("Сейчас Telegram пришлёт тебе код подтверждения.")
    print("Введи его здесь — это безопасно, код нужен только для авторизации.\n")

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.start()

    session_string = client.session.save()

    print("\n" + "=" * 50)
    print("✅ ГОТОВО! Вот твоя строка сессии:")
    print("=" * 50)
    print(session_string)
    print("=" * 50)
    print("\n📋 Скопируй ЭТУ СТРОКУ целиком и сохрани как")
    print("   переменную окружения TG_SESSION_STRING на Railway.\n")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(generate_session())
