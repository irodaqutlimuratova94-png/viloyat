from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.deps import current_driver, current_user
from app.models import (
    Complaint, DriverProfile, Favorite, Review, Trip, TripLocation, TripRequest, User, Vehicle,
)
from app.regions import UZ_TZ, valid_region
from app.schemas import (
    ComplaintIn, DemandIn, DriverOut, FavoriteIn, LocationOut, RequestDecision, RequestIn,
    ReviewIn, TripIn, TripOut, TripPatch,
)
from app.services import active_subscription, enqueue, ratings_for, utcnow

router = APIRouter(tags=["trips"])

LOAD = (
    selectinload(Trip.driver).selectinload(DriverProfile.user),
    selectinload(Trip.vehicle),
    selectinload(Trip.locations),
)


async def to_out(db: AsyncSession, trips: list[Trip]) -> list[TripOut]:
    ratings = await ratings_for(db, list({t.driver_id for t in trips}))
    out = []
    for t in trips:
        r = ratings.get(t.driver_id)
        out.append(
            TripOut(
                id=t.id, from_region=t.from_region, from_city=t.from_city, to_region=t.to_region,
                to_city=t.to_city, depart_at=t.depart_at, seats_total=t.seats_total, seats_free=t.seats_free,
                price_uzs=t.price_uzs, comment=t.comment, status=t.status, car=t.vehicle.make_model,
                driver=DriverOut(
                    id=t.driver_id, name=t.driver.user.full_name, photo_url=t.driver.user.photo_url,
                    rating=r[0] if r else None, rating_count=r[1] if r else 0,
                    verified=t.driver.verification == "verified",
                ),
                locations=[LocationOut(kind=l.kind, lat=l.lat, lon=l.lon, address=l.address) for l in t.locations],
            )
        )
    return out


async def load_trips(db: AsyncSession, ids: list[int]) -> list[Trip]:
    rows = (await db.execute(select(Trip).options(*LOAD).where(Trip.id.in_(ids)).order_by(Trip.id))).scalars().all()
    return list(rows)


async def _get_trip(db: AsyncSession, trip_id: int) -> Trip:
    trips = await load_trips(db, [trip_id])
    if not trips:
        raise HTTPException(404, "Safar topilmadi")
    return trips[0]


def _add_locations(db, trip_id: int, pickup, meeting, dropoff):
    for kind, loc in (("pickup", pickup), ("meeting", meeting), ("dropoff", dropoff)):
        if loc:
            db.add(TripLocation(trip_id=trip_id, kind=kind, lat=loc.lat, lon=loc.lon, address=loc.address))


@router.post("/trips", response_model=list[TripOut], status_code=201)
async def create_trip(
    body: TripIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=64),
    drv: DriverProfile = Depends(current_driver),
    db: AsyncSession = Depends(get_session),
):
    now = utcnow()
    if idempotency_key:  # takroriy yuborishdan himoya
        prev = (await db.execute(select(Trip.id).where(Trip.driver_id == drv.id, Trip.idempotency_key.in_((idempotency_key, f"{idempotency_key}:r"))))).scalars().all()
        if prev:
            return await to_out(db, await load_trips(db, list(prev)))

    if not await active_subscription(db, drv.id, now):
        raise HTTPException(402, "Faol obuna yo‘q. Yangi safar e’lon qilish uchun obunani yangilang.")
    if body.depart_at <= now:
        raise HTTPException(422, "Jo‘nash vaqti kelajakda bo‘lishi kerak")

    vq = select(Vehicle).where(Vehicle.driver_id == drv.id)
    if body.vehicle_id:
        vq = vq.where(Vehicle.id == body.vehicle_id)
    vehicle = (await db.execute(vq.order_by(Vehicle.id).limit(1))).scalar_one_or_none()
    if vehicle is None:
        raise HTTPException(422, "Avtomobil topilmadi")
    if body.seats_total > vehicle.seats - 1:
        raise HTTPException(422, f"Bo‘sh o‘rinlar soni {vehicle.seats - 1} dan oshmasligi kerak")

    dup = (
        await db.execute(
            select(Trip.id).where(
                Trip.driver_id == drv.id, Trip.status == "active", Trip.depart_at == body.depart_at,
                Trip.from_region == body.from_region, Trip.to_region == body.to_region,
            )
        )
    ).first()
    if dup:
        raise HTTPException(409, "Bu vaqtga shu yo‘nalishda safaringiz allaqachon bor")

    main = Trip(
        driver_id=drv.id, vehicle_id=vehicle.id, from_region=body.from_region, from_city=body.from_city,
        to_region=body.to_region, to_city=body.to_city, depart_at=body.depart_at, seats_total=body.seats_total,
        seats_free=body.seats_total, price_uzs=body.price_uzs, comment=body.comment,
        has_return=body.has_return, idempotency_key=idempotency_key,
    )
    db.add(main)
    try:
        await db.flush()
        _add_locations(db, main.id, body.pickup, body.meeting, body.dropoff)
        ids = [main.id]
        if body.has_return:
            back = Trip(
                driver_id=drv.id, vehicle_id=vehicle.id, from_region=body.to_region, from_city=body.to_city,
                to_region=body.from_region, to_city=body.from_city, depart_at=body.return_depart_at,
                seats_total=body.seats_total, seats_free=body.seats_total, price_uzs=body.price_uzs,
                comment=body.comment, return_of_id=main.id,
                idempotency_key=f"{idempotency_key}:r" if idempotency_key else None,
            )
            db.add(back)
            await db.flush()
            _add_locations(db, back.id, body.dropoff, None, body.pickup)
            ids.append(back.id)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Safar allaqachon yaratilgan")
    return await to_out(db, await load_trips(db, ids))


