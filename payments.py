import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_driver
from app.models import DriverProfile, Payment, SubscriptionPlan
from app.payments.base import get_provider
from app.services import enqueue, grant_paid, utcnow

log = logging.getLogger("payments")
router = APIRouter(tags=["payments"])


@router.get("/plans")
async def plans(db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.is_active.is_(True)).order_by(SubscriptionPlan.days))).scalars().all()
    return [{"id": p.id, "code": p.code, "name": p.name, "days": p.days, "price_uzs": p.price_uzs} for p in rows]


class PayIn(BaseModel):
    plan_id: int


@router.post("/payments", status_code=201)
async def create_payment(body: PayIn, drv: DriverProfile = Depends(current_driver), db: AsyncSession = Depends(get_session)):
    plan = await db.get(SubscriptionPlan, body.plan_id)
    if plan is None or not plan.is_active:
        raise HTTPException(404, "Tarif topilmadi")
    try:
        provider = get_provider()
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    pay = Payment(user_id=drv.user_id, driver_id=drv.id, plan_id=plan.id, amount_uzs=plan.price_uzs, provider=provider.name)
    db.add(pay)
    await db.flush()
    await db.commit()
    return {"payment_id": pay.id, "amount_uzs": pay.amount_uzs, "pay_url": provider.create_invoice_url(pay.id, pay.amount_uzs)}


@router.post("/payments/webhook")
async def webhook(request: Request, db: AsyncSession = Depends(get_session)):
    """To'lov FAQAT provayder imzosi tekshirilgandan keyin 'paid' deb qayd etiladi."""
    body = await request.body()
    try:
        provider = get_provider()
    except RuntimeError:
        raise HTTPException(503, "Provayder sozlanmagan")
    if not provider.verify_webhook(dict(request.headers), body):
        log.warning("webhook: imzo noto'g'ri")
        raise HTTPException(401, "Imzo noto‘g‘ri")
    try:
        ev = provider.parse_webhook(body)
    except Exception:
        raise HTTPException(400, "Webhook formati noto‘g‘ri")

    pay = (await db.execute(select(Payment).where(Payment.id == ev.payment_id).with_for_update())).scalar_one_or_none()
    if pay is None or pay.provider != provider.name:
        raise HTTPException(404, "To‘lov topilmadi")
    if pay.status == "paid":  # takroriy webhook: idempotent
        return {"ok": True, "duplicate": True}
    if ev.status != "paid":
        pay.status = "failed"
        await db.commit()
        return {"ok": True}
    if ev.amount_uzs != pay.amount_uzs:
        log.error("webhook: summa mos emas payment=%s", pay.id)
        raise HTTPException(400, "Summa mos kelmadi")

    plan = await db.get(SubscriptionPlan, pay.plan_id)
    now = utcnow()
    pay.status, pay.provider_txn_id, pay.paid_at = "paid", ev.provider_txn_id, now
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Tranzaksiya identifikatori allaqachon ishlatilgan")
    sub = await grant_paid(db, pay.driver_id, plan, pay.id, now)
    await enqueue(db, pay.user_id, "payment_ok", f"To‘lov qabul qilindi. Obunangiz {sub.ends_at:%d.%m.%Y} gacha amal qiladi.", f"pay{pay.id}")
    await db.commit()
    return {"ok": True}
