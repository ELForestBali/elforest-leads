import asyncio
import logging
import httpx
import config
from db import get_pool, get_failed_leads, update_lead_score, is_duplicate, save_lead
from scorer import score_lead
from alerter import send_alert
from emailer import send_email_alert

log = logging.getLogger(__name__)


async def _get_stats_text() -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        today    = await conn.fetchval("SELECT COUNT(*) FROM leads WHERE created_at > NOW() - INTERVAL '24h'")
        week     = await conn.fetchval("SELECT COUNT(*) FROM leads WHERE created_at > NOW() - INTERVAL '7d'")
        total    = await conn.fetchval("SELECT COUNT(*) FROM leads")
        hot_day  = await conn.fetchval("SELECT COUNT(*) FROM leads WHERE tier='hot'  AND created_at > NOW() - INTERVAL '24h'")
        warm_day = await conn.fetchval("SELECT COUNT(*) FROM leads WHERE tier='warm' AND created_at > NOW() - INTERVAL '24h'")

        top_groups = await conn.fetch("""
            SELECT chat_title, COUNT(*) AS cnt
            FROM leads WHERE created_at > NOW() - INTERVAL '7d'
            GROUP BY chat_title ORDER BY cnt DESC LIMIT 5
        """)

        last_hot = await conn.fetch("""
            SELECT sender_name, username, chat_title, score, reason
            FROM leads WHERE tier = 'hot'
            ORDER BY created_at DESC LIMIT 3
        """)

    lines = [
        "📊 <b>ElForest Lead Monitor — статистика</b>\n",
        f"<b>Сегодня:</b> {today} лидов  (🔥 {hot_day} hot · 🌤 {warm_day} warm)",
        f"<b>Неделя:</b>  {week} лидов",
        f"<b>Всего:</b>   {total} лидов",
    ]

    if top_groups:
        lines.append("\n<b>Топ групп за неделю:</b>")
        for r in top_groups:
            lines.append(f"  • {r['chat_title']}: {r['cnt']}")

    if last_hot:
        lines.append("\n<b>Последние горячие лиды:</b>")
        for r in last_hot:
            contact = f"@{r['username']}" if r['username'] else r['sender_name']
            lines.append(f"  🔥 {contact} · {r['chat_title']} · {r['score']}/10")
            lines.append(f"     {r['reason']}")

    return "\n".join(lines)


async def _reprocess(http: httpx.AsyncClient):
    """Перескоривает лиды с ошибкой парсинга и шлёт алерты."""
    failed = await get_failed_leads()
    if not failed:
        await _send(http, "✅ Нет записей с ошибкой парсинга.")
        return

    await _send(http, f"🔄 Перескориваю {len(failed)} записей...")
    alerted = 0
    for row in failed:
        result = await score_lead(row["text"])
        await update_lead_score(row["msg_id"], result)
        score = result.get("score", 0)
        chat_username = ""
        min_score = config.get_min_score(chat_username)
        if score >= min_score:
            await send_alert(row["text"], result, row["sender_name"], row["username"], row["chat_title"])
            await send_email_alert(row["text"], result, row["sender_name"], row["username"], row["chat_title"])
            alerted += 1

    await _send(http, f"✅ Готово. Обработано: {len(failed)}, алертов отправлено: {alerted}.")


