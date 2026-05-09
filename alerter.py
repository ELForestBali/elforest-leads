import httpx
import config

# Эмодзи для каждого уровня лида — делает алерты визуально понятными одним взглядом
TIER_EMOJI = {
    "hot":  "🔥",
    "warm": "🌤",
    "cold": "❄️"
}

INTENT_LABEL = {
    "rent":  "аренда",
    "buy":   "покупка",
    "info":  "информация",
    "other": "другое"
}

DURATION_LABEL = {
    "short":   "краткосрочно",
    "long":    "долгосрочно",
    "unknown": "срок неизвестен"
}

async def send_alert(text: str, result: dict, sender_name: str, username: str, chat_title: str):
    """
    Отправляет форматированное уведомление тебе в Telegram через бота.
    
    Используем Telegram Bot API напрямую через httpx (простой HTTP-запрос).
    parse_mode HTML позволяет использовать жирный текст и цитаты.
    """
    emoji = TIER_EMOJI.get(result.get("tier", "cold"), "❓")
    score = result.get("score", 0)
    intent = INTENT_LABEL.get(result.get("intent", "other"), "?")
    duration = DURATION_LABEL.get(result.get("duration", "unknown"), "?")
    budget = "✅ да" if result.get("budget_signal") else "нет"

    # Форматируем контакт отправителя
    if username:
        contact = f'<a href="https://t.me/{username}">@{username}</a>'
    else:
        contact = f"{sender_name} (нет username)"

    # Обрезаем текст сообщения до 400 символов для компактности алерта
    preview = text[:400] + ("..." if len(text) > 400 else "")

    message = (
        f"{emoji} <b>Новый лид ElForest</b> — score <b>{score}/10</b>\n\n"
        f"👤 {sender_name} ({contact})\n"
        f"📍 Группа: {chat_title}\n"
        f"🎯 Намерение: {intent} | {duration}\n"
        f"💰 Сигнал бюджета: {budget}\n"
        f"💬 {result.get('reason', '')}\n\n"
        f"<blockquote>{preview}</blockquote>"
    )

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage",
            json={
                "chat_id": config.ALERT_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
        )
        if resp.status_code != 200:
            print(f"[alerter] ошибка отправки алерта: {resp.text}")
