import html
from datetime import datetime, timedelta

from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.regions import CITIES, REGIONS, UZ_TZ

M_FIND, M_BECOME, M_POST, M_LOC = "🚕 Safar topish", "🚗 Haydovchi bo‘lish", "➕ Safar joylash", "📍 Lokatsiya yuborish"
M_MY, M_PROFILE, M_FAV, M_SUB, M_HELP = "🧳 Safarlarim", "👤 Profilim", "⭐ Sevimlilar", "💳 Obuna", "📞 Yordam"


def main_menu():
    kb = ReplyKeyboardBuilder()
    for t in (M_FIND, M_BECOME, M_POST, M_LOC, M_MY, M_PROFILE, M_FAV, M_SUB, M_HELP):
        kb.button(text=t)
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


def nav_row(kb: InlineKeyboardBuilder, back: str | None):
    row = []
    if back:
        row.append(("⬅️ Ortga", back))
    row.append(("🏠 Bekor qilish", "cancel"))
    for text, data in row:
        kb.button(text=text, callback_data=data)
    return len(row)


def regions_kb(prefix: str, back: str | None = None):
    kb = InlineKeyboardBuilder()
    for code, name in REGIONS.items():
        kb.button(text=name.replace(" viloyati", ""), callback_data=f"{prefix}:{code}")
    kb.adjust(2)
    n = nav_row(kb, back)
    kb.adjust(*([2] * 7), n)
    return kb.as_markup()


def cities_kb(prefix: str, region: str, back: str | None, any_label: str):
    kb = InlineKeyboardBuilder()
    kb.button(text=any_label, callback_data=f"{prefix}:-")
    for i, c in enumerate(CITIES.get(region, [])):
        kb.button(text=c, callback_data=f"{prefix}:{i}")
    kb.adjust(2)
    n = nav_row(kb, back)
    return kb.as_markup()


def dates_kb(prefix: str, back: str | None, allow_any: bool):
    kb = InlineKeyboardBuilder()
    today = datetime.now(UZ_TZ).date()
    for i in range(7):
        d = today + timedelta(days=i)
        label = "Bugun" if i == 0 else "Ertaga" if i == 1 else d.strftime("%d.%m")
        kb.button(text=label, callback_data=f"{prefix}:{d.isoformat()}")
    if allow_any:
        kb.button(text="Istalgan kun", callback_data=f"{prefix}:any")
    kb.adjust(3)
    nav_row(kb, back)
    return kb.as_markup()


def number_kb(prefix: str, nums, back: str | None):
    kb = InlineKeyboardBuilder()
    for n in nums:
        kb.button(text=str(n), callback_data=f"{prefix}:{n}")
    kb.adjust(4)
    nav_row(kb, back)
    return kb.as_markup()


def skip_kb(skip_cb: str, back: str | None):
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ O‘tkazib yuborish", callback_data=skip_cb)
    nav_row(kb, back)
    kb.adjust(1, 2)
    return kb.as_markup()


def location_request_kb():
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="📍 Joriy lokatsiyamni yuborish", request_location=True))
    kb.add(KeyboardButton(text="🏠 Asosiy menyu"))
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True, one_time_keyboard=True)


def contact_request_kb():
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True))
    kb.add(KeyboardButton(text="🏠 Asosiy menyu"))
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True, one_time_keyboard=True)


def esc(x) -> str:
    return html.escape(str(x)) if x is not None else ""


def money(v: int) -> str:
    return f"{v:,}".replace(",", " ") + " so‘m"


def fmt_dt(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(UZ_TZ).strftime("%d.%m.%Y %H:%M")


def place(region: str, city: str | None) -> str:
    return esc(f"{REGIONS[region]}" + (f", {city}" if city else ""))


def trip_card(t: dict) -> str:
    d = t["driver"]
    rating = f" ⭐{d['rating']} ({d['rating_count']})" if d["rating"] else ""
    lines = [
        f"🚗 <b>{place(t['from_region'], t['from_city'])} → {place(t['to_region'], t['to_city'])}</b>",
        f"🕒 {fmt_dt(t['depart_at'])}",
        f"💺 Bo‘sh joy: {t['seats_free']}",
        f"💰 {money(t['price_uzs'])} (1 yo‘lovchi)",
        f"👤 {esc(d['name'])}{' ✅' if d['verified'] else ''}{rating}",
        f"🚘 {esc(t['car'])}",
    ]
    if t.get("comment"):
        lines.append(f"💬 {esc(t['comment'])}")
    return "\n".join(lines)