@router.get("/trips", response_model=list[TripOut])
async def search_trips(
    from_region: str | None = None, to_region: str | None = None,
    from_city: str | None = None, to_city: str | None = None,
    date_: date | None = Query(default=None, alias="date"),
    min_price: int | None = Query(default=None, ge=0), max_price: int | None = Query(default=None, ge=0),
    min_seats: int = Query(default=1, ge=1, le=60),
    time_from: time | None = None, time_to: time | None = None,
    limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_session),
):
    for r in (from_region, to_region):
        if r and not valid_region(r):
            raise HTTPException(422, "Noto‘g‘ri hudud kodi")
    now = utcnow()
    q = select(Trip).options(*LOAD).where(
        Trip.status == "active", Trip.moderation == "ok", Trip.depart_at > now, Trip.seats_free >= min_seats
    )
    if from_region:
        q = q.where(Trip.from_region == from_region)
    if to_region:
        q = q.where(Trip.to_region == to_region)
    if from_city:
        q = q.where(Trip.from_city == from_city)
    if to_city:
        q = q.where(Trip.to_city == to_city)
    if min_price is not None:
        q = q.where(Trip.price_uzs >= min_price)
    if max_price is not None:
        q = q.where(Trip.price_uzs <= max_price)
    if date_:
        start = datetime.combine(date_, time.min, tzinfo=UZ_TZ)
        q = q.where(Trip.depart_at >= start, Trip.depart_at < start + timedelta(days=1))
    q = q.order_by(Trip.depart_at, Trip.id)
    if time_from or time_to:  # kun ichidagi vaqt filtri (Toshkent vaqti)
        rows = (await db.execute(q.limit(500))).scalars().all()
        rows = [
            t for t in rows
            if (not time_from or t.depart_at.astimezone(UZ_TZ).time() >= time_from)
            and (not time_to or t.depart_at.astimezone(UZ_TZ).time() <= time_to)
        ][offset : offset + limit]
    else:
        rows = (await db.execute(q.limit(limit).offset(offset))).scalars().all()
    return await to_out(db, list(rows))


@router.get("/trips/mine", response_model=list[TripOut])
async def my_trips(drv: DriverProfile = Depends(current_driver), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(Trip).options(*LOAD).where(Trip.driver_id == drv.id).order_by(Trip.depart_at.desc()).limit(100))).scalars().all()
    return await to_out(db, list(rows))


@router.get("/trips/{trip_id}", response_model=TripOut)
async def get_trip(trip_id: int, db: AsyncSession = Depends(get_session)):
    t = await _get_trip(db, trip_id)
    if t.moderation != "ok":
        raise HTTPException(404, "Safar topilmadi")
    return (await to_out(db, [t]))[0]


def _own(trip: Trip, drv: DriverProfile) -> None:
    if trip.driver_id != drv.id:
        raise HTTPException(403, "Bu sizning safaringiz emas")


async def _notify_passengers(db, trip: Trip, text: str, kind: str):
    reqs = (await db.execute(select(TripRequest).where(TripRequest.trip_id == trip.id, TripRequest.status.in_(("pending", "accepted"))))).scalars().all()
    for r in reqs:
        await enqueue(db, r.passenger_id, kind, text)
    return reqs


