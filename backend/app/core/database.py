"""SQLAlchemy 非同期エンジン / セッション管理。

デフォルトは SQLite (aiosqlite)。.env の DATABASE_URL を書き換えると
MySQL (asyncmy) にも切り替えられる。
"""
from sqlalchemy import event
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

# SQLite は既定だと読み書きがぶつかる（ロールバックジャーナル）ため、負荷対策として
# WAL（読み書きの並行性が上がる）＋ busy_timeout を設定する。
if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA temp_store=MEMORY")
        finally:
            cursor.close()


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
            # 常時 ON AIR のプリセット局／DJの自動退出（後から追加）
            "always_on_air": "BOOLEAN DEFAULT 0",
            "dj_stay_minutes": "INTEGER",
        }
        for column, ddl in wanted.items():
            if column not in existing:
                conn.exec_driver_sql(f"ALTER TABLE stations ADD COLUMN {column} {ddl}")
        # 既存行の整合（常在局フラグは起動時のシードで設定される）

    # 負荷対策: 検索で使うインデックスを既存DBにも張る（新規テーブルは create_all が作成）
    indexes = {
        "programs": ("start_time", "end_time", "is_archived"),
        "reservations": ("end_time", "status"),
        "messages": ("created_at",),
    }
    for table, columns in indexes.items():
        if table not in tables:
            continue
        for column in columns:
            name = f"ix_{table}_{column}"
            try:
                conn.exec_driver_sql(
                    f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({column})"
                )
            except Exception:
                # 既に存在する・未対応の方言などは無視（起動を止めない）
                pass

    if "messages" in tables:
        existing = {c["name"] for c in inspector.get_columns("messages")}
        if "thread_id" not in existing:
            conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN thread_id INTEGER")
