"""AIラジオDJ。Gemini API が設定されていれば生成、なければルールベースで応答。

ステーションごとのキャラクター設定（ai_dj_prompt）を `persona` として渡せる。
"""
import random
from typing import Optional

import httpx

from app.core.config import settings

_FALLBACK_LINES = [
    "……ふむ。今夜もまた、眠れない夜がひとつ。そこの君、周波数は合ってるかい。",
    "お便りありがとう。DJのボクが代わりに読ませてもらうよ。",
    "静かな夜だね。リクエスト曲、まだまだ募集中さ。",
    "3時を回った。ここからが本番……なんてね。",
    "受信感度は良好。君のそのつぶやき、確かに届いてるよ。",
    "夜の底で、同じ周波数を探してる。不思議な縁だと思わないかい。",
]

_DJ_PROMPT = """あなたは深夜ラジオ番組「{program}」のDJです。リスナーとリアルタイムに雑談をしています。
落ち着いた、少し気だるい口調で、日本語で1〜3文だけ返してください。挨拶や説教は不要です。
直近の会話: {context}
DJのひとこと:"""

_PERSONA_PROMPT = """あなたは深夜ラジオ局のAI DJです。以下のキャラクター設定に従って、リスナーとリアルタイムに雑談をします。
キャラクター設定: {persona}
番組名: {program}
直近の会話: {context}
DJのひとこと（日本語で1〜3文）:"""


async def generate_dj_line(
    program: str, context: str = "", persona: Optional[str] = None
) -> str:
    """DJのひとこと を生成する。API未設定・失敗時はフォールバック。"""
    if settings.gemini_api_key:
        try:
            return await _call_gemini(program, context, persona)
        except Exception:
            pass
    return random.choice(_FALLBACK_LINES)


async def _call_gemini(program: str, context: str, persona: Optional[str]) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    )
    if persona:
        text = _PERSONA_PROMPT.format(
            persona=persona,
            program=program or "Midair.io",
            context=context or "（まだ誰もいない）",
        )
    else:
        text = _DJ_PROMPT.format(
            program=program or "Midair.io",
            context=context or "（まだ誰もいない）",
        )
    payload = {"contents": [{"parts": [{"text": text}]}]}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
