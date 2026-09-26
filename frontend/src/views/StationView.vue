<template>
  <div class="station-view">
    <div class="station-view__grid">
      <div class="station-view__tuner">
        <RadioTuner
          :channels="stations"
          :current-frequency="dialFrequency"
          :tuned-frequency="frequency"
          :listener-count="listenerCount"
          show-commit
          :can-commit="canCommit"
          @change-frequency="onDial"
          @commit="commitDial"
        />
        <!-- ダイヤルが空き周波数を指しているときは、そのまま切り替えずに案内する -->
        <p v-if="dialDiffers && !pendingStation" class="station-view__hint">
          {{ dialFrequency.toFixed(1) }}MHz は空き周波数です（放送なし）。
          <router-link to="/frequencies">周波数マップ</router-link> から開局できます。
        </p>
      </div>

      <section class="station-view__stream">
        <div class="now">
          <span class="now__dot" :class="{ 'is-live': currentStation && currentStation.is_live }"></span>
          {{ currentStation ? currentStation.callsign : '—' }}
          <span v-if="currentStation && currentStation.is_bot" class="now__bot">🤖 AUTO DJ</span>
          <span class="now__freq">{{ frequency.toFixed(1) }} MHz</span>
          <button
            v-if="auth.isLoggedIn"
            class="btn btn--ghost now__fav"
            @click="toggleFavorite"
          >
            {{ favorited ? '★' : '☆' }}
          </button>
        </div>

        <!-- スレッド情報（2chライク） -->
        <div class="thread-bar">
          <span class="thread-bar__no">第{{ thread ? thread.number : 1 }}スレ</span>
          <span class="thread-bar__title">{{ currentStation ? currentStation.callsign : '—' }}</span>
          <span class="thread-bar__count">{{ thread ? thread.post_count : 0 }} / {{ maxPosts }}</span>
          <router-link
            v-if="currentStation"
            class="thread-bar__archive"
            :to="`/archive?station=${currentStation.id}`"
          >過去スレ</router-link>
        </div>

        <ChatStream :messages="messages" :my-handle="handle" />
        <MessageInput
          :disabled="!connected"
          @send="sendChat"
          @request-youtube="requestYoutube"
          @call-dj="callDj"
        />
      </section>

      <div class="station-view__side">
        <RadioPlayer
          :video-id="playerTrack.videoId"
          :started-at="playerTrack.startedAt"
          :channel-name="currentStation ? currentStation.callsign : ''"
          :status="currentStation ? currentStation.status : ''"
          @player-error="onPlayerError"
          @ended="onPlayerEnded"
        />
        <PlayLog
          :station-id="currentStation ? currentStation.id : null"
          :latest="latestTrack"
          :reload-key="trackReloadKey"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import RadioTuner from '../components/RadioTuner.vue'
import ChatStream from '../components/ChatStream.vue'
import MessageInput from '../components/MessageInput.vue'
import RadioPlayer from '../components/RadioPlayer.vue'
import PlayLog from '../components/PlayLog.vue'
import { api, getToken, wsHost, wsPath } from '../api'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const stations = ref([])
// 受信中の周波数（チャット・再生・スレッドが連動する）
const frequency = ref(80.0)
// チューナーのダイヤル位置（決定するまで局は切り替わらない）
const dialFrequency = ref(80.0)
const messages = ref([])
const thread = ref(null)
const maxPosts = ref(1000)
const handle = ref('')
const connected = ref(false)
const listenerCount = ref(0)
const track = ref({ videoId: null, startedAt: null })
// 再生ログ（PlayLog）をリアルタイム更新するための受け渡し
const latestTrack = ref(null)
const trackReloadKey = ref(0)
const favorited = ref(false)

let socket = null

const currentStation = computed(
  () => stations.value.find((s) => Math.abs(s.frequency - frequency.value) < 0.05) || null
)

