from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException

from app.db import get_session
from app.deps import current_driver, current_user
from app.models import DriverProfile, Trip, TripRequest, User, Vehicle
from app.schemas import DriverRegisterIn
from app.services import active_subscription, enqueue, start_trial, utcnow

router = APIRouter(prefix="/drivers", tags=["drivers"])


async def subscription_view(db: AsyncSession, driver_id: int) -> dict:
    now = utcnow()
    sub = await active_subscription(db, driver_id, now)
    if not sub:
        return {"active": False, "kind": None, "ends_at": None, "days_left": 0}
    return {"active": True, "kind": sub.kind, "ends_at": sub.ends_at, "days_left": max((sub.ends_at - now).days, 0)}


@router.post("/register", status_code=201)
async def register(body: DriverRegisterIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_session)):
    exists = (await db.execute(select(DriverProfile.id).where(DriverProfile.user_id == user.id))).first()
    if exists:
        raise HTTPException(409, "Siz allaqachon haydovchisiz")
    drv = DriverProfile(user_id=user.id)
    db.add(drv)
    try:
        await db.flush()
        db.add(Vehicle(driver_id=drv.id, make_model=body.make_model, plate=body.plate, seats=body.seats, color=body.color))
        user.full_name = body.full_name
        user.contact_consent = True  # haydovchi yo'lovchilar bog'lanishi uchun ro'yxatdan o'tadi
        await start_trial(db, drv, utcnow())  # 30 kunlik (yoki admin belgilagan) bepul muddat
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Bu davlat raqami allaqachon ro‘yxatdan o‘tgan")
    return {"driver_id": drv.id, "subscription": await subscription_view(db, drv.id)}


@router.get("/me")
async def my_profile(drv: DriverProfile = Depends(current_driver), db: AsyncSession = Depends(get_session)):
    vehicles = (await db.execute(select(Vehicle).where(Vehicle.driver_id == drv.id))).scalars().all()
    return {
        "id": drv.id, "verification": drv.verification,
        "vehicles": [{"id": v.id, "make_model": v.make_model, "plate": v.plate, "seats": v.seats, "color": v.color} for v in vehicles],
        "subscription": await subscription_view(db, drv.id),
    }


@router.get("/me/requests")
async def incoming_requests(drv: DriverProfile = Depends(current_driver), db: AsyncSession = Depends(get_session)):
    """Haydovchining safarlariga kelgan so'rovlar (yo'lovchining telefoni ko'rsatilmaydi)."""
    rows = (
        await db.execute(
            select(TripRequest, Trip, User)
            .join(Trip, Trip.id == TripRequest.trip_id)
            .join(User, User.id == TripRequest.passenger_id)
            .where(Trip.driver_id == drv.id)
            .order_by(TripRequest.created_at.desc())
            .limit(100)
        )
    ).all()
    return [
        {"id": r.id, "trip_id": t.id, "passenger": u.full_name, "seats": r.seats, "message": r.message, "status": r.status}
        for r, t, u in rows
    ]