@router.patch("/trips/{trip_id}", response_model=TripOut)
async def edit_trip(trip_id: int, body: TripPatch, drv: DriverProfile = Depends(current_driver), db: AsyncSession = Depends(get_session)):
    t = await _get_trip(db, trip_id)
    _own(t, drv)
    if t.status != "active":
        raise HTTPException(409, "Faqat faol safarni tahrirlash mumkin")
    if body.depart_at is not None:
        if body.depart_at <= utcnow():
            raise HTTPException(422, "Jo‘nash vaqti kelajakda bo‘lishi kerak")
        changed = body.depart_at != t.depart_at
        t.depart_at = body.depart_at
        if changed:
            await _notify_passengers(db, t, f"Safar #{t.id} jo‘nash vaqti o‘zgardi. Tafsilotlarni tekshiring.", "trip_changed")
    if body.seats_free is not None:
        if body.seats_free > t.seats_total:
            raise HTTPException(422, "Bo‘sh o‘rinlar umumiy sondan oshmasligi kerak")
        t.seats_free = body.seats_free
    if body.price_uzs is not None:
        t.price_uzs = body.price_uzs
    if body.comment is not None:
        t.comment = body.comment
    await db.commit()
    return (await to_out(db, [t]))[0]


@router.delete("/trips/{trip_id}")
async def cancel_trip(trip_id: int, drv: DriverProfile = Depends(current_driver), db: AsyncSession = Depends(get_session)):
    """Safar o'chirilmaydi, 'cancelled' deb belgilanadi (yo'lovchilar tarixi saqlanadi)."""
    t = await _get_trip(db, trip_id)
    _own(t, drv)
    if t.status == "active":
        t.status = "cancelled"
        reqs = await _notify_passengers(db, t, f"Safar #{t.id} haydovchi tomonidan bekor qilindi.", "trip_cancelled")
        for r in reqs:
            r.status = "cancelled"
    await db.commit()
    return {"ok": True}


@router.post("/trips/{trip_id}/requests", status_code=201)
async def request_trip(trip_id: int, body: RequestIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_session)):
    t = await _get_trip(db, trip_id)
    if t.status != "active" or t.moderation != "ok" or t.depart_at <= utcnow():
        raise HTTPException(409, "Safar mavjud emas")
    if t.driver.user_id == user.id:
        raise HTTPException(409, "O‘z safaringizga so‘rov yubora olmaysiz")
    if not user.contact_consent:
        raise HTTPException(403, "Haydovchi bilan bog‘lanish uchun aloqa roziligini bering")
    if body.seats > t.seats_free:
        raise HTTPException(409, "Yetarli bo‘sh o‘rin yo‘q")
    req = TripRequest(trip_id=t.id, passenger_id=user.id, seats=body.seats, message=body.message)
    db.add(req)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Siz bu safarga allaqachon so‘rov yuborgansiz")
    await enqueue(db, t.driver.user_id, "trip_request", f"Safar #{t.id} bo‘yicha yangi so‘rov: {user.full_name}, {body.seats} o‘rin.")
    await db.commit()
    return {"id": req.id, "status": req.status}


@router.get("/trips/{trip_id}/contact")
async def trip_contact(trip_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_session)):
    """Haydovchi kontaktlari: faqat tizimga kirgan va rozilik bergan foydalanuvchiga."""
    if not user.contact_consent:
        raise HTTPException(403, "Avval aloqa roziligini bering")
    t = await _get_trip(db, trip_id)
    du = t.driver.user
    tg = f"https://t.me/{du.username}" if du.username else (f"tg://user?id={du.telegram_id}" if du.telegram_id else None)
    phone = du.phone if (du.phone and du.contact_consent) else None
    return {"telegram": tg, "phone": phone}


@router.patch("/requests/{request_id}")
async def decide_request(request_id: int, body: RequestDecision, drv: DriverProfile = Depends(current_driver), db: AsyncSession = Depends(get_session)):
    req = (await db.execute(select(TripRequest).where(TripRequest.id == request_id).with_for_update())).scalar_one_or_none()
    if req is None or req.trip_id is None:
        raise HTTPException(404, "So‘rov topilmadi")
    t = (await db.execute(select(Trip).where(Trip.id == req.trip_id).with_for_update())).scalar_one()
    _own(t, drv)
    if req.status != "pending":
        raise HTTPException(409, "So‘rov allaqachon ko‘rib chiqilgan")
    if body.status == "accepted":
        if req.seats > t.seats_free:
            raise HTTPException(409, "Yetarli bo‘sh o‘rin yo‘q")
        t.seats_free -= req.seats
    req.status = body.status
    word = "qabul qilindi" if body.status == "accepted" else "rad etildi"
    await enqueue(db, req.passenger_id, "request_decision", f"Safar #{t.id} bo‘yicha so‘rovingiz {word}.")
    await db.commit()
    return {"ok": True, "status": req.status}


