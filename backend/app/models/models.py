"""DBモデル定義（ユーザー / ステーション / 番組 / メッセージ / お気に入り）。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    """リスナー / パーソナリティ / 管理者。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    discord_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # listener / broadcaster / admin
    role: Mapped[str] = mapped_column(String(20), default="listener")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "discord_id": self.discord_id,
            "avatar_url": self.avatar_url,
            "bio": self.bio,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Station(Base):
    """開局された放送局（周波数）。"""

    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    frequency: Mapped[float] = mapped_column(Float, unique=True, index=True)
    callsign: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text, default="")
    theme_color: Mapped[str] = mapped_column(String(10), default="#ffffff")
    current_youtube_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    playback_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_live: Mapped[bool] = mapped_column(Boolean, default=False)
    # 状態: reserved（予約/開局準備中） / live（放送中/ON AIR） / off_air（停波中）
    status: Mapped[str] = mapped_column(String(16), default="live")
    scheduled_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    scheduled_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ai_dj_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_dj_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # 専用局（24時間常設・申請承認制）用
    is_dedicated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    dedicated_genre: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    track_duration_sec: Mapped[int] = mapped_column(Integer, default=180)

    owner: Mapped["User"] = relationship("User", lazy="selectin")

    def set_status(self, status: str) -> None:
        """状態を設定し、互換用 is_live も同期する。"""
        self.status = status
        self.is_live = status == "live"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "owner_username": self.owner.username if self.owner else None,
            "frequency": self.frequency,
            "callsign": self.callsign,
            # フロント互換用のエイリアス
            "name": self.callsign,
            "description": self.description,
            "theme_color": self.theme_color,
            "current_youtube_id": self.current_youtube_id,
            "playback_started_at": (
                self.playback_started_at.isoformat()
                if self.playback_started_at
                else None
            ),
            "is_live": self.status == "live",
            "status": self.status,
            "scheduled_start": (
                self.scheduled_start.isoformat() if self.scheduled_start else None
            ),
            "scheduled_end": (
                self.scheduled_end.isoformat() if self.scheduled_end else None
            ),
            "ai_dj_enabled": self.ai_dj_enabled,
            "ai_dj_prompt": self.ai_dj_prompt,
            "is_dedicated": bool(self.is_dedicated),
            "dedicated_genre": self.dedicated_genre,
            "track_duration_sec": self.track_duration_sec,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Program(Base):
    """番組表（タイムテーブル）の番組枠。"""

    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    default_youtube_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    station: Mapped["Station"] = relationship("Station", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "station_id": self.station_id,
            "callsign": self.station.callsign if self.station else None,
            "frequency": self.station.frequency if self.station else None,
            "title": self.title,
            "description": self.description,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "default_youtube_id": self.default_youtube_id,
            "is_archived": self.is_archived,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Message(Base):
    """ステーション内のメッセージ（チャット / DJ / リクエスト）。"""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("broadcast_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # 2chライクなスレッド（掲示板のスレ）
    thread_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    sender_name: Mapped[str] = mapped_column(String(50), default="名無しのリスナー")
    content: Mapped[str] = mapped_column(Text, default="")
    offset_seconds: Mapped[int] = mapped_column(Integer, default=0)
    youtube_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_dj: Mapped[bool] = mapped_column(Boolean, default=False)
    is_broadcaster: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped[Optional["User"]] = relationship("User", lazy="selectin")

    def to_dict(self) -> dict:
        # フロント互換用のエイリアス（author / message_type）
        if self.is_dj:
            message_type = "dj"
        elif self.youtube_id:
            message_type = "youtube"
        else:
            message_type = "chat"
        return {
            "id": self.id,
            "station_id": self.station_id,
            "session_id": self.session_id,
            "thread_id": self.thread_id,
            "offset_seconds": self.offset_seconds,
            "user_id": self.user_id,
            "sender_name": self.sender_name,
            "author": self.sender_name,
            "content": self.content,
            "youtube_id": self.youtube_id,
            "is_dj": self.is_dj,
            "is_broadcaster": self.is_broadcaster,
            "message_type": message_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class StationFavorite(Base):
    """リスナーのお気に入り周波数。"""

    __tablename__ = "station_favorites"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class BroadcastSession(Base):
    """放送セッション（ON AIR〜OFF AIR の1区切りを自動記録）。

    番組予約の有無を問わず、ON AIR した瞬間に自動発行される。
    """

    __tablename__ = "broadcast_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )
    session_title: Mapped[str] = mapped_column(String(150), default="突発ゲリラ放送")
    program_reservation_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    peak_listeners: Mapped[int] = mapped_column(Integer, default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    station: Mapped["Station"] = relationship("Station", lazy="selectin")

    def to_dict(self) -> dict:
        duration = None
        if self.started_at:
            end = self.ended_at or datetime.now()
            duration = max(0, int((end - self.started_at).total_seconds()))
        return {
            "id": self.id,
            "station_id": self.station_id,
            "station_callsign": self.station.callsign if self.station else None,
            "frequency": self.station.frequency if self.station else None,
            "session_title": self.session_title,
            "program_reservation_id": self.program_reservation_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "is_live": self.ended_at is None,
            "total_messages": self.total_messages,
            "peak_listeners": self.peak_listeners,
            "duration_seconds": duration,
            "is_public": self.is_public,
        }


class SessionTrack(Base):
    """セッション中に流れた YouTube 曲の履歴（開始オフセット付き）。"""

    __tablename__ = "session_tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("broadcast_sessions.id", ondelete="CASCADE"), index=True
    )
    youtube_id: Mapped[str] = mapped_column(String(32))
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    started_offset_sec: Mapped[int] = mapped_column(Integer, default=0)
    played_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "youtube_id": self.youtube_id,
            "title": self.title,
            "started_offset_sec": self.started_offset_sec,
            "played_at": self.played_at.isoformat() if self.played_at else None,
        }


class Reservation(Base):
    """周波数の時間枠予約（放送前の枠取り / 開局準備中）。"""

    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    frequency: Mapped[float] = mapped_column(Float, index=True)
    callsign: Mapped[str] = mapped_column(String(50), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    # active / cancelled / expired
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped["User"] = relationship("User", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "frequency": self.frequency,
            "callsign": self.callsign,
            "note": self.note,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class BotStation(Base):
    """自動DJ局（DJ BOT）の設定。

    station_id を持つ局は「ランダムに曲を流し続ける」自動DJ対象になる。
    """

    __tablename__ = "bot_stations"

    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), primary_key=True
    )
    # 1曲を流し続ける秒数の目安（この時間が経過したら次の曲へ）
    interval_seconds: Mapped[int] = mapped_column(Integer, default=180)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def to_dict(self) -> dict:
        return {
            "station_id": self.station_id,
            "interval_seconds": self.interval_seconds,
        }


class DedicatedApplication(Base):
    """専用局（24時間常設）の開設申請。管理者の審査で承認/却下される。"""

    __tablename__ = "dedicated_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    desired_frequency: Mapped[float] = mapped_column(Float)
    callsign: Mapped[str] = mapped_column(String(50))
    station_title: Mapped[str] = mapped_column(String(150))
    genre: Mapped[str] = mapped_column(String(50), default="general")
    concept_description: Mapped[str] = mapped_column(Text, default="")
    # 初期音源リスト [{youtube_id, title, duration}, ...]
    initial_tracks_json: Mapped[str] = mapped_column(Text, default="[]")
    ai_dj_concept: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # pending / approved / rejected
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    applicant: Mapped["User"] = relationship(
        "User", foreign_keys=[applicant_id], lazy="selectin"
    )

    def to_dict(self) -> dict:
        import json

        try:
            tracks = json.loads(self.initial_tracks_json or "[]")
        except Exception:
            tracks = []
        return {
            "id": self.id,
            "applicant_id": self.applicant_id,
            "applicant_username": self.applicant.username if self.applicant else None,
            "desired_frequency": self.desired_frequency,
            "callsign": self.callsign,
            "station_title": self.station_title,
            "genre": self.genre,
            "concept_description": self.concept_description,
            "initial_tracks": tracks,
            "track_count": len(tracks),
            "ai_dj_concept": self.ai_dj_concept,
            "status": self.status,
            "review_note": self.review_note,
            "reviewed_by": self.reviewed_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }


class DedicatedTrackLibrary(Base):
    """専用局の内部音源プール（固定ライブラリ）。"""

    __tablename__ = "dedicated_track_library"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )
    youtube_id: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255), default="")
    artist: Mapped[str] = mapped_column(String(150), default="Unknown")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=200)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "station_id": self.station_id,
            "youtube_id": self.youtube_id,
            "title": self.title,
            "artist": self.artist,
            "duration_seconds": self.duration_seconds,
        }


class BroadcastQueue(Base):
    """リアルタイム送出待ちキュー（リスナーリクエスト＋予定曲）。"""

    __tablename__ = "broadcast_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )
    youtube_id: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255), default="")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=200)
    requested_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    requested_by_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_played: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "station_id": self.station_id,
            "youtube_id": self.youtube_id,
            "title": self.title,
            "duration_seconds": self.duration_seconds,
            "requested_by_user_id": self.requested_by_user_id,
            "requested_by_name": self.requested_by_name,
            "is_played": self.is_played,
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Thread(Base):
    """2chライクな掲示板スレッド。

    1スレッドは最大 MAX_THREAD_POSTS（既定1000）投稿で自動的にアーカイブされ、
    新しいスレッド（次の番号）が自動で作成される。
    """

    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )
    # 局ごとの通し番号（第Nスレ）
    number: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(150), default="")
    post_count: Mapped[int] = mapped_column(Integer, default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    station: Mapped["Station"] = relationship("Station", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "station_id": self.station_id,
            "number": self.number,
            "title": self.title,
            "post_count": self.post_count,
            "is_archived": self.is_archived,
            "station_callsign": self.station.callsign if self.station else None,
            "frequency": self.station.frequency if self.station else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
        }
