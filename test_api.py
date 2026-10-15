import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Notification, Subscription, Trip
from app.payments.base import sign
from app.services import create_expiry_reminders
from tests.conftest import make_admin, make_plan, make_user, register_driver, trip_body


async def test_driver_gets_30_day_trial(client):
    _, h = await register_driver(client)
    me = (await client.get("/api/drivers/me", headers=h)).json()
    assert me["subscription"]["active"] and me["subscription"]["kind"] == "trial"
    assert 29 <= me["subscription"]["days_left"] <= 30


async def test_duplicate_plate_rejected(client):
    await register_driver(client, tg=10)
    _, h2 = await make_user("Boshqa", 11, consent=False)
    r = await client.post("/api/drivers/register", headers=h2, json={"full_name": "Boshqa", "make_model": "Nexia 3", "plate": "01a 123 bc", "seats": 5})
    assert r.status_code == 409


async def test_create_search_edit_cancel_trip(client):
    _, h = await register_driver(client)
    r = await client.post("/api/trips", headers=h, json=trip_body())
    assert r.status_code == 201, r.text
    tid = r.json()[0]["id"]
    found = (await client.get("/api/trips", params={"from_region": "toshkent_shahri", "to_region": "samarqand"})).json()
    assert [t["id"] for t in found] == [tid] and found[0]["price_uzs"] == 120000 and found[0]["car"] == "Chevrolet Malibu"
    assert (await client.get("/api/trips", params={"to_region": "buxoro"})).json() == []
    assert (await client.get("/api/trips", params={"max_price": 100000})).json() == []
    assert (await client.patch(f"/api/trips/{tid}", headers=h, json={"price_uzs": 130000})).json()["price_uzs"] == 130000
    assert (await client.delete(f"/api/trips/{tid}", headers=h)).status_code == 200
    assert (await client.get("/api/trips")).json() == []


async def test_trip_validation_and_duplicates(client):
    _, h = await register_driver(client)
    assert (await client.post("/api/trips", headers=h, json=trip_body(seats_total=5))).status_code == 422  # 5 o'rindiq -> max 4
    assert (await client.post("/api/trips", headers=h, json=trip_body(depart_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()))).status_code == 422
    assert (await client.post("/api/trips", headers=h, json=trip_body(pickup={"lat": 55.7, "lon": 37.6}))).status_code == 422  # O'zbekistondan tashqari
    body = trip_body()
    assert (await client.post("/api/trips", headers=h, json=body)).status_code == 201
    assert (await client.post("/api/trips", headers=h, json=body)).status_code == 409


async def test_idempotency_key_prevents_double_post(client):
    _, h = await register_driver(client)
    hh = {**h, "Idempotency-Key": "abc123"}
    a = await client.post("/api/trips", headers=hh, json=trip_body())
    b = await client.post("/api/trips", headers=hh, json=trip_body())
    assert a.status_code == b.status_code == 201 and a.json()[0]["id"] == b.json()[0]["id"]


async def test_return_trip_created(client):
    _, h = await register_driver(client)
    back = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    r = await client.post("/api/trips", headers=h, json=trip_body(has_return=True, return_depart_at=back))
    assert r.status_code == 201 and len(r.json()) == 2
    assert r.json()[1]["from_region"] == "samarqand" and r.json()[1]["to_region"] == "toshkent_shahri"


async def test_expired_subscription_blocks_posting_but_keeps_data(client):
    _, h = await register_driver(client)
    tid = (await client.post("/api/trips", headers=h, json=trip_body())).json()[0]["id"]
    async with SessionLocal() as db:
        for s in (await db.execute(select(Subscription))).scalars():
            s.ends_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db.commit()
    assert (await client.post("/api/trips", headers=h, json=trip_body(price_uzs=99000))).status_code == 402
    assert (await client.get(f"/api/trips/{tid}")).status_code == 200  # avvalgi safar saqlanadi
    assert (await client.get("/api/drivers/me", headers=h)).json()["subscription"]["active"] is False


async def test_request_flow_consent_seats_contact(client):
    _, dh = await register_driver(client, tg=10)
    tid = (await client.post("/api/trips", headers=dh, json=trip_body())).json()[0]["id"]
    _, ph = await make_user("Yo'lovchi", 20, consent=False)
    assert (await client.post(f"/api/trips/{tid}/requests", headers=ph, json={"seats": 1})).status_code == 403
    assert (await client.get(f"/api/trips/{tid}/contact", headers=ph)).status_code == 403
    await client.patch("/api/me", headers=ph, json={"contact_consent": True})
    r = await client.post(f"/api/trips/{tid}/requests", headers=ph, json={"seats": 2})
    assert r.status_code == 201
    assert (await client.post(f"/api/trips/{tid}/requests", headers=ph, json={"seats": 1})).status_code == 409
    contact = (await client.get(f"/api/trips/{tid}/contact", headers=ph)).json()
    assert contact["telegram"] == "https://t.me/drv10" and contact["phone"] is None
    assert (await client.get(f"/api/trips/{tid}/contact")).status_code == 401
    # boshqa haydovchi so'rovni hal qila olmaydi
    _, other = await register_driver(client, "Boshqa", 12, "01B777CC")
    rid = r.json()["id"]
    assert (await client.patch(f"/api/requests/{rid}", headers=other, json={"status": "accepted"})).status_code == 403
    assert (await client.patch(f"/api/requests/{rid}", headers=dh, json={"status": "accepted"})).status_code == 200
    assert (await client.get(f"/api/trips/{tid}")).json()["seats_free"] == 1
    async with SessionLocal() as db:
        kinds = {n.kind for n in (await db.execute(select(Notification))).scalars()}
    assert {"trip_request", "request_decision"} <= kinds


