"""Obuna va bepul sinov mantig'i (DB'siz, toza funksiyalar)."""
from datetime import datetime, timedelta

REMINDER_DAYS = (7, 3, 1)


def trial_end(start: datetime, days: int) -> datetime:
    if days <= 0:
        raise ValueError("sinov muddati musbat bo'lishi kerak")
    return start + timedelta(days=days)


def is_active(ends_at: datetime, now: datetime) -> bool:
    return ends_at > now


def reminder_bucket(ends_at: datetime, now: datetime) -> int | None:
    """Tugashiga <=1 / <=3 / <=7 kun qolgan bo'lsa shunga mos 1/3/7, aks holda None."""
    left = ends_at - now
    if left <= timedelta(0):
        return None
    for d in sorted(REMINDER_DAYS):
        if left <= timedelta(days=d):
            return d
    return None


def paid_start(now: datetime, current_end: datetime | None) -> datetime:
    """Pullik obuna amaldagi obuna tugashidan keyin boshlanadi (kunlar yo'qolmaydi)."""
    return current_end if current_end and current_end > now else now
