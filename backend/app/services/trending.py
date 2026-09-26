"""自動DJ局（DJ BOT / Vocaloid BOT）の選曲ソース。

- trending:  YouTube mostPopular（ミュージック）から人気曲を取得
- search:    YouTube 検索（任意クエリ）から曲を取得
- vocaloid:  歌声合成（ボカロ等）の歌声・ジャンル・年代・プロデューサー・
             歌声合成エンジン別の検索テーマを巡回し、候補を蓄積しながら選曲する。
             歌声合成のクレジットが確認できる曲（＝合成音声の歌唱）だけを流す
             （合成音声歌唱優先）。

いずれも「埋め込み再生できる通常動画」だけを採用し、ランダムに1曲選ぶ。
APIキー未設定・取得失敗時は埋め込み可能な内蔵プールにフォールバックする。
"""
import random
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.core.config import settings
from app.services.youtube import parse_iso_duration

# APIが使えないとき用の内蔵フォールバック（埋め込み再生できることを確認済みのID）。
# ※ 少なすぎると同じ曲がすぐ再登場するので、ジャンルを散らして多めに持っておく
_FALLBACK: list[tuple[str, str]] = [
    ("60ItHLz5WEA", "Alan Walker - Faded"),
    ("JGwWNGJdvx8", "Ed Sheeran - Shape of You"),
    ("fJ9rUzIMcZQ", "Queen - Bohemian Rhapsody"),
    ("dQw4w9WgXcQ", "Rick Astley - Never Gonna Give You Up"),
    ("s4UW__ysPEM", "Fujii Kaze - You"),
    ("5ll40JRPoHM", "SEKAI NO OWARI「Supermarket」"),
    ("FnjYuHgAKq4", "Mrs. GREEN APPLE - Feeling【LIVE】"),
    ("tWez_36Zs6I", "ヨルシカ - LIVE「レプリカント」"),
    ("Lufa9QAFFeY", "ROSÉ - new trick"),
    ("K2quL_v3Lqc", "LEE JISOO - MISMATCH / THE FIRST TAKE"),
    ("4J06I7qy7kM", "仲川瑠夏 - 朝にならないで / THE FIRST TAKE"),
    ("otEgL_cdHdo", "稲葉浩志 / RIZAN"),
    ("uzsSnLLHx5M", "BE:FIRST / WATCH ME feat. BIA"),
    ("8rNve_w6XGw", "Hey! Say! JUMP - ハニカミ"),
    ("DXzpRZpF12E", "Snow Man 'show time...'"),
    ("0WzUWCS6-X0", "Snow Man '奇跡'"),
    ("EH2rhQlvz7A", "Snow Man 'グッタイム'"),
    ("JpIw7rSLRqc", "M!LK - 時空超えてユニバース"),
    ("qjsOs4Kjr5Q", "坂道選抜「Audition」"),
    ("Sp4xl7wtqtc", "櫻坂46『愛MUST BE』"),
    ("Ky3mIUfBb5c", "INI｜'BEYOND THE SKY'"),
    ("tdznAT137QI", "Aぇ! group「Emotion」"),
    ("lYafXo-rjU8", "初星学園「め」"),
    ("bpHBIO-Ridc", "【Kanaria×葛葉】アイデンティティ【セルフカバー】"),
    ("DeKLpgzh-qQ", "稲葉曇『ロストアンブレラ』Vo. 歌愛ユキ"),
    ("4xDzrJKXOOY", "lofi synthwave radio 🌌"),
]

