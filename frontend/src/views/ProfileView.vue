<template>
  <div class="profile">
    <p v-if="!auth.isLoggedIn" class="profile__guest">
      マイページを見るにはログインしてください。
      <router-link to="/login">ログイン</router-link>
    </p>

    <template v-else>
      <!-- プロフィール -->
      <div class="profile__card">
        <div class="profile__avatar">{{ initial }}</div>
        <div class="profile__info">
          <h2 class="profile__name">{{ user.username || '—' }}</h2>
          <p class="profile__meta">
            <span class="role" :class="`role--${user.role}`">{{ roleLabel }}</span>
            <span v-if="user.email">{{ user.email }}</span>
            <span v-if="user.created_at">登録: {{ fmtDate(user.created_at) }}</span>
          </p>
        </div>
      </div>

      <!-- 統計 -->
      <div class="stats">
        <div class="stat"><span class="stat__num">{{ stats.stations }}</span><span class="stat__label">保有局</span></div>
        <div class="stat"><span class="stat__num">{{ stats.sessions }}</span><span class="stat__label">放送セッション</span></div>
        <div class="stat"><span class="stat__num">{{ stats.messages }}</span><span class="stat__label">メッセージ</span></div>
        <div class="stat"><span class="stat__num">{{ stats.favorites }}</span><span class="stat__label">お気に入り</span></div>
      </div>

      <!-- 局管理 -->
      <section class="block">
        <div class="block__head">
          <h3>局管理</h3>
          <div class="block__head-actions">
            <button class="btn btn--ghost" @click="loadStations">↻ 更新</button>
            <router-link class="btn btn--primary" to="/stations">＋ 開局する</router-link>
          </div>
        </div>
        <p v-if="!stations.length" class="block__empty">まだ局を持っていません。</p>
        <div v-for="s in stations" :key="s.id" class="st">
          <div class="st__main">
            <span class="st__freq">{{ s.frequency.toFixed(1) }} MHz</span>
            <span class="st__name">{{ s.callsign }}</span>
            <span class="st__live" :class="{ 'is-live': s.is_live }">{{ s.is_live ? '● ON AIR' : '○ OFF' }}</span>
            <span class="st__listeners">LISTENER {{ s.listener_count }}</span>
          </div>
          <div class="st__actions">
            <router-link class="btn btn--ghost" :to="`/station/${s.id}`">聴く</router-link>
            <button v-if="s.status !== 'live'" class="btn btn--ghost" @click="setAir(s, 'on-air')">ON AIR</button>
            <button v-else class="btn btn--ghost" @click="setAir(s, 'off-air')">OFF AIR</button>
            <button class="btn btn--ghost" @click="closeStation(s)">廃局</button>
          </div>
        </div>
      </section>

      <!-- 過去スレッド（アーカイブ） -->
      <section class="block">
        <div class="block__head">
          <h3>過去スレッド（アーカイブ）</h3>
          <router-link class="btn btn--ghost" to="/archive">アーカイブを開く</router-link>
        </div>
        <p class="block__empty">放送ごとのチャットログは「アーカイブ」に保存されます。</p>
      </section>

      <!-- 過去の放送セッション -->
      <section class="block">
        <div class="block__head">
          <h3>過去の放送セッション</h3>
          <button class="btn btn--ghost" @click="loadSessions">↻ 更新</button>
        </div>
        <p v-if="!sessions.length" class="block__empty">まだ放送セッションがありません。</p>
        <div v-for="s in sessions" :key="s.id" class="sess">
          <span class="sess__title">{{ s.session_title }}</span>
          <span class="sess__meta">{{ s.frequency != null ? s.frequency.toFixed(1) : '—' }}MHz {{ s.station_callsign }}</span>
          <span class="sess__meta">{{ fmt(s.started_at) }} ・ {{ mmss(s.duration_seconds || 0) }} ・ {{ s.total_messages }}件</span>
          <span v-if="s.is_live" class="sess__live">● 放送中</span>
        </div>
      </section>

      <!-- お気に入り -->
      <section class="block">
        <div class="block__head">
          <h3>お気に入り局</h3>
          <button class="btn btn--ghost" @click="loadFavorites">↻ 更新</button>
        </div>
        <p v-if="!favorites.length" class="block__empty">お気に入りはまだありません。</p>
        <div v-else class="fav">
          <router-link
            v-for="f in favorites"
            :key="f.id"
            class="fav__item"
            :to="`/station/${f.id}`"
          >
            <span class="fav__freq">{{ f.frequency.toFixed(1) }}</span>
            <span class="fav__name">{{ f.callsign }}</span>
          </router-link>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const user = ref(auth.user || {})
