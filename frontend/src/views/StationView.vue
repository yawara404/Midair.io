<template>
  <div class="station-view">
    <div class="station-view__grid">
      <RadioTuner
        :channels="stations"
        :current-frequency="frequency"
        :listener-count="listenerCount"
        @change-frequency="changeFrequency"
      />

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
          :video-id="track.videoId"
          :started-at="track.startedAt"
          :channel-name="currentStation ? currentStation.callsign : ''"
          :status="currentStation ? currentStation.status : ''"
          @player-error="onPlayerError"
          @ended="onPlayerEnded"
        />

        <!-- 再生ログ（NOW PLAYING の履歴） -->
        <section class="tracklog">
          <div class="tracklog__head">
            <span>再生ログ</span>
            <button class="btn btn--ghost tracklog__refresh" @click="loadTrackLog">↻</button>
          </div>
          <div class="tracklog__body">
            <p v-if="!trackLog.length" class="tracklog__empty">まだ曲のログがありません。</p>
            <a
              v-for="t in trackLog"
              :key="t.id"
              class="tracklog__item"
              :class="{ 'is-current': t.youtube_id === track.videoId }"
              :href="`https://youtu.be/${t.youtube_id}`"
              target="_blank"
              rel="noopener"
            >
              <span class="tracklog__time">{{ fmtTime(t.played_at) }}</span>
              <MarqueeText class="tracklog__title" :text="t.title || t.youtube_id" />
            </a>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import RadioTuner from '../components/RadioTuner.vue'
import ChatStream from '../components/ChatStream.vue'
import MessageInput from '../components/MessageInput.vue'
import RadioPlayer from '../components/RadioPlayer.vue'
import MarqueeText from '../components/MarqueeText.vue'
import { api, getToken, wsHost } from '../api'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const auth = useAuthStore()

const stations = ref([])
const frequency = ref(80.0)
const messages = ref([])
const handle = ref('')
const connected = ref(false)
const listenerCount = ref(0)
const track = ref({ videoId: null, startedAt: null })
const favorited = ref(false)
const trackLog = ref([])

let socket = null

const currentStation = computed(
  () => stations.value.find((s) => Math.abs(s.frequency - frequency.value) < 0.05) || null
)

function wsUrl(stationId) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const token = getToken()
  const qs = token ? `?token=${encodeURIComponent(token)}` : ''
  return `${proto}://${wsHost()}/ws/${stationId}${qs}`
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
      break
    case 'message_deleted':
      messages.value = messages.value.filter((m) => m.id !== data.id)
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
      loadTrackLog()
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

async function loadHistory(stationId) {
  try {
    const res = await api(`/stations/${stationId}/messages?limit=100`)
    messages.value = res.messages || []
  } catch (e) {
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
    frequency.value = target.frequency
    listenerCount.value = target.listener_count || 0
    track.value = { videoId: target.current_youtube_id, startedAt: target.playback_started_at }
    await loadHistory(target.id)
    connect(target.id)
    await refreshFavorite()
    await loadTrackLog()
  } catch (e) {
    console.error(e)
  }
}

function changeFrequency(freq) {
  frequency.value = Math.round(freq * 10) / 10
  const s = currentStation.value
  if (!s) return
  listenerCount.value = s.listener_count || 0
  track.value = { videoId: s.current_youtube_id, startedAt: s.playback_started_at }
  loadHistory(s.id)
  connect(s.id)
  refreshFavorite()
  loadTrackLog()
}

// この局の再生ログ（過去に流れた曲）
async function loadTrackLog() {
  const s = currentStation.value
  if (!s) {
    trackLog.value = []
    return
  }
  try {
    const res = await api(`/stations/${s.id}/tracks?limit=50`)
    trackLog.value = res.tracks || []
  } catch (e) {
    trackLog.value = []
  }
}

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
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

// 自動DJ局で曲が最後まで再生されたら次曲へ
async function onPlayerEnded({ videoId } = {}) {
  const s = currentStation.value
  if (!s || !s.is_bot || !videoId) return
  try {
    await api(`/stations/${s.id}/bot/ended`, {
      method: 'POST',
      body: JSON.stringify({ video_id: videoId }),
    })
  } catch (e) {
    /* 次曲はバックエンドのループが処理する */
  }
}

// 自動DJ局で埋め込み再生に失敗した曲を報告し、次曲へ切り替えてもらう
async function onPlayerError({ videoId } = {}) {
  const s = currentStation.value
  if (!s || !s.is_bot || !videoId) return
  try {
    await api(`/stations/${s.id}/bot/report`, {
      method: 'POST',
      body: JSON.stringify({ video_id: videoId }),
    })
  } catch (e) {
    /* 次曲はバックエンドのループが処理する */
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
    const s = stations.value.find((x) => x.id === Number(id))
    if (s) changeFrequency(s.frequency)
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

/* 再生ログ */
.tracklog {
  background: var(--panel);
  border: 1px solid var(--line-strong);
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.tracklog__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid var(--line-strong);
  font-size: 12px;
  color: var(--green);
  letter-spacing: 1px;
}
.tracklog__refresh {
  font-size: 12px;
  min-width: 34px;
  min-height: 32px;
  padding: 4px 10px;
}
.tracklog__body {
  overflow-y: auto;
  max-height: 320px;
  display: flex;
  flex-direction: column;
}
.tracklog__empty {
  color: var(--text-dim);
  font-size: 12px;
  padding: 12px;
}
.tracklog__item {
  display: flex;
  gap: 10px;
  align-items: center;
  min-height: 40px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--line);
  text-decoration: none;
  font-size: 12px;
}
.tracklog__item:hover {
  background: #151515;
}
.tracklog__item.is-current {
  border-left: 2px solid var(--green);
}
.tracklog__time {
  color: var(--text-dim);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.tracklog__title {
  color: var(--text);
  flex: 1;
  min-width: 0;
}
/* 内側のマーキー要素にも色を継承させる（リンク既定色を打ち消す） */
.tracklog__item .tracklog__title,
.tracklog__item .tracklog__title :deep(.marquee__inner) {
  color: var(--text);
  text-decoration: none;
}
.tracklog__item.is-current .tracklog__title,
.tracklog__item.is-current .tracklog__title :deep(.marquee__inner) {
  color: var(--green);
}
.now {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  font-size: 14px;
}
.now__dot {
  width: 10px;
  height: 10px;
  background: var(--text-dim);
}
.now__dot.is-live {
  background: var(--green);
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
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
}
@media (max-width: 1080px) {
  /* モバイルはページ全体をスクロールさせ、チャットだけ高さを固定 */
  .station-view {
    height: auto;
  }
  .station-view__grid {
    grid-template-columns: 1fr;
  }
  .station-view__stream {
    height: 78vh;
    min-height: 480px;
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
    gap: 10px;
  }
  .now {
    flex-wrap: wrap;
    font-size: 13px;
    gap: 8px;
    padding: 8px 12px;
    margin-bottom: 10px;
  }
  .now__freq {
    margin-left: auto;
  }
  .station-view__stream {
    height: 80vh;
    min-height: 520px;
  }
  /* 再生ログは高さを抑える */
  .tracklog__body {
    max-height: 220px;
  }
}
</style>