async def test_demand_notifies_matching_drivers(client):
    did, dh = await register_driver(client)
    await client.post("/api/trips", headers=dh, json=trip_body())
    _, ph = await make_user("Yo'lovchi", 20)
    r = await client.post("/api/demands", headers=ph, json={"from_region": "toshkent_shahri", "to_region": "samarqand"})
    assert r.status_code == 201 and r.json()["drivers_notified"] == 1
    r2 = await client.post("/api/demands", headers=ph, json={"from_region": "toshkent_shahri", "to_region": "buxoro"})
    assert r2.json()["drivers_notified"] == 0


async def test_payment_webhook_signed_idempotent_extends(client):
    _, h = await register_driver(client)
    admin = await make_admin()
    pid = await make_plan(50000)
    pay = (await client.post("/api/payments", headers=h, json={"plan_id": pid})).json()
    ev = json.dumps({"payment_id": pay["payment_id"], "txn_id": "T1", "amount": 50000, "status": "paid"}).encode()
    assert (await client.post("/api/payments/webhook", content=ev, headers={"X-Signature": "bad"})).status_code == 401
    wrong = json.dumps({"payment_id": pay["payment_id"], "txn_id": "T1", "amount": 1, "status": "paid"}).encode()
    assert (await client.post("/api/payments/webhook", content=wrong, headers={"X-Signature": sign("pay-secret", wrong)})).status_code == 400
    ok = {"X-Signature": sign("pay-secret", ev)}
    assert (await client.post("/api/payments/webhook", content=ev, headers=ok)).status_code == 200
    assert (await client.post("/api/payments/webhook", content=ev, headers=ok)).json().get("duplicate") is True
    me = (await client.get("/api/drivers/me", headers=h)).json()["subscription"]
    assert me["days_left"] >= 59  # 30 sinov + 30 pullik qo'shildi
    async with SessionLocal() as db:
        subs = (await db.execute(select(Subscription).where(Subscription.kind == "paid"))).scalars().all()
    assert len(subs) == 1  # takroriy webhook ikkinchi obuna yaratmadi


async def test_admin_separation_and_actions(client):
    _, uh = await make_user("Oddiy", 30)
    assert (await client.get("/api/admin/stats", headers=uh)).status_code in (401, 403)  # user tokeni admin emas
    assert (await client.get("/api/admin/stats")).status_code == 401
    ah = await make_admin()
    assert (await client.get("/api/admin/stats", headers=ah)).status_code == 200
    assert (await client.post("/api/admin/login", json={"username": "boss", "password": "wrong"})).status_code == 401
    assert (await client.post("/api/admin/login", json={"username": "boss", "password": "correct-horse-battery"})).status_code == 200
    # admin tokeni foydalanuvchi endpointida ishlamaydi
    assert (await client.get("/api/me", headers=ah)).status_code == 401


async def test_trial_days_setting_applies_to_new_drivers_and_is_audited(client):
    ah = await make_admin()
    assert (await client.put("/api/admin/settings/trial-days", headers=ah, json={"days": 10})).status_code == 200
    _, h = await register_driver(client)
    assert (await client.get("/api/drivers/me", headers=h)).json()["subscription"]["days_left"] in (9, 10)
    log = (await client.get("/api/admin/audit", headers=ah)).json()
    assert any(a["action"] == "set_trial_days" for a in log)


async def test_block_and_moderate(client):
    uid, uh = await make_user("Yomon", 40)
    ah = await make_admin()
    await client.post(f"/api/admin/users/{uid}/block", headers=ah, json={"hours": 2})
    assert (await client.get("/api/me", headers=uh)).status_code == 403
    await client.post(f"/api/admin/users/{uid}/unblock", headers=ah)
    assert (await client.get("/api/me", headers=uh)).status_code == 200
    _, dh = await register_driver(client)
    tid = (await client.post("/api/trips", headers=dh, json=trip_body())).json()[0]["id"]
    await client.post(f"/api/admin/trips/{tid}/moderate", headers=ah, json={"hidden": True})
    assert (await client.get("/api/trips")).json() == []


async def test_reminders_created_once(client):
    await register_driver(client)
    async with SessionLocal() as db:
        s = (await db.execute(select(Subscription))).scalars().first()
        s.ends_at = datetime.now(timezone.utc) + timedelta(days=2)
        await db.commit()
        assert await create_expiry_reminders(db, datetime.now(timezone.utc)) == 1
        assert await create_expiry_reminders(db, datetime.now(timezone.utc)) == 0
