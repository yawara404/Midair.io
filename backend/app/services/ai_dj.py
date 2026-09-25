"""AIラジオDJ / AIチャットbot（自由思考型）。

LLM（Gemini API / OpenAI互換 API）で、キャラクター設定（ai_dj_prompt）と
直前の会話を踏まえてその場で文章を生成する。定型文のリストは使わない。
プロバイダは LLM_PROVIDER（auto/gemini/openai）で切り替える。

- チャットbot: リスナーの発言に、文脈を踏まえて自由に返信する。
- アイドルDJ: 会話が途切れたときに、キャラクターとして自由に話しかける。

Gemini API が未設定・失敗時は None を返し、呼び出し側は「何も投稿しない」。
（＝定型文での代替はしない）
"""
import re
import time
from typing import Optional

import httpx

from app.core.config import settings

# 返信の先頭に付きがちな「Mia:」「DJ:」などのラベルを除去する
_SELF_LABEL = re.compile(r"^\s*(Mia|ミア|DJ|AI)\s*[:：]\s*", re.IGNORECASE)


def _clean(text: str) -> str:
    text = (text or "").strip()
    text = _SELF_LABEL.sub("", text)
    return text.strip()

_DJ_PROMPT = """あなたは配信「{program}」のDJです。以下のキャラクター設定になりきって、
リスナーに今この瞬間のひとことを、自由に考えて話してください。定型文の暗唱はしないこと。
出力は必ず自然な日本語のみ（英単語・ローマ字・記号の羅列を混ぜない）。
キャラクター設定: {persona}
直前の会話（参考。無ければ空）:
{context}
DJのひとこと（日本語で1〜3文）:"""

_CHAT_PROMPT = """あなたは配信「{program}」のDJです。以下のキャラクター設定になりきり、
リスナーの発言へ、DJとして自然に返信してください。
相手の発言の内容を踏まえて、毎回ちがう言い方で、自由に考えて返すこと（定型文の暗唱はしない）。
出力は必ず自然な日本語のみ（英単語・ローマ字・記号の羅列を混ぜない）。
キャラクター設定: {persona}
直前の会話（参考。無ければ空）:
{context}
リスナーの発言: {message}
返信（日本語で1〜2文。絵文字や顔文字を少し混ぜてOK）:"""


def active_provider() -> Optional[str]:
    """使用する LLM プロバイダを返す（auto はキーの有無で判定）。"""
    p = (settings.llm_provider or "auto").strip().lower()
    if p == "gemini":
        return "gemini" if settings.gemini_api_key else None
    if p == "openai":
        return "openai" if settings.openai_api_key else None
    # auto: OpenAI互換キーがあれば優先、無ければ Gemini
    if settings.openai_api_key:
        return "openai"
    if settings.gemini_api_key:
        return "gemini"
    return None


def is_llm_configured() -> bool:
    """LLM（Gemini または OpenAI互換）が設定されているか。"""
    return active_provider() is not None


async def _call_gemini(prompt: str) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": settings.llm_temperature,
            "maxOutputTokens": settings.llm_max_tokens,
        },
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, timeout=25)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


async def _call_openai(prompt: str) -> str:
    """OpenAI 互換 API（/chat/completions）で生成する。"""
    base = (settings.openai_base_url or "").rstrip("/")
    headers = {"Content-Type": "application/json"}
    if settings.openai_api_key:
        headers["Authorization"] = f"Bearer {settings.openai_api_key}"
    payload = {
        "model": settings.openai_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": settings.llm_temperature,
        "top_p": 0.9,
        "max_tokens": settings.llm_max_tokens,
        "frequency_penalty": 0.3,
    }
    async with httpx.AsyncClient() as client:
        # アイドル後にモデルを再ロードする場合があるため長め（16GB機・12Bで最大2分程度）
        resp = await client.post(
            f"{base}/chat/completions", json=payload, headers=headers, timeout=180
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


async def _call_llm(prompt: str) -> str:
    """設定されたプロバイダで生成する。"""
    if active_provider() == "openai":
        return await _call_openai(prompt)
    return await _call_gemini(prompt)


async def generate_dj_line(
    program: str, context: str = "", persona: Optional[str] = None
) -> Optional[str]:
    """アイドルDJのひとことをLLMで自由生成する。失敗時は None。"""
    if not is_llm_configured():
        return None
    prompt = _DJ_PROMPT.format(
        program=program or "Midair.io",
        persona=persona or "深夜ラジオのDJ。落ち着いた口調。",
        context=context or "（まだ誰もいない）",
    )
    try:
        return _clean(await _call_llm(prompt))
    except Exception:
        return None


async def generate_chat_reply(
    program: str, persona: Optional[str], message: str, context: str = ""
) -> Optional[str]:
    """リスナーの発言への返信をLLMで自由生成する。失敗時は None。"""
    if not is_llm_configured():
        return None
    prompt = _CHAT_PROMPT.format(
        program=program or "Midair.io",
        persona=persona or "明るく親しみやすいチャットbot",
        message=message or "（無言）",
        context=context or "（なし）",
    )
    try:
        return _clean(await _call_llm(prompt))
    except Exception:
        return None


# 局ごとの最終返信時刻（連投を防ぐ）
_last_reply: dict[int, float] = {}


async def maybe_chat_reply(
    station_id: int,
    program: str,
    persona: Optional[str],
    enabled: bool,
    message: str,
    context: str = "",
) -> Optional[str]:
    """チャットbotが有効な局で、クールダウンを考慮して自由生成の返信を返す。"""
    if not enabled:
        return None
    now = time.time()
    if now - _last_reply.get(station_id, 0.0) < max(0, settings.bot_reply_cooldown_seconds):
        return None
    _last_reply[station_id] = now
    return await generate_chat_reply(program, persona, message, context=context)
