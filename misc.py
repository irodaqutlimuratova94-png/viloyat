from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Trip
from app.regions import CITIES, REGIONS
from app.services import utcnow

router = APIRouter(tags=["misc"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_session)):
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/regions")
async def regions():
    return [{"code": c, "name": n, "cities": CITIES.get(c, [])} for c, n in REGIONS.items()]


@router.get("/popular-routes")
async def popular(db: AsyncSession = Depends(get_session)):
    rows = (
        await db.execute(
            select(Trip.from_region, Trip.to_region, func.count(Trip.id), func.min(Trip.price_uzs))
            .where(Trip.status == "active", Trip.moderation == "ok", Trip.depart_at > utcnow())
            .group_by(Trip.from_region, Trip.to_region)
            .order_by(func.count(Trip.id).desc())
            .limit(8)
        )
    ).all()
    return [{"from_region": a, "to_region": b, "trips": n, "min_price_uzs": p} for a, b, n, p in rows]
