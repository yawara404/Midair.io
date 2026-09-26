<template>
  <div class="app-shell">
    <header class="app-nav">
      <!-- モバイル用ハンバーガーボタン（左上） -->
      <button
        class="app-nav__burger"
        :class="{ 'is-open': menuOpen }"
        type="button"
        aria-label="メニュー"
        :aria-expanded="menuOpen ? 'true' : 'false'"
        @click.stop="menuOpen = !menuOpen"
      >
        <span></span><span></span><span></span>
      </button>

      <router-link to="/" class="app-nav__brand">Midair<span>.io</span></router-link>

      <nav class="app-nav__links" :class="{ 'is-open': menuOpen }" @click="menuOpen = false">
        <router-link to="/" class="app-nav__home">ホーム</router-link>
        <router-link to="/stations">周波数を探す</router-link>
        <router-link to="/frequencies">周波数マップ</router-link>
        <router-link to="/timetable">番組表</router-link>
        <router-link to="/studio">スタジオ</router-link>
        <router-link v-if="auth.isAdmin" to="/admin" class="app-nav__admin">管理</router-link>
      </nav>
      <div class="app-nav__auth">
        <template v-if="auth.isLoggedIn">
          <router-link to="/profile" class="app-nav__user" title="マイページ">
            {{ auth.user?.username || 'マイページ' }}
          </router-link>
          <button class="btn btn--ghost" @click="auth.logout()">ログアウト</button>
        </template>
        <router-link v-else to="/login" class="btn btn--ghost">ログイン</router-link>
      </div>

      <!-- ヘルプメニュー（右上） -->
      <div class="app-nav__help" :class="{ 'is-open': helpOpen }">
        <button
          class="app-nav__help-btn"
          type="button"
          aria-label="ヘルプ"
          :aria-expanded="helpOpen ? 'true' : 'false'"
          title="ヘルプ"
          @click.stop="helpOpen = !helpOpen"
        >?</button>
        <div v-if="helpOpen" class="help" @click.stop>
          <div class="help__head">
            <span>ヘルプ</span>
            <button class="help__close" type="button" aria-label="閉じる" @click="helpOpen = false">✕</button>
          </div>

          <div class="help__body">
            <section class="help__sec">
              <h4>はじめかた</h4>
              <ul>
                <li><b>ホーム</b>：周波数ダイヤルで局を選ぶ（±0.1は長押しで連続調整）</li>
                <li><b>掲示板へ</b>：選んだ局のチャットに参加（匿名OK）</li>
                <li><b>周波数マップ</b>：空きスロットの確認・開局・予約・専用局の申請</li>
              </ul>
            </section>
            <section class="help__sec">
              <h4>周波数は2つのエリアに分かれています</h4>
              <ul>
                <li>
                  <b>専用局帯（{{ dedicatedText }}）</b>：
                  24時間常設の専用局の申請専用。一般の開局・時間枠予約はできません
                </li>
                <li>
                  <b>自由な周波数（{{ freeText }}）</b>：
                  誰でも自由に開局・時間枠予約できる一般エリア。専用局は作れません
                </li>
                <li>ダイヤルの位置は OSD に <b>DEDICATED AREA / FREE AREA</b> として表示されます</li>
              </ul>
            </section>
            <section class="help__sec">
              <h4>DJと話す</h4>
              <ul>
                <li>DJは「<b>DJさん</b>」「<b>hey DJ</b>」と呼びかけたときだけ返事します（大文字小文字・全角半角は問いません）</li>
                <li>「<b>DJを呼ぶ</b>」ボタンでも呼べます</li>
                <li>無言の時間が続くと、DJが<b>約2分おきに独り口</b>を話します（<b>今流れている曲</b>に連動して内容が変わります）</li>
                <li>AIチャットbotの「Miaちゃん」局（88.0MHz）は呼びかけなしでも返信します</li>
              </ul>
            </section>
            <section class="help__sec">
              <h4>DJ（パーソナリティ）の使い方</h4>
              <ul>
                <li>
                  <b>開局</b>：「周波数を探す」→「＋ 開局する」で空き周波数（自由な周波数 {{ freeText }}）を選び、
                  コールサイン・放送方針・AI DJキャラクターを設定します
                </li>
                <li>
                  <b>スタジオ</b>：局の編集／BGM切替（YouTube URL）／ミュート／ON AIR・OFF AIR／廃局／番組表の追加
                </li>
                <li>
                  <b>AI DJの設定</b>：スタジオの「AI DJ」チェックで有効・無効、キャラクター設定で口調や呼び方を指定
                  （例: 落ち着いた低音の深夜DJ）。設定は返信・曲コメント・曲紹介に反映されます
                </li>
                <li>
                  <b>呼びかけ必須</b>：リスナーが「DJさん」「hey DJ」と呼んだときだけ返事します
                  （「DJを呼ぶ」ボタンも可）。無言の時間が続いたときは<b>約2分おきに独り口</b>を話します
                </li>
                <li>
                  <b>曲に連動</b>：DJの独り口は<b>今流れている曲</b>に触れます（BGMを切り替えると内容も変わります）
                </li>
                <li>
                  <b>リクエスト</b>：リスナーは「♪ リクエスト」で曲を投げられます（BGMは変わりません）。
                  流す曲はBGM切替・番組のBGM動画ID・専用局の音源プールで決まります
                </li>
                <li>
                  <b>24時間流すには</b>：{{ autoOffText }}で自動停波するため、
                  常設したい場合は専用局（{{ dedicatedText }}）を申請してください（専用局は自動停波の対象外）
                </li>
                <li>
                  <b>おまかせで流す</b>：プリセット局「DJ BOT」（84.0MHz）／「Vocaloid BOT」（85.0MHz）が
                  24時間ランダム選曲でオンエアしています（登録不要・そのまま聴けます）
                </li>
              </ul>
            </section>
            <section class="help__sec">
              <h4>放送のルール</h4>
              <ul>
                <li>
                  <b>切り忘れ対策</b>：{{ autoOffText }}で自動停波します
                  （専用局・自動DJ局・番組枠は対象外）
                </li>
                <li>停波（OFF AIR）のスロットは砂嵐表示。周波数は廃局するまで確保されます</li>
                <li>停波の前に放送内で予告が流れます</li>
              </ul>
            </section>
            <section class="help__sec">
              <h4>主な機能</h4>
              <ul>
                <li><b>周波数を探す</b>：局の一覧。空き周波数（自由な周波数）で開局できます</li>
                <li><b>番組表</b>：日別の番組予定（EPG）。開始/終了で自動 ON AIR・停波</li>
                <li><b>スタジオ</b>：自分の局の編集・BGM・AI DJ・番組管理</li>
                <li><b>マイページ</b>：右上のユーザー名から。局管理・曲のログ</li>
                <li><b>専用局</b>：周波数マップ内の申請フォームから（専用局帯のみ・24時間常設）</li>
              </ul>
            </section>
            <section class="help__sec">
              <h4>権限について</h4>
              <ul>
                <li>リスナー：チャット・リクエスト・専用局の申請</li>
                <li>パーソナリティ：開局した局の運営（BGM切替・ON AIR/停波・モデレーション）</li>
                <li>専用局マスター：承認された専用局の運営</li>
                <li>管理者：専用局申請の審査（管理メニュー）</li>
              </ul>
            </section>
            <p class="help__foot">Midair.io — 深夜ラジオのアジト</p>
          </div>
        </div>
      </div>
    </header>
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { api } from './api'

