import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.payments.base import TestProvider, sign
from app.regions import CITIES, REGIONS, in_uzbekistan
from app.security import (
    create_token, decode_token, hash_password, verify_password, verify_telegram_login,
)
from app.subscription import paid_start, reminder_bucket, trial_end

NOW = datetime(2026, 10, 12, tzinfo=timezone.utc)


def test_trial_is_30_days():
    assert trial_end(NOW, 30) == NOW + timedelta(days=30)
    with pytest.raises(ValueError):
        trial_end(NOW, 0)


@pytest.mark.parametrize("left,exp", [(timedelta(days=20), None), (timedelta(days=7), 7), (timedelta(days=5), 7),
                                      (timedelta(days=3), 3), (timedelta(days=2), 3), (timedelta(hours=20), 1), (timedelta(hours=-1), None)])
def test_reminder_buckets(left, exp):
    assert reminder_bucket(NOW + left, NOW) == exp


def test_paid_start_appends():
    assert paid_start(NOW, NOW + timedelta(days=5)) == NOW + timedelta(days=5)
    assert paid_start(NOW, NOW - timedelta(days=1)) == NOW


def test_regions():
    assert len(REGIONS) == 14 and set(CITIES) == set(REGIONS)
    assert in_uzbekistan(41.31, 69.28) and not in_uzbekistan(55.7, 37.6)


def test_tokens_not_interchangeable():
    t = create_token(5)
    assert decode_token(t, "user")["sub"] == "5"
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(t, "admin")


def test_password_hash():
    h = hash_password("pw")
    assert verify_password("pw", h) and not verify_password("x", h)


def test_telegram_login_signature():
    bt = "123456:TEST-TOKEN"
    d = {"id": 1, "first_name": "A", "auth_date": int(time.time())}
    chk = "\n".join(f"{k}={d[k]}" for k in sorted(d))
    d["hash"] = hmac.new(hashlib.sha256(bt.encode()).digest(), chk.encode(), hashlib.sha256).hexdigest()
    assert verify_telegram_login(d, bt, 3600)
    assert not verify_telegram_login({**d, "first_name": "B"}, bt, 3600)
    assert not verify_telegram_login(d, bt, 3600, now=time.time() + 10**6)


def test_webhook_signature():
    body = json.dumps({"payment_id": 1, "txn_id": "t", "amount": 5, "status": "paid"}).encode()
    p = TestProvider("s")
    assert p.verify_webhook({"X-Signature": sign("s", body)}, body)
    assert not p.verify_webhook({"X-Signature": "bad"}, body)
    assert not TestProvider("").verify_webhook({"X-Signature": sign("", body)}, body)
