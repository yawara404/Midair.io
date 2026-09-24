"""認証 API（登録 / ログイン / プロフィール / Discord OAuth2）。"""
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    hash_password,
    require_user,
    verify_password,
)
from app.models.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    username: str
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/register")
async def register(data: RegisterIn, db: AsyncSession = Depends(get_db)):
    username = data.username.strip()
    email = data.email.strip().lower()
    if not username or not email or not data.password:
        raise HTTPException(status_code=400, detail="ユーザー名・メール・パスワードを入力してください")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="パスワードは6文字以上で入力してください")
    existing = await db.execute(
        select(User).where(or_(User.username == username, User.email == email))
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="そのユーザー名またはメールは既に使われています")
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(data.password),
        role="listener",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(user.id)
    return {"success": True, "access_token": token, "user": user.to_dict()}


@router.post("/login")
async def login(data: LoginIn, db: AsyncSession = Depends(get_db)):
    email = data.email.strip().lower()
    result = await db.execute(
        select(User).where(or_(User.email == email, User.username == email))
    )
    user = result.scalars().first()
    if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="メールアドレスまたはパスワードが違います")
    token = create_access_token(user.id)
    return {"success": True, "access_token": token, "user": user.to_dict()}


@router.get("/me")
async def me(user: User = Depends(require_user)):
    return {"success": True, "user": user.to_dict()}


# ---- Discord OAuth2（環境変数設定時のみ有効） ----

@router.get("/discord/login")
async def discord_login(redirect: Optional[str] = None):
    if not settings.discord_client_id:
        raise HTTPException(status_code=501, detail="Discord OAuth2 は設定されていません")
    # 認証後の戻り先。指定がなければ FRONTEND_URL を使う（state で引き回す）
    target = redirect or settings.frontend_url
    base = "https://discord.com/api/oauth2/authorize"
    params = (
        f"client_id={settings.discord_client_id}"
        f"&redirect_uri={quote(settings.discord_redirect_uri or '', safe='')}"
        f"&response_type=code&scope=identify%20email"
        f"&state={quote(target, safe='')}"
    )
    return RedirectResponse(f"{base}?{params}")


@router.get("/discord/callback")
async def discord_callback(
    code: str,
    state: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    if not settings.discord_client_id or not settings.discord_client_secret:
        raise HTTPException(status_code=501, detail="Discord OAuth2 は設定されていません")
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": settings.discord_client_id,
                "client_secret": settings.discord_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.discord_redirect_uri,
            },
            timeout=20,
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        me_resp = await client.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        me_resp.raise_for_status()
        d = me_resp.json()

    discord_id = d["id"]
    username = d.get("username") or f"discord_{discord_id}"
    email = d.get("email") or f"{discord_id}@discord.midair"
    avatar = d.get("avatar")
    avatar_url = (
        f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar}.png" if avatar else None
    )

    result = await db.execute(select(User).where(User.discord_id == discord_id))
    user = result.scalars().first()
    if not user:
        user = User(
            username=username,
            email=email,
            discord_id=discord_id,
            avatar_url=avatar_url,
            role="listener",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    jwt_token = create_access_token(user.id)
    target = state or settings.frontend_url
    return RedirectResponse(f"{target}?token={jwt_token}")