# Vocaloid BOT 用フォールバック（YouTube API が使えないときも1曲ループに
# ならないよう、歌声・曲調の異なる曲を並べる。いずれも埋め込み再生を確認済み）
_VOCALOID_FALLBACK: list[tuple[str, str]] = [
    ("TXzfQ0cP1P0", "【初音ミク】恋愛裁判 Love Trial【オリジナルMV】"),
    ("OuLZlZ18APQ", "【初音ミク】39みゅーじっく！【オリジナルMV】"),
    ("9O2VyUM5MlQ", "まにまに / 初音ミク"),
    ("DeKLpgzh-qQ", "稲葉曇『ロストアンブレラ』Vo. 歌愛ユキ"),
    ("lw7pcm1W5tw", "ピノキオピー - ノンブレス・オブリージュ feat. 初音ミク"),
    ("ZEy36W1xX8c", "メルティランドナイトメア / はるまきごはん feat.初音ミク"),
    ("AS4q9yaWJkI", "ハチ - 砂の惑星 feat.初音ミク"),
    ("qtuX4cHk-vE", "マシュマリー / MIMI feat.初音ミク"),
    ("jhl5afLEKdo", "World is Mine / ryo（supercell）feat. 初音ミク"),
    ("0HYm60Mjm0k", "命に嫌われている。/初音ミク"),
    ("KushW6zvazM", "DECO*27 - ゴーストルール feat. 初音ミク"),
    ("vqiULULdvMA", "【鏡音リンレン】ぼうけんのしょがきえました！【オリジナルMV】"),
    ("CiEC329xPos", "ひとしずく×やま△ - 祝福のメシアとアイの塔"),
    ("V0m7gyCu5nM", "おまじない / 天使電影 feat.可不×裏命×星界"),
    ("fHkRfcDILWI", "最後の夏にしよう / 重音テト・初音ミク・可不"),
    ("uB_jQ8H2Yeg", "一千光年 / いよわ feat. 初音ミク、v_flower、歌愛ユキ、GUMI、可不、星界"),
    ("FSLxRRQdNs4", "ただ病名が欲しかった / 可不・星界・カゼヒキ"),
    ("LLjfal8jCYI", "オーバーライド - 重音テトSV[吉田夜世]"),
    ("hXabKIYl_Yo", "星界ちゃんと可不ちゃんのおつかい合騒曲"),
    ("xwqjhRwg7xc", "キティ / kitty - miku"),
    ("P_CSdxSGfaA", "wowaka『アンノウン・マザーグース』feat. 初音ミク"),
    ("tzaDeBNDp1c", "逢魔時の帰り方 / しとお Vo.狐子"),
    ("PubukElqUJw", "異星にいこうね / いよわ feat.星界"),
    ("lJB8ByV1nj4", "おどりゃんせ / YurryCanon feat.MIKU&GUMI"),
    ("kbNdx0yqbZE", "DECO*27 - モニタリング feat. 初音ミク"),
    ("7xht3kQO_TM", "『ハナタバ』/ MIMI feat. 可不"),
    ("b2GJcYBoVyg", "神のまにまに / れるりり feat.ミク&リン&GUMI"),
    ("TkroHwQYpFE", "【初音ミク】ヒビカセ【オリジナル】"),
    ("8xFBLego17k", "【初音ミク】1925【オリジナル曲】"),
    ("pLN6GK6_ILg", "【初音ミク】骸骨楽団とリリア【オリジナル曲】"),
    ("bcLYdxMusHc", "TOKIO FUNKA / トキヲ・ファンカ - takamatt feat.GUMI"),
    ("L0tcMxp8Iy8", "歌愛ユキ「いかないで」(remaster)"),
    ("4MgXOeZWu2U", "「Butter-Fly～初音ミクVersion～」みきとP"),
    ("Om3MTou2kPg", "【IA】六兆年と一夜物語【オリジナル曲・PV付】"),
    ("Xg-qfsKN2_E", "みきとP『ロキ』MV"),
    ("_FhgjDhBAWI", "【初音ミク】孤独毒毒【syudou】"),
    ("PAwZl3Up-hc", "『はぐ』/ 初音ミク・可不"),
    ("3em-J9yYPAo", "1000年生きてる / いよわ feat.初音ミク"),
    ("jMKPYg0uhCI", "柊マグネタイト - マーシャル・マキシマイザー / 可不"),
    ("ERo-sPa1a5g", "八王子P × Giga「Gimme×Gimme feat. 初音ミク・鏡音リン」"),
    ("ZB75e7vzX0I", "wowaka『ワールズエンド・ダンスホール』feat. 初音ミク＆巡音ルカ"),
    ("oidKy7khp8o", "初音ミクオリジナル曲「Calc.」"),
    ("7Y9sJvLI3Po", "ジェヘナ(Gehenna) / wotaku feat. 初音ミク"),
    ("YjOzaIXEoPA", "【初音ミク】ブラック★ロックシューター【オリジナル曲】"),
    ("shs0rAiwsGQ", "千本桜 / WhiteFlame feat 初音ミク"),
    ("vnw8zURAxkU", "wowaka『ローリンガール』feat. 初音ミク"),
    ("7zwCIz-Ohn4", "DECO*27 - 乙女解剖 feat. 初音ミク"),
    ("poiZSEjQBgw", "【巡音ルカ GUMI】ハッピーシンセサイザ【オリジナル曲】"),
    # 歌声バンク「ナースロボ_タイプT」の曲と、控えめに優先するボカロP「higma」の曲
    # （いずれも videos.list で埋め込み可・長さ 90〜600 秒を確認済み）
    ("dFNh-Ibxt-Y", "アヴァート / 初音ミク・ナースロボ_タイプT"),
    ("RUzzgOat1xY", "【ナースロボ_タイプT】心象【オリジナル】"),
    ("76gmJU5iasU", "お天使お姉さん / 初音ミク×ナースロボ_タイプT"),
    ("w0zK9LtZC0Q", "higma - ムーンゲイザー feat. 初音ミク"),
    ("KDaMHtlHAj8", "higma - ながいよる feat. 開発コードmiki"),
    ("AXDiqn_E1do", "higma - レター feat. 初音ミク"),
    ("jqlu-FGLayg", "higma - colorful feat.初音ミク"),
    ("fiC_MdCm_qA", "higma - 話は続く feat. AI ナースロボ_タイプT"),
]

# --- Vocaloid BOT の選曲テーマ ---
# 定番の人気順50件に固定されないよう、テーマを「ファミリー」に分けて巡回する。
# 1回のリフレッシュでファミリーをまたいで複数テーマを引き、候補プールに蓄積する。
_VOCALOID_CHARACTERS = [
    "初音ミク オリジナル曲",
    "鏡音リン 鏡音レン オリジナル曲",
    "巡音ルカ オリジナル曲",
    "MEIKO KAITO オリジナル曲",
    "GUMI オリジナル曲",
    "IA flower オリジナル曲",
    "重音テト 可不 星界 オリジナル曲",
    "結月ゆかり 歌愛ユキ オリジナル曲",
    # 歌声合成音声（VOCALOID6 等）のボイスバンクも定番の歌声として扱う。
    # 表記は半角アンダースコア（ナースロボ_タイプT）を正式とするが、
    # タイトル側の全角（＿）も選曲判定では同じものとして扱う。
    "ナースロボ_タイプT オリジナル曲",
]
_VOCALOID_GENRES = [
    "ボカロ ロック オリジナル曲",
    "ボカロ バラード 名曲",
    "ボカロ エレクトロ ダンス オリジナル曲",
    "ボカロ 和風 オリジナル曲",
    "ボカロ ラップ オリジナル曲",
    "ボカロ かわいい ポップ オリジナル曲",
    "ボカロ 切ない 名曲",
    "ボカロ 疾走感 オリジナル曲",
]
# 歌声合成エンジン別（VOCALOID / Synthesizer V / CeVIO など）。
# 人の歌唱（歌ってみた）ではなく合成音声が歌う曲だけを集めるため、
# エンジン名でもテーマを引き、歌声の種類をばらけさせる。
_VOCALOID_ENGINES = [
    "VOCALOID オリジナル曲",
    "Synthesizer V オリジナル曲",
    "CeVIO オリジナル曲",
    "VOICEROID オリジナル曲",
    "UTAU オリジナル曲",
    "NEUTRINO 歌",
    "NEUTRINO オリジナル曲",
    "VOICEVOX 歌",
]
_VOCALOID_PRODUCERS = [
    "DECO*27", "ピノキオピー", "稲葉曇", "ハチ", "wowaka", "みきとP",
    "kemu", "Neru", "40mP", "ナユタン星人", "じん", "はるまきごはん",
    "一二三", "Kikuo", "ツミキ", "すりぃ", "syudou", "n-buna",
    # 追加したボカロP（歌声ではなく制作側なのでこちらに入れる）
    "higma",
]
# 英字表記が定着しているPの別名（チャンネル名の照合に使う）
_VOCALOID_PRODUCER_ALIASES: dict[str, tuple] = {
    "ナユタン星人": ("nayutalien",),
    "ピノキオピー": ("pinocchiop",),
    "稲葉曇": ("inabakumori",),
    "はるまきごはん": ("harumakigohan",),
    "じん": ("jin",),
    "一二三": ("hifumi",),
    "すりぃ": ("surii", "three"),
    "ツミキ": ("tsumiki",),
    "40mP": ("40meterp", "40mp"),
    "みきとP": ("mikitop", "mikito"),
}
_VOCALOID_THEMES: list[dict] = [
    *[{"family": "character", "query": q} for q in _VOCALOID_CHARACTERS],
    *[{"family": "genre", "query": q} for q in _VOCALOID_GENRES],
    *[{"family": "engine", "query": q} for q in _VOCALOID_ENGINES],
    # 新曲（公開日順・最近のもの）と定番（再生数順・殿堂入り）を分けて候補に入れる
    {"family": "era", "query": "ボカロ 新曲 オリジナル曲", "order": "date",
     "published_after_days": 90},
    {"family": "era", "query": "ボカロ オリジナル曲 話題", "order": "date",
     "published_after_days": 365},
    {"family": "era", "query": "ボカロ 名曲 オリジナル曲", "order": "viewCount"},
    {"family": "era", "query": "ボカロ 殿堂入り オリジナル曲", "order": "viewCount"},
    *[
        {"family": "producer", "producer": p, "query": f"{p} ボカロ オリジナル曲"}
        for p in _VOCALOID_PRODUCERS
    ],
]

