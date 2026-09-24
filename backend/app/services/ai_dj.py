"""AIラジオDJ / AIチャットbot。Gemini API が設定されていれば生成、なければルールベース。

- ステーションごとのキャラクター設定（ai_dj_prompt）を `persona` として渡せる。
- リスナーの発言に返信する「チャットbot」モード（Discordのチャットbot的な挙動）に対応。
"""
import random
import time
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

# チャットbotのフォールバック（Gemini未設定時）。オタクJKっぽい相づち。
_CHAT_FALLBACK = [
    "えっ、それめっちゃ分かる〜！うちもそれ好き！",
    "うわ〜、それってアニメのやつですか？詳しく聞きたい！",
    "きゃ〜、先輩それ知ってるんですか！？推しポイント高い…！",
    "それな〜！深夜にその話題はアツいｗ",
    "うちも今それ考えてたとこ！シンクロじゃん！",
    "え、まって、その曲ボカロですか？神選曲〜",
    "ふぁ〜、眠くなってきたけど、まだ起きてます…！",
    "先輩、その話もっと聞かせてください！(｡･ω･｡)",
    "いいですね〜！今日もいい夜になってきた！",
    "それってあの作品のやつですよね？うちもハマってます！",
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

# チャットbot（リスナーの発言に返信する）
_CHAT_PROMPT = """あなたは配信「{program}」に常駐するAIチャットbotです。以下のキャラクター設定に従い、
リスナーの発言に、Discordのチャットbotのように気軽に返信してください。
キャラクター設定: {persona}
リスナーの発言: {message}
返信（日本語で1〜2文。絵文字や顔文字を少し混ぜてOK。同じ語尾の繰り返しは避ける）:"""


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


async def generate_chat_reply(
    program: str, persona: Optional[str], message: str
) -> str:
    """リスナーの発言への返信を生成する。API未設定・失敗時はフォールバック。"""
    if settings.gemini_api_key:
        try:
            return await _call_gemini_chat(program, persona, message)
        except Exception:
            pass
    return random.choice(_CHAT_FALLBACK)


# 局ごとの最終返信時刻（連投を防ぐ）
_last_reply: dict[int, float] = {}


async def maybe_chat_reply(
    station_id: int,
    program: str,
    persona: Optional[str],
    enabled: bool,
    message: str,
) -> Optional[str]:
    """チャットbotが有効な局で、クールダウンを考慮して返信を生成する。"""
    if not enabled:
        return None
    now = time.time()
    if now - _last_reply.get(station_id, 0.0) < max(0, settings.bot_reply_cooldown_seconds):
        return None
    _last_reply[station_id] = now
    return await generate_chat_reply(program, persona, message)


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
    return await _generate(url, text)


async def _call_gemini_chat(program: str, persona: Optional[str], message: str) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    )
    text = _CHAT_PROMPT.format(
        program=program or "Midair.io",
        persona=persona or "明るく親しみやすいチャットbot",
        message=message or "（無言）",
    )
    return await _generate(url, text)


async def _generate(url: str, text: str) -> str:
    payload = {"contents": [{"parts": [{"text": text}]}]}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