const stats = ref({ stations: 0, sessions: 0, messages: 0, favorites: 0 })
const stations = ref([])
const sessions = ref([])
const favorites = ref([])

const initial = computed(() => (user.value.username || '?').slice(0, 1).toUpperCase())
const roleLabel = computed(
  () =>
    ({ listener: 'リスナー', broadcaster: 'パーソナリティ', admin: '管理者' }[user.value.role] ||
      user.value.role ||
      '')
)

function pad(n) {
  return String(n).padStart(2, '0')
}
function fmt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
function fmtDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
}
function mmss(s) {
  s = Math.max(0, Math.floor(s || 0))
  return `${pad(Math.floor(s / 60))}:${pad(s % 60)}`
}

async function loadProfile() {
  try {
    const res = await api('/me')
    user.value = res.user || {}
    stats.value = res.stats || stats.value
  } catch (e) {
    console.error(e)
  }
}
async function loadStations() {
  try {
    const res = await api('/stations/mine')
    stations.value = res.stations || []
  } catch (e) {
    stations.value = []
  }
}
async function loadSessions() {
  try {
    const res = await api('/me/sessions?limit=50')
    sessions.value = res.sessions || []
  } catch (e) {
    sessions.value = []
  }
}
async function loadFavorites() {
  try {
    const res = await api('/favorites')
    favorites.value = res.favorites || []
  } catch (e) {
    favorites.value = []
  }
}

async function setAir(s, action) {
  try {
    const res = await api(`/stations/${s.id}/${action}`, { method: 'POST' })
    s.status = res.status
    s.is_live = res.status === 'live'
  } catch (e) {
    console.error(e)
  }
}

async function closeStation(s) {
  if (!confirm('廃局して周波数を返還しますか？（チャット・番組も削除されます）')) return
  try {
    await api(`/stations/${s.id}`, { method: 'DELETE' })
    stations.value = stations.value.filter((x) => x.id !== s.id)
    await loadProfile()
  } catch (e) {
    console.error(e)
  }
}

onMounted(async () => {
  if (!auth.isLoggedIn) return
  await Promise.all([loadProfile(), loadStations(), loadTracks(), loadSessions(), loadFavorites()])
})
</script>

<style scoped>
.profile__guest {
  color: var(--text-dim);
  font-size: 14px;
}
.profile__guest a {
  color: var(--green);
}

.profile__card {
  display: flex;
  align-items: center;
  gap: 18px;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  padding: 20px;
  position: relative;
}
.profile__card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background-image: repeating-linear-gradient(45deg, #1c1c1c 0 6px, #0a0a0a 6px 12px);
}
.profile__avatar {
  width: 64px;
  height: 64px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: 800;
  color: #000;
  background: var(--green);
}
.profile__name {
  margin: 0 0 6px;
  font-size: 22px;
  color: var(--green);
}
.profile__meta {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  font-size: 12px;
  color: var(--text-dim);
}
.role {
  font-size: 11px;
  letter-spacing: 1px;
  padding: 2px 8px;
  border: 1px solid var(--line-strong);
  color: var(--text-dim);
}
.role--broadcaster,
.role--admin {
  color: var(--green);
  border-color: var(--green);
}

.stats {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
  margin: 16px 0;
}
.stat {
  background: var(--panel);
  border: 1px solid var(--line-strong);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: center;
}
.stat__num {
  font-size: 26px;
  color: var(--green);
  font-variant-numeric: tabular-nums;
}
.stat__label {
  font-size: 11px;
  color: var(--text-dim);
  letter-spacing: 1px;
}