# ファミリー -> テーマ一覧（ファミリーごとに先頭から順に巡回する）
_VOCALOID_BY_FAMILY: dict[str, list[dict]] = {
    family: [theme for theme in _VOCALOID_THEMES if theme["family"] == family]
    for family in dict.fromkeys(theme["family"] for theme in _VOCALOID_THEMES)
}
# 起動ごとに開始位置を変えて、毎回同じ順番で巡回しないようにする
_vocaloid_index: dict[str, int] = {
    family: random.randrange(len(themes))
    for family, themes in _VOCALOID_BY_FAMILY.items()
}

# 実際に埋め込み再生できなかった動画（このプロセス内で除外する）
_failed_ids: set[str] = set()

# キャッシュ: key -> {"at": float, "items": list[dict]}
_cache: dict[str, dict] = {}

# 直近に選んだ投稿者（チャンネル）。同じボカロPの曲が連続しないようにする。
_RECENT_CHANNEL_WINDOW = 4
_recent_channels: list[str] = []
# 候補プール内で1投稿者（チャンネル）が占められる上限。
# プロデューサーテーマの曲だけでプールが埋まらないようにする。
_MAX_POOL_PER_CHANNEL = 25


def _remember_channel(channel: Optional[str]) -> None:
    """選んだ曲の投稿者を直近リストへ追加する（古いものから捨てる）。"""
    name = (channel or "").strip()
    if not name:
        return
    _recent_channels.append(name)
    if len(_recent_channels) > _RECENT_CHANNEL_WINDOW:
        del _recent_channels[:-_RECENT_CHANNEL_WINDOW]


def _fallback_items(source: str = "trending") -> list[dict]:
    """内蔵プール（APIキー未設定・取得失敗時）。Vocaloid BOT は全て合成音声の歌唱。"""
    tracks = _VOCALOID_FALLBACK if source == "vocaloid" else _FALLBACK
    items = []
    for vid, title in tracks:
        # 歌声合成のクレジット（タイトルにあれば 2、無ければ 1）を付けておく
        level = 0
        if source == "vocaloid":
            level = 2 if _voice_credit(_normalize_text(title), _word_text(title)) else 1
        items.append(
            {
                "youtube_id": vid,
                "title": title,
                "duration": None,
                "fallback": True,
                "synth_level": level,
            }
        )
    return items


# 選曲プールがこれより少ないときは、内蔵リストで補充する。
# （曲数が少ないと、除外しきれずに同じ曲が近い間隔で再登場してしまう）
_MIN_POOL_FOR_ROTATION = 30


def _top_up_with_fallback(items: list[dict], source: str) -> list[dict]:
    """取得できた候補が少ないとき、内蔵リスト（埋め込み確認済み）で補充する。"""
    have = {item["youtube_id"] for item in items}
    extra = [x for x in _fallback_items(source) if x["youtube_id"] not in have]
    return items + extra


def mark_failed(video_id: Optional[str]) -> None:
    """再生できなかった動画をブロックリストに追加する。"""
    if video_id:
        _failed_ids.add(video_id)