// ダイヤルが指している局（決定する前のプレビュー）
const pendingStation = computed(
  () => stations.value.find((s) => Math.abs(s.frequency - dialFrequency.value) < 0.05) || null
)
// ダイヤルと受信中がずれているか（＝決定できる状態か）
const dialDiffers = computed(() => Math.abs(dialFrequency.value - frequency.value) >= 0.05)
const canCommit = computed(() => Boolean(pendingStation.value) && dialDiffers.value)

// 停波中（砂嵐）の局では曲を再生しない
// （古い current_youtube_id が残っていても、砂嵐の裏で鳴り続けないようにする）
const playerTrack = computed(() => {
  if (currentStation.value && currentStation.value.status === 'off_air') {
    return { videoId: null, startedAt: null }
  }
  return track.value
})

function wsUrl(stationId) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const token = getToken()
  const qs = token ? `?token=${encodeURIComponent(token)}` : ''
  return `${proto}://${wsHost()}${wsPath()}/${stationId}${qs}`
}

function connect(stationId) {
  if (socket) {
    socket.onclose = null
    socket.onmessage = null
    socket.close()
  }
  connected.value = false
  socket = new WebSocket(wsUrl(stationId))
  socket.onopen = () => {
    connected.value = true
  }
  socket.onclose = () => {
    connected.value = false
  }
  socket.onmessage = (event) => {
    let data
    try {
      data = JSON.parse(event.data)
    } catch {
      return
    }
    handleEvent(data)
  }
}

function handleEvent(data) {
  switch (data.type) {
    case 'welcome':
      handle.value = data.handle
      if (data.track) {
        track.value = { videoId: data.track.youtube_video_id, startedAt: data.track.playback_started_at }
      }
      break
    case 'message':
      messages.value.push(data)
      if (thread.value) thread.value.post_count += 1
      break
    case 'message_deleted':
      messages.value = messages.value.filter((m) => m.id !== data.id)
      break
    case 'thread_update':
      // 1000投稿に達して新スレへ切り替わった
      if (data.thread) {
        thread.value = data.thread
        messages.value = []
      }
      break
    case 'system':
      messages.value.push({
        id: `sys-${Date.now()}-${Math.random()}`,
        author: 'SYS',
        content: data.content,
        message_type: 'system',
      })
      if (data.listener_count != null) listenerCount.value = data.listener_count
      break
    case 'track_update':
      track.value = { videoId: data.youtube_video_id, startedAt: data.playback_started_at }
      // 再生ログをリロードなしで更新（track が無いイベントは再取得で追随）
      if (data.track) {
        latestTrack.value = { ...data.track, _at: Date.now() }
      } else {
        trackReloadKey.value += 1
      }
      break
    case 'live_update':
      if (currentStation.value) {
        currentStation.value.is_live = data.is_live
        if (data.status) currentStation.value.status = data.status
      }
      break
    case 'frequency_status':
      if (currentStation.value && Math.abs(currentStation.value.frequency - data.frequency) < 0.05) {
        currentStation.value.status = data.status
        currentStation.value.is_live = data.status === 'live'
      }
      break
    case 'error':
      messages.value.push({
        id: `err-${Date.now()}-${Math.random()}`,
        author: 'SYS',
        content: data.content,
        message_type: 'system',
      })
      break
  }
}

// 現在スレッドと投稿ログを読み込む
async function loadThread(stationId) {
  try {
    const res = await api(`/stations/${stationId}/thread`)
    thread.value = res.thread || null
    maxPosts.value = res.max_posts || 1000
    messages.value = res.messages || []
  } catch (e) {
    thread.value = null
    messages.value = []
  }
}

async function loadStations() {
  try {
    const res = await api('/stations')
    stations.value = res.stations || []
    if (!stations.value.length) return
    const routeId = Number(route.params.id)
    const target = stations.value.find((s) => s.id === routeId) || stations.value[0]
    tuneTo(target)
  } catch (e) {
    console.error(e)
  }
}

