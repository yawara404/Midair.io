<template>
  <footer class="site-footer">
    <div class="site-footer__links">
      <button
        v-for="key in KEYS"
        :key="key"
        class="site-footer__link"
        type="button"
        @click="open(key)"
      >
        {{ PAGES[key].title }}
      </button>
    </div>
    <p class="site-footer__copy">
      © {{ year }} Midair<span>.io</span> — 深夜ラジオのアジト
    </p>
  </footer>

  <!-- 情報モーダル（プライバシーポリシー / 利用規約 / サイトマップ / 運営情報） -->
  <Teleport to="body">
    <div v-if="current" class="info-modal" @click.self="close">
      <div
        class="info-modal__panel"
        role="dialog"
        aria-modal="true"
        :aria-label="current.title"
      >
        <div class="info-modal__head">
          <span class="info-modal__title">{{ current.title }}</span>
          <button class="info-modal__close" type="button" aria-label="閉じる" @click="close">✕</button>
        </div>
        <div class="info-modal__body">
          <p v-if="current.updated" class="info-modal__updated">最終更新: {{ current.updated }}</p>
          <section v-for="(sec, i) in current.sections" :key="i" class="info-modal__sec">
            <h4 v-if="sec.h">{{ sec.h }}</h4>
            <p v-if="sec.p" class="info-modal__p">{{ sec.p }}</p>
            <ul v-if="sec.items">
              <li v-for="(item, j) in sec.items" :key="j">{{ item }}</li>
            </ul>
            <div v-if="sec.links" class="info-modal__links">
              <template v-for="(link, j) in sec.links" :key="j">
                <router-link
                  v-if="link.to"
                  class="info-modal__link"
                  :to="link.to"
                  @click="close"
                >→ {{ link.label }}</router-link>
                <a
                  v-else
                  class="info-modal__link"
                  :href="link.href"
                  target="_blank"
                  rel="noopener"
                >→ {{ link.label }}</a>
              </template>
            </div>
          </section>
        </div>
        <div class="info-modal__foot">
          <button class="btn btn--ghost" type="button" @click="close">閉じる</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'

// 運営者情報（必要なら書き換えてください）
const OPERATOR = {
  github: 'https://github.com/yawara404/Midair.io',
  publicUrl: 'https://music.wawa-app.me/Midair.io/',
}
const UPDATED = '2026-09-26'

const KEYS = ['about', 'privacy', 'terms', 'sitemap']

