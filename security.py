import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl

import jwt

from app.config import get_settings

ALGO = "HS256"
PBKDF2_ITERS = 600_000


def create_token(subject: int, typ: str = "user") -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": str(subject), "typ": typ, "iat": now, "exp": now + timedelta(minutes=s.jwt_expire_minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGO)


def decode_token(token: str, typ: str) -> dict:
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGO])
    if payload.get("typ") != typ:
        raise jwt.InvalidTokenError("noto'g'ri token turi")
    return payload


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERS)
    return f"pbkdf2${PBKDF2_ITERS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, digest = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters))
    except ValueError:
        return False
    return hmac.compare_digest(dk.hex(), digest)


def verify_telegram_login(data: dict, bot_token: str, max_age: int, now: float | None = None) -> bool:
    """Telegram Login Widget: secret = SHA256(bot_token)."""
    data = {k: str(v) for k, v in data.items()}
    received = data.pop("hash", "")
    if not received or not bot_token:
        return False
    check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hashlib.sha256(bot_token.encode()).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received):
        return False
    try:
        age = (now or time.time()) - int(data.get("auth_date", "0"))
    except ValueError:
        return False
    return 0 <= age <= max_age


def verify_webapp_init_data(init_data: str, bot_token: str, max_age: int, now: float | None = None) -> dict | None:
    """Telegram Mini App initData: secret = HMAC('WebAppData', bot_token). Muvaffaqiyatda maydonlar dict'i."""
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", "")
    if not received or not bot_token:
        return None
    check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received):
        return None
    try:
        age = (now or time.time()) - int(pairs.get("auth_date", "0"))
    except ValueError:
        return None
    return pairs if 0 <= age <= max_age else None
