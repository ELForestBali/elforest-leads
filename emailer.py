import httpx
import config
from datetime import datetime, timezone

TIER_LABEL     = {"hot": "HOT", "warm": "WARM", "cold": "COLD"}
INTENT_LABEL   = {"rent": "аренда", "buy": "покупка", "info": "информация", "other": "другое"}
DURATION_LABEL = {"short": "краткосрочно", "long": "долгосрочно", "unknown": "не указано"}

RESEND_URL = "https://api.resend.com/emails"


async def send_email_alert(
    text: str,
    result: dict,
    sender_name: str,
    username: str,
    chat_title: str,
):
    if not config.RESEND_API_KEY:
        return

    score    = result.get("score", 0)
    tier     = TIER_LABEL.get(result.get("tier", "cold"), "?")
    intent   = INTENT_LABEL.get(result.get("intent", "other"), "?")
    duration = DURATION_LABEL.get(result.get("duration", "unknown"), "?")
    budget   = "да" if result.get("budget_signal") else "нет"
    reason   = result.get("reason", "")
    contact  = f"https://t.me/{username}" if username else f"{sender_name} (нет username)"
    ts       = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    subject = f"lead_tg_{chat_title}"

    body = (
        f"Score: {score}/10 — {tier}\n"
        f"Намерение: {intent} | {duration}\n"
        f"Сигнал бюджета: {budget}\n"
        f"Вывод: {reason}\n"
        f"\n"
        f"Отправитель: {sender_name}\n"
        f"Контакт: {contact}\n"
        f"Группа: {chat_title}\n"
        f"Время: {ts}\n"
        f"\n"
        f"--- Сообщение ---\n"
        f"{text}\n"
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                RESEND_URL,
                headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
                json={
                    "from":    "ElForest Monitor <onboarding@resend.dev>",
                    "to":      [config.EMAIL_TO],
                    "subject": subject,
                    "text":    body,
                },
            )
            if resp.status_code not in (200, 201):
                print(f"[emailer] ошибка Resend: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[emailer] ошибка отправки: {e}")
