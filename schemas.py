from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.regions import UZ_TZ, in_uzbekistan, valid_region


class LocationIn(BaseModel):
    lat: float
    lon: float
    address: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _uz(self):
        if not in_uzbekistan(self.lat, self.lon):
            raise ValueError("Lokatsiya O‘zbekiston hududida bo‘lishi kerak")
        return self


class LocationOut(BaseModel):
    kind: str
    lat: float
    lon: float
    address: str | None


def _aware(v: datetime) -> datetime:
    return v.replace(tzinfo=UZ_TZ) if v.tzinfo is None else v  # sodda vaqt = Toshkent vaqti


class TripIn(BaseModel):
    from_region: str
    from_city: str | None = Field(default=None, max_length=100)
    to_region: str
    to_city: str | None = Field(default=None, max_length=100)
    depart_at: datetime
    seats_total: int = Field(ge=1, le=60)
    price_uzs: int = Field(gt=0, le=50_000_000)
    comment: str | None = Field(default=None, max_length=500)
    vehicle_id: int | None = None
    pickup: LocationIn | None = None
    meeting: LocationIn | None = None
    dropoff: LocationIn | None = None
    has_return: bool = False
    return_depart_at: datetime | None = None

    @field_validator("from_region", "to_region")
    @classmethod
    def _region(cls, v):
        if not valid_region(v):
            raise ValueError("Noto‘g‘ri hudud kodi")
        return v

    @field_validator("depart_at", "return_depart_at")
    @classmethod
    def _tz(cls, v):
        return _aware(v) if v else v

    @model_validator(mode="after")
    def _chk(self):
        if self.from_region == self.to_region and (self.from_city or "") == (self.to_city or ""):
            raise ValueError("Jo‘nash va boriladigan joy bir xil bo‘lmasligi kerak")
        if self.has_return and not self.return_depart_at:
            raise ValueError("Qaytish safari uchun vaqt kerak")
        if self.has_return and self.return_depart_at <= self.depart_at:
            raise ValueError("Qaytish vaqti jo‘nash vaqtidan keyin bo‘lishi kerak")
        return self


class TripPatch(BaseModel):
    depart_at: datetime | None = None
    seats_free: int | None = Field(default=None, ge=0, le=60)
    price_uzs: int | None = Field(default=None, gt=0, le=50_000_000)
    comment: str | None = Field(default=None, max_length=500)

    @field_validator("depart_at")
    @classmethod
    def _tz(cls, v):
        return _aware(v) if v else v


class DriverOut(BaseModel):
    id: int
    name: str
    photo_url: str | None
    rating: float | None
    rating_count: int
    verified: bool


class TripOut(BaseModel):
    id: int
    from_region: str
    from_city: str | None
    to_region: str
    to_city: str | None
    depart_at: datetime
    seats_total: int
    seats_free: int
    price_uzs: int
    comment: str | None
    status: str
    car: str
    driver: DriverOut
    locations: list[LocationOut]


class DriverRegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    make_model: str = Field(min_length=2, max_length=80)
    plate: str = Field(min_length=4, max_length=16)
    seats: int = Field(ge=1, le=60)
    color: str | None = Field(default=None, max_length=32)

    @field_validator("plate")
    @classmethod
    def _plate(cls, v):
        return "".join(v.upper().split())


class MePatch(BaseModel):
    contact_consent: bool | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=120)


class RequestIn(BaseModel):
    seats: int = Field(default=1, ge=1, le=10)
    message: str | None = Field(default=None, max_length=300)


class DemandIn(BaseModel):
    from_region: str
    to_region: str
    wanted_date: datetime | None = None
    seats: int = Field(default=1, ge=1, le=10)

    @field_validator("from_region", "to_region")
    @classmethod
    def _region(cls, v):
        if not valid_region(v):
            raise ValueError("Noto‘g‘ri hudud kodi")
        return v


class RequestDecision(BaseModel):
    status: str = Field(pattern="^(accepted|rejected)$")


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: str | None = Field(default=None, max_length=500)


class ComplaintIn(BaseModel):
    text: str = Field(min_length=5, max_length=2000)
    target_user_id: int | None = None
    trip_id: int | None = None


class FavoriteIn(BaseModel):
    from_region: str
    to_region: str

    @field_validator("from_region", "to_region")
    @classmethod
    def _region(cls, v):
        if not valid_region(v):
            raise ValueError("Noto‘g‘ri hudud kodi")
        return v


class AdminLoginIn(BaseModel):
    username: str
    password: str


class PlanIn(BaseModel):
    code: str = Field(min_length=2, max_length=32, pattern="^[a-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=80)
    days: int = Field(gt=0, le=3650)
    price_uzs: int = Field(ge=0, le=100_000_000)
    is_active: bool = True


class PlanPatch(BaseModel):
    name: str | None = None
    days: int | None = Field(default=None, gt=0, le=3650)
    price_uzs: int | None = Field(default=None, ge=0, le=100_000_000)
    is_active: bool | None = None


class BroadcastIn(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    audience: str = Field(default="all", pattern="^(all|drivers|passengers)$")
    region: str | None = None  # maqsadli: shu hududga qatnovchi faol safarlari bor haydovchilar
