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
import unicodedata
from typing import Optional

import httpx

from app.core.config import settings

# 返信の先頭に付きがちな「Mia:」「DJ:」などのラベルを除去する
_SELF_LABEL = re.compile(r"^\s*(Mia|ミア|DJ|AI)\s*[:：]\s*", re.IGNORECASE)

# DJの呼びかけ（「DJさん」「hey DJ」）。大文字小文字・全角半角は区別しない。
#   DJさん / DJ さん / ＤＪさん / hey DJ / Hey, DJ! / ヘイDJ など
_DJ_MENTION_RE = re.compile(
    r"(?<![a-z0-9])dj\s*さん|(?<![a-z0-9])(?:hey|ヘイ)[\s,、!！.．:：]*dj(?![a-z0-9])"
)


def _clean(text: str) -> str:
    text = (text or "").strip()
    text = _SELF_LABEL.sub("", text)
    return text.strip()


def mentions_dj(message: str) -> bool:
    """メッセージがDJを呼びかけているか（「DJさん」「hey DJ」）。

    大文字小文字・全角半角は区別しない（NFKC 正規化してから判定する）。
    """
    if not message:
        return False
    normalized = unicodedata.normalize("NFKC", message).lower()
    return bool(_DJ_MENTION_RE.search(normalized))


def dj_should_reply(program: str, message: str) -> bool:
    """この局のDJがこのメッセージに返事すべきか。

    - `dj_reply_requires_call=False` なら従来どおり全部に返事する。
    - Discord連携局（Miaちゃん）はチャットbotなので常時返事する。
    - それ以外の局のDJは「DJさん」「hey DJ」と呼びかけられたときだけ返事する。
    """
    if not settings.dj_reply_requires_call:
        return True
    if program and program == settings.discord_station_callsign:
        return True
    return mentions_dj(message)


_DJ_PROMPT = """あなたは配信「{program}」のDJです。以下のキャラクター設定になりきって、
リスナーに今この瞬間のひとことを、自由に考えて話してください。定型文の暗唱はしないこと。
出力は必ず自然な日本語のみ（英単語・ローマ字・記号の羅列を混ぜない）。
キャラクター設定: {persona}
今オンエア中の曲（この曲の印象・歌詞・聴きどころなどに必ず触れること）: {track}
直前に流れた曲（参考。無ければ空）: {recent}
直前の会話（参考。無ければ空）:
{context}
DJのひとこと（日本語で1〜3文）:"""

_TRACK_INTRO_PROMPT = """あなたは配信「{program}」のDJです。以下のキャラクター設定になりきって、
たった今流れ始めた曲をリスナーに紹介するひとことを、自由に考えて話してください。
定型文の暗唱はしないこと。
出力は必ず自然な日本語のみ（英単語・ローマ字・記号の羅列を混ぜない）。
キャラクター設定: {persona}
今流れ始めた曲（曲名。必ずこの曲に触れること）: {track}
その前に流れていた曲（参考。無ければ空）: {previous}
直前の会話（参考。無ければ空）:
{context}
DJの曲紹介（日本語で1〜2文）:"""

_CHAT_PROMPT = """あなたは配信「{program}」のDJです。以下のキャラクター設定になりきり、
リスナーの発言へ、DJとして自然に返信してください。
相手の発言の内容を踏まえて、毎回ちがう言い方で、自由に考えて返すこと（定型文の暗唱はしない）。
出力は必ず自然な日本語のみ（英単語・ローマ字・記号の羅列を混ぜない）。
キャラクター設定: {persona}
今オンエア中の曲（参考。話の流れで自然に触れてよい）: {track}
直前の会話（参考。無ければ空）:
{context}
リスナーの発言: {message}
返信（日本語で1〜2文。絵文字や顔文字を少し混ぜてOK）:"""

# 曲名が分からないときにプロンプトへ渡す指示（曲名を捏造させない）
_NO_TRACK = "（曲名が不明。曲名には触れず、放送全体の話題で話す）"

# YouTube の動画IDらしい文字列（タイトルが取れなかったときのフォールバック値）
_ID_LIKE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _track_label(track: Optional[str]) -> str:
    """プロンプトに載せる曲名。動画IDしか無いときは「曲名不明」として扱う。"""
    text = (track or "").strip()
    if not text or _ID_LIKE.match(text):
        return _NO_TRACK
    return text


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
    program: str,
    context: str = "",
    persona: Optional[str] = None,
    track: Optional[str] = None,
    recent: Optional[str] = None,
) -> Optional[str]:
    """アイドルDJのひとことをLLMで自由生成する。失敗時は None。

    track（今オンエア中の曲名）を渡すと、その曲に触れたコメントになる。
    recent には直前まで流れていた曲名（「A → B」形式）を渡せる。
    """
    if not is_llm_configured():
        return None
    prompt = _DJ_PROMPT.format(
        program=program or "Midair.io",
        persona=persona or "深夜ラジオのDJ。落ち着いた口調。",
        track=_track_label(track),
        recent=(recent or "").strip() or "（なし）",
        context=context or "（まだ誰もいない）",
    )
    try:
        return _clean(await _call_llm(prompt))
    except Exception:
        return None


async def generate_track_intro(
    program: str,
    persona: Optional[str],
    track: str,
    previous: Optional[str] = None,
    context: str = "",
) -> Optional[str]:
    """曲が切り替わったときの曲紹介コメントをLLMで自由生成する。失敗時は None。"""
    if not is_llm_configured() or not (track or "").strip():
        return None
    prompt = _TRACK_INTRO_PROMPT.format(
        program=program or "Midair.io",
        persona=persona or "深夜ラジオのDJ。落ち着いた口調。",
        track=track.strip(),
        previous=(previous or "").strip() or "（なし）",
        context=context or "（なし）",
    )
    try:
        return _clean(await _call_llm(prompt))
    except Exception:
        return None


async def generate_chat_reply(
    program: str,
    persona: Optional[str],
    message: str,
    context: str = "",
    track: Optional[str] = None,
) -> Optional[str]:
    """リスナーの発言への返信をLLMで自由生成する。失敗時は None。"""
    if not is_llm_configured():
        return None
    prompt = _CHAT_PROMPT.format(
        program=program or "Midair.io",
        persona=persona or "明るく親しみやすいチャットbot",
        message=message or "（無言）",
        track=_track_label(track),
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
    track: Optional[str] = None,
) -> Optional[str]:
    """チャットbotが有効な局で、クールダウンを考慮して自由生成の返信を返す。

    DJ（呼びかけ必須の局）は「DJさん」「hey DJ」と呼びかけられたときだけ返信する
    （`dj_should_reply` を参照）。
    """
    if not enabled:
        return None
    if not dj_should_reply(program, message):
        return None
    now = time.time()
    if now - _last_reply.get(station_id, 0.0) < max(0, settings.bot_reply_cooldown_seconds):
        return None
    _last_reply[station_id] = now
    return await generate_chat_reply(
        program, persona, message, context=context, track=track
    )