.block {
  background: var(--panel);
  border: 1px solid var(--line-strong);
  margin-bottom: 16px;
}
.block__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line-strong);
}
.block__head h3 {
  margin: 0;
  font-size: 15px;
  color: var(--green);
  letter-spacing: 1px;
}
.block__head-actions {
  display: flex;
  gap: 8px;
}
.block__empty {
  padding: 18px 16px;
  color: var(--text-dim);
  font-size: 12px;
}

.st {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line);
  flex-wrap: wrap;
}
.st:last-child {
  border-bottom: none;
}
.st__main {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
  flex: 1;
}
.st__freq {
  color: var(--green);
  font-variant-numeric: tabular-nums;
}
.st__name {
  color: var(--text);
}
.st__live {
  font-size: 11px;
  color: var(--text-dim);
}
.st__live.is-live {
  color: var(--green);
  animation: blink 1.8s infinite;
}
.st__listeners {
  font-size: 11px;
  color: var(--text-dim);
}
.st__actions {
  display: flex;
  gap: 8px;
}

.log-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  max-width: 100%;
  min-width: 0;
}
.log {
  min-width: 520px;
  border-collapse: collapse;
}
/* モバイルでは曲ログを縦積みにして見切れをなくす */
@media (max-width: 640px) {
  .log-wrap {
    overflow-x: visible;
  }
  .log {
    min-width: 0;
    width: 100%;
  }
  .log thead {
    display: none;
  }
  .log tr {
    display: block;
    padding: 10px 14px;
    border-bottom: 1px solid var(--line);
  }
  .log td {
    display: block;
    border: none;
    padding: 2px 0;
  }
  .log__freq,
  .log__time {
    display: inline;
    margin-right: 10px;
  }
  /* 曲リンクをタップしやすい高さに */
  .log__track a {
    display: block;
    padding: 6px 0;
    font-size: 13px;
  }
  .log__session {
    display: block;
    font-size: 11px;
  }
}
.log th,
.log td {
  text-align: left;
  padding: 10px 14px;
  border-bottom: 1px solid var(--line);
  font-size: 12px;
  vertical-align: top;
}
.log th {
  color: var(--text-dim);
  font-weight: 400;
  letter-spacing: 2px;
  font-size: 11px;
  border-bottom: 1px solid var(--line-strong);
}
.log__time {
  color: var(--text-dim);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.log__freq {
  color: var(--green);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.log__st {
  color: var(--text-dim);
  margin-left: 6px;
}
.log__track a {
  color: var(--text);
  text-decoration: none;
  display: inline-block;
}
.log__track a:hover {
  color: var(--green);
  text-decoration: underline;
}
.log__session {
  color: var(--text-dim);
}

.sess {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--line);
  flex-wrap: wrap;
}
.sess:last-child {
  border-bottom: none;
}
.sess__title {
  color: var(--green);
}
.sess__meta {
  font-size: 11px;
  color: var(--text-dim);
  font-variant-numeric: tabular-nums;
}
.sess__live {
  font-size: 11px;
  color: var(--green);
  animation: blink 1.8s infinite;
}

.fav {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 14px 16px;
}
.fav__item {
  display: flex;
  gap: 8px;
  align-items: baseline;
  text-decoration: none;
  border: 1px solid var(--line-strong);
  padding: 6px 10px;
  color: var(--text-dim);
}
.fav__item:hover {
  border-color: var(--green);
  color: var(--green);
}
.fav__freq {
  color: var(--green);
  font-variant-numeric: tabular-nums;
}
.fav__name {
  font-size: 12px;
}

@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.25;
  }
}

@media (max-width: 720px) {
  .stats {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 560px) {
  .profile__card {
    flex-direction: column;
    text-align: center;
    gap: 12px;
  }
  .profile__meta {
    justify-content: center;
  }
  .block__head {
    flex-wrap: wrap;
  }
  .st {
    align-items: flex-start;
  }
  .st__main {
    flex-basis: 100%;
  }
  .st__actions {
    width: 100%;
    flex-wrap: wrap;
  }
  .st__actions .btn {
    flex: 1;
    text-align: center;
  }
  .sess {
    gap: 6px 12px;
  }
}
</style>
