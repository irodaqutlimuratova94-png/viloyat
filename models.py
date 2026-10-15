from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """Doim timezone-aware UTC. SQLite naive qaytarsa ham UTC deb qabul qilinadi."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("naive datetime qabul qilinmaydi")
            return value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class Base(DeclarativeBase):
    pass


def created_col() -> Mapped[datetime]:
    return mapped_column(UTCDateTime, server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    username: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    full_name: Mapped[str] = mapped_column(String(120), default="")
    photo_url: Mapped[str | None] = mapped_column(String(500))
    contact_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked_until: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = created_col()


class DriverProfile(Base):
    __tablename__ = "driver_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    verification: Mapped[str] = mapped_column(String(16), default="pending")  # pending|verified|rejected
    bio: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = created_col()
    user: Mapped[User] = relationship()
    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="driver")


class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("driver_profiles.id"), index=True)
    make_model: Mapped[str] = mapped_column(String(80))
    plate: Mapped[str] = mapped_column(String(16), unique=True)
    seats: Mapped[int] = mapped_column(Integer)
    color: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = created_col()
    driver: Mapped[DriverProfile] = relationship(back_populates="vehicles")
    __table_args__ = (CheckConstraint("seats BETWEEN 1 AND 60", name="ck_vehicle_seats"),)


class Trip(Base):
    __tablename__ = "trips"
    id: Mapped[int] = mapped_column(primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("driver_profiles.id"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    from_region: Mapped[str] = mapped_column(String(32))
    from_city: Mapped[str | None] = mapped_column(String(100))
    to_region: Mapped[str] = mapped_column(String(32))
    to_city: Mapped[str | None] = mapped_column(String(100))
    depart_at: Mapped[datetime] = mapped_column(UTCDateTime)
    seats_total: Mapped[int] = mapped_column(Integer)
    seats_free: Mapped[int] = mapped_column(Integer)
    price_uzs: Mapped[int] = mapped_column(Integer)  # butun so'm
    comment: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|cancelled|completed
    moderation: Mapped[str] = mapped_column(String(16), default="ok")  # ok|hidden
    has_return: Mapped[bool] = mapped_column(Boolean, default=False)
    return_of_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id"))
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_col()
    driver: Mapped[DriverProfile] = relationship()
    vehicle: Mapped[Vehicle] = relationship()
    locations: Mapped[list["TripLocation"]] = relationship(cascade="all, delete-orphan")
    __table_args__ = (
        Index("ix_trips_search", "from_region", "to_region", "depart_at"),
        UniqueConstraint("driver_id", "idempotency_key", name="uq_trip_idem"),
        CheckConstraint("price_uzs > 0", name="ck_trip_price"),
        CheckConstraint("seats_free >= 0 AND seats_free <= seats_total", name="ck_trip_seats"),
    )


class TripLocation(Base):
    __tablename__ = "trip_locations"
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # pickup|meeting|dropoff
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    address: Mapped[str | None] = mapped_column(String(300))
    __table_args__ = (UniqueConstraint("trip_id", "kind", name="uq_trip_loc_kind"),)


class TripRequest(Base):
    """trip_id bor bo'lsa: konkret safarga so'rov. trip_id yo'q bo'lsa: yo'lovchi talabi."""

    __tablename__ = "trip_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id"), index=True)
    passenger_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    seats: Mapped[int] = mapped_column(Integer, default=1)
    message: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|accepted|rejected|cancelled|open|closed
    from_region: Mapped[str | None] = mapped_column(String(32))
    to_region: Mapped[str | None] = mapped_column(String(32))
    wanted_date: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = created_col()
    trip: Mapped[Trip | None] = relationship()
    passenger: Mapped[User] = relationship()
    __table_args__ = (UniqueConstraint("trip_id", "passenger_id", name="uq_request_once"),)


class Favorite(Base):
    __tablename__ = "favorites"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    from_region: Mapped[str] = mapped_column(String(32))
    to_region: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (UniqueConstraint("user_id", "from_region", "to_region", name="uq_fav"),)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("driver_profiles.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint("trip_id", "author_id", name="uq_review_once"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_rating"),
    )


class Complaint(Base):
    __tablename__ = "complaints"
    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    target_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id"))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open|resolved|rejected
    created_at: Mapped[datetime] = created_col()


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    days: Mapped[int] = mapped_column(Integer)
    price_uzs: Mapped[int] = mapped_column(Integer)  # admin belgilaydi
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (CheckConstraint("days > 0 AND price_uzs >= 0", name="ck_plan"),)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("driver_profiles.id"), index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("subscription_plans.id"))
    kind: Mapped[str] = mapped_column(String(8))  # trial|paid
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|cancelled
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"))
    created_at: Mapped[datetime] = created_col()


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("driver_profiles.id"))
    plan_id: Mapped[int] = mapped_column(ForeignKey("subscription_plans.id"))
    amount_uzs: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(32))
    provider_txn_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="created")  # created|paid|failed
    created_at: Mapped[datetime] = created_col()
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    __table_args__ = (UniqueConstraint("provider", "provider_txn_id", name="uq_payment_txn"),)


class Notification(Base):
    """Chiquvchi navbat: bot shu jadvaldan xabarlarni yetkazadi."""

    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(Text)
    dedupe_key: Mapped[str | None] = mapped_column(String(64))
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    error: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "dedupe_key", name="uq_notif_dedupe"),
        Index("ix_notif_pending", "sent_at"),
    )


class AdminUser(Base):
    __tablename__ = "admin_users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = created_col()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str | None] = mapped_column(String(32))
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_col()


class AppSetting(Base):
    """Sozlamalar (masalan trial_days). Topshiriqdagi 15 jadvalga qo'shimcha."""

    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))