# --- Shorts（縦型のショート動画）避け ---
# YouTube Data API には Shorts 判定が無く、サムネイルも 16:9 で返るため、
# タイトル/説明のハッシュタグと動画の長さから推定して除外する。
_SHORTS_MARKERS = (
    "#shorts", "#short", "#ショート", "#ytshorts", "#ytshort",
    "＃shorts", "＃ショート",
)
# これ未満の動画は「曲」ではなく Shorts・クリップとみなす
_MIN_SONG_SECONDS = 90
# 人の歌唱（歌ってみた・演奏してみた等）を示す目印。
# タイトルだけでなくタグ・説明欄でも探す（タイトルに書かれないことが多いため）。
# 日本語の目印は、空白・記号を除いた文字列に含まれるかで判定する。
_HUMAN_JP_MARKERS = (
    "歌ってみた", "歌わせてみた", "歌ってみました", "歌いました", "歌い手",
    "弾いてみた", "演奏してみた", "カバー",
)
# 英字の目印は「単語として」現れるかで判定する
# （sunflower / discover のような語を cover と誤検出しないため）
_HUMAN_EN_MARKERS = ("cover", "utaite")
# ボカロP本人の歌唱（セルフカバー・本人歌唱）。できるだけ避けるため、
# タイトルに歌声合成のクレジットが無ければ除外する（チャンネルでは救済しない）。
_SELF_VOCAL_JP_MARKERS = (
    "セルフカバー", "本人歌唱", "セルフ歌唱", "セルフボーカル", "自分で歌ってみた",
    "歌ってみました", "歌わせて頂きました", "歌わせていただきました",
)
_SELF_VOCAL_EN_MARKERS = ("self cover", "selfcover", "self-cover", "self vocal")
# 曲ではなく宣伝・クロスフェード等の動画
_NON_SONG_JP_MARKERS = ("トレーラー", "クロスフェード", "試聴", "予告")
_NON_SONG_EN_MARKERS = ("trailer", "teaser", "crossfade", "digest", "preview")
# 歌声合成（VOCALOID / Synthesizer V / CeVIO / VOICEROID / UTAU など）のクレジット。
# キャラクター名とエンジン名の両方を見て「合成音声の歌唱」かどうかを判定する。
# 合成音声歌唱優先のため、これが確認できない曲は Vocaloid BOT では流さない。
# 日本語の目印（空白・記号を除いた文字列に含まれるかで判定）
_VOICE_SYNTH_JP_MARKERS = (
    # VOCALOID / Synthesizer V / CeVIO / VOICEROID / UTAU / A.I.VOICE 等の歌声
    "初音ミク", "ミク", "鏡音", "巡音", "ルカ", "重音テト", "歌愛ユキ",
    "結月ゆかり", "波音リツ", "音街ウナ", "可不", "星界", "裏命", "狐子",
    "羽累", "宮舞モカ", "琴葉茜", "琴葉葵", "紲星あかり",
    "東北ずん子", "東北きりたん", "ずんだもん", "四国めたん", "春日部つむぎ",
    "小春六花", "夏色花梨", "花隈千冬", "鳴花ヒメ", "鳴花ミコト",
    "メグッポイド", "蒼姫ラピス",
    # VOCALOID6 等の歌声バンク（初音ミク等と同じ「歌う側」）。
    # 正式表記は半角アンダースコア（ナースロボ_タイプT）。全角（＿）の表記ゆれも
    # 拾えるよう「ナースロボ」で部分一致させる。
    "ナースロボ",
    # エンジン・種別名
    "ボカロ", "ボーカロイド", "ボイスロイド", "歌声合成", "歌唱合成",
)
# 英字の歌声名・エンジン名も単語として判定する（ia / flower 等の短い名前を安全に扱う）
_VOICE_SYNTH_EN_MARKERS = (
    # エンジン名
    "vocaloid", "cevio", "synthv", "synthesizer", "voiceroid", "aivoice",
    "utau", "neutrino", "voicevox", "vflower",
    # キャラクター名
    "hatsune miku", "miku", "kagamine", "megurine luka", "luka", "meiko",
    "kaito", "gumi", "megpoid", "ia", "flower", "fukase", "yuzuki yukari",
    "yukari", "teto", "kasane teto", "kafu", "sekai", "zundamon", "una",
)
# 「初音ミクが歌ってみた」「ずんだもん cover」のように、合成音声自身が歌う書き方。
# タイトルに人の歌唱の目印（歌ってみた・カバー）があっても、この形なら
# 合成音声の歌唱として候補に残す。
_SYNTH_SING_JP_SUFFIXES = (
    "が歌ってみた", "も歌ってみた", "の歌ってみた", "歌ってみた", "が歌う", "が唄う",
)
_SYNTH_SING_EN_SUFFIXES = ("cover", "covers", "sings", "singing")
# Vocaloid BOT が候補として採用する長さの範囲（長いミックスは10分上限で除外）
_VOCALOID_MIN_SECONDS = _MIN_SONG_SECONDS
_VOCALOID_MAX_SECONDS = 600

# 判定用に取り除く記号・空白（日本語マーカー用）
# アンダースコアは全角（＿）・半角（_）を同じものとして扱う
_NAME_NOISE_RE = re.compile(
    r"[\s\u3000\-_\uff3f./|｜*＊+＋（）()【】\[\]「」『』:：;；!！?？、,，・&＆~〜]"
)
# 英字マーカー用：記号を区切りにして単語へ分解する
_WORD_SPLIT_RE = re.compile(r"[^0-9a-z\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]+")
# 「IAオリジナル曲」「GUMIオリジナル曲」のように日本語へ直接くっつく英字も
# 単語として扱えるよう、日英の境界にも区切りを入れる
_ASCII_JP_BOUNDARY_RE = re.compile(
    r"(?<=[0-9a-z])(?=[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff])"
    r"|(?<=[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff])(?=[0-9a-z])"
)


def _normalize_text(value: Optional[str]) -> str:
    """判定用に小文字化し、空白・記号を除去する。"""
    return _NAME_NOISE_RE.sub("", (value or "").lower())


def _title_key(value: Optional[str]) -> str:
    """曲名の比較用キー（小文字化して空白・記号を除去）。"""
    return _normalize_text(value)


def _same_title(a: str, b: str) -> bool:
    """同じ曲名とみなすか（公式MV/remaster等の表記ゆれを許容する）。

    短い方が長い方に含まれ、かつ十分な長さ（8文字以上）があるときだけ
    「同じ曲」と判定する（「マシュマリー」のような短い曲名の誤判定を防ぐ）。
    """
    if not a or not b:
        return False
    if a == b:
        return True
    short, long = sorted((a, b), key=len)
    return len(short) >= 8 and short in long


def _word_text(value: Optional[str]) -> str:
    """英字マーカー判定用に、記号と日英の境界で区切って単語へ分解する。"""
    text = _WORD_SPLIT_RE.sub(" ", (value or "").lower())
    text = _ASCII_JP_BOUNDARY_RE.sub(" ", text)
    return text.strip()


def _has_jp(text: str, markers: tuple) -> bool:
    """（空白除去済みの）テキストに日本語の目印が含まれるか。"""
    return any(marker in text for marker in markers)


def _has_en(words: str, markers: tuple) -> bool:
    """（単語分解済みの）テキストに英字の目印が単語として含まれるか。"""
    padded = f" {words} "
    return any(f" {marker} " in padded for marker in markers)


