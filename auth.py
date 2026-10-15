import json

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import current_user
from app.models import DriverProfile, User
from app.schemas import MePatch
from app.security import create_token, verify_telegram_login, verify_webapp_init_data
from app.services import active_subscription, upsert_telegram_user, utcnow

router = APIRouter(tags=["auth"])


@router.post("/auth/telegram")
async def auth_telegram(payload: dict = Body(...), db: AsyncSession = Depends(get_session)):
    """Telegram Login Widget ma'lumotlarini imzo orqali tekshiradi."""
    s = get_settings()
    if not verify_telegram_login(payload, s.bot_token, s.telegram_auth_max_age):
        raise HTTPException(401, "Telegram ma’lumotlari tasdiqlanmadi")
    name = " ".join(x for x in (payload.get("first_name"), payload.get("last_name")) if x) or "Foydalanuvchi"
    user = await upsert_telegram_user(db, int(payload["id"]), name, payload.get("username"), payload.get("photo_url"))
    await db.commit()
    return {"access_token": create_token(user.id), "token_type": "bearer"}


@router.post("/auth/telegram-webapp")
async def auth_webapp(init_data: str = Body(..., embed=True), db: AsyncSession = Depends(get_session)):
    s = get_settings()
    fields = verify_webapp_init_data(init_data, s.bot_token, s.telegram_auth_max_age)
    if fields is None or "user" not in fields:
        raise HTTPException(401, "Telegram ma’lumotlari tasdiqlanmadi")
    u = json.loads(fields["user"])
    name = " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x) or "Foydalanuvchi"
    user = await upsert_telegram_user(db, int(u["id"]), name, u.get("username"), u.get("photo_url"))
    await db.commit()
    return {"access_token": create_token(user.id), "token_type": "bearer"}


@router.get("/me")
async def me(user: User = Depends(current_user), db: AsyncSession = Depends(get_session)):
    drv = (await db.execute(select(DriverProfile).where(DriverProfile.user_id == user.id))).scalar_one_or_none()
    sub = await active_subscription(db, drv.id, utcnow()) if drv else None
    return {
        "id": user.id, "full_name": user.full_name, "username": user.username,
        "has_phone": bool(user.phone), "phone_verified": user.phone_verified,
        "contact_consent": user.contact_consent, "photo_url": user.photo_url,
        "is_driver": drv is not None,
        "driver_verification": drv.verification if drv else None,
        "subscription": {"kind": sub.kind, "ends_at": sub.ends_at} if sub else None,
    }


@router.patch("/me")
async def patch_me(body: MePatch, user: User = Depends(current_user), db: AsyncSession = Depends(get_session)):
    if body.contact_consent is not None:
        user.contact_consent = body.contact_consent
    if body.full_name:
        user.full_name = body.full_name
    await db.commit()
    return {"ok": True}
