# Viloyatga Boramiz

Viloyatlararo safar hamrohlarini topish xizmati: **FastAPI** backend + **Aiogram 3** bot + **Next.js** veb-sayt, yagona PostgreSQL bazasi.

> **Holat (halol hisobot):** kod yozilgan, lekin ishlab chiqilgan muhitda tarmoq yo‘q edi, shuning uchun
> Python/Node paketlari o‘rnatilmadi va **FastAPI, SQLAlchemy, aiogram va Next.js ishga tushirilmadi**.
> Quyidagi “Nima tekshirilgan” bo‘limiga qarang. Birinchi ishga tushirishda xatolar chiqishi mumkin.

## Tuzilma

```
backend/
  app/            FastAPI: models, routers (auth, drivers, trips, payments, admin, misc), services, security
  app/payments/   to'lov provayderi adapteri (hozir faqat "test")
  bot/            Aiogram 3 bot (FSM, inline tugmalar) + yetkazish/eslatma ishchilari
  alembic/        migratsiyalar
  tests/          pytest
frontend/         Next.js 15 + TypeScript + Tailwind (app router)
docker-compose.yml, .env.example
```

## Ishga tushirish (Docker)

```bash
cp .env.example .env        # JWT_SECRET, BOT_TOKEN, BOT_USERNAME, parollarni to'ldiring
docker compose up --build   # db, redis, api(:8000), bot, web(:3000)
docker compose exec api python -m app.cli create-admin <login>   # admin yaratish (parol so'raladi)
```

- Veb: http://localhost:3000 · Admin: `/admin` · API hujjatlari (dev): http://localhost:8000/docs
- Telegram bilan kirish uchun @BotFather → `/setdomain` ga veb-saytingiz domenini (https) kiriting. `localhost` da widget ishlamaydi: ngrok/domen kerak.
- Tarif narxlari **yo‘q**: admin panelida “Sozlamalar → Yangi tarif” orqali o‘zingiz kiriting.

## Testlar

```bash
cd backend && pip install -r requirements-dev.txt && pytest
```

## Nima tekshirilgan, nima yo‘q

| Qism | Holat |
|---|---|
| Obuna mantiqi (30 kun, 7/3/1 eslatma, obunani uzaytirish), JWT, parol xeshi, Telegram Login/Mini App imzosi, to'lov webhook imzosi, hududlar | **Ishga tushirib tekshirilgan** (toza Python, `backend/tests/test_logic.py` bilan bir xil tekshiruvlar) |
| Barcha `.py` fayllar | Sintaksis tekshirilgan (`py_compile`) |
| API endpointlar (`tests/test_api.py`, ~14 senariy) | **Yozilgan, ishga tushirilmagan** (fastapi/sqlalchemy/httpx o'rnatilmagan) |
| Bot | **Yozilgan, ishga tushirilmagan**; haqiqiy token bilan qo'lda sinash kerak |
| Frontend | **Yozilgan, `npm install`/`build`/`tsc` ishga tushirilmagan** |
| PostgreSQL, Docker | Sinalmagan |

## Ma'lum cheklovlar va keyingi qadamlar

1. **To‘lov provayderi ulanmagan.** `app/payments/base.py` da adapter interfeysi va HMAC-imzoli `test` provayder bor. Payme/Click/Uzum kabi provayderning *amaldagi* API hujjatiga qarab `PaymentProvider` vorisini yozing (invoice, imzo/auth, webhook formati). Webhook kodi: imzo → summa tekshiruvi → idempotent “paid” qaydi → obuna uzaytirish.
2. **Migratsiya** `0001` modellardan `create_all` qiladi. Production'dan oldin Postgres'da `alembic revision --autogenerate` bilan aniq migratsiya yarating.
3. **Telefon orqali kirish yo‘q:** SMS provayderi yo‘q. Kirish — Telegram; telefon raqam botda kontakt tugmasi orqali tasdiqlanadi (faqat o‘z raqami qabul qilinadi).
4. **Shahar/tuman ro‘yxati to‘liq emas** (`app/regions.py`): faqat asosiy shaharlar. To'liq ma'muriy ro'yxat bilan to'ldiring. Viloyat kodlari qat'iy tekshiriladi.
5. **Haydovchi hujjatlarini tekshirish** faqat `verification` holati (pending/verified/rejected) va admin tomonidan qo‘lda belgilash; hujjat yuklash yo‘q.
6. Bot hozir **long polling**; webhook rejimi yo‘q. `REDIS_URL` bo‘sh bo‘lsa FSM xotirada (restartda yo‘qoladi). Bot yetkazish sikli bitta nusxada ishlashi kerak.
7. Takroriy safar himoyasi: `Idempotency-Key` + tekshiruv; poyga holatida ikki parallel so‘rov bir xil safarni yaratishi nazariy mumkin (DB darajasida partial unique index qo‘shish tavsiya etiladi).
8. Veb: JWT `localStorage` da (XSS xavfi); production uchun httpOnly cookie ko‘rib chiqing. Reyting/shikoyat UI minimal. Telegram Mini App uchun asosiy kirish bor, alohida Mini App interfeysi yo‘q.
9. Haydovchi harakatini real vaqtda kuzatish — topshiriqqa ko‘ra kiritilmagan.
10. Ommaviy OSM tile-serveri og‘ir yuklama uchun emas: `NEXT_PUBLIC_TILE_URL` bilan o‘zgartiring. Xarita provayderi `frontend/lib/map/` da almashtiriladi.

## Xavfsizlik

- Sirlar faqat `.env` da; `JWT_SECRET` majburiy (bo'lmasa API ishga tushmaydi).
- Foydalanuvchi va admin tokenlari alohida (`typ` claim) — bir-birining o‘rnini bosmaydi; admin endpointlari `current_admin` bilan himoyalangan; har admin amali `audit_logs` ga yoziladi.
- Telefon raqamlari ommaviy ro‘yxatda yo‘q; kontakt faqat tizimga kirgan va rozilik bergan foydalanuvchiga beriladi.
- Pul — butun so‘m (`Integer`). To‘lov faqat imzosi tekshirilgan webhookdan keyin “paid”.
- Webhook imzosi sozlanmagan bo‘lsa (`PAYMENT_SECRET` bo‘sh) hech qanday webhook qabul qilinmaydi.

## Huquqiy eslatma

Shaxsiy ma'lumotlar (O‘zbekiston “Shaxsiy ma’lumotlar to‘g‘risida”gi qonuni, ma’lumotlarni mamlakat ichida saqlash talabi va h.k.) hamda to‘lov/litsenziya talablari bo‘yicha **yurist bilan maslahatlashing**: kod faqat texnik qismni qo‘llab-quvvatlaydi (rozilik bayrog‘i, kirish nazorati, audit).

## Monitoring

JSON emas, oddiy formatdagi loglar (`x-request-id` bilan so‘rov jurnali), `/api/health`, ixtiyoriy Sentry (`SENTRY_DSN`).
