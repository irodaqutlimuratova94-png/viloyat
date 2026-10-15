"""Dastlabki sxema (16 jadval)

DIQQAT: bu migratsiya sxemani app.models metadatasidan quradi (create_all). U 0001 holatini
muzlatmaydi: modellar keyinroq o'zgarsa, yangi bazada 0001 allaqachon yangi sxemani yaratadi.
Production'dan oldin Postgres'ga ulangan holda `alembic revision --autogenerate` bilan
aniq (qo'lda yozilgan) 0001 ni qayta generatsiya qiling va ko'rib chiqing.
"""
from alembic import op

from app.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
