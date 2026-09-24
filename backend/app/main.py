"""FastAPI エントリーポイント。"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory, init_db
from app.core.security import hash_password
from app.models.models import (
    BotStation,
    Message,
    Program,
    Reservation,
    Station,
    User,
)
from app.routers import (
    archives,
    auth,
    bot,
    dedicated,
    frequencies,
    lineworks,
    me,
    programs,
    stations,
    threads,
    ws,
)
from app.routers.frequencies import broadcast_frequency_status
from app.services.ai_dj import generate_dj_line
from app.services.bot_dj import play_limit_seconds, play_next
from app.services.sessions import close_session, open_session
from app.services.websocket_manager import manager

# 管理者アカウント（初期シード）。値は .env で設定する（既定は開発用のダミー）。
_ADMIN_USERNAME = settings.admin_username
_ADMIN_EMAIL = settings.admin_email
_ADMIN_PASSWORD = settings.admin_password

# 自動DJ局（プリセット局）。選曲ソースは services/bot_dj.BOT_SOURCES が callsign で判定する。
_BOT_PRESETS = [
    {
        "name": "DJ BOT",
        "frequency": 84.0,
        "description": "人気曲をランダムに流し続ける24時間営業の自動DJ局。",
        "prompt": "常時オンエアでランダムに選曲し続ける、24時間営業の自動DJ。",
    },
    {
        "name": "Vocaloid BOT",
        "frequency": 85.0,
        "description": "ボカロ曲をランダムに流し続ける自動DJ局。",
        "prompt": "ボカロ好きのための自動DJ。",
    },
]

# 初期投入する公式ステーション（開局者: admin）
_SEED_STATIONS = [
    (80.0, "Midair.io 開局周波数", "すべてのはじまり。深夜の挨拶はここから。"),
    (82.5, "リクエスト天国", "君の一曲、ここで流す。どんどん投げて。"),
    (86.0, "語り部の部屋", "怪談、体験談、眠れない話。夜は長い。"),
    (88.9, "Midair.io 最終便", "終電のあと、一番星まで。最終周波数。"),
]

# AIチャットbot常駐局（プリセット）。ai_dj_enabled + キャラ設定で、話しかけると返信する。
_AI_CHAT_PRESETS = [
    {
        "name": "Miaちゃん",
        "frequency": 88.0,
        "description": "オタク天使のAIチャットbot「Miaちゃん」が常駐する局。話しかけると返してくれます。",
        "prompt": (
            "あなたは「Miaちゃん」という名前の、オタクな天使です。"
            "アニメ・ゲーム・声優・ボカロ・深夜ラジオが大好きで、推しの話になると止まりません。"
            "明るくて優しく、ふわっとした口調。「〜だよっ」「めっちゃ」「それな〜」"
            "「えらいえらい！」などのやわらかい言葉を使い、絵文字や顔文字を少し混ぜます。"
            "リスナーは「フォロワーちゃん」と呼びます。返信は1〜2文で短く。"
        ),
    },
]


async def _seed() -> None:
    """admin ユーザーと公式ステーションを初期投入する。"""
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.username == _ADMIN_USERNAME))
        admin = result.scalars().first()
        if admin is None:
            admin = User(
                username=_ADMIN_USERNAME,
                email=_ADMIN_EMAIL,
                password_hash=hash_password(_ADMIN_PASSWORD),
                role="admin",
            )
            session.add(admin)
            await session.commit()
            await session.refresh(admin)

        station_result = await session.execute(select(Station.id))
        if station_result.first() is None:
            created = []
            for freq, name, desc in _SEED_STATIONS:
                st = Station(
                    owner_id=admin.id,
                    frequency=freq,
                    callsign=name,
                    description=desc,
                    status="live",
                )
                session.add(st)
                created.append(st)
            await session.commit()
            # 公式局は最初から放送中なので、放送セッションも自動で開いておく
            for st in created:
                await open_session(session, st, title=f"{st.callsign} 放送")

        # 自動DJ局（DJ BOT / Vocaloid BOT）を用意する
        await _ensure_bot_stations(session, admin)
        # AIチャットbot常駐局（Miaちゃん）を用意する
        await _ensure_ai_chat_stations(session, admin)


async def _ensure_ai_chat_stations(session, admin: User) -> None:
    """AIチャットbotが常駐するプリセット局を用意する。"""
    for preset in _AI_CHAT_PRESETS:
        station = (
            await session.execute(
                select(Station).where(Station.callsign == preset["name"])
            )
        ).scalars().first()
        if station is not None:
            continue
        used = {
            round(float(f), 1)
            for f in (await session.execute(select(Station.frequency))).scalars().all()
        }
        freq = round(float(preset["frequency"]), 1)
        while freq in used and freq <= settings.station_freq_max + 1e-9:
            freq = round(freq + 0.1, 1)
        station = Station(
            owner_id=admin.id,
            frequency=freq,
            callsign=preset["name"],
            description=preset["description"],
            status="live",
            ai_dj_enabled=True,
            ai_dj_prompt=preset["prompt"],
        )
        session.add(station)
        await session.commit()
        await session.refresh(station)
        await open_session(session, station, title=f"{preset['name']} 放送")


async def _ensure_bot_stations(session, admin: User) -> None:
    """常時オンエアの自動DJ局（プリセット）を用意する。"""
    for preset in _BOT_PRESETS:
        station = (
            await session.execute(
                select(Station).where(Station.callsign == preset["name"])
            )
        ).scalars().first()

        used = {
            round(float(f), 1)
            for f in (await session.execute(select(Station.frequency))).scalars().all()
        }
        # 既定レンジ外になった既存の自動DJ局は、範囲内の空き周波数へ移す
        if (
            station is not None
            and (
                station.frequency < settings.station_freq_min
                or station.frequency > settings.station_freq_max
            )
        ):
            hint = round(float(preset["frequency"]), 1)
            if hint < settings.station_freq_min or hint > settings.station_freq_max:
                hint = round(settings.station_freq_max, 1)
            while hint in used and hint <= settings.station_freq_max + 1e-9:
                hint = round(hint + 0.1, 1)
            used.discard(round(float(station.frequency), 1))
            station.frequency = hint
            await session.commit()

        if station is None:
            freq = round(float(preset["frequency"]), 1)
            if freq < settings.station_freq_min or freq > settings.station_freq_max:
                freq = round(settings.station_freq_max, 1)
            while freq in used and freq <= settings.station_freq_max + 1e-9:
                freq = round(freq + 0.1, 1)
            station = Station(
                owner_id=admin.id,
                frequency=freq,
                callsign=preset["name"],
                description=preset["description"],
                status="live",
                ai_dj_enabled=True,
                ai_dj_prompt=preset["prompt"],
            )
            session.add(station)
            await session.commit()
            await session.refresh(station)
            await open_session(session, station, title=f"{preset['name']} 放送")

        # 自動DJ設定（未登録なら作る）
        if await session.get(BotStation, station.id) is None:
            session.add(
                BotStation(
                    station_id=station.id,
                    interval_seconds=settings.dj_bot_interval_seconds,
                )
            )
            await session.commit()


async def _dj_bot_loop() -> None:
    """自動DJ局が一定間隔でランダムに次の曲をオンエアし続ける。"""
    await asyncio.sleep(6)
    while True:
        await asyncio.sleep(5)
        if not settings.dj_bot_enabled:
            continue
        async with async_session_factory() as session:
            bots = (await session.execute(select(BotStation))).scalars().all()
            for bot in bots:
                station = await session.get(Station, bot.station_id)
                if station is None:
                    continue

                # 自動DJ局は常時オンエアを維持する
                if station.status != "live":
                    station.set_status("live")
                    await session.commit()
                    await open_session(session, station, title=f"{station.callsign} 放送")
                    await broadcast_frequency_status(station.frequency, "live", station.id)
                    await manager.broadcast(
                        station.id,
                        {"type": "live_update", "is_live": True, "status": "live"},
                    )

                now = datetime.now()
                elapsed = None
                if station.playback_started_at:
                    elapsed = (now - station.playback_started_at).total_seconds()
                # 曲の長さぶん再生（長すぎる曲は最大 dj_bot_max_seconds でスキップ）
                limit = await play_limit_seconds(station.current_youtube_id)
                if (
                    station.current_youtube_id
                    and elapsed is not None
                    and elapsed < limit
                ):
                    continue

                # 人気曲（YouTube mostPopular）からランダムに次の1曲をオンエア
                await play_next(session, station)


async def _dj_loop() -> None:
    """会話が途切れたステーションにDJが自動で話しかける。"""
    await asyncio.sleep(5)
    while True:
        await asyncio.sleep(10)
        if not settings.dj_enabled:
            continue
        for station_id in manager.active_channels():
            if manager.idle_seconds(station_id) < settings.dj_idle_seconds:
                continue
            async with async_session_factory() as session:
                station = await session.get(Station, station_id)
                if station is None or not station.ai_dj_enabled:
                    manager.touch(station_id)
                    continue
                # LINE WORKS 連携局（Miaちゃん）は idle DJ を行わない
                if station.callsign == settings.lineworks_station_callsign:
                    manager.touch(station_id)
                    continue
                program = station.callsign
                persona = station.ai_dj_prompt
            line = await generate_dj_line(program, persona=persona)
            if not line:
                # LLM未設定・失敗時は何も投稿しない（定型文は使わない）
                manager.touch(station_id)
                continue
            async with async_session_factory() as session:
                msg = Message(
                    station_id=station_id,
                    sender_name="DJ",
                    content=line,
                    is_dj=True,
                )
                session.add(msg)
                await session.commit()
                await session.refresh(msg)
                payload = msg.to_dict()
            await manager.broadcast(station_id, {"type": "message", **payload})
            manager.touch(station_id)


async def _lifecycle_loop() -> None:
    """予約枠の開始/終了に応じてステーションを自動で ON AIR / OFF AIR させる。"""
    await asyncio.sleep(3)
    while True:
        await asyncio.sleep(15)
        now = datetime.now()
        async with async_session_factory() as session:
            started = (
                await session.execute(
                    select(Station).where(
                        Station.status == "reserved",
                        Station.scheduled_start.isnot(None),
                        Station.scheduled_start <= now,
                    )
                )
            ).scalars().all()
            for s in started:
                s.set_status("live")
                await broadcast_frequency_status(s.frequency, "live", s.id)

            ended = (
                await session.execute(
                    select(Station).where(
                        Station.status == "live",
                        Station.scheduled_end.isnot(None),
                        Station.scheduled_end <= now,
                    )
                )
            ).scalars().all()
            for s in ended:
                s.set_status("off_air")
                await broadcast_frequency_status(s.frequency, "off_air", s.id)

            expired = (
                await session.execute(
                    select(Reservation).where(
                        Reservation.status == "active", Reservation.end_time <= now
                    )
                )
            ).scalars().all()
            for r in expired:
                r.status = "expired"
                await broadcast_frequency_status(r.frequency, "empty", None)

            # 番組枠の自動オンエア（タイムテーブル連動）
            program_changed = False
            active_programs = (
                await session.execute(
                    select(Program).where(
                        Program.start_time <= now, Program.end_time > now
                    )
                )
            ).scalars().all()
            for p in active_programs:
                st = await session.get(Station, p.station_id)
                if st is not None and st.status != "live":
                    st.set_status("live")
                    if p.default_youtube_id:
                        st.current_youtube_id = p.default_youtube_id
                        st.playback_started_at = now
                    # 番組開始でも放送セッションを自動記録
                    await open_session(session, st, title=p.title)
                    await broadcast_frequency_status(st.frequency, "live", st.id)
                    if p.default_youtube_id:
                        await manager.broadcast(
                            st.id,
                            {
                                "type": "track_update",
                                "youtube_video_id": p.default_youtube_id,
                                "playback_started_at": now.isoformat(),
                            },
                        )
                    program_changed = True

            # 番組終了で停波（直近に終了した番組のみ・他に放送中が無い場合）
            finished_programs = (
                await session.execute(
                    select(Program).where(
                        Program.end_time <= now,
                        Program.end_time > now - timedelta(minutes=5),
                        Program.is_archived == False,
                    )
                )
            ).scalars().all()
            for p in finished_programs:
                p.is_archived = True
                program_changed = True
                other = (
                    await session.execute(
                        select(Program).where(
                            Program.station_id == p.station_id,
                            Program.start_time <= now,
                            Program.end_time > now,
                        )
                    )
                ).scalars().first()
                st = await session.get(Station, p.station_id)
                if (
                    other is None
                    and st is not None
                    and st.status == "live"
                    and st.scheduled_end is None
                ):
                    st.set_status("off_air")
                    await close_session(session, st.id)
                    await broadcast_frequency_status(st.frequency, "off_air", st.id)

            if started or ended or expired or program_changed:
                await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _seed()
    # 全ステーションに現在スレッドがあることを保証
    from app.core.database import async_session_factory as _asf
    from app.services.threads import ensure_all_stations

    async with _asf() as _session:
        await ensure_all_stations(_session)
    dj_task = asyncio.create_task(_dj_loop())
    life_task = asyncio.create_task(_lifecycle_loop())
    bot_task = asyncio.create_task(_dj_bot_loop())
    # 専用局の自律運行（APScheduler: 10秒間隔）
    scheduler = _start_dedicated_scheduler()
    yield
    if scheduler is not None:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass
    for task in (dj_task, life_task, bot_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def _start_dedicated_scheduler():
    """専用局の送出エンジンを APScheduler で定期実行する。"""
    if not settings.dedicated_engine_enabled:
        return None
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except Exception:
        return None

    async def _job():
        from app.core.database import async_session_factory
        from app.services.dedicated import check_and_advance

        async with async_session_factory() as session:
            try:
                await check_and_advance(session)
            except Exception:
                pass

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _job,
        "interval",
        seconds=max(3, settings.dedicated_engine_interval_seconds),
        id="dedicated_engine",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    return scheduler


app = FastAPI(title=settings.app_name, lifespan=lifespan, root_path=settings.root_path)

if settings.cors_origins.strip() == "*":
    _origins = ["*"]
    _allow_credentials = False
else:
    _origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    _allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(stations.router)
app.include_router(frequencies.router)
app.include_router(programs.router)
app.include_router(archives.router)
app.include_router(me.router)
app.include_router(bot.router)
app.include_router(dedicated.router)
app.include_router(threads.router)
app.include_router(lineworks.router)
app.include_router(ws.router)


@app.get("/")
async def root():
    return {"success": True, "name": settings.app_name, "message": "Midair.io API is running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/discord/ingest")
async def discord_ingest(request: Request):
    """Discord 側の Webhook 送信先。受け取った発言を対象ステーションへ流す。"""
    station_id = request.query_params.get("station_id")
    body = {}
    if request.headers.get("content-type", "").startswith("application/json"):
        body = await request.json()
    content = (body.get("content") or "").strip()
    username = (body.get("username") or "Discord").strip()[:50]
    if not content or not station_id:
        return {"success": False, "error": "content と station_id が必要です"}
    try:
        station_id = int(station_id)
    except (TypeError, ValueError):
        return {"success": False, "error": "station_id が不正です"}

    from app.routers.ws import _persist_message

    payload = await _persist_message(station_id, username, content[:500])
    await manager.broadcast(station_id, {"type": "message", **payload})
    manager.touch(station_id)
    return {"success": True}
