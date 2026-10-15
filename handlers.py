import re
import uuid
from datetime import datetime

from aiogram import BaseMiddleware, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import User
from app.regions import CITIES, REGIONS, UZ_TZ
from app.services import upsert_telegram_user
from bot import api
from bot.ui import (
    M_BECOME, M_FAV, M_FIND, M_HELP, M_LOC, M_MY, M_POST, M_PROFILE, M_SUB, cities_kb, contact_request_kb,
    dates_kb, esc, fmt_dt, location_request_kb, main_menu, money, number_kb, place, regions_kb, skip_kb, trip_card,
)

router = Router()
MENU = {M_FIND, M_BECOME, M_POST, M_LOC, M_MY, M_PROFILE, M_FAV, M_SUB, M_HELP, "🏠 Asosiy menyu"}
NOT_MENU = ~F.text.in_(MENU)


class MenuResets(BaseMiddleware):
    """Menyu tugmasi bosilsa, oqim (FSM) bekor qilinadi va matn 'javob' sifatida yutilmaydi."""

    async def __call__(self, handler, event: Message, data):
        if event.text in MENU:
            if (st := data.get("state")) is not None:
                await st.clear()
            data["raw_state"] = None
        return await handler(event, data)


router.message.outer_middleware(MenuResets())
UZ_PHONE = re.compile(r"^\+?998\d{9}$")


class Find(StatesGroup):
    from_r = State(); to_r = State(); city = State(); date = State(); pax = State()


class Post(StatesGroup):
    from_r = State(); from_c = State(); to_r = State(); to_c = State(); pickup = State(); dropoff = State()
    date = State(); time = State(); seats = State(); price = State(); confirm = State()


class Become(StatesGroup):
    phone = State(); model = State(); plate = State(); seats = State()


class Loc(StatesGroup):
    wait = State()


async def me(m) -> int:
    """Telegram foydalanuvchisini bazaga yozadi/yangilaydi va ichki user_id ni qaytaradi."""
    u = m.from_user
    async with SessionLocal() as db:
        user = await upsert_telegram_user(db, u.id, u.full_name, u.username)
        await db.commit()
        return user.id


# ---------- umumiy ----------
@router.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear()
    await me(m)
    await m.answer("<b>Viloyatga Boramiz</b>\nManzilingiz bir, yo‘lingiz bir.\n\nQuyidagi menyudan tanlang 👇", reply_markup=main_menu())


