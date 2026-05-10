import asyncio
import smtplib
import ssl
from email.mime.text import MIMEText
from datetime import datetime, timezone

import config

TIER_LABEL   = {"hot": "HOT", "warm": "WARM", "cold": "COLD"}
INTENT_LABEL = {"rent": "аренда", "buy": "покупка", "info": "информация", "other": "другое"}
DURATION_LABEL = {"short": "краткосрочно", "long": "долгосрочно", "unknown": "не указано"}

def _send_sync(subject: str, body: str):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"]    = config.EMAIL_FROM
    msg["To"]      = config.EMAIL_TO

    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls(context=ctx)
        smtp.login(config.EMAIL_FROM, config.EMAIL_PASSWORD)
        smtp.sendmail(config.EMAIL_FROM, config.EMAIL_TO, msg.as_bytes())

async def send_email_alert(
    text: str,
    result: dict,
    sender_name: str,
    username: str,
    chat_title: str,
):
    if not config.EMAIL_FROM or not config.EMAIL_PASSWORD:
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
        await asyncio.to_thread(_send_sync, subject, body)
    except Exception as e:
        print(f"[emailer] ошибка отправки: {e}")