@router.get("/me/requests")
async def my_requests(user: User = Depends(current_user), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(TripRequest).where(TripRequest.passenger_id == user.id).order_by(TripRequest.created_at.desc()).limit(100))).scalars().all()
    return [{"id": r.id, "trip_id": r.trip_id, "seats": r.seats, "status": r.status, "from_region": r.from_region, "to_region": r.to_region} for r in rows]


@router.delete("/requests/{request_id}")
async def cancel_request(request_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_session)):
    req = (await db.execute(select(TripRequest).where(TripRequest.id == request_id, TripRequest.passenger_id == user.id).with_for_update())).scalar_one_or_none()
    if req is None:
        raise HTTPException(404, "So‘rov topilmadi")
    if req.status in ("pending", "accepted", "open"):
        if req.status == "accepted" and req.trip_id:
            t = (await db.execute(select(Trip).where(Trip.id == req.trip_id).with_for_update())).scalar_one()
            t.seats_free = min(t.seats_total, t.seats_free + req.seats)
        req.status = "cancelled"
    await db.commit()
    return {"ok": True}


@router.post("/demands", status_code=201)
async def create_demand(body: DemandIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_session)):
    """Mos safar topilmasa: yo'lovchi talabi. Shu yo'nalishdagi haydovchilarga bildirishnoma ketadi."""
    if not user.contact_consent:
        raise HTTPException(403, "Avval aloqa roziligini bering")
    wanted = body.wanted_date.replace(tzinfo=UZ_TZ) if body.wanted_date and body.wanted_date.tzinfo is None else body.wanted_date
    d = TripRequest(passenger_id=user.id, seats=body.seats, status="open", from_region=body.from_region, to_region=body.to_region, wanted_date=wanted)
    db.add(d)
    await db.flush()
    drivers = (
        await db.execute(
            select(DriverProfile.user_id).join(Trip, Trip.driver_id == DriverProfile.id).where(
                Trip.status == "active", Trip.moderation == "ok", Trip.depart_at > utcnow(),
                Trip.from_region == body.from_region, Trip.to_region == body.to_region,
            ).distinct()
        )
    ).scalars().all()
    notified = 0
    for uid in drivers:
        if uid != user.id and await enqueue(db, uid, "demand", f"Yo‘lovchi shu yo‘nalishda safar qidirmoqda ({body.seats} o‘rin). Safaringiz mos kelsa, e’londa bo‘sh joy qoldiring.", f"demand{d.id}"):
            notified += 1
    await db.commit()
    return {"id": d.id, "drivers_notified": notified}


@router.get("/favorites")
async def list_favorites(user: User = Depends(current_user), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(Favorite).where(Favorite.user_id == user.id))).scalars().all()
    return [{"id": f.id, "from_region": f.from_region, "to_region": f.to_region} for f in rows]


@router.post("/favorites", status_code=201)
async def add_favorite(body: FavoriteIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_session)):
    db.add(Favorite(user_id=user.id, from_region=body.from_region, to_region=body.to_region))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()  # allaqachon bor: idempotent
    return {"ok": True}


@router.delete("/favorites/{fav_id}")
async def del_favorite(fav_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_session)):
    f = (await db.execute(select(Favorite).where(Favorite.id == fav_id, Favorite.user_id == user.id))).scalar_one_or_none()
    if f:
        await db.delete(f)
        await db.commit()
    return {"ok": True}


@router.post("/trips/{trip_id}/reviews", status_code=201)
async def add_review(trip_id: int, body: ReviewIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_session)):
    t = await _get_trip(db, trip_id)
    ok = (await db.execute(select(TripRequest.id).where(TripRequest.trip_id == t.id, TripRequest.passenger_id == user.id, TripRequest.status == "accepted"))).first()
    if not ok:
        raise HTTPException(403, "Faqat qabul qilingan yo‘lovchi baholay oladi")
    if t.depart_at > utcnow():
        raise HTTPException(409, "Safar tugagandan keyin baholash mumkin")
    db.add(Review(trip_id=t.id, author_id=user.id, driver_id=t.driver_id, rating=body.rating, text=body.text))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Siz bu safarni allaqachon baholagansiz")
    return {"ok": True}


@router.post("/complaints", status_code=201)
async def complain(body: ComplaintIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_session)):
    c = Complaint(author_id=user.id, target_user_id=body.target_user_id, trip_id=body.trip_id, text=body.text)
    db.add(c)
    await db.commit()
    return {"id": c.id}
