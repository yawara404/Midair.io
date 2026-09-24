"""番組表（タイムテーブル）・アーカイブ API。"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_user
from app.core.utils import parse_youtube_id
from app.models.models import Message, Program, Station, User

router = APIRouter(prefix="/api", tags=["programs"])


class ProgramIn(BaseModel):
    title: str
    description: Optional[str] = ""
    start_time: datetime
    end_time: datetime
    default_youtube_id: Optional[str] = None


def _require_owner(station: Optional[Station], user: User) -> Station:
    if not station:
        raise HTTPException(status_code=404, detail="ステーションが見つかりません")
    if station.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="このステーションの編集権限がありません")
    return station


@router.get("/stations/{station_id}/programs")
async def list_programs(station_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Program).where(Program.station_id == station_id).order_by(Program.start_time.asc())
    )
    return {"success": True, "programs": [p.to_dict() for p in result.scalars().all()]}


@router.post("/stations/{station_id}/programs", status_code=201)
async def create_program(
    station_id: int,
    data: ProgramIn,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    station = _require_owner(await db.get(Station, station_id), user)
    if data.end_time <= data.start_time:
        raise HTTPException(status_code=400, detail="終了時刻は開始時刻より後を指定してください")
    program = Program(
        station_id=station_id,
        title=data.title.strip(),
        description=data.description or "",
        start_time=data.start_time,
        end_time=data.end_time,
        default_youtube_id=parse_youtube_id(data.default_youtube_id),
    )
    db.add(program)
    await db.commit()
    await db.refresh(program)
    return {"success": True, "program": program.to_dict()}


@router.put("/programs/{program_id}")
async def update_program(
    program_id: int,
    data: ProgramIn,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    program = await db.get(Program, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="番組が見つかりません")
    _require_owner(await db.get(Station, program.station_id), user)
    if data.end_time <= data.start_time:
        raise HTTPException(status_code=400, detail="終了時刻は開始時刻より後を指定してください")
    program.title = data.title.strip()
    program.description = data.description or ""
    program.start_time = data.start_time
    program.end_time = data.end_time
    program.default_youtube_id = parse_youtube_id(data.default_youtube_id)
    await db.commit()
    await db.refresh(program)
    return {"success": True, "program": program.to_dict()}


@router.delete("/programs/{program_id}")
async def delete_program(
    program_id: int, user: User = Depends(require_user), db: AsyncSession = Depends(get_db)
):
    program = await db.get(Program, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="番組が見つかりません")
    _require_owner(await db.get(Station, program.station_id), user)
    await db.delete(program)
    await db.commit()
    return {"success": True}


@router.get("/timetable")
async def timetable(date: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """指定日（YYYY-MM-DD）の番組表を返す。未指定時は直近7日。"""
    if date:
        try:
            day = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="date は YYYY-MM-DD 形式で指定してください")
        start = day
        end = day + timedelta(days=1)
    else:
        start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
    result = await db.execute(
        select(Program)
        .where(Program.end_time > start, Program.start_time < end)
        .order_by(Program.start_time.asc())
    )
    return {"success": True, "programs": [p.to_dict() for p in result.scalars().all()]}


@router.get("/stations/{station_id}/archive")
async def station_archive(station_id: int, db: AsyncSession = Depends(get_db)):
    """過去の番組（終了済み）をアーカイブとして返す。"""
    result = await db.execute(
        select(Program)
        .where(Program.station_id == station_id, Program.end_time < datetime.now())
        .order_by(Program.start_time.desc())
    )
    return {"success": True, "programs": [p.to_dict() for p in result.scalars().all()]}


@router.get("/programs/{program_id}/messages")
async def program_messages(program_id: int, db: AsyncSession = Depends(get_db)):
    """番組放送時間内のチャットログ（録音テープ風アーカイブ）。"""
    program = await db.get(Program, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="番組が見つかりません")
    result = await db.execute(
        select(Message)
        .where(
            Message.station_id == program.station_id,
            Message.created_at >= program.start_time,
            Message.created_at <= program.end_time,
        )
        .order_by(Message.id.asc())
    )
    return {"success": True, "messages": [m.to_dict() for m in result.scalars().all()]}