def _looks_like_shorts(item: dict) -> bool:
    """Shorts らしき動画かどうかを推定する（ハッシュタグ・長さ）。"""
    snippet = item.get("snippet", {})
    text = f"{snippet.get('title') or ''} {snippet.get('description') or ''}"
    text = text.lower().replace(" ", "").replace("\u3000", "")
    if any(marker in text for marker in _SHORTS_MARKERS):
        return True
    duration = parse_iso_duration(item.get("contentDetails", {}).get("duration"))
    return duration is not None and duration < _MIN_SONG_SECONDS


def _view_count(item: dict) -> Optional[int]:
    """再生数（statistics.viewCount）を返す。取得できないときは None。"""
    raw = item.get("statistics", {}).get("viewCount")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _voice_credit(compact: str, words: str) -> bool:
    """歌声合成（VOCALOID / Synthesizer V / CeVIO など）のクレジットがあるか。

    日本語（キャラクター名・エンジン名）と英字（単語として現れる名前）の
    両方を見る。あればその動画は合成音声が歌っている可能性が高い。
    """
    return _has_jp(compact, _VOICE_SYNTH_JP_MARKERS) or _has_en(
        words, _VOICE_SYNTH_EN_MARKERS
    )


def _synth_credit_level(item: dict) -> int:
    """歌声合成のクレジットの強さを返す（合成音声歌唱優先の判定に使う）。

    2 = タイトルにクレジットがある（＝合成音声が歌っていることがほぼ確実）
    1 = タグ・説明欄・投稿者名にクレジットがある
    0 = どこにも無い（合成音声の歌唱と確認できない）
    """
    snippet = item.get("snippet", {})
    raw_title = snippet.get("title")
    if _voice_credit(_normalize_text(raw_title), _word_text(raw_title)):
        return 2
    raw_tags = " ".join(snippet.get("tags") or [])
    raw_meta = (
        f"{raw_tags} {snippet.get('description') or ''} {snippet.get('channelTitle') or ''}"
    )
    if _voice_credit(_normalize_text(raw_meta), _word_text(raw_meta)):
        return 1
    return 0


def _synth_sings_in_title(compact: str, words: str) -> bool:
    """タイトルが「合成音声自身が歌っている」書き方かどうか。

    「初音ミクが歌ってみた」「ずんだもん cover」のように、人の歌唱の目印
    （歌ってみた・カバー）が合成音声を主語に使われている場合は、人の歌唱を
    示す目印として扱わない（＝合成音声の歌唱として候補に残す）。
    """
    if any(
        f"{vocal}{suffix}" in compact
        for vocal in _VOICE_SYNTH_JP_MARKERS
        for suffix in _SYNTH_SING_JP_SUFFIXES
    ):
        return True
    padded = f" {words} "
    return any(
        f" {vocal} {suffix} " in padded
        for vocal in _VOICE_SYNTH_EN_MARKERS
        for suffix in _SYNTH_SING_EN_SUFFIXES
    )


def _channel_matches(producer: str, channel: Optional[str]) -> bool:
    """そのP本人（Topic チャンネル等を含む）の投稿かどうか。"""
    target = _normalize_text(channel)
    if not target:
        return False
    names = [_normalize_text(producer), *_VOCALOID_PRODUCER_ALIASES.get(producer, ())]
    for name in names:
        if not name:
            continue
        if name in target or target in name:
            return True
        # 表記ゆれ対策（例: 40mP → 40meterP）
        if len(name) >= 3 and name[:3] in target:
            return True
    return False


def _producer_key(name: Optional[str]) -> str:
    """名前の比較用キー（小文字化・記号除去。全角/半角のアンダースコアも無視）。

    正式表記は半角（ナースロボ_タイプT）だが、全角（ナースロボ＿タイプT）で
    クレジットされている曲も同じものとして扱う。
    """
    return _normalize_text(name).replace("＿", "").replace("_", "")


def _boosted_names() -> tuple:
    """控えめに優先する名前（.env: DJ_BOT_VOCALOID_BOOST_NAMES）。

    ボカロP（例: higma）と歌声バンク（例: ナースロボ_タイプT）のどちらも指定できる。
    """
    raw = settings.dj_bot_vocaloid_boost_names or ""
    return tuple(name.strip() for name in raw.split(",") if name.strip())


def _is_boosted(
    producer: Optional[str] = None,
    channel: Optional[str] = None,
    title: Optional[str] = None,
) -> bool:
    """控えめに優先する名前の曲か。

    プロデューサー名・チャンネル名・曲名のいずれかに含まれていれば対象にする
    （歌声バンクは曲名側にクレジットされるため、曲名も見る）。
    全角/半角のアンダースコアの違いは無視する。
    """
    boosted = _boosted_names()
    if not boosted:
        return False
    targets = [
        key
        for key in (
            _producer_key(producer),
            _producer_key(channel),
            _producer_key(title),
        )
        if key
    ]
    for name in boosted:
        key = _producer_key(name)
        # 短すぎる名前は誤って一致しやすいので無視する
        if len(key) < 3:
            continue
        for target in targets:
            if key == target or key in target:
                return True
    return False


def _channel_is_trusted(channel: Optional[str], extra_producer: Optional[str] = None) -> bool:
    """ボカロの公式チャンネル・既知のボカロP本人のチャンネルかどうか。"""
    if _has_jp(_normalize_text(channel), _VOICE_SYNTH_JP_MARKERS) or _has_en(
        _word_text(channel), _VOICE_SYNTH_EN_MARKERS
    ):
        return True
    producers = list(_VOCALOID_PRODUCERS)
    if extra_producer:
        producers.append(extra_producer)
    return any(_channel_matches(producer, channel) for producer in producers)


