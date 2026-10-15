import os

os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////tmp/vb_test.db"
os.environ["BOT_TOKEN"] = "123456:TEST-TOKEN"
os.environ["PAYMENT_PROVIDER"] = "test"
os.environ["PAYMENT_SECRET"] = "pay-secret"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AdminUser, Base, SubscriptionPlan, User  # noqa: E402
from app.security import create_token, hash_password  # noqa: E402


@pytest.fixture(autouse=True)
async def fresh_db():
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        await c.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def make_user(name="Ali", tg=1, consent=True, username=None) -> tuple[int, dict]:
    async with SessionLocal() as db:
        u = User(telegram_id=tg, full_name=name, username=username, contact_consent=consent)
        db.add(u)
        await db.commit()
        return u.id, {"Authorization": f"Bearer {create_token(u.id)}"}


async def make_admin() -> dict:
    async with SessionLocal() as db:
        a = AdminUser(username="boss", password_hash=hash_password("correct-horse-battery"))
        db.add(a)
        await db.commit()
        return {"Authorization": f"Bearer {create_token(a.id, 'admin')}"}


async def make_plan(price=50000) -> int:
    async with SessionLocal() as db:
        p = SubscriptionPlan(code="m1", name="1 oy", days=30, price_uzs=price)
        db.add(p)
        await db.commit()
        return p.id


async def register_driver(client, name="Haydovchi", tg=10, plate="01A123BC", seats=5):
    uid, h = await make_user(name, tg, consent=False, username=f"drv{tg}")
    r = await client.post("/api/drivers/register", headers=h, json={"full_name": name, "make_model": "Chevrolet Malibu", "plate": plate, "seats": seats})
    assert r.status_code == 201, r.text
    return uid, h


def trip_body(**kw):
    from datetime import datetime, timedelta, timezone

    b = {
        "from_region": "toshkent_shahri", "from_city": "Chilonzor", "to_region": "samarqand", "to_city": "Samarqand",
        "depart_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(), "seats_total": 3, "price_uzs": 120000,
        "pickup": {"lat": 41.28, "lon": 69.20, "address": "Chilonzor"},
    }
    b.update(kw)
    return b
