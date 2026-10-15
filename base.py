"""To'lov provayderi adapteri.

Haqiqiy provayder (Payme/Click/Uzum va h.k.) uchun PaymentProvider'dan voris yozing va
PROVIDERS ga qo'shing. Provayderning AMALDAGI hujjatlariga ko'ra create_invoice,
verify_webhook va parse_webhook ni to'ldiring. Hozirgi 'test' provayder faqat ishlab chiqish
va testlar uchun: oddiy HMAC-SHA256 imzo (X-Signature sarlavhasi) bilan ishlaydi.
"""
import hashlib
import hmac
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.config import get_settings


@dataclass
class WebhookEvent:
    payment_id: int
    provider_txn_id: str
    amount_uzs: int
    status: str  # "paid" | "failed"


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    def create_invoice_url(self, payment_id: int, amount_uzs: int) -> str: ...

    @abstractmethod
    def verify_webhook(self, headers: dict[str, str], body: bytes) -> bool: ...

    @abstractmethod
    def parse_webhook(self, body: bytes) -> WebhookEvent: ...


def sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestProvider(PaymentProvider):
    __test__ = False  # pytest uni test sinfi deb yig'masin
    name = "test"

    def __init__(self, secret: str):
        self.secret = secret

    def create_invoice_url(self, payment_id: int, amount_uzs: int) -> str:
        return f"{get_settings().public_web_url}/pay/{payment_id}?amount={amount_uzs}&provider=test"

    def verify_webhook(self, headers: dict[str, str], body: bytes) -> bool:
        if not self.secret:
            return False  # sir sozlanmagan bo'lsa hech qachon qabul qilinmaydi
        got = {k.lower(): v for k, v in headers.items()}.get("x-signature", "")
        return hmac.compare_digest(sign(self.secret, body), got)

    def parse_webhook(self, body: bytes) -> WebhookEvent:
        d = json.loads(body)
        return WebhookEvent(int(d["payment_id"]), str(d["txn_id"]), int(d["amount"]), str(d["status"]))


def get_provider() -> PaymentProvider:
    s = get_settings()
    if s.payment_provider == "test":
        return TestProvider(s.payment_secret)
    raise RuntimeError(
        f"'{s.payment_provider}' provayderi hali ulanmagan: app/payments/ ichida adapter yozing"
    )
