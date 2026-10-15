"""Bot backend API'ning mijozi: foydalanuvchi nomidan (JWT) murojaat qiladi.
Shu tufayli obuna, validatsiya, idempotentlik qoidalari veb bilan aynan bir xil."""
import httpx

from app.config import get_settings
from app.security import create_token

_client: httpx.AsyncClient | None = None


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=get_settings().api_internal_url + "/api", timeout=15)
    return _client


async def call(method: str, path: str, user_id: int | None = None, **kw) -> tuple[int, object]:
    headers = kw.pop("headers", {})
    if user_id is not None:
        headers["Authorization"] = f"Bearer {create_token(user_id)}"
    try:
        r = await client().request(method, path, headers=headers, **kw)
    except httpx.HTTPError:
        return 503, {"detail": "Server bilan aloqa yo‘q. Birozdan so‘ng urinib ko‘ring."}
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {}


def error_text(data) -> str:
    d = data.get("detail") if isinstance(data, dict) else None
    if isinstance(d, str):
        return d
    if isinstance(d, list) and d:  # pydantic 422
        return "Ma’lumot noto‘g‘ri: " + "; ".join(str(x.get("msg", "")).removeprefix("Value error, ") for x in d[:2])
    return "Xatolik yuz berdi. Qayta urinib ko‘ring."
