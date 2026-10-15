import asyncio
import html
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Notification, User
from app.services import create_expiry_reminders, utcnow

log = logging.getLogger("bot.workers")


async def deliver_loop(bot: Bot, interval: float = 3.0):
    """notifications jadvalidan yetkazilmaganlarini Telegram orqali jo'natadi."""
    while True:
        try:
            async with SessionLocal() as db:
                rows = (
                    await db.execute(
                        select(Notification, User.telegram_id)
                        .join(User, User.id == Notification.user_id)
                        .where(Notification.sent_at.is_(None), Notification.error.is_(None), User.telegram_id.is_not(None))
                        .order_by(Notification.id)
                        .limit(25)
                    )
                ).all()
                for n, tg_id in rows:
                    try:
                        await bot.send_message(tg_id, html.escape(n.text))
                        n.sent_at = utcnow()
                    except TelegramRetryAfter as e:
                        await asyncio.sleep(e.retry_after)
                        break
                    except (TelegramForbiddenError, TelegramBadRequest) as e:
                        n.error = str(e)[:200]  # foydalanuvchi botni bloklagan va h.k.: qayta urinilmaydi
                    except Exception:
                        log.exception("notification %s yuborilmadi, keyinroq qayta uriniladi", n.id)
                    await asyncio.sleep(0.05)
                await db.commit()
        except Exception:
            log.exception("deliver_loop xatosi")
        await asyncio.sleep(interval)


async def reminder_loop(interval: float = 3600.0):
    """Obuna tugashiga 7/3/1 kun qolganda eslatma (takrorlanmaydi: dedupe_key)."""
    while True:
        try:
            async with SessionLocal() as db:
                n = await create_expiry_reminders(db, utcnow())
                if n:
                    log.info("eslatmalar navbatga qo'yildi: %s", n)
        except Exception:
            log.exception("reminder_loop xatosi")
        await asyncio.sleep(interval)
