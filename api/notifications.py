import os
import logging
import urllib.parse
import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _token() -> str | None:
    return os.getenv("TELEGRAM_BOT_TOKEN")


def _build_checkin_url(player_name: str) -> str:
    base = os.getenv("PUBLIC_URL", os.getenv("API_URL", "http://localhost:8000")).rstrip("/")
    slug = urllib.parse.quote(player_name, safe="")
    return f"{base}/checkin/{slug}"


def send_telegram(chat_id: str, message: str) -> bool:
    token = _token()
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — notifications disabled")
        return False
    url = TELEGRAM_API.format(token=token, method="sendMessage")
    try:
        r = httpx.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        logger.error("Telegram send failed to %s: %s", chat_id, e)
        return False


async def _already_submitted(db, table: str, player_name: str, today: str) -> bool:
    async with db.execute(
        f"SELECT 1 FROM {table} WHERE player_name = ? AND timestamp LIKE ? LIMIT 1",
        (player_name, f"{today}%"),
    ) as cur:
        return await cur.fetchone() is not None


async def send_morning_reminders(db_path) -> dict:
    import aiosqlite
    from datetime import date
    today = date.today().isoformat()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT name, contact FROM roster WHERE contact IS NOT NULL AND contact != ""'
        ) as cur:
            players = await cur.fetchall()

        sent, failed, skipped = 0, 0, 0
        for row in players:
            name, chat_id = row["name"], row["contact"]
            if await _already_submitted(db, "wellness", name, today):
                skipped += 1
                continue
            url = _build_checkin_url(name)
            msg = (
                f"Good morning {name}! 🏏 Don't forget your morning wellness check-in:\n"
                f"{url}\n"
                f"Takes less than 2 minutes!"
            )
            if send_telegram(chat_id, msg):
                sent += 1
            else:
                failed += 1

    logger.info("Morning reminders: %d sent, %d failed, %d skipped (already submitted)", sent, failed, skipped)
    return {"sent": sent, "failed": failed, "skipped": skipped, "total": sent + failed + skipped}


async def send_evening_reminders(db_path) -> dict:
    import aiosqlite
    from datetime import date
    today = date.today().isoformat()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT name, contact FROM roster WHERE contact IS NOT NULL AND contact != ""'
        ) as cur:
            players = await cur.fetchall()

        sent, failed, skipped = 0, 0, 0
        for row in players:
            name, chat_id = row["name"], row["contact"]
            if await _already_submitted(db, "evening", name, today):
                skipped += 1
                continue
            url = _build_checkin_url(name)
            msg = (
                f"Hey {name}! Evening check-in reminder 🌙\n"
                f"{url}\n"
                f"Log your session & recovery before you sleep!"
            )
            if send_telegram(chat_id, msg):
                sent += 1
            else:
                failed += 1

    logger.info("Evening reminders: %d sent, %d failed, %d skipped (already submitted)", sent, failed, skipped)
    return {"sent": sent, "failed": failed, "skipped": skipped, "total": sent + failed + skipped}
