from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import (
    AdminUser, AuditLog, Complaint, DriverProfile, Payment, Subscription, SubscriptionPlan,
    Trip, TripRequest, User,
)
from app.regions import valid_region
from app.schemas import AdminLoginIn, BroadcastIn, PlanIn, PlanPatch
from app.security import create_token, verify_password
from app.services import audit, enqueue, get_setting_int, set_setting, utcnow
from app.config import get_settings

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login")
async def login(body: AdminLoginIn, db: AsyncSession = Depends(get_session)):
    adm = (await db.execute(select(AdminUser).where(AdminUser.username == body.username))).scalar_one_or_none()
    if adm is None or not adm.is_active or not verify_password(body.password, adm.password_hash):
        raise HTTPException(401, "Login yoki parol noto‘g‘ri")
    audit(db, adm.id, "login", "admin", adm.id)
    await db.commit()
    return {"access_token": create_token(adm.id, "admin"), "token_type": "bearer"}


@router.get("/users")
async def users(q: str | None = None, limit: int = Query(50, le=200), offset: int = 0, _=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    stmt = select(User).order_by(User.id.desc()).limit(limit).offset(offset)
    if q:
        stmt = stmt.where(User.full_name.ilike(f"%{q}%") | User.username.ilike(f"%{q}%"))
    rows = (await db.execute(stmt)).scalars().all()
    return [{"id": u.id, "name": u.full_name, "username": u.username, "telegram_id": u.telegram_id, "blocked": u.is_blocked, "blocked_until": u.blocked_until, "created_at": u.created_at} for u in rows]


class BlockIn(BaseModel):
    hours: int | None = Field(default=None, gt=0, le=24 * 365)  # None = muddatsiz


@router.post("/users/{user_id}/block")
async def block(user_id: int, body: BlockIn, adm=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    u = await db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    u.is_blocked = True
    u.blocked_until = utcnow() + timedelta(hours=body.hours) if body.hours else None
    audit(db, adm.id, "block_user", "user", user_id, {"hours": body.hours})
    await db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/unblock")
async def unblock(user_id: int, adm=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    u = await db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    u.is_blocked, u.blocked_until = False, None
    audit(db, adm.id, "unblock_user", "user", user_id)
    await db.commit()
    return {"ok": True}


@router.get("/drivers")
async def drivers(_=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(DriverProfile, User).join(User, User.id == DriverProfile.user_id).order_by(DriverProfile.id.desc()).limit(200))).all()
    return [{"id": d.id, "user_id": u.id, "name": u.full_name, "verification": d.verification} for d, u in rows]


class VerifyIn(BaseModel):
    verification: str = Field(pattern="^(pending|verified|rejected)$")


@router.post("/drivers/{driver_id}/verification")
async def verify_driver(driver_id: int, body: VerifyIn, adm=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    d = await db.get(DriverProfile, driver_id)
    if d is None:
        raise HTTPException(404, "Haydovchi topilmadi")
    d.verification = body.verification
    audit(db, adm.id, "driver_verification", "driver", driver_id, {"to": body.verification})
    await enqueue(db, d.user_id, "verification", {"verified": "Profilingiz tasdiqlandi ✅", "rejected": "Profilingiz tasdiqlanmadi. Ma’lumotlarni tekshiring.", "pending": "Profilingiz qayta tekshiruvga qo‘yildi."}[body.verification])
    await db.commit()
    return {"ok": True}


@router.get("/trips")
async def trips(status: str | None = None, limit: int = Query(100, le=300), _=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    stmt = select(Trip).order_by(Trip.id.desc()).limit(limit)
    if status:
        stmt = stmt.where(Trip.status == status)
    rows = (await db.execute(stmt)).scalars().all()
    return [{"id": t.id, "driver_id": t.driver_id, "from": t.from_region, "to": t.to_region, "depart_at": t.depart_at, "price_uzs": t.price_uzs, "status": t.status, "moderation": t.moderation} for t in rows]


class ModerateIn(BaseModel):
    hidden: bool


@router.post("/trips/{trip_id}/moderate")
async def moderate(trip_id: int, body: ModerateIn, adm=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    t = await db.get(Trip, trip_id)
    if t is None:
        raise HTTPException(404, "Safar topilmadi")
    t.moderation = "hidden" if body.hidden else "ok"
    audit(db, adm.id, "moderate_trip", "trip", trip_id, {"hidden": body.hidden})
    await db.commit()
    return {"ok": True}


@router.get("/complaints")
async def complaints(_=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(Complaint).order_by(Complaint.id.desc()).limit(200))).scalars().all()
    return [{"id": c.id, "author_id": c.author_id, "target_user_id": c.target_user_id, "trip_id": c.trip_id, "text": c.text, "status": c.status} for c in rows]


class ComplaintDecision(BaseModel):
    status: str = Field(pattern="^(resolved|rejected)$")


@router.post("/complaints/{cid}/resolve")
async def resolve_complaint(cid: int, body: ComplaintDecision, adm=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    c = await db.get(Complaint, cid)
    if c is None:
        raise HTTPException(404, "Shikoyat topilmadi")
    c.status = body.status
    audit(db, adm.id, "resolve_complaint", "complaint", cid, {"status": body.status})
    await db.commit()
    return {"ok": True}


@router.get("/subscriptions")
async def subscriptions(_=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(Subscription).order_by(Subscription.id.desc()).limit(200))).scalars().all()
    return [{"id": s.id, "driver_id": s.driver_id, "kind": s.kind, "status": s.status, "starts_at": s.starts_at, "ends_at": s.ends_at} for s in rows]


@router.get("/payments")
async def payments(_=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(Payment).order_by(Payment.id.desc()).limit(200))).scalars().all()
    return [{"id": p.id, "driver_id": p.driver_id, "amount_uzs": p.amount_uzs, "provider": p.provider, "status": p.status, "paid_at": p.paid_at} for p in rows]


@router.get("/plans")
async def list_plans(_=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(SubscriptionPlan).order_by(SubscriptionPlan.id))).scalars().all()
    return [{"id": p.id, "code": p.code, "name": p.name, "days": p.days, "price_uzs": p.price_uzs, "is_active": p.is_active} for p in rows]


@router.post("/plans", status_code=201)
async def create_plan(body: PlanIn, adm=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    p = SubscriptionPlan(**body.model_dump())
    db.add(p)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Bu kodli tarif mavjud")
    audit(db, adm.id, "create_plan", "plan", p.id, body.model_dump())
    await db.commit()
    return {"id": p.id}


@router.patch("/plans/{plan_id}")
async def patch_plan(plan_id: int, body: PlanPatch, adm=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    p = await db.get(SubscriptionPlan, plan_id)
    if p is None:
        raise HTTPException(404, "Tarif topilmadi")
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(p, k, v)
    audit(db, adm.id, "update_plan", "plan", plan_id, changes)
    await db.commit()
    return {"ok": True}


class TrialIn(BaseModel):
    days: int = Field(gt=0, le=365)


@router.get("/settings/trial-days")
async def get_trial(_=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    return {"days": await get_setting_int(db, "trial_days", get_settings().default_trial_days)}


@router.put("/settings/trial-days")
async def put_trial(body: TrialIn, adm=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    """Faqat KEYIN ro'yxatdan o'tadigan haydovchilarga ta'sir qiladi."""
    await set_setting(db, "trial_days", str(body.days))
    audit(db, adm.id, "set_trial_days", "setting", "trial_days", {"days": body.days})
    await db.commit()
    return {"ok": True}


@router.get("/stats")
async def stats(_=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    now = utcnow()

    async def count(stmt):
        return (await db.execute(stmt)).scalar_one()

    return {
        "users": await count(select(func.count(User.id))),
        "drivers": await count(select(func.count(DriverProfile.id))),
        "active_trips": await count(select(func.count(Trip.id)).where(Trip.status == "active", Trip.depart_at > now)),
        "total_trips": await count(select(func.count(Trip.id))),
        "requests": await count(select(func.count(TripRequest.id))),
        "open_complaints": await count(select(func.count(Complaint.id)).where(Complaint.status == "open")),
        "active_subscriptions": await count(select(func.count(Subscription.id)).where(Subscription.status == "active", Subscription.ends_at > now)),
        "paid_total_uzs": await count(select(func.coalesce(func.sum(Payment.amount_uzs), 0)).where(Payment.status == "paid")),
    }


@router.post("/broadcast")
async def broadcast(body: BroadcastIn, adm=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    """Xabarlar navbatga qo'yiladi; botning yetkazish sikli ularni jo'natadi."""
    stmt = select(User.id).where(User.telegram_id.is_not(None), User.is_blocked.is_(False))
    driver_users = select(DriverProfile.user_id)
    if body.region:
        if not valid_region(body.region):
            raise HTTPException(422, "Noto‘g‘ri hudud kodi")
        regional = select(DriverProfile.user_id).join(Trip, Trip.driver_id == DriverProfile.id).where(
            Trip.status == "active", Trip.depart_at > utcnow(), (Trip.from_region == body.region) | (Trip.to_region == body.region)
        )
        stmt = stmt.where(User.id.in_(regional))
    elif body.audience == "drivers":
        stmt = stmt.where(User.id.in_(driver_users))
    elif body.audience == "passengers":
        stmt = stmt.where(User.id.not_in(driver_users))
    ids = (await db.execute(stmt)).scalars().all()
    key = f"bc{int(utcnow().timestamp())}"
    for uid in ids:
        await enqueue(db, uid, "broadcast", body.text, key)
    audit(db, adm.id, "broadcast", "notification", key, {"audience": body.audience, "region": body.region, "recipients": len(ids)})
    await db.commit()
    return {"queued": len(ids)}


@router.get("/audit")
async def audit_log(limit: int = Query(100, le=500), _=Depends(current_admin), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit))).scalars().all()
    return [{"id": a.id, "admin_id": a.admin_id, "action": a.action, "entity": a.entity, "entity_id": a.entity_id, "details": a.details, "created_at": a.created_at} for a in rows]