const auth = useAuthStore()
const route = useRoute()
// モバイルのハンバーガーメニュー開閉
const menuOpen = ref(false)
// ヘルプメニュー開閉
const helpOpen = ref(false)

// ヘルプに載せる周波数帯・切り忘れ対策の設定（/api/bands から取得。失敗時は既定値を表示）
const BANDS_FALLBACK = {
  bands: [
    { key: 'dedicated', dedicated: true, min: 76.0, max: 79.9 },
    { key: 'free', dedicated: false, min: 80.0, max: 89.0 },
  ],
  auto_off: { after_minutes: 360, idle_minutes: 120, notice_minutes: 5 },
}
const bandInfo = ref(BANDS_FALLBACK)

function rangeText(bands) {
  if (!bands.length) return '—'
  return bands.map((b) => `${b.min.toFixed(1)}〜${b.max.toFixed(1)}MHz`).join(' と ')
}

function minutesText(minutes) {
  if (minutes >= 60 && minutes % 60 === 0) return `${minutes / 60}時間`
  return `${minutes}分`
}

const dedicatedText = computed(() =>
  rangeText(bandInfo.value.bands.filter((b) => b.dedicated))
)
const freeText = computed(() =>
  rangeText(bandInfo.value.bands.filter((b) => !b.dedicated))
)
// 「ON AIR から6時間、または無人（リスナー0人）のまま2時間」形式
const autoOffText = computed(() => {
  const cfg = bandInfo.value.auto_off || {}
  const parts = []
  if (cfg.after_minutes > 0) parts.push(`ON AIR から${minutesText(cfg.after_minutes)}`)
  if (cfg.idle_minutes > 0) parts.push(`無人（リスナー0人）のまま${minutesText(cfg.idle_minutes)}`)
  if (!parts.length) return '放置された放送は停波しません（自動停波は無効）'
  return parts.join('、または ')
})

