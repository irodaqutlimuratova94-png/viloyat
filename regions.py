"""O'zbekistonning 14 ta ma'muriy hududi va asosiy shahar/tumanlar.

DIQQAT: shahar/tuman ro'yxati to'liq emas (asosiy shahar va markazlar). To'liq ro'yxatni
rasmiy ma'lumotnoma (SOATO/MHOBIT) asosida CITIES ga qo'shing; viloyat kodlari qat'iy tekshiriladi,
shahar nomi esa ro'yxatda bo'lmasa ham erkin matn sifatida qabul qilinadi.
"""
from datetime import timedelta, timezone

UZ_TZ = timezone(timedelta(hours=5))  # O'zbekistonda yozgi vaqt yo'q: UTC+5 doimiy

REGIONS: dict[str, str] = {
    "toshkent_shahri": "Toshkent shahri",
    "toshkent": "Toshkent viloyati",
    "samarqand": "Samarqand viloyati",
    "buxoro": "Buxoro viloyati",
    "andijon": "Andijon viloyati",
    "fargona": "Farg‘ona viloyati",
    "namangan": "Namangan viloyati",
    "qashqadaryo": "Qashqadaryo viloyati",
    "surxondaryo": "Surxondaryo viloyati",
    "jizzax": "Jizzax viloyati",
    "sirdaryo": "Sirdaryo viloyati",
    "navoiy": "Navoiy viloyati",
    "xorazm": "Xorazm viloyati",
    "qoraqalpogiston": "Qoraqalpog‘iston Respublikasi",
}

CITIES: dict[str, list[str]] = {
    "toshkent_shahri": ["Chilonzor", "Yunusobod", "Mirzo Ulug‘bek", "Sergeli", "Yakkasaroy", "Olmazor"],
    "toshkent": ["Nurafshon", "Chirchiq", "Olmaliq", "Angren", "Bekobod", "Yangiyo‘l"],
    "samarqand": ["Samarqand", "Kattaqo‘rg‘on", "Urgut", "Bulung‘ur", "Jomboy"],
    "buxoro": ["Buxoro", "Kogon", "G‘ijduvon", "Qorako‘l", "Vobkent"],
    "andijon": ["Andijon", "Asaka", "Shahrixon", "Xonobod", "Marhamat"],
    "fargona": ["Farg‘ona", "Marg‘ilon", "Qo‘qon", "Quva", "Rishton"],
    "namangan": ["Namangan", "Chust", "Pop", "Uychi", "Chortoq"],
    "qashqadaryo": ["Qarshi", "Shahrisabz", "Kitob", "G‘uzor", "Koson"],
    "surxondaryo": ["Termiz", "Denov", "Sherobod", "Boysun", "Sho‘rchi"],
    "jizzax": ["Jizzax", "G‘allaorol", "Do‘stlik", "Zomin", "Forish"],
    "sirdaryo": ["Guliston", "Sirdaryo", "Shirin", "Yangiyer", "Boyovut"],
    "navoiy": ["Navoiy", "Zarafshon", "Uchquduq", "Karmana", "Nurota"],
    "xorazm": ["Urganch", "Xiva", "Xonqa", "Shovot", "Hazorasp"],
    "qoraqalpogiston": ["Nukus", "Qo‘ng‘irot", "Mo‘ynoq", "To‘rtko‘l", "Xo‘jayli"],
}

# O'zbekiston chegarasini qamrovchi taxminiy to'rtburchak (aniq chegara emas, yuzaki filtr)
UZ_BBOX = (37.1, 45.7, 55.9, 73.2)  # min_lat, max_lat, min_lon, max_lon


def valid_region(code: str | None) -> bool:
    return code in REGIONS


def in_uzbekistan(lat: float, lon: float) -> bool:
    return UZ_BBOX[0] <= lat <= UZ_BBOX[1] and UZ_BBOX[2] <= lon <= UZ_BBOX[3]
