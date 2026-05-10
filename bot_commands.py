import asyncio
import logging
import httpx
import config
from db import get_pool

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


async def poll_commands():
    """
    Long-polling петля для приёма команд от бота.
    Запускается как фоновая задача из main.py.
    Отвечает на /stats статистикой из БД.
    """
    offset = 0
    timeout = httpx.Timeout(35.0, connect=10.0)
    log.info("🤖 Bot command polling запущен. Напиши боту /stats")

    async with httpx.AsyncClient(timeout=timeout) as client:
        # Сообщаем о старте в алерт-чат
        try:
            await _send(client, "🤖 ElForest Monitor запущен. Команды: /stats")
        except Exception as e:
            log.warning(f"[bot_commands] не удалось отправить стартовое сообщение: {e}")

        while True:
            try:
                resp = await client.get(
                    f"https://api.telegram.org/bot{config.BOT_TOKEN}/getUpdates",
                    params={"offset": offset, "timeout": 30, "allowed_updates": ["message"]},
                )
                for update in resp.json().get("result", []):
                    offset = update["update_id"] + 1
                    text = update.get("message", {}).get("text", "")
                    log.info(f"[bot_commands] команда получена: {text!r}")
                    if text.startswith("/stats"):
                        stats = await _get_stats_text()
                        await _send(client, stats)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"[bot_commands] ошибка: {e}")
                await asyncio.sleep(5)