// 遷移したら閉じる
watch(
  () => route.fullPath,
  () => {
    menuOpen.value = false
    helpOpen.value = false
  }
)

// メニュー外をクリックしたら閉じる
function onDocClick(e) {
  const nav = document.querySelector('.app-nav')
  if (nav && !nav.contains(e.target)) menuOpen.value = false
  const help = document.querySelector('.app-nav__help')
  if (help && !help.contains(e.target)) helpOpen.value = false
}
watch([menuOpen, helpOpen], ([m, h]) => {
  if (m || h) document.addEventListener('click', onDocClick, true)
  else document.removeEventListener('click', onDocClick, true)
})
onBeforeUnmount(() => document.removeEventListener('click', onDocClick, true))

onMounted(async () => {
  await auth.hydrateFromUrl()
  // 保存済みトークンだけある状態でもユーザー情報を読み込む
  await auth.ensureUser()
  // ヘルプに載せる帯域・切り忘れ対策の設定（失敗時は既定値のまま）
  try {
    const res = await api('/bands')
    if (res && res.bands) {
      bandInfo.value = {
        bands: res.bands,
        auto_off: res.auto_off || BANDS_FALLBACK.auto_off,
      }
    }
  } catch (e) {
    /* 既定値で表示する */
  }
})
</script>

<style>
:root {
  --bg: #080808;
  --panel: #101010;
  --panel-deep: #0b0b0b;
  --green: #ffffff;
  --green-dim: #2a2a2a;
  --amber: #e8e8e8;
  --amber-dim: #1a1a1a;
  --text: #e8e8e8;
  --text-dim: #8a8a8a;
  --line: #2a2a2a;
  --line-strong: #555555;
  --faint: #3f3f3f;
  --red: #ffffff;
}

* {
  box-sizing: border-box;
}

html,
body,
#app {
  margin: 0;
  padding: 0;
  height: 100%;
}

body {
  background-color: var(--bg);
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: 40px 40px;
  color: var(--text);
  font-family: "Hiragino Kaku Gothic ProN", "Noto Sans JP", "Osaka-Mono", Menlo, Consolas, monospace;
  -webkit-font-smoothing: antialiased;
}

