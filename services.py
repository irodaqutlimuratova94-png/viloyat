import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    AppSetting, AuditLog, DriverProfile, Notification, Review, Subscription, User,
)
from app.subscription import paid_start, reminder_bucket, trial_end


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def user_is_blocked(user: User, now: datetime) -> bool:
    if not user.is_blocked:
        return False
    return user.blocked_until is None or user.blocked_until > now


async def get_setting_int(db: AsyncSession, key: str, default: int) -> int:
    row = await db.get(AppSetting, key)
    return int(row.value) if row else default


async def set_setting(db: AsyncSession, key: str, value: str) -> None:
    row = await db.get(AppSetting, key)
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))


async def upsert_telegram_user(
    db: AsyncSession, tg_id: int, full_name: str, username: str | None, photo_url: str | None = None
) -> User:
    user = (await db.execute(select(User).where(User.telegram_id == tg_id))).scalar_one_or_none()
    if user is None:
        user = User(telegram_id=tg_id, full_name=full_name, username=username, photo_url=photo_url)
        db.add(user)
    else:
        user.username = username
        if not user.full_name:
            user.full_name = full_name
        if photo_url:
            user.photo_url = photo_url
    await db.flush()
    return user


async def active_subscription(db: AsyncSession, driver_id: int, now: datetime) -> Subscription | None:
    q = (
        select(Subscription)
        .where(Subscription.driver_id == driver_id, Subscription.status == "active", Subscription.ends_at > now)
        .order_by(Subscription.ends_at.desc())
        .limit(1)
    )
    return (await db.execute(q)).scalar_one_or_none()


async def start_trial(db: AsyncSession, driver: DriverProfile, now: datetime) -> Subscription:
    """Ro'yxatdan o'tgan sanadan boshlab sinov muddati. Admin sozlamasi: app_settings.trial_days."""
    days = await get_setting_int(db, "trial_days", get_settings().default_trial_days)
    sub = Subscription(driver_id=driver.id, kind="trial", starts_at=now, ends_at=trial_end(now, days))
    db.add(sub)
    await db.flush()
    return sub


async def grant_paid(db: AsyncSession, driver_id: int, plan, payment_id: int, now: datetime) -> Subscription:
    cur = await active_subscription(db, driver_id, now)
    start = paid_start(now, cur.ends_at if cur else None)
    from datetime import timedelta

    sub = Subscription(
        driver_id=driver_id, plan_id=plan.id, kind="paid", starts_at=start,
        ends_at=start + timedelta(days=plan.days), payment_id=payment_id,
    )
    db.add(sub)
    await db.flush()
    return sub


async def enqueue(db: AsyncSession, user_id: int, kind: str, text: str, dedupe_key: str | None = None) -> bool:
    if dedupe_key:
        exists = await db.execute(
            select(Notification.id).where(
                Notification.user_id == user_id, Notification.kind == kind, Notification.dedupe_key == dedupe_key
            )
        )
        if exists.first():
            return False
    db.add(Notification(user_id=user_id, kind=kind, text=text, dedupe_key=dedupe_key))
    return True


async def create_expiry_reminders(db: AsyncSession, now: datetime) -> int:
    """Faol obunalar uchun 7/3/1 kunlik eslatmalarni navbatga qo'yadi (takrorlanmaydi)."""
    subs = (
        await db.execute(
            select(Subscription, DriverProfile.user_id)
            .join(DriverProfile, DriverProfile.id == Subscription.driver_id)
            .where(Subscription.status == "active", Subscription.ends_at > now)
        )
    ).all()
    created = 0
    for sub, user_id in subs:
        d = reminder_bucket(sub.ends_at, now)
        if d is None:
            continue
        what = "Bepul sinov muddatingiz" if sub.kind == "trial" else "Obunangiz"
        text = f"{what} tugashiga {d} kun{'dan kam' if d > 1 else ''} qoldi. Yangi safar e’lon qilishda to‘xtalib qolmaslik uchun obunani yangilang."
        if await enqueue(db, user_id, "sub_expiry", text, f"sub{sub.id}:d{d}"):
            created += 1
    await db.commit()
    return created


async def ratings_for(db: AsyncSession, driver_ids: list[int]) -> dict[int, tuple[float, int]]:
    if not driver_ids:
        return {}
    rows = await db.execute(
        select(Review.driver_id, func.avg(Review.rating), func.count(Review.id))
        .where(Review.driver_id.in_(driver_ids))
        .group_by(Review.driver_id)
    )
    return {d: (round(float(a), 2), c) for d, a, c in rows.all()}


def audit(db: AsyncSession, admin_id: int | None, action: str, entity: str, entity_id, details: dict | None = None):
    db.add(
        AuditLog(
            admin_id=admin_id, action=action, entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=json.dumps(details, ensure_ascii=False) if details else None,
        )
    )