@router.message(F.text == "🏠 Asosiy menyu")
@router.message(Command("menu"))
async def menu(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("Asosiy menyu", reply_markup=main_menu())


@router.callback_query(F.data == "cancel")
async def cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer("Bekor qilindi")
    await cb.message.answer("Bekor qilindi. Asosiy menyu:", reply_markup=main_menu())


@router.message(F.text == M_HELP)
async def help_(m: Message):
    await m.answer("📞 <b>Yordam</b>\nSavol va takliflar uchun administratorga yozing. Shikoyat yuborish: veb-saytdagi “Shikoyat” bo‘limi.\nPlatforma haydovchi va yo‘lovchini bog‘laydi; narxni haydovchining o‘zi belgilaydi.")


# ---------- SAFAR TOPISH ----------
async def find_from(t: Message, s: FSMContext):
    await s.set_state(Find.from_r)
    await t.answer("Qayerdan yo‘lga chiqasiz?", reply_markup=regions_kb("f1"))


async def find_to(t: Message, s: FSMContext):
    await s.set_state(Find.to_r)
    await t.answer("Qayerga borasiz?", reply_markup=regions_kb("f2", "fb:from_r"))


async def find_city(t: Message, s: FSMContext):
    d = await s.get_data()
    await s.set_state(Find.city)
    await t.answer("Shahar yoki tuman?", reply_markup=cities_kb("f3", d["to"], "fb:to_r", "Barcha shaharlar"))


async def find_date(t: Message, s: FSMContext):
    await s.set_state(Find.date)
    await t.answer("Safar sanasi?", reply_markup=dates_kb("f4", "fb:city", True))


async def find_pax(t: Message, s: FSMContext):
    await s.set_state(Find.pax)
    await t.answer("Yo‘lovchilar soni?", reply_markup=number_kb("f5", range(1, 5), "fb:date"))


FIND_STEPS = {"from_r": find_from, "to_r": find_to, "city": find_city, "date": find_date}


@router.message(F.text == M_FIND)
async def find_start(m: Message, state: FSMContext):
    await state.clear()
    await me(m)
    await find_from(m, state)


@router.callback_query(F.data.startswith("fb:"))
async def find_back(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await FIND_STEPS[cb.data.split(":")[1]](cb.message, state)


@router.callback_query(Find.from_r, F.data.startswith("f1:"))
async def f1(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.update_data(frm=cb.data.split(":")[1])
    await find_to(cb.message, state)


@router.callback_query(Find.to_r, F.data.startswith("f2:"))
async def f2(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.update_data(to=cb.data.split(":")[1])
    await find_city(cb.message, state)


@router.callback_query(Find.city, F.data.startswith("f3:"))
async def f3(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    v, d = cb.data.split(":")[1], await state.get_data()
    await state.update_data(city=None if v == "-" else CITIES[d["to"]][int(v)])
    await find_date(cb.message, state)


@router.callback_query(Find.date, F.data.startswith("f4:"))
async def f4(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    v = cb.data.split(":", 1)[1]
    await state.update_data(date=None if v == "any" else v)
    await find_pax(cb.message, state)


@router.callback_query(Find.pax, F.data.startswith("f5:"))
async def f5(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    d = await state.get_data()
    pax = int(cb.data.split(":")[1])
    await state.update_data(pax=pax)
    params = {"from_region": d["frm"], "to_region": d["to"], "min_seats": pax, "limit": 8}
    if d.get("city"):
        params["to_city"] = d["city"]
    if d.get("date"):
        params["date"] = d["date"]
    code, trips = await api.call("GET", "/trips", params=params)
    if code != 200:
        return await cb.message.answer(api.error_text(trips), reply_markup=main_menu())
    if not trips:
        kb = InlineKeyboardBuilder()
        kb.button(text="🔔 Talab yaratish (haydovchilarga xabar)", callback_data="demand")
        kb.button(text="⭐ Yo‘nalishni sevimlilarga", callback_data="fav")
        kb.adjust(1)
        return await cb.message.answer("Hozircha mos safar topilmadi. Talab qoldirsangiz, shu yo‘nalishdagi haydovchilarga xabar yuboramiz.", reply_markup=kb.as_markup())
    await cb.message.answer(f"Topildi: {len(trips)} ta safar", reply_markup=main_menu())
    for t in trips:
        kb = InlineKeyboardBuilder()
        kb.button(text="🙋 So‘rov yuborish", callback_data=f"req:{t['id']}:{pax}")
        kb.button(text="📞 Haydovchi bilan bog‘lanish", callback_data=f"contact:{t['id']}")
        if t["locations"]:
            kb.button(text="🗺 Xaritada ko‘rish", callback_data=f"loc:{t['id']}")
        kb.adjust(1)
        await cb.message.answer(trip_card(t), reply_markup=kb.as_markup())


def consent_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Roziman", callback_data="consent")
    kb.button(text="Bekor qilish", callback_data="cancel")
    return kb.as_markup()


CONSENT_TEXT = "Haydovchi bilan bog‘lanish uchun ismingiz va Telegram profilingiz haydovchiga ko‘rinishiga rozimisiz?"


@router.callback_query(F.data == "consent")
async def consent(cb: CallbackQuery):
    uid = await me(cb)
    code, _ = await api.call("PATCH", "/me", uid, json={"contact_consent": True})
    await cb.answer("Rahmat!" if code == 200 else "Xatolik")
    await cb.message.answer("Rozilik qabul qilindi. Endi qaytadan “So‘rov yuborish” yoki “Bog‘lanish” tugmasini bosing.")


@router.callback_query(F.data.startswith("req:"))
async def req_trip(cb: CallbackQuery):
    _, tid, pax = cb.data.split(":")
    uid = await me(cb)
    code, data = await api.call("POST", f"/trips/{tid}/requests", uid, json={"seats": int(pax)})
    await cb.answer()
    if code == 403:
        return await cb.message.answer(CONSENT_TEXT, reply_markup=consent_kb())
    await cb.message.answer("✅ So‘rov haydovchiga yuborildi. Javob kelganda xabar beramiz." if code == 201 else f"⚠️ {api.error_text(data)}")


@router.callback_query(F.data.startswith("contact:"))
async def contact(cb: CallbackQuery):
    uid = await me(cb)
    code, data = await api.call("GET", f"/trips/{cb.data.split(':')[1]}/contact", uid)
    await cb.answer()
    if code == 403:
        return await cb.message.answer(CONSENT_TEXT, reply_markup=consent_kb())
    if code != 200:
        return await cb.message.answer(f"⚠️ {api.error_text(data)}")
    lines = []
    if data["telegram"]:
        lines.append(f"✈️ Telegram: {data['telegram']}")
    if data["phone"]:
        lines.append(f"📞 Telefon: {esc(data['phone'])}")
    await cb.message.answer("\n".join(lines) or "Haydovchi kontaktlarini ochmagan. “So‘rov yuborish” tugmasidan foydalaning.")


@router.callback_query(F.data.startswith("loc:"))
async def show_loc(cb: CallbackQuery):
    await cb.answer()
    code, t = await api.call("GET", f"/trips/{cb.data.split(':')[1]}")
    if code != 200:
        return await cb.message.answer(f"⚠️ {api.error_text(t)}")
    names = {"pickup": "Jo‘nash joyi", "meeting": "Uchrashuv nuqtasi", "dropoff": "Tushirish nuqtasi"}
    for l in t["locations"]:
        await cb.message.answer(f"📍 {names[l['kind']]}" + (f": {esc(l['address'])}" if l["address"] else ""))
        await cb.message.answer_location(l["lat"], l["lon"])


@router.callback_query(F.data == "fav")
async def add_fav(cb: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    uid = await me(cb)
    code, _ = await api.call("POST", "/favorites", uid, json={"from_region": d.get("frm"), "to_region": d.get("to")})
    await cb.answer("Saqlandi ⭐" if code == 201 else "Xatolik", show_alert=code != 201)


@router.callback_query(F.data == "demand")
async def demand(cb: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    uid = await me(cb)
    body = {"from_region": d.get("frm"), "to_region": d.get("to"), "seats": d.get("pax", 1)}
    if d.get("date"):
        body["wanted_date"] = d["date"] + "T00:00:00"
    code, data = await api.call("POST", "/demands", uid, json=body)
    await cb.answer()
    if code == 403:
        return await cb.message.answer(CONSENT_TEXT, reply_markup=consent_kb())
    await cb.message.answer(f"✅ Talab saqlandi. {data['drivers_notified']} ta haydovchiga xabar yuborildi." if code == 201 else f"⚠️ {api.error_text(data)}")


@router.message(F.text == M_FAV)
async def favorites(m: Message):
    uid = await me(m)
    code, favs = await api.call("GET", "/favorites", uid)
    if code != 200 or not favs:
        return await m.answer("Sevimli yo‘nalishlar yo‘q. Qidiruvdan keyin “⭐ Sevimlilarga” tugmasini bosing.")
    await m.answer("⭐ <b>Sevimli yo‘nalishlar</b>\n" + "\n".join(f"• {esc(REGIONS[f['from_region']])} → {esc(REGIONS[f['to_region']])}" for f in favs))


# ---------- HAYDOVCHI BO'LISH ----------
@router.message(F.text == M_BECOME)
async def become(m: Message, state: FSMContext):
    await state.clear()
    uid = await me(m)
    code, _ = await api.call("GET", "/drivers/me", uid)
    if code == 200:
        return await m.answer("Siz allaqachon haydovchisiz. “➕ Safar joylash” tugmasidan foydalaning.")
    await state.set_state(Become.phone)
    await m.answer("Haydovchi sifatida ro‘yxatdan o‘tamiz. Avval telefon raqamingizni yuboring (tugma orqali — raqam tasdiqlanadi):", reply_markup=contact_request_kb())


@router.message(Become.phone, F.contact)
async def become_phone(m: Message, state: FSMContext):
    c = m.contact
    if c.user_id != m.from_user.id:
        return await m.answer("Faqat o‘zingizning raqamingizni yuboring.")
    phone = "+" + c.phone_number.lstrip("+")
    if not UZ_PHONE.match(phone):
        return await m.answer("Platforma faqat O‘zbekiston raqamlari (+998...) bilan ishlaydi.")
    uid = await me(m)
    async with SessionLocal() as db:
        u = await db.get(User, uid)
        u.phone, u.phone_verified = phone, True
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            return await m.answer("Bu raqam boshqa akkauntga bog‘langan.")
    await state.set_state(Become.model)
    await m.answer("Avtomobil rusumi va modeli? (masalan: Chevrolet Malibu)", reply_markup=main_menu())


@router.message(Become.model, F.text, NOT_MENU)
async def become_model(m: Message, state: FSMContext):
    if not 2 <= len(m.text) <= 80:
        return await m.answer("2–80 belgi kiriting.")
    await state.update_data(model=m.text.strip())
    await state.set_state(Become.plate)
    await m.answer("Davlat raqami? (masalan: 01A123BC)")


@router.message(Become.plate, F.text, NOT_MENU)
async def become_plate(m: Message, state: FSMContext):
    plate = "".join(m.text.upper().split())
    if not re.fullmatch(r"[0-9A-Z]{4,12}", plate):
        return await m.answer("Raqam noto‘g‘ri. Masalan: 01A123BC")
    await state.update_data(plate=plate)
    await state.set_state(Become.seats)
    await m.answer("Avtomobilda jami nechta o‘rindiq bor (haydovchi bilan)? 2–8")


@router.message(Become.seats, F.text, NOT_MENU)
async def become_seats(m: Message, state: FSMContext):
    if not (m.text.isdigit() and 2 <= int(m.text) <= 8):
        return await m.answer("2 dan 8 gacha son kiriting.")
    d = await state.get_data()
    uid = await me(m)
    code, data = await api.call("POST", "/drivers/register", uid, json={
        "full_name": m.from_user.full_name, "make_model": d["model"], "plate": d["plate"], "seats": int(m.text)})
    await state.clear()
    if code != 201:
        return await m.answer(f"⚠️ {api.error_text(data)}", reply_markup=main_menu())
    left = data["subscription"]["days_left"]
    await m.answer(f"✅ Ro‘yxatdan o‘tdingiz! Bepul sinov muddati: {left} kun. Endi “➕ Safar joylash” tugmasini bosing.", reply_markup=main_menu())


# ---------- SAFAR JOYLASH ----------
async def post_from_r(t, s):
    await s.set_state(Post.from_r); await t.answer("Qayerdan jo‘naysiz?", reply_markup=regions_kb("p1"))


async def post_from_c(t, s):
    d = await s.get_data(); await s.set_state(Post.from_c)
    await t.answer("Jo‘nash shahri/tumani?", reply_markup=cities_kb("p2", d["frm"], "pb:from_r", "Ko‘rsatmayman"))


async def post_to_r(t, s):
    await s.set_state(Post.to_r); await t.answer("Qayerga borasiz?", reply_markup=regions_kb("p3", "pb:from_c"))


async def post_to_c(t, s):
    d = await s.get_data(); await s.set_state(Post.to_c)
    await t.answer("Boriladigan shahar/tuman?", reply_markup=cities_kb("p4", d["to"], "pb:to_r", "Ko‘rsatmayman"))


async def post_pickup(t, s):
    await s.set_state(Post.pickup)
    await t.answer("📍 Jo‘nash lokatsiyasini yuboring (📎 → Lokatsiya) yoki o‘tkazib yuboring.", reply_markup=skip_kb("skip:pickup", "pb:to_c"))
    await t.answer("Joriy joyingizda bo‘lsangiz, tugmadan foydalaning:", reply_markup=location_request_kb())


async def post_dropoff(t, s):
    await s.set_state(Post.dropoff)
    await t.answer("📍 Boriladigan manzil lokatsiyasini yuboring yoki o‘tkazib yuboring.", reply_markup=skip_kb("skip:dropoff", "pb:pickup"))


async def post_date(t, s):
    await s.set_state(Post.date); await t.answer("Jo‘nash sanasi?", reply_markup=dates_kb("p5", "pb:dropoff", False))


async def post_time(t, s):
    await s.set_state(Post.time); await t.answer("Jo‘nash vaqtini yozing (SS:DD), masalan 14:30. Toshkent vaqti.")


async def post_seats(t, s):
    d = await s.get_data(); await s.set_state(Post.seats)
    await t.answer("Nechta bo‘sh o‘rin?", reply_markup=number_kb("p6", range(1, min(d["max_seats"], 8) + 1), "pb:date"))


async def post_price(t, s):
    await s.set_state(Post.price); await t.answer("Bir yo‘lovchi uchun narxni so‘mda yozing (masalan 120000). Narxni o‘zingiz belgilaysiz.")


POST_STEPS = {"from_r": post_from_r, "from_c": post_from_c, "to_r": post_to_r, "to_c": post_to_c,
              "pickup": post_pickup, "dropoff": post_dropoff, "date": post_date}


@router.message(F.text == M_POST)
async def post_start(m: Message, state: FSMContext):
    await state.clear()
    uid = await me(m)
    code, drv = await api.call("GET", "/drivers/me", uid)
    if code != 200:
        return await m.answer("Avval “🚗 Haydovchi bo‘lish” orqali ro‘yxatdan o‘ting.")
    if not drv["subscription"]["active"]:
        return await m.answer("Faol obunangiz yo‘q, shuning uchun yangi safar e’lon qila olmaysiz. “💳 Obuna” bo‘limidan tarif tanlang. Avvalgi safarlaringiz saqlanadi.")
    await state.update_data(max_seats=drv["vehicles"][0]["seats"] - 1, key=uuid.uuid4().hex)
    await post_from_r(m, state)


@router.callback_query(F.data.startswith("pb:"))
async def post_back(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await POST_STEPS[cb.data.split(":")[1]](cb.message, state)


@router.callback_query(Post.from_r, F.data.startswith("p1:"))
async def p1(cb: CallbackQuery, state: FSMContext):
    await cb.answer(); await state.update_data(frm=cb.data.split(":")[1]); await post_from_c(cb.message, state)


@router.callback_query(Post.from_c, F.data.startswith("p2:"))
async def p2(cb: CallbackQuery, state: FSMContext):
    await cb.answer(); v = cb.data.split(":")[1]; d = await state.get_data()
    await state.update_data(frm_city=None if v == "-" else CITIES[d["frm"]][int(v)]); await post_to_r(cb.message, state)


@router.callback_query(Post.to_r, F.data.startswith("p3:"))
async def p3(cb: CallbackQuery, state: FSMContext):
    await cb.answer(); await state.update_data(to=cb.data.split(":")[1]); await post_to_c(cb.message, state)


@router.callback_query(Post.to_c, F.data.startswith("p4:"))
async def p4(cb: CallbackQuery, state: FSMContext):
    await cb.answer(); v = cb.data.split(":")[1]; d = await state.get_data()
    await state.update_data(to_city=None if v == "-" else CITIES[d["to"]][int(v)]); await post_pickup(cb.message, state)


@router.message(Post.pickup, F.location)
async def got_pickup(m: Message, state: FSMContext):
    await state.update_data(pickup={"lat": m.location.latitude, "lon": m.location.longitude})
    await m.answer("Qabul qilindi ✅", reply_markup=main_menu()); await post_dropoff(m, state)


@router.message(Post.dropoff, F.location)
async def got_dropoff(m: Message, state: FSMContext):
    await state.update_data(dropoff={"lat": m.location.latitude, "lon": m.location.longitude}); await post_date(m, state)


@router.callback_query(F.data == "skip:pickup", Post.pickup)
async def skip_pickup(cb: CallbackQuery, state: FSMContext):
    await cb.answer(); await post_dropoff(cb.message, state)


@router.callback_query(F.data == "skip:dropoff", Post.dropoff)
async def skip_dropoff(cb: CallbackQuery, state: FSMContext):
    await cb.answer(); await post_date(cb.message, state)


@router.callback_query(Post.date, F.data.startswith("p5:"))
async def p5(cb: CallbackQuery, state: FSMContext):
    await cb.answer(); await state.update_data(date=cb.data.split(":", 1)[1]); await post_time(cb.message, state)


@router.message(Post.time, F.text, NOT_MENU)
async def p_time(m: Message, state: FSMContext):
    if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", m.text.strip()):
        return await m.answer("Vaqt formati noto‘g‘ri. Masalan: 14:30")
    await state.update_data(time=m.text.strip().zfill(5)); await post_seats(m, state)


@router.callback_query(Post.seats, F.data.startswith("p6:"))
async def p6(cb: CallbackQuery, state: FSMContext):
    await cb.answer(); await state.update_data(seats=int(cb.data.split(":")[1])); await post_price(cb.message, state)


@router.message(Post.price, F.text, NOT_MENU)
async def p_price(m: Message, state: FSMContext):
    digits = re.sub(r"[\s,.]", "", m.text)
    if not (digits.isdigit() and 1000 <= int(digits) <= 50_000_000):
        return await m.answer("Narx 1 000 dan 50 000 000 so‘mgacha bo‘lgan son bo‘lsin.")
    await state.update_data(price=int(digits)); d = await state.get_data()
    await state.set_state(Post.confirm)
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Safarni e’lon qilish", callback_data="post_ok")
    kb.button(text="⬅️ Boshidan", callback_data="pb:from_r"); kb.button(text="🏠 Bekor qilish", callback_data="cancel")
    kb.adjust(1, 2)
    await m.answer(
        "<b>Tekshiring:</b>\n"
        f"📍 {place(d['frm'], d.get('frm_city'))} → {place(d['to'], d.get('to_city'))}\n"
        f"🕒 {esc(d['date'])} {esc(d['time'])}\n💺 {d['seats']} o‘rin\n💰 {money(d['price'])}\n"
        f"🗺 Lokatsiya: {'jo‘nash ' if d.get('pickup') else ''}{'manzil' if d.get('dropoff') else ''}{'' if d.get('pickup') or d.get('dropoff') else 'ko‘rsatilmagan'}",
        reply_markup=kb.as_markup())


@router.callback_query(Post.confirm, F.data == "post_ok")
async def post_ok(cb: CallbackQuery, state: FSMContext):
    d = await state.get_data(); uid = await me(cb)
    body = {"from_region": d["frm"], "from_city": d.get("frm_city"), "to_region": d["to"], "to_city": d.get("to_city"),
            "depart_at": f"{d['date']}T{d['time']}:00", "seats_total": d["seats"], "price_uzs": d["price"],
            "pickup": d.get("pickup"), "dropoff": d.get("dropoff")}
    code, data = await api.call("POST", "/trips", uid, json=body, headers={"Idempotency-Key": d["key"]})  # qayta bosishdan himoya
    await cb.answer()
    if code != 201:
        return await cb.message.answer(f"⚠️ {api.error_text(data)}", reply_markup=main_menu())
    await state.clear()
    await cb.message.answer(f"✅ Safar e’lon qilindi. Identifikator: <b>#{data[0]['id']}</b>", reply_markup=main_menu())


# ---------- LOKATSIYA ----------
@router.message(F.text == M_LOC)
async def loc_menu(m: Message, state: FSMContext):
    await state.set_state(Loc.wait)
    await m.answer("Joriy lokatsiyangizni yuboring:", reply_markup=location_request_kb())


@router.message(Loc.wait, F.location)
async def loc_got(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("Lokatsiya qabul qilindi. Safar joylashda 📎 → Lokatsiya orqali jo‘nash nuqtasini belgilang.", reply_markup=main_menu())


# ---------- SAFARLARIM / PROFIL / OBUNA ----------
@router.message(F.text == M_MY)
async def my_trips(m: Message):
    uid = await me(m)
    code, trips = await api.call("GET", "/trips/mine", uid)
    if code == 200:  # haydovchi
        await m.answer(f"🚗 <b>Mening safarlarim</b> ({len(trips)})")
        for t in trips[:10]:
            kb = InlineKeyboardBuilder()
            if t["status"] == "active":
                kb.button(text="❌ Bekor qilish", callback_data=f"tcancel:{t['id']}")
            await m.answer(f"#{t['id']} · {esc(t['status'])}\n" + trip_card(t), reply_markup=kb.as_markup())
        _, reqs = await api.call("GET", "/drivers/me/requests", uid)
        for r in [r for r in reqs if r["status"] == "pending"][:10]:
            kb = InlineKeyboardBuilder()
            kb.button(text="✅ Qabul", callback_data=f"rd:{r['id']}:accepted"); kb.button(text="✖️ Rad", callback_data=f"rd:{r['id']}:rejected")
            await m.answer(f"🙋 Safar #{r['trip_id']}: {esc(r['passenger'])}, {r['seats']} o‘rin", reply_markup=kb.as_markup())
    code, reqs = await api.call("GET", "/me/requests", uid)
    if code == 200 and reqs:
        names = {"pending": "kutilmoqda", "accepted": "qabul qilindi", "rejected": "rad etildi", "cancelled": "bekor", "open": "talab ochiq"}
        await m.answer("🧳 <b>Mening so‘rovlarim</b>\n" + "\n".join(f"• #{r['trip_id'] or 'talab'} — {names.get(r['status'], r['status'])}" for r in reqs[:15]))
    elif code == 200 and not trips:
        await m.answer("Hozircha safarlar yo‘q.")


@router.callback_query(F.data.startswith("tcancel:"))
async def tcancel(cb: CallbackQuery):
    uid = await me(cb)
    code, data = await api.call("DELETE", f"/trips/{cb.data.split(':')[1]}", uid)
    await cb.answer("Bekor qilindi" if code == 200 else api.error_text(data), show_alert=code != 200)


@router.callback_query(F.data.startswith("rd:"))
async def decide(cb: CallbackQuery):
    _, rid, st = cb.data.split(":")
    uid = await me(cb)
    code, data = await api.call("PATCH", f"/requests/{rid}", uid, json={"status": st})
    await cb.answer("Bajarildi" if code == 200 else api.error_text(data), show_alert=code != 200)


@router.message(F.text == M_PROFILE)
async def profile(m: Message):
    uid = await me(m)
    code, p = await api.call("GET", "/me", uid)
    if code != 200:
        return await m.answer(api.error_text(p))
    txt = [f"👤 <b>{esc(p['full_name'])}</b>", f"📱 Telefon: {'tasdiqlangan ✅' if p['phone_verified'] else 'kiritilmagan'}",
           f"🤝 Aloqa roziligi: {'bor' if p['contact_consent'] else 'yo‘q'}"]
    if p["is_driver"]:
        txt.append(f"🚗 Haydovchi: {esc(p['driver_verification'])}")
    await m.answer("\n".join(txt))


@router.message(F.text == M_SUB)
async def subscription(m: Message):
    uid = await me(m)
    code, d = await api.call("GET", "/drivers/me", uid)
    if code != 200:
        return await m.answer("Obuna faqat haydovchilar uchun. Yo‘lovchilar uchun xizmat bepul.")
    s = d["subscription"]
    head = (f"{'Bepul sinov' if s['kind'] == 'trial' else 'Pullik obuna'}: {fmt_dt(s['ends_at'])} gacha ({s['days_left']} kun)"
            if s["active"] else "❗ Faol obuna yo‘q. Yangi safar e’lon qilish uchun tarif tanlang.")
    _, plans = await api.call("GET", "/plans")
    kb = InlineKeyboardBuilder()
    for p in plans or []:
        kb.button(text=f"{p['name']} — {money(p['price_uzs'])}", callback_data=f"pay:{p['id']}")
    kb.adjust(1)
    await m.answer(f"💳 <b>Obuna</b>\n{head}" + ("" if plans else "\n\nTariflar hali belgilanmagan."), reply_markup=kb.as_markup() if plans else None)


@router.callback_query(F.data.startswith("pay:"))
async def pay(cb: CallbackQuery):
    uid = await me(cb)
    code, data = await api.call("POST", "/payments", uid, json={"plan_id": int(cb.data.split(":")[1])})
    await cb.answer()
    if code != 201:
        return await cb.message.answer(f"⚠️ {api.error_text(data)}")
    kb = InlineKeyboardBuilder(); kb.button(text="💳 To‘lash", url=data["pay_url"])
    await cb.message.answer(f"To‘lov summasi: {money(data['amount_uzs'])}. To‘lov provayder tomonidan tasdiqlangach obuna avtomatik faollashadi.", reply_markup=kb.as_markup())
