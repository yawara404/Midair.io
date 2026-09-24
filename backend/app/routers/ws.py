"""WebSocket エンドポイント。リアルタイムチャット・曲リクエスト・DJ呼びかけ。

認証は任意。クエリ `?token=<JWT>` を渡すとログイン済みとして扱われ、
送信者名にユーザー名が使われる。開局者は BGM 強制切り替え・モデレーション権限を持つ。
"""
import random
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.security import decode_token
from app.core.utils import parse_youtube_id
from app.models.models import Message, Station, User
from app.services.ai_dj import generate_dj_line
from app.services.discord_sync import send_to_discord
from app.services.sessions import current_offset, record_track
from app.services.websocket_manager import manager

router = APIRouter()


def _now() -> datetime:
    return datetime.now()


async def _persist_message(
    station_id: int,
    sender_name: str,
    content: str,
    user_id: Optional[int] = None,
    is_dj: bool = False,
    is_broadcaster: bool = False,
    youtube_id: Optional[str] = None,
) -> dict:
    async with async_session_factory() as session:
        # 放送セッションに自動バインド（offset = セッション開始からの経過秒）
        session_id, offset = await current_offset(session, station_id)
        msg = Message(
            station_id=station_id,
            session_id=session_id,
            offset_seconds=offset,
            user_id=user_id,
            sender_name=sender_name,
            content=content,
            youtube_id=youtube_id,
            is_dj=is_dj,
            is_broadcaster=is_broadcaster,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return msg.to_dict()


async def _broadcast_track(
    station_id: int, video_id: Optional[str], started_at_iso: Optional[str]
) -> None:
    await manager.broadcast(
        station_id,
        {
            "type": "track_update",
            "youtube_video_id": video_id,
            "playback_started_at": started_at_iso,
        },
    )


@router.websocket("/ws")
async def global_websocket(websocket: WebSocket):
    """ロビー接続。周波数ステータスなどのグローバルイベントを受信する。"""
    await manager.connect(0, websocket, "lobby")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        manager.disconnect(0, websocket)


@router.websocket("/ws/{station_id}")
async def websocket_endpoint(websocket: WebSocket, station_id: int):
    token = websocket.query_params.get("token")
    user_id = decode_token(token) if token else None

    async with async_session_factory() as session:
        station = await session.get(Station, station_id)
        if station is None:
            await websocket.close(code=4404)
            return
        owner_id = station.owner_id
        station_name = station.callsign
        ai_dj_prompt = station.ai_dj_prompt
        current_track = {
            "youtube_video_id": station.current_youtube_id,
            "playback_started_at": (
                station.playback_started_at.isoformat()
                if station.playback_started_at
                else None
            ),
        }
        user = await session.get(User, user_id) if user_id else None
        username = user.username if user else None

    is_broadcaster = bool(user_id and user_id == owner_id)
    handle = username or f"名無しのリスナー#{random.randint(0, 9999):04d}"

    await manager.connect(station_id, websocket, handle)

    try:
        await websocket.send_json(
            {
                "type": "welcome",
                "handle": handle,
                "user_id": user_id,
                "is_broadcaster": is_broadcaster,
                "station_id": station_id,
                "station_name": station_name,
                "track": current_track,
            }
        )

        await manager.broadcast(
            station_id,
            {
                "type": "system",
                "content": f"{handle} が周波数に合流しました（現在 {manager.channel_count(station_id)} 人）",
                "listener_count": manager.channel_count(station_id),
            },
        )

        while True:
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except Exception:
                continue

            msg_type = data.get("type", "chat")
            manager.touch(station_id)

            if msg_type == "chat":
                content = (data.get("content") or "").strip()[:500]
                if not content:
                    continue
                payload = await _persist_message(
                    station_id, handle, content, user_id=user_id,
                    is_broadcaster=is_broadcaster,
                )
                await manager.broadcast(station_id, {"type": "message", **payload})
                await send_to_discord(
                    settings.discord_webhook_url, content, f"[{station_name}] {handle}"
                )

            elif msg_type == "youtube_request":
                raw = data.get("url") or data.get("video_id") or ""
                video_id = parse_youtube_id(raw)
                if not video_id:
                    await websocket.send_json(
                        {"type": "error", "content": "YouTubeのURLまたは動画IDを正しく入力してください"}
                    )
                    continue
                if is_broadcaster:
                    # 開局者はBGMを強制切り替え
                    async with async_session_factory() as session:
                        station = await session.get(Station, station_id)
                        station.current_youtube_id = video_id
                        station.playback_started_at = _now()
                        await session.commit()
                        # 選曲ログ（プロフィールの「過去の曲」）にも記録する
                        await record_track(session, station_id, video_id)
                        started_iso = station.playback_started_at.isoformat()
                    payload = await _persist_message(
                        station_id, handle, f"曲をオンエアしました: https://youtu.be/{video_id}",
                        user_id=user_id, is_broadcaster=True, youtube_id=video_id,
                    )
                    await manager.broadcast(station_id, {"type": "message", **payload})
                    await _broadcast_track(station_id, video_id, started_iso)
                else:
                    # リスナーはリクエストとして投げる（BGMは変わらない）
                    payload = await _persist_message(
                        station_id, handle,
                        f"曲をリクエスト: https://youtu.be/{video_id}",
                        user_id=user_id, youtube_id=video_id,
                    )
                    await manager.broadcast(station_id, {"type": "message", **payload})

            elif msg_type == "dj_call":
                context = (data.get("content") or "").strip()
                line = await generate_dj_line(station_name, context, ai_dj_prompt)
                payload = await _persist_message(
                    station_id, "DJ", line, is_dj=True
                )
                await manager.broadcast(station_id, {"type": "message", **payload})

            else:
                await websocket.send_json(
                    {"type": "error", "content": f"不明なメッセージ種別: {msg_type}"}
                )

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(station_id, websocket)
        await manager.broadcast(
            station_id,
            {
                "type": "system",
                "content": f"{handle} が周波数を離れました（現在 {manager.channel_count(station_id)} 人）",
                "listener_count": manager.channel_count(station_id),
            },
        )