async def _backfill(http: httpx.AsyncClient, tg_client, limit: int = 100):
    """Забирает последние N сообщений из каждой группы и обрабатывает новые."""
    from config import TARGET_GROUPS, get_min_score, NEGATIVE_KEYWORDS, ALL_POSITIVE_KEYWORDS

    await _send(http, f"🔄 Бэкфилл: последние {limit} сообщений × {len(TARGET_GROUPS)} групп...")

    total_new = 0
    total_alerted = 0

    for group in TARGET_GROUPS:
        try:
            async for msg in tg_client.iter_messages(group, limit=limit):
                text = msg.message or ""
                if not text or len(text) < 25:
                    continue
                text_lower = text.lower()
                if any(kw in text_lower for kw in NEGATIVE_KEYWORDS):
                    continue
                if not any(kw in text_lower for kw in ALL_POSITIVE_KEYWORDS):
                    continue

                msg_id = f"{msg.chat_id}_{msg.id}"
                if await is_duplicate(msg_id):
                    continue

                try:
                    sender = await msg.get_sender()
                    sender_name = getattr(sender, "first_name", "") or "Unknown"
                    username = getattr(sender, "username", None) or ""
                except Exception:
                    sender_name = "Unknown"
                    username = ""

                try:
                    chat = await msg.get_chat()
                    chat_title = getattr(chat, "title", group)
                    chat_uname = getattr(chat, "username", "") or ""
                except Exception:
                    chat_title = group
                    chat_uname = ""

                result = await score_lead(text)
                await save_lead(msg_id, text, result, sender_name, username, chat_title)
                total_new += 1

                score = result.get("score", 0)
                if score >= get_min_score(chat_uname):
                    await send_alert(text, result, sender_name, username, chat_title)
                    await send_email_alert(text, result, sender_name, username, chat_title)
                    total_alerted += 1

                await asyncio.sleep(0.3)  # щадящий темп

        except Exception as e:
            log.warning(f"[backfill] группа {group}: {e}")

    await _send(http, f"✅ Бэкфилл завершён. Новых: {total_new}, алертов: {total_alerted}.")


async def _check_groups(http: httpx.AsyncClient, tg_client):
    """Проверяет реальный доступ к каждой группе из TARGET_GROUPS."""
    from config import TARGET_GROUPS
    await _send(http, f"🔍 Проверяю доступ к {len(TARGET_GROUPS)} группам...")

    ok, banned, missing = [], [], []

    for group in TARGET_GROUPS:
        try:
            msgs = await tg_client.get_messages(group, limit=1)
            ok.append(group)
        except Exception as e:
            err = str(e).lower()
            if any(w in err for w in ("banned", "forbidden", "kicked", "restricted", "private")):
                banned.append((group, str(e)[:60]))
            else:
                missing.append((group, str(e)[:60]))
        await asyncio.sleep(0.5)

    lines = [f"✅ <b>Доступно ({len(ok)}):</b>"]
    for g in ok:
        lines.append(f"  • {g}")

    if banned:
        lines.append(f"\n🚫 <b>Забанен / нет доступа ({len(banned)}):</b>")
        for g, e in banned:
            lines.append(f"  • {g} — {e}")

    if missing:
        lines.append(f"\n❓ <b>Другая ошибка ({len(missing)}):</b>")
        for g, e in missing:
            lines.append(f"  • {g} — {e}")

    await _send(http, "\n".join(lines))


async def _send(client: httpx.AsyncClient, text: str):
    await client.post(
        f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage",
        json={
            "chat_id": config.ALERT_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
    )


async def poll_commands(tg_client):
    offset = 0
    timeout = httpx.Timeout(35.0, connect=10.0)
    log.info("🤖 Bot command polling запущен. Напиши боту /stats")

    async with httpx.AsyncClient(timeout=timeout) as http:
        try:
            await _send(http, "🤖 ElForest Monitor запущен. Команды: /stats · /reprocess · /backfill [N] · /checkgroups")
        except Exception as e:
            log.warning(f"[bot_commands] стартовое сообщение не отправлено: {e}")

        while True:
            try:
                resp = await http.get(
                    f"https://api.telegram.org/bot{config.BOT_TOKEN}/getUpdates",
                    params={"offset": offset, "timeout": 30, "allowed_updates": ["message"]},
                )
                for update in resp.json().get("result", []):
                    offset = update["update_id"] + 1
                    text = update.get("message", {}).get("text", "")
                    log.info(f"[bot_commands] команда: {text!r}")

                    if text.startswith("/stats"):
                        stats = await _get_stats_text()
                        await _send(http, stats)

                    elif text.startswith("/reprocess"):
                        await _reprocess(http)

                    elif text.startswith("/backfill"):
                        parts = text.split()
                        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 100
                        asyncio.create_task(_backfill(http, tg_client, limit))

                    elif text.startswith("/checkgroups"):
                        asyncio.create_task(_check_groups(http, tg_client))

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"[bot_commands] ошибка: {e}")
                await asyncio.sleep(5)