/* 共通ボタン */
.btn {
  font-family: inherit;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid var(--line-strong);
  background: #0b0b0b;
  color: var(--text);
  padding: 8px 14px;
  border-radius: 0;
  letter-spacing: 0.02em;
  transition: all 0.12s ease;
  text-decoration: none;
  display: inline-block;
}
.btn:hover:not(:disabled) {
  background: var(--green);
  color: #000;
  border-color: var(--green);
}
.btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.btn--primary {
  background: var(--green);
  border-color: var(--green);
  color: #000;
  font-weight: 700;
}
.btn--primary:hover:not(:disabled) {
  background: #d6d6d6;
  border-color: #d6d6d6;
  color: #000;
}
.btn--amber {
  background: var(--amber-dim);
  border-color: var(--line-strong);
  color: var(--green);
  font-weight: 700;
}
.btn--amber:hover:not(:disabled) {
  background: var(--green);
  color: #000;
}
.btn--ghost {
  background: transparent;
  border-color: var(--line-strong);
  color: var(--text-dim);
}
.btn--ghost:hover:not(:disabled) {
  color: var(--green);
  background: transparent;
  border-color: var(--green);
}

/* ナビゲーション */
.app-shell {
  height: 100vh;
  height: 100dvh;
  display: flex;
  flex-direction: column;
}
.app-nav {
  position: relative;
  display: flex;
  align-items: center;
  gap: 22px;
  padding: 14px 26px;
  background: #0b0b0b;
  border-bottom: 1px solid var(--line-strong);
}
.app-nav::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -5px;
  height: 5px;
  background-image: repeating-linear-gradient(45deg, #1c1c1c 0 6px, #0a0a0a 6px 12px);
}
.app-nav__brand {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 2px;
  color: var(--green);
  text-decoration: none;
}
.app-nav__brand span {
  color: var(--text-dim);
  font-weight: 400;
}
/* ハンバーガーボタン（モバイルのみ表示） */
.app-nav__burger {
  display: none;
}
.app-nav__links {
  display: flex;
  gap: 4px;
}
.app-nav__links a {
  color: var(--text-dim);
  text-decoration: none;
  font-size: 13px;
  padding: 8px 12px;
  border: 1px solid transparent;
  letter-spacing: 1px;
}
.app-nav__links a:hover {
  color: var(--green);
}
.app-nav__links a.router-link-active {
  color: var(--green);
  border-color: var(--line-strong);
  background: #111;
}
/* ホームは完全一致のときだけアクティブ（他のページで点灯しないように） */
.app-nav__links a.app-nav__home.router-link-active {
  color: var(--text-dim);
  border-color: transparent;
  background: transparent;
}
.app-nav__links a.app-nav__home.router-link-exact-active {
  color: var(--green);
  border-color: var(--line-strong);
  background: #111;
}
.app-nav__auth {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}
.app-nav__user {
  color: var(--green);
  font-size: 13px;
  text-decoration: none;
  border-bottom: 1px dotted transparent;
}
.app-nav__user:hover {
  border-bottom-color: var(--green);
}
.app-nav__user.router-link-active {
  border-bottom-color: var(--green);
}

/* ===== ヘルプメニュー（右上） ===== */
.app-nav__help {
  position: relative;
  flex-shrink: 0;
}
.app-nav__help-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: inherit;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-dim);
  background: transparent;
  border: 1px solid var(--line-strong);
  border-radius: 50%;
  cursor: pointer;
  transition: all 0.12s ease;
}
.app-nav__help-btn:hover,
.app-nav__help.is-open .app-nav__help-btn {
  color: #000;
  background: var(--green);
  border-color: var(--green);
}
.help {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  width: min(420px, calc(100vw - 24px));
  max-height: 76vh;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.7);
  z-index: 80;
}
.help::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background-image: repeating-linear-gradient(45deg, #1c1c1c 0 6px, #0a0a0a 6px 12px);
}
.help__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--line-strong);
  color: var(--green);
  font-size: 14px;
  letter-spacing: 1px;
}
.help__close {
  background: none;
  border: none;
  color: var(--text-dim);
  font-size: 14px;
  cursor: pointer;
  padding: 0 4px;
}
.help__close:hover {
  color: var(--green);
}
.help__body {
  padding: 12px 14px 16px;
}
.help__sec {
  margin-bottom: 14px;
}
.help__sec h4 {
  margin: 0 0 6px;
  font-size: 12px;
  letter-spacing: 1px;
  color: var(--green);
  border-left: 2px solid var(--green);
  padding-left: 8px;
}
.help__sec ul {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.help__sec li {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-dim);
}
.help__sec li b {
  color: var(--text);
}
.help__foot {
  margin: 4px 0 0;
  padding-top: 10px;
  border-top: 1px dashed var(--line-strong);
  font-size: 10px;
  letter-spacing: 1px;
  color: var(--faint);
  text-align: center;
}