def _unfit_reason(item: dict, producer: Optional[str] = None) -> Optional[str]:
    """Vocaloid BOT の候補として不適切な理由を返す（問題なければ None）。

    プロデューサー名で検索すると、そのPの曲を人間が歌った動画（歌ってみた）や
    別アーティストの動画、アルバムの宣伝・クロスフェードも混ざるため、
    メタ情報（タイトル / タグ / 説明欄 / チャンネル）から判定して除外する。
    合成音声歌唱優先のため、歌声合成のクレジットが確認できない曲も除外する
    （settings.dj_bot_vocaloid_synth_only）。
    """
    snippet = item.get("snippet", {})
    raw_title = snippet.get("title")
    raw_tags = " ".join(snippet.get("tags") or [])
    raw_description = snippet.get("description")
    channel = snippet.get("channelTitle")

    # 日本語マーカー用（空白・記号を除去）と、英字マーカー用（単語に分解）
    title = _normalize_text(raw_title)
    title_words = _word_text(raw_title)
    tags = _normalize_text(raw_tags)
    tags_words = _word_text(raw_tags)
    meta = f"{tags} {_normalize_text(raw_description)}"
    meta_words = f"{tags_words} {_word_text(raw_description)}"

    if (
        _has_jp(title, _NON_SONG_JP_MARKERS)
        or _has_jp(tags, _NON_SONG_JP_MARKERS)
        or _has_en(f"{title_words} {tags_words}", _NON_SONG_EN_MARKERS)
    ):
        return "宣伝・クロスフェード等"

    # ボカロP本人の歌唱（セルフカバー・本人歌唱）はできるだけ避ける
    if _has_jp(f"{title} {meta}", _SELF_VOCAL_JP_MARKERS) or _has_en(
        f"{title_words} {meta_words}", _SELF_VOCAL_EN_MARKERS
    ):
        return "P本人の歌唱"

    # タイトルが人の歌唱（歌ってみた・カバー）でも、合成音声自身が歌う書き方
    # （「初音ミクが歌ってみた」等）なら合成音声の歌唱として候補に残す
    if (
        _has_jp(title, _HUMAN_JP_MARKERS) or _has_en(title_words, _HUMAN_EN_MARKERS)
    ) and not _synth_sings_in_title(title, title_words):
        return "人の歌唱"

    # 歌声合成のクレジットの強さ（2=タイトル / 1=タグ・説明欄・投稿者名 / 0=無し）
    synth_level = _synth_credit_level(item)

    if not _channel_is_trusted(channel, producer):
        # ボカロ公式・既知のPのチャンネルではないので、タイトルに歌声合成の
        # クレジットがある動画だけを候補にする（人の歌唱・別アーティストを避ける）
        if synth_level < 2:
            return "別アーティスト"
        # タイトルにクレジットがあっても、タグ・説明欄が人の歌唱を示すなら除外する
        # （本家のクレジットとしてボカロ名を書く「歌ってみた」動画を避けるため）
        if _has_jp(meta, _HUMAN_JP_MARKERS) or _has_en(meta_words, _HUMAN_EN_MARKERS):
            return "人の歌唱"
        return None

    # ここから下はボカロ公式・既知のボカロP本人のチャンネル。
    # タグ・説明欄の「歌ってみた」は、ボカロ曲の投稿でも付くことがあるため見逃す。
    # その代わり、合成音声歌唱優先で、歌声合成のクレジットが確認できない曲
    # （インスト・P本人の歌唱など）は流さない。
    if settings.dj_bot_vocaloid_synth_only and synth_level == 0:
        return "歌声合成のクレジット無し"
    return None


def _filter_items(items: list[dict], theme: Optional[dict] = None) -> list[dict]:
    """埋め込み可能な通常動画だけを抽出する（Shorts は除外）。

    theme を渡すと Vocaloid BOT 用の判定（人の歌唱・別アーティスト等）も行い、
    歌声合成のクレジットの強さ（synth_level）を候補に付ける。
    """
    out = []
    min_views = max(0, settings.dj_bot_min_views)
    for item in items:
        video_id = item.get("id")
        snippet = item.get("snippet", {})
        status = item.get("status", {})
        if not video_id:
            continue
        if status.get("embeddable") is False:
            continue
        if snippet.get("liveBroadcastContent") not in (None, "none"):
            continue
        if video_id in _failed_ids:
            continue
        # 曲として聴けない Shorts・極端に短いクリップは選曲候補から外す
        if _looks_like_shorts(item):
            continue
        synth_level = 0
        if theme is not None:
            if _unfit_reason(item, theme.get("producer")):
                continue
            synth_level = _synth_credit_level(item)
        views = _view_count(item)
        # 再生数が少なすぎる動画（無人気の投稿）は選曲候補から外す
        if views is not None and views <= min_views:
            continue
        out.append(
            {
                "youtube_id": video_id,
                "title": snippet.get("title"),
                "channel": snippet.get("channelTitle"),
                "views": views,
                "duration": parse_iso_duration(
                    item.get("contentDetails", {}).get("duration")
                ),
                "synth_level": synth_level,
                # 公開日時（新曲・急上昇を優先するために使う）
                "published_at": snippet.get("publishedAt"),
                # 控えめに優先する名前（既定: ナースロボ_タイプT / higma）の曲か
                "boost": theme is not None
                and _is_boosted(
                    theme.get("producer"),
                    snippet.get("channelTitle"),
                    snippet.get("title"),
                ),
            }
        )
    return out


async def _videos_by_ids(ids: list[str], theme: Optional[dict] = None) -> list[dict]:
    """動画IDから snippet/status/contentDetails を取得してフィルタする。"""
    ids = [i for i in ids if i]
    if not ids or not settings.youtube_api_key:
        return []
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,status,contentDetails,statistics",
                    "id": ",".join(ids[:50]),
                    "maxResults": 50,
                    "key": settings.youtube_api_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
    except Exception:
        return []
    return _filter_items(items, theme=theme)


async def _fetch_trending() -> list[dict]:
    """YouTube mostPopular（ミュージック）から取得する。"""
    if not settings.youtube_api_key:
        return []
    params = {
        "part": "snippet,status,contentDetails,statistics",
        "chart": "mostPopular",
        "videoCategoryId": "10",  # Music
        "maxResults": 50,
        "key": settings.youtube_api_key,
    }
    region = (settings.dj_bot_region or "").strip()
    if region:
        params["regionCode"] = region
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/videos", params=params, timeout=10
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
    except Exception:
        return []
    return _filter_items(items)


