// サイト情報（フッターの情報モーダルと /about /privacy /terms /sitemap の各ページで共用）
//
// URL はハッシュ（#privacy 等）ではなく通常のパス（/privacy）で直リンクできます。
// Google OAuth の同意画面に登録するポリシーURLも、フラグメント無しのこのパスを使います。

// 運営者情報（必要なら書き換えてください）
export const OPERATOR = {
  github: 'https://github.com/yawara404/Midair.io',
  publicUrl: 'https://music.wawa-app.me/Midair.io/',
}
export const UPDATED = '2026-09-26'

export const KEYS = ['about', 'privacy', 'terms', 'sitemap']

export const PAGES = {
  about: {
    path: '/about',
    title: 'このサイトについて',
    sections: [
      {
        p: 'Midair.io（ミッドエア）は、周波数ダイヤルを合わせて各チャンネル（局）に入る、24時間リアルタイムの匿名ラジオ掲示板です。リスナーは「名無し」で聴くことができ、空き周波数を取得すると自分で開局（パーソナリティ）して放送できます。',
      },
      {
        h: '周波数は2つのエリア',
        items: [
          '専用局帯（既定 76.0〜79.9MHz）— 24時間常設の専用局の申請専用エリア',
          '自由な周波数（既定 80.0〜89.0MHz）— 誰でも自由に開局・時間枠予約できる一般エリア',
          '総スロット数は 131（76.0〜89.0MHz / 0.1MHz刻み）で固定です',
        ],
      },
      {
        h: '仕組み',
        items: [
          'フロントエンド: Vue 3 + Vite（単一ソースから Web版 / スタンドアロン版を生成）',
          'バックエンド: FastAPI + SQLAlchemy + WebSocket',
          '楽曲再生: YouTube 公式埋め込みプレイヤー（IFrame Player API）',
          'AI DJ / AIチャットbot: LLM（Gemini / OpenAI互換 API / ローカル Ollama）で自由生成',
        ],
      },
      {
        h: '運営・お問い合わせ',
        items: [
          '個人開発の実験サービスです。予告なく内容の変更・停止を行うことがあります。',
          'お問い合わせは下記までお願いします（運営者情報は必要に応じて追記します）。',
        ],
        links: [
          { label: 'GitHub リポジトリ（Issue）', href: OPERATOR.github },
          { label: '公開URLを開く', href: OPERATOR.publicUrl },
        ],
      },
    ],
  },
  privacy: {
    path: '/privacy',
    title: 'プライバシーポリシー',
    updated: UPDATED,
    sections: [
      {
        h: '取得する情報',
        items: [
          '匿名で利用する場合: ランダムなニックネーム（例: 名無しのリスナー#1234）と投稿本文のみ。氏名・住所・電話番号などは取得しません。',
          'アカウント登録時: ユーザー名・メールアドレス・パスワード（bcrypt でハッシュ化して保存し、原文は保存しません）・権限（ロール）。',
          'Discord ログインを利用した場合: Discord のユーザーID・表示名・アバター画像URL。',
          '投稿・放送に関する記録: チャット本文、投稿時刻、スレッド、放送セッション、再生した曲のログ、お気に入り、専用局の申請内容。',
          'アクセスログ: サーバーの運用ログに IP アドレスやリクエスト内容が記録されることがあります（障害対応・不正防止のため）。',
        ],
      },
      {
        h: '利用目的',
        items: [
          'サービスの提供（チャットの配信、放送の同期、番組表の表示など）',
          'AI DJ / AIチャットbot の返信・コメントの生成',
          '不正利用の防止、障害対応、サービス改善のための統計把握',
        ],
      },
      {
        h: '外部サービスへの送信',
        items: [
          'AI DJ / AIチャットbot: 返信やコメントを生成するため、直近の会話と現在オンエア中の曲名を、運営者が設定した LLM プロバイダ（Google Gemini／OpenAI 互換 API／ローカル Ollama）へ送信します。ローカル Ollama を使う場合、これらの内容は外部へ送信されません。',
          'Discord: 運営者が Discord 連携を有効にした局では、その局のチャットが Discord へ転送されます（Discord 側の投稿が本サイトに取り込まれることもあります）。',
          'YouTube: 楽曲の再生は YouTube の公式埋め込みプレイヤーで行うため、Google／YouTube のプライバシーポリシーが適用されます。',
        ],
      },
      {
        h: 'Cookie・ローカルストレージ',
        items: [
          '広告・アクセス解析を目的とした Cookie は使用していません。',
          'ログイン状態を保つため、お使いのブラウザの localStorage にトークン（midair_token）とユーザー情報（midair_user）を保存します。ログアウトすると削除されます。',
        ],
      },
      {
        h: 'アクセス解析',
        items: [
          'アクセス解析ツールは導入していません（Google Search Console の所有権確認用メタタグのみ）。',
        ],
      },
      {
        h: '保存期間と削除',
        items: [
          '投稿は過去ログ（アーカイブ）として保持されます。局を廃局すると、その局のチャット・番組・再生ログは削除されます。',
          'アカウント情報や投稿の削除をご希望の場合は、下記の連絡先へご連絡ください。',
        ],
      },
      {
        h: 'お問い合わせ',
        items: [
          '未成年の方は保護者の同意を得たうえでご利用ください。',
          '本ポリシーは必要に応じて改定します（重要な変更はサイト上で告知します）。',
        ],
        links: [{ label: 'GitHub リポジトリ（Issue）', href: OPERATOR.github }],
      },
    ],
  },

  terms: {
    path: '/terms',
    title: '利用規約・免責',
    updated: UPDATED,
    sections: [
      {
        h: '禁止事項',
        items: [
          '誹謗中傷、差別的表現、脅迫、個人情報（本名・住所・勤務先など）の晒し',
          '違法行為の勧誘・犯罪予告、権利（著作権・商標・肖像権など）を侵害する行為',
          '宣伝・スパム・連投など、他のリスナーの利用を妨げる行為',
          'なりすまし、サービスへの不正アクセス・過度な負荷をかける行為',
          'YouTube をはじめとする外部サービスの利用規約に反する行為',
        ],
      },
      {
        h: '投稿と放送の扱い',
        items: [
          '投稿内容は匿名でも記録されます。1スレッド 1000 投稿に達すると自動でアーカイブされ、次のスレッドが作成されます。',
          '運営者およびパーソナリティは、規約違反や不適切と判断した投稿を予告なく削除・非表示にできます（モデレーション）。',
          '放送（選曲・DJ コメント・番組内容）の責任は、その局のパーソナリティに帰属します。',
        ],
      },
      {
        h: '著作権',
        items: [
          '楽曲は YouTube の公式埋め込みプレイヤーで再生され、権利は各権利者に帰属します。本サイトは音源を保持・配布しません。',
          'AI DJ / AIチャットbot のコメントは LLM による生成物であり、内容の正確性を保証しません。',
        ],
      },
      {
        h: '免責',
        items: [
          '本サービスは現状有姿で提供され、可用性・継続性・データの保全を保証しません。予告なく変更・停止・データが失われることがあります。',
          '本サービスの利用によって生じた損害について、運営者は責任を負いかねます。',
          '本規約は必要に応じて改定します（重要な変更はサイト上で告知します）。',
        ],
      },
    ],
  },
  sitemap: {
    path: '/sitemap',
    title: 'サイトマップ',
    sections: [
      {
        h: 'ページ',
        links: [
          { label: 'ホーム（周波数チューナー）', to: '/' },
          { label: '周波数を探す / 開局', to: '/stations' },
          { label: '周波数マップ（空き・予約・専用局）', to: '/frequencies' },
          { label: '番組表（タイムテーブル）', to: '/timetable' },
          { label: '過去ログ（アーカイブ）', to: '/archive' },
          { label: 'ログイン / 新規登録', to: '/login' },
          { label: 'スタジオ（自分の局の運営・要ログイン）', to: '/studio' },
          { label: 'マイページ（要ログイン）', to: '/profile' },
          { label: '専用局（要ログイン）', to: '/dedicated' },
          { label: '管理（管理者のみ）', to: '/admin' },
        ],
      },
      {
        h: '主な機能',
        items: [
          '周波数チューナー — ダイヤルで局を選ぶ（専用局エリア / 自由な周波数を OSD 表示）',
          '匿名チャット・2chライクなスレッド・過去ログ',
          'YouTube BGM 同期再生と再生ログ',
          'AI DJ — 「DJさん」「hey DJ」で呼びかけ / 曲連動コメント / 曲紹介コメント',
          '開局と時間枠予約 / 24時間常設の専用局（申請承認制）',
          '自動DJ局「DJ BOT」「Vocaloid BOT」「管理者セレクト」、AIチャットbot「Miaちゃん」',
        ],
      },
      {
        h: '関連ファイル',
        items: [
          'sitemap.xml — 検索エンジン向けのサイトマップ（本ページの下のリンクから開けます）',
          'llms.txt — AI エージェント向けのサイト情報',
        ],
        links: [{ label: 'sitemap.xml を開く', href: `${OPERATOR.publicUrl}sitemap.xml` }],
      },
    ],
  },
}

/** パスからページを引く（/privacy → PAGES.privacy） */
export function pageByPath(path) {
  const clean = String(path || '').replace(/\/+$/, '') || '/'
  const key = KEYS.find((k) => PAGES[k].path === clean)
  return key ? PAGES[key] : null
}
