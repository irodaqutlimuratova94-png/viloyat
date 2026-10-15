import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import AdminUser, DriverProfile, User
from app.security import decode_token
from app.services import user_is_blocked, utcnow

bearer = HTTPBearer(auto_error=False)


def _payload(cred: HTTPAuthorizationCredentials | None, typ: str) -> dict:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Tizimga kiring")
    try:
        return decode_token(cred.credentials, typ)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token yaroqsiz yoki muddati tugagan")


async def current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: AsyncSession = Depends(get_session)
) -> User:
    user = await db.get(User, int(_payload(cred, "user")["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Foydalanuvchi topilmadi")
    if user_is_blocked(user, utcnow()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Akkaunt vaqtincha bloklangan")
    return user


async def current_driver(user: User = Depends(current_user), db: AsyncSession = Depends(get_session)) -> DriverProfile:
    drv = (await db.execute(select(DriverProfile).where(DriverProfile.user_id == user.id))).scalar_one_or_none()
    if drv is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Avval haydovchi sifatida ro‘yxatdan o‘ting")
    return drv


async def current_admin(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: AsyncSession = Depends(get_session)
) -> AdminUser:
    """Admin tokeni foydalanuvchi tokenidan alohida (typ='admin'): bir-birining o'rnini bosmaydi."""
    adm = await db.get(AdminUser, int(_payload(cred, "admin")["sub"]))
    if adm is None or not adm.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ruxsat yo‘q")
    return adm