async def _fetch_search(
    query: str,
    order: str = "viewCount",
    published_after_days: Optional[int] = None,
    theme: Optional[dict] = None,
) -> list[dict]:
    """YouTube 検索クエリ（例: ボカロ）から取得する。

    order: relevance / date / viewCount / rating / title
    published_after_days: 指定すると「この日数以内に公開」に絞る（新曲テーマ用）
    theme: 指定すると Vocaloid BOT 用の判定（人の歌唱・別アーティスト等）も行う
    """
    if not settings.youtube_api_key or not query:
        return []
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "videoEmbeddable": "true",
        "maxResults": 50,
        "order": order,
        "key": settings.youtube_api_key,
    }
    region = (settings.dj_bot_region or "").strip()
    if region:
        params["regionCode"] = region
    if published_after_days:
        after = datetime.now(timezone.utc) - timedelta(days=int(published_after_days))
        params["publishedAfter"] = after.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/search", params=params, timeout=10
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
    except Exception:
        return []
    ids = [item.get("id", {}).get("videoId") for item in items]
    # 埋め込み可否・長さをまとめて取得
    return await _videos_by_ids(ids, theme=theme)


def _cache_key(source: str, query: Optional[str]) -> str:
    return f"{source}:{query or ''}"


def _next_vocaloid_themes(count: int) -> list[dict]:
    """ファミリーをまたいで次のテーマを選ぶ。

    毎回ちがう組み合わせ（歌声・ジャンル・年代・プロデューサー・急上昇）になるよう、
    ファミリーごとの巡回位置を1つずつ進めながら選ぶ。テーマ数がファミリー数を
    超えるときは、同じファミリー内の別テーマを続けて選ぶ。
    急上昇（新曲）も他のファミリーと同じ頻度で巡回する（選曲では公開日の浅さで
    少しだけ後押しする。dj_bot_vocaloid_fresh_bias）。
    """
    families = list(_VOCALOID_BY_FAMILY)
    random.shuffle(families)
    total = min(max(1, count), len(_VOCALOID_THEMES))
    picked: list[dict] = []
    for position in range(total):
        family = families[position % len(families)]
        themes = _VOCALOID_BY_FAMILY[family]
        index = _vocaloid_index[family] % len(themes)
        picked.append(themes[index])
        _vocaloid_index[family] = (index + 1) % len(themes)
    return picked


async def _fetch_vocaloid(themes_per_refresh: Optional[int] = None) -> list[dict]:
    """複数テーマの検索結果を集め、曲として扱いやすい長さのものだけ残す。

    歌声・ジャンル・年代・プロデューサーを横断するため、1回の取得でも
    「いつも同じ人気上位50曲」にならず、歌姫や傾向がばらけた候補になる。
    """
    themes = _next_vocaloid_themes(
        themes_per_refresh or settings.dj_bot_vocaloid_themes_per_refresh
    )
    items: list[dict] = []
    seen: set[str] = set()
    for theme in themes:
        found = await _fetch_search(
            theme["query"],
            order=theme.get("order", "relevance"),
            published_after_days=theme.get("published_after_days"),
            theme=theme,
        )
        for item in found:
            if item["youtube_id"] in seen:
                continue
            seen.add(item["youtube_id"])
            items.append(item)
    # 極端に短い動画（Shorts 等）と長いミックスを除く
    return [
        item for item in items
        if item["duration"] is None
        or _VOCALOID_MIN_SECONDS <= item["duration"] <= _VOCALOID_MAX_SECONDS
    ]


def _cache_ttl_seconds(source: str) -> int:
    """選曲プールのキャッシュ有効期間（秒）。"""
    if source == "vocaloid":
        # 候補を溜めながら少しずつテーマを入れ替えるため、長めに保持する
        return max(30, settings.dj_bot_vocaloid_cache_minutes) * 60
    return max(1, settings.dj_bot_trending_cache_minutes) * 60


def _merge_vocaloid_pool(old: list[dict], new: list[dict]) -> list[dict]:
    """Vocaloid BOT の候補プールを蓄積する。

    プロデューサーテーマは1人の曲がまとめて入るため、投稿者ごとの上限を設けて
    「特定のPばかり流れる」状態にならないようにする。
    """
    cap = max(10, settings.dj_bot_vocaloid_pool_size)
    merged: dict[str, dict] = {}
    per_channel: dict[str, int] = {}
    for item in old + new:
        if item.get("fallback"):
            # API不通時の代替曲は、実際の候補が取れたら混ぜない
            continue
        video_id = item["youtube_id"]
        is_new = video_id not in merged
        channel = (item.get("channel") or "").strip()
        if is_new and channel:
            if per_channel.get(channel, 0) >= _MAX_POOL_PER_CHANNEL:
                continue
            per_channel[channel] = per_channel.get(channel, 0) + 1
        # 既存の曲も末尾へ移して「最新の情報」として残す
        # （新しく取れた急上昇の候補が末尾の切り捨てで消えないようにする）
        merged.pop(video_id, None)
        merged[video_id] = item
    return list(merged.values())[-cap:]


async def pool(source: str = "trending", query: Optional[str] = None) -> list[dict]:
    """選曲プール（キャッシュ付き）。取得できなければフォールバックを返す。"""
    key = _cache_key(source, query)
    ttl = _cache_ttl_seconds(source)
    now = time.time()
    entry = _cache.get(key)
    if entry and entry["items"] and now - entry["at"] < ttl:
        return entry["items"]

    if source == "vocaloid":
        # 起動直後（キャッシュなし）は多めにテーマを引いて、最初から候補を厚くする
        themes = settings.dj_bot_vocaloid_themes_per_refresh * (2 if entry is None else 1)
        items = await _fetch_vocaloid(themes)
        # 内蔵フォールバックだけの状態から復帰したときは、候補を入れ替える
        if items and entry and any(
            not item.get("fallback") for item in entry["items"]
        ):
            items = _merge_vocaloid_pool(entry["items"], items)
    else:
        items = await _fetch_search(query) if source == "search" else await _fetch_trending()
    if items:
        # 取得できた曲が少ないときは内蔵リストで補充する
        # （曲数が少ないと、同じ曲が近い間隔で再登場してしまう）
        if len(items) < _MIN_POOL_FOR_ROTATION:
            items = _top_up_with_fallback(items, source)
        _cache[key] = {"at": now, "items": items}
        return items
    if entry and entry["items"]:
        entry["at"] = now
        return entry["items"]
    items = _fallback_items(source)
    _cache[key] = {"at": now, "items": items}
    return items