.app-main {
  flex: 1;
  min-height: 0;
  padding: 22px 26px;
  overflow-y: auto;
}

/* ===== モバイル最適化 ===== */
@media (max-width: 900px) {
  .app-nav {
    flex-wrap: nowrap;
    gap: 8px;
    padding: 10px 12px;
  }
  .app-nav__brand {
    font-size: 18px;
    padding: 6px 0;
  }
  .app-nav__auth {
    margin-left: auto;
    gap: 6px;
  }
  .app-nav__user {
    padding: 8px 4px;
    font-size: 13px;
  }
  .app-nav__auth .btn {
    min-height: 36px;
    padding: 8px 12px;
  }
  .app-nav__help-btn {
    width: 36px;
    height: 36px;
  }

  /* ハンバーガーボタン（左上） */
  .app-nav__burger {
    display: inline-flex;
    flex-shrink: 0;
    flex-direction: column;
    justify-content: center;
    gap: 4px;
    width: 40px;
    height: 34px;
    padding: 0 9px;
    background: transparent;
    border: 1px solid var(--line-strong);
    cursor: pointer;
  }
  .app-nav__burger span {
    display: block;
    height: 2px;
    background: var(--green);
    transition: transform 0.15s ease, opacity 0.15s ease;
  }
  .app-nav__burger.is-open span:nth-child(1) {
    transform: translateY(6px) rotate(45deg);
  }
  .app-nav__burger.is-open span:nth-child(2) {
    opacity: 0;
  }
  .app-nav__burger.is-open span:nth-child(3) {
    transform: translateY(-6px) rotate(-45deg);
  }

  /* ナビはドロップダウンで格納 */
  .app-nav__links {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    z-index: 50;
    display: none;
    flex-direction: column;
    gap: 0;
    margin: 0;
    padding: 4px 0;
    background: #0b0b0b;
    border-bottom: 1px solid var(--line-strong);
    box-shadow: 0 14px 30px rgba(0, 0, 0, 0.6);
  }
  .app-nav__links.is-open {
    display: flex;
  }
  .app-nav__links a {
    padding: 12px 18px;
    border: none;
    border-bottom: 1px solid var(--line);
    font-size: 14px;
  }
  .app-nav__links a:last-child {
    border-bottom: none;
  }
  .app-nav__links a.router-link-active {
    background: #151515;
  }
  .app-nav__links a.app-nav__home.router-link-active {
    color: var(--text-dim);
    background: transparent;
  }
  .app-nav__links a.app-nav__home.router-link-exact-active {
    color: var(--green);
    background: #151515;
  }

  .app-main {
    padding: 10px 12px;
  }
}
@media (max-width: 520px) {
  .app-nav {
    gap: 8px;
    padding: 10px;
  }
  .app-nav__brand {
    font-size: 16px;
    letter-spacing: 1px;
  }
  .app-nav__links a {
    font-size: 13px;
    letter-spacing: 0.3px;
    padding: 11px 16px;
  }
  .app-main {
    padding: 8px;
  }
  .btn {
    font-size: 12px;
    padding: 7px 10px;
  }
}
</style>