// チューナーのダイヤル操作。この時点では局を切り替えない（決定ボタンで切り替える）
function onDial(freq) {
  dialFrequency.value = Math.round(freq * 10) / 10
}

// ダイヤルで合わせた局に切り替える。
// URL を更新（＝履歴に積む）してから切り替えるので、ブラウザの戻る/進むで局を行き来できる。
function commitDial() {
  const s = pendingStation.value
  if (!s || !dialDiffers.value) return
  if (Number(route.params.id) === s.id) {
    // URL は既にこの局を指している（直接来た場合など）→ 受信だけ切り替える
    tuneTo(s)
    return
  }
  router.push(`/station/${s.id}`)
}

// 局に合わせる（決定時・履歴の移動時・初回表示時の共通処理）
function tuneTo(station) {
  if (!station) return
  frequency.value = station.frequency
  dialFrequency.value = station.frequency
  listenerCount.value = station.listener_count || 0
  track.value = { videoId: station.current_youtube_id, startedAt: station.playback_started_at }
  loadThread(station.id)
  connect(station.id)
  refreshFavorite()
}

function sendChat(text) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: 'chat', content: text }))
  }
}

function requestYoutube(value) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: 'youtube_request', url: value }))
  }
}

function callDj(text) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: 'dj_call', content: text }))
  }
}

// 曲が最後まで再生されたときの報告
//  - 自動DJ局: 次曲へ（バックエンドが選曲）
//  - 通常局/専用局: 曲終了を報告（通常局は砂嵐にするため。専用局はエンジンが次曲を送出）
async function onPlayerEnded({ videoId } = {}) {
  const s = currentStation.value
  if (!s || !videoId) return
  try {
    if (s.is_bot) {
      await api(`/stations/${s.id}/bot/ended`, {
        method: 'POST',
        body: JSON.stringify({ video_id: videoId }),
      })
    } else {
      await api(`/stations/${s.id}/track-ended`, {
        method: 'POST',
        body: JSON.stringify({ video_id: videoId, reason: 'ended' }),
      })
    }
  } catch (e) {
    /* 自動DJ局はバックエンドのループが次曲を処理する */
  }
}

// 埋め込み再生できなかった曲の報告（自動DJ局は次曲へ、通常局は砂嵐にする）
async function onPlayerError({ videoId } = {}) {
  const s = currentStation.value
  if (!s || !videoId) return
  try {
    if (s.is_bot) {
      await api(`/stations/${s.id}/bot/report`, {
        method: 'POST',
        body: JSON.stringify({ video_id: videoId }),
      })
    } else {
      await api(`/stations/${s.id}/track-ended`, {
        method: 'POST',
        body: JSON.stringify({ video_id: videoId, reason: 'error' }),
      })
    }
  } catch (e) {
    /* 失敗時は何もしない（次曲はバックエンド/パーソナリティが処理する） */
  }
}

async function refreshFavorite() {
  const s = currentStation.value
  if (!s || !auth.isLoggedIn) {
    favorited.value = false
    return
  }
  try {
    const res = await api('/favorites')
    favorited.value = (res.favorites || []).some((f) => f.id === s.id)
  } catch (e) {
    favorited.value = false
  }
}

async function toggleFavorite() {
  const s = currentStation.value
  if (!s || !auth.isLoggedIn) return
  try {
    if (favorited.value) {
      await api(`/stations/${s.id}/favorite`, { method: 'DELETE' })
      favorited.value = false
    } else {
      await api(`/stations/${s.id}/favorite`, { method: 'POST' })
      favorited.value = true
    }
  } catch (e) {}
}

watch(
  () => route.params.id,
  (id) => {
    // チューナーの決定・ブラウザの戻る/進む・直リンクのいずれでもここを通る
    const s = stations.value.find((x) => x.id === Number(id))
    if (s) tuneTo(s)
  }
)