def _age_days(item: dict) -> Optional[float]:
    """公開からの経過日数（公開日時が無い・不正なら None）。"""
    raw = item.get("published_at")
    if not raw:
        return None
    try:
        published = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - published).total_seconds() / 86400)


def _popularity_weight(item: dict, source: str = "trending") -> float:
    """選曲の重み。再生数が多い曲ほど選ばれやすくする（人気曲優先）。

    dj_bot_popularity_power で強さを変える（0=等倍＝完全ランダム、
    0.5=控えめに人気曲を優先、1.0=再生数に比例）。
    Vocaloid BOT では合成音声歌唱優先のため、タイトルに歌声合成のクレジットが
    ある曲（synth_level=2）の重みを dj_bot_vocaloid_synth_bias 倍し、さらに
    「最新の急上昇」を優先するため、公開から日が浅い曲の重みを
    dj_bot_vocaloid_fresh_bias で引き上げる。
    """
    power = max(0.0, min(float(settings.dj_bot_popularity_power), 2.0))
    views = item.get("views") or 0
    if power <= 0 or views <= 0:
        # 重み付け無効、または再生数が不明（フォールバック曲など）は等倍
        weight = 1.0
    else:
        weight = float(views) ** power
    if source == "vocaloid":
        if item.get("synth_level") == 2:
            weight *= 1.0 + max(0.0, float(settings.dj_bot_vocaloid_synth_bias))
        # 控えめに優先する名前（既定: ナースロボ_タイプT / higma）の曲
        if item.get("boost"):
            weight *= 1.0 + max(0.0, float(settings.dj_bot_vocaloid_boost_bias))
        # 最新の急上昇を優先: 公開から fresh_days 以内は (1+bias) 倍、
        # その3倍の日数以内は半分のプラス
        fresh_days = max(0, int(settings.dj_bot_vocaloid_fresh_days))
        fresh_bias = max(0.0, float(settings.dj_bot_vocaloid_fresh_bias))
        age = _age_days(item)
        if age is not None and fresh_days > 0 and fresh_bias > 0:
            if age <= fresh_days:
                weight *= 1.0 + fresh_bias
            elif age <= fresh_days * 3:
                weight *= 1.0 + fresh_bias / 2
    return weight


async def random_track(
    exclude_id: Optional[str] = None,
    exclude_ids: Optional[list[str]] = None,
    exclude_titles: Optional[list[str]] = None,
    source: str = "trending",
    query: Optional[str] = None,
) -> Optional[dict]:
    """プールからランダムに1曲選ぶ（失敗済み・最近の曲を避ける）。

    exclude_ids: 直近に流した動画ID（新しい順）
    exclude_titles: 直近に流した曲名（新しい順）。同じ曲の別動画（別投稿）が
      続かないようにするために使う。
    """
    items = await pool(source, query)
    if not items:
        return None
    candidates = [x for x in items if x["youtube_id"] not in _failed_ids]
    if not candidates:
        # 全曲がブロックされた（誤報告やAPI障害など）場合はブロックを解除して
        # 選曲を続ける。ここで空を返すと局が同じ曲のまま止まってしまう。
        _failed_ids.clear()
        candidates = items
    if source == "vocaloid":
        # 合成音声歌唱優先: 歌声合成のクレジットが確認できる曲だけを対象にする
        # （古い候補プールや内蔵プールが混ざっていても人の歌唱を流さない）
        credited = [x for x in candidates if (x.get("synth_level") or 0) > 0]
        candidates = credited or candidates

    # 直近に流した曲（新しい順）。今オンエア中の曲を先頭に置く。
    recent_ids: list[str] = [vid for vid in (exclude_ids or ()) if vid]
    if exclude_id:
        recent_ids.insert(0, exclude_id)
    recent_id_set = set(recent_ids)
    recent_title_keys = [
        key for key in (_title_key(t) for t in (exclude_titles or ())) if key
    ]

    def _id_blocked(item: dict) -> bool:
        return item["youtube_id"] in recent_id_set

    def _title_blocked(item: dict) -> bool:
        if not recent_title_keys:
            return False
        key = _title_key(item.get("title"))
        return bool(key) and any(_same_title(key, r) for r in recent_title_keys)

    choices = [x for x in candidates if not _id_blocked(x) and not _title_blocked(x)]
    if not choices:
        # プールが除外リストより小さいとき（＝内蔵フォールバックに落ちている等）は、
        # 直近に流した順に多めに外し、最後に流れた方から優先して避ける。
        # 全部を除外して「直前の1曲以外」から選ぶと、同じ曲がすぐ再登場して
        # しまう（例: 12曲しかないのに30曲除外 → 恋愛裁判が30分後に再登場）。
        keep = max(2, len(candidates) // 3)
        block = max(0, len(candidates) - keep)
        blocked_ids = set(recent_ids[:block])
        id_ok = [x for x in candidates if x["youtube_id"] not in blocked_ids]
        # 曲名が同じ（＝同じ曲の別動画）ものはさらに後回しにする
        choices = [x for x in id_ok if not _title_blocked(x)] or id_ok
        if not choices:
            # それでも残らないときは、せめて直前の1曲だけは避ける
            choices = [x for x in candidates if x["youtube_id"] != exclude_id] or candidates
    # 同じ投稿者（ボカロPなど）の曲が続かないように、直近の投稿者は後回しにする
    recent_channels = set(_recent_channels)
    preferred = [
        x for x in choices
        if (x.get("channel") or "").strip()
        and (x.get("channel") or "").strip() not in recent_channels
    ]
    finalists = preferred or choices
    # 再生数の多い曲ほど選ばれやすくする（人気曲優先。重みが全て等倍なら一様抽選）。
    # 加えて Vocaloid BOT はタイトルに歌声合成のクレジットがある曲を優先する。
    weights = [_popularity_weight(x, source) for x in finalists]
    if all(weight == 1.0 for weight in weights):
        pick = random.choice(finalists)
    else:
        pick = random.choices(finalists, weights=weights, k=1)[0]
    _remember_channel(pick.get("channel"))
    return pick
