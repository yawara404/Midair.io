"""SQLAlchemy 非同期エンジン / セッション管理。

デフォルトは SQLite (aiosqlite)。.env の DATABASE_URL を書き換えると
MySQL (asyncmy) にも切り替えられる。
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False, future=True)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db():
    """FastAPI 依存性注入用のセッションを yield する。"""
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """テーブルを作成する（存在しない場合のみ）＋ 既存DBへの簡易マイグレーション。"""
    from app.models.models import (  # noqa: F401
        BotStation,
        BroadcastQueue,
        BroadcastSession,
        DedicatedApplication,
        DedicatedTrackLibrary,
        Message,
        Program,
        Reservation,
        SessionTrack,
        Station,
        StationFavorite,
        Thread,
        User,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_sqlite)


def _migrate_sqlite(conn) -> None:
    """SQLite の既存テーブルに不足カラムを追加する（後方互換）。"""
    from sqlalchemy import inspect

    inspector = inspect(conn)
    tables = set(inspector.get_table_names())

    if "stations" in tables:
        existing = {c["name"] for c in inspector.get_columns("stations")}
        wanted = {
            "is_dedicated": "BOOLEAN DEFAULT 0",
            "dedicated_genre": "VARCHAR(50)",
            "track_duration_sec": "INTEGER DEFAULT 180",
        }
        for column, ddl in wanted.items():
            if column not in existing:
                conn.exec_driver_sql(f"ALTER TABLE stations ADD COLUMN {column} {ddl}")

    if "messages" in tables:
        existing = {c["name"] for c in inspector.get_columns("messages")}
        if "thread_id" not in existing:
            conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN thread_id INTEGER")