const PAGES = {
  about: {
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

const current = ref(null)
const year = new Date().getFullYear()

// ハッシュでモーダルを直リンクできるようにする（Google 認証のポリシーURL用）
//   例: /#privacy  /#terms  /#sitemap  /#about
// ※ スタンドアロン版はハッシュをルーティングに使うため、そのときは URL を触らない
const USE_HASH_LINK = !__STANDALONE__
const HASH_ALIASES = {
  privacy: 'privacy',
  'privacy-policy': 'privacy',
  policy: 'privacy',
  terms: 'terms',
  'terms-of-service': 'terms',
  sitemap: 'sitemap',
  'site-map': 'sitemap',
  about: 'about',
  info: 'about',
}

function keyFromHash() {
  const raw = (window.location.hash || '').replace(/^#\/?/, '').trim().toLowerCase()
  if (!raw) return null
  const key = HASH_ALIASES[raw] || raw
  return PAGES[key] ? key : null
}

// URL のハッシュをモーダルの状態に合わせる（履歴を1つ積むので「戻る」で閉じられる）
function applyHash(key) {
  if (!USE_HASH_LINK) return
  if (key) {
    if (window.location.hash === `#${key}`) return
    window.history.pushState(null, '', `#${key}`)
    return
  }
  if (!window.location.hash) return
  window.history.pushState(null, '', window.location.pathname + window.location.search)
}

function open(key) {
  const page = PAGES[key] || null
  current.value = page
  applyHash(page ? key : null)
}

function close() {
  const had = Boolean(current.value)
  current.value = null
  if (had) applyHash(null)
}

function onKeydown(e) {
  if (e.key === 'Escape') close()
}

// 直リンク（/#privacy など）やブラウザの戻る/進むに追従する
function onHashChange() {
  const key = keyFromHash()
  if (key) current.value = PAGES[key]
  else if (current.value) current.value = null
}

// モーダル表示中は Esc で閉じ、背面のスクロールを止める
watch(current, (page) => {
  if (page) {
    document.addEventListener('keydown', onKeydown)
    document.body.style.overflow = 'hidden'
  } else {
    document.removeEventListener('keydown', onKeydown)
    document.body.style.overflow = ''
  }
})

onMounted(() => {
  if (!USE_HASH_LINK) return
  window.addEventListener('hashchange', onHashChange)
  // ハッシュ付きで開かれた場合はそのモーダルを表示する
  const key = keyFromHash()
  if (key) current.value = PAGES[key]
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
  if (USE_HASH_LINK) window.removeEventListener('hashchange', onHashChange)
})
</script>

<style scoped>
/* ===== フッター（ホーム下部。全文字を白で統一） ===== */
.site-footer {
  margin-top: 22px;
  padding: 14px 16px 18px;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px 16px;
}
.site-footer__links {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
}
.site-footer__link {
  background: none;
  border: none;
  padding: 0;
  font-family: inherit;
  font-size: 12px;
  letter-spacing: 0.02em;
  color: var(--green);
  cursor: pointer;
  border-bottom: 1px dashed var(--line-strong);
}
.site-footer__link:hover {
  color: var(--green);
  border-bottom-color: var(--green);
  border-bottom-style: solid;
}
.site-footer__copy {
  margin: 0;
  font-size: 11px;
  letter-spacing: 1px;
  color: var(--green);
}

/* ===== 情報モーダル ===== */
.info-modal {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.72);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px 14px;
  overflow-y: auto;
}
.info-modal__panel {
  display: flex;
  flex-direction: column;
  width: min(660px, 100%);
  max-height: 86vh;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  border-top: 3px solid var(--green);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.8);
  margin: auto;
}
.info-modal__head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line-strong);
}
.info-modal__title {
  font-size: 15px;
  letter-spacing: 1px;
  color: var(--green);
}
.info-modal__close {
  background: none;
  border: none;
  color: var(--green);
  font-size: 14px;
  cursor: pointer;
  padding: 2px 6px;
}
.info-modal__close:hover {
  color: var(--green);
}
.info-modal__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  padding: 14px 16px 6px;
}
.info-modal__updated {
  margin: 0 0 12px;
  font-size: 11px;
  color: var(--green);
}
.info-modal__sec {
  margin-bottom: 16px;
}
.info-modal__sec h4 {
  margin: 0 0 6px;
  font-size: 12px;
  letter-spacing: 1px;
  color: var(--green);
  border-left: 2px solid var(--green);
  padding-left: 8px;
}
.info-modal__sec ul {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.info-modal__sec li,
.info-modal__p {
  font-size: 12px;
  line-height: 1.75;
  color: var(--green);
}
.info-modal__p {
  margin: 0;
}
.info-modal__links {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.info-modal__link {
  font-size: 12px;
  line-height: 1.7;
  color: var(--green);
  text-decoration: none;
  border-bottom: 1px dashed var(--line-strong);
  padding: 2px 0;
}
.info-modal__link:hover {
  color: var(--green);
  border-bottom-color: var(--green);
}
.info-modal__foot {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  padding: 10px 16px;
  border-top: 1px solid var(--line-strong);
}

@media (max-width: 560px) {
  .site-footer {
    flex-direction: column;
    align-items: flex-start;
    padding: 12px;
  }
  .info-modal {
    padding: 12px 10px;
  }
  .info-modal__panel {
    max-height: 90vh;
  }
  .info-modal__body {
    padding: 12px 12px 4px;
  }
}
</style>