onMounted(loadStations)
onBeforeUnmount(() => {
  if (socket) socket.close()
})
</script>

<style scoped>
/* 画面高さいっぱいに固定し、チャット欄は内部スクロールさせる */
.station-view {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.station-view__grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 300px 1fr 320px;
  gap: 16px;
}
/* グリッド項目の min-width:auto によるトラック拡大（横見切れ）を防ぐ */
.station-view__grid > * {
  min-width: 0;
}
/* チューナー列（ラッパー）。PC では中身を縦いっぱいに伸ばす */
.station-view__tuner {
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
}
.station-view__tuner :deep(.tuner) {
  flex: 1;
  min-height: 0;
}
.station-view__stream {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.station-view__side {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  overflow-y: auto;
}
/* チューナー列も高さに収めてスクロール可能に */
.station-view :deep(.tuner) {
  min-height: 0;
  overflow-y: auto;
}
/* ダイヤルが空き周波数を指しているときの案内（掲示板は切り替えない） */
.station-view__hint {
  margin: 8px 0 0;
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--text-dim);
}
.station-view__hint a {
  color: var(--green);
  text-decoration: underline;
}

.now {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  font-size: 14px;
  color: var(--hi);
}
.now__dot {
  width: 10px;
  height: 10px;
  background: var(--dim);
}
.now__dot.is-live {
  background: var(--hi);
  animation: blink 1.6s infinite;
}
.now__bot {
  font-size: 10px;
  letter-spacing: 1px;
  color: var(--green);
  border: 1px solid var(--line-strong);
  padding: 2px 6px;
}
.now__freq {
  margin-left: auto;
  color: var(--green);
  font-variant-numeric: tabular-nums;
}
.now__fav {
  margin-left: 8px;
}

/* スレッドバー（2chライク） */
.thread-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  margin: 8px 0 10px;
  background: var(--panel-deep);
  border: 1px solid var(--line-strong);
  font-size: 12px;
  flex-wrap: wrap;
}
.thread-bar__no {
  color: #000;
  background: var(--green);
  font-weight: 700;
  padding: 2px 8px;
  letter-spacing: 1px;
}
.thread-bar__title {
  color: var(--text);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.thread-bar__count {
  color: var(--text-dim);
  font-variant-numeric: tabular-nums;
}
.thread-bar__archive {
  color: var(--green);
  text-decoration: none;
  border: 1px solid var(--line-strong);
  padding: 2px 8px;
}
.thread-bar__archive:hover {
  background: var(--green);
  color: #000;
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

@media (max-width: 1080px) {
  /* モバイルは縦積み。チャットを画面いっぱいに近づける */
  .station-view {
    height: auto;
  }
  .station-view__grid {
    grid-template-columns: 1fr;
    gap: 10px;
  }
  .station-view__stream {
    /* ビューポート高さいっぱいのチャット（vh は古いブラウザ用フォールバック） */
    height: calc(100vh - 118px);
    height: calc(100dvh - 118px);
    min-height: 500px;
    max-height: 1200px;
  }
  .station-view__side {
    overflow: visible;
  }
  .station-view :deep(.tuner) {
    overflow: visible;
  }
}

@media (max-width: 560px) {
  .station-view__grid {
    gap: 8px;
  }
  .station-view__stream {
    height: calc(100vh - 108px);
    height: calc(100dvh - 108px);
    min-height: 460px;
  }
  .now {
    flex-wrap: wrap;
    font-size: 12px;
    gap: 6px;
    padding: 6px 10px;
    margin-bottom: 5px;
  }
  .now__freq {
    margin-left: auto;
  }
  .thread-bar {
    padding: 5px 9px;
    margin: 5px 0 6px;
    font-size: 11px;
    gap: 6px;
  }
  .thread-bar__archive {
    padding: 2px 6px;
  }
}
</style>
