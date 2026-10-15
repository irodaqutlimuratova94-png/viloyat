"""Boshqaruv buyruqlari: python -m app.cli create-admin <login>  (parol so'raladi)"""
import asyncio
import getpass
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models import AdminUser
from app.security import hash_password


async def create_admin(username: str) -> None:
    pw = getpass.getpass("Parol (kamida 12 belgi): ")
    if len(pw) < 12:
        sys.exit("Parol juda qisqa")
    async with SessionLocal() as db:
        if (await db.execute(select(AdminUser).where(AdminUser.username == username))).scalar_one_or_none():
            sys.exit("Bunday admin mavjud")
        db.add(AdminUser(username=username, password_hash=hash_password(pw)))
        await db.commit()
    print("Admin yaratildi")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "create-admin":
        asyncio.run(create_admin(sys.argv[2]))
    else:
        sys.exit("Foydalanish: python -m app.cli create-admin <login>")
