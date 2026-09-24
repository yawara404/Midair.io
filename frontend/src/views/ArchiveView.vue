<template>
  <div class="archive">
    <div class="archive__head">
      <div>
        <h2>アーカイブ（公開）</h2>
        <p>予約なしのゲリラ放送も自動で録音されます。<strong>ログイン不要</strong>で誰でも再生できます。</p>
      </div>
      <button class="btn btn--ghost" @click="loadSessions">↻ 更新</button>
    </div>

    <div class="archive__layout">
      <aside class="archive__list">
        <button
          v-for="s in sessions"
          :key="s.id"
          class="session-card"
          :class="{ 'is-active': current && current.id === s.id }"
          @click="openSession(s)"
        >
          <span class="session-card__title">{{ s.session_title }}</span>
          <span class="session-card__meta">
            {{ s.frequency != null ? s.frequency.toFixed(1) : '—' }}MHz {{ s.station_callsign || '—' }}
          </span>
          <span class="session-card__meta">
            {{ fmt(s.started_at) }} ・ {{ s.total_messages }}件 ・ {{ mmss(s.duration_seconds || 0) }}
          </span>
          <span v-if="s.is_live" class="session-card__live">● 放送中</span>
        </button>
        <p v-if="!sessions.length" class="archive__empty">まだアーカイブがありません。</p>
      </aside>

      <section v-if="current" class="replay">
        <div class="replay__head">
          <span class="replay__title">{{ current.session_title }}</span>
          <span class="replay__meta">
            {{ fmt(current.started_at) }} 〜 {{ current.ended_at ? fmtTime(current.ended_at) : '放送中' }}
          </span>
        </div>

        <div class="replay__player">
          <div id="archive-player" class="replay__frame"></div>
          <div v-if="!currentTrack" class="replay__no-track">
            この時間帯に音源はありません（チャットのみ）。
          </div>
        </div>

        <div class="replay__controls">
          <button class="btn btn--primary" @click="togglePlay">
            {{ playing ? '⏸ 一時停止' : '▶ タイムシフト再生' }}
          </button>
          <input
            class="replay__seek"
            type="range"
            min="0"
            :max="duration"
            :value="elapsed"
            @input="seek"
          />
          <span class="replay__time">{{ mmss(elapsed) }} / {{ mmss(duration) }}</span>
        </div>

        <div ref="logEl" class="replay__log">
          <div
            v-for="m in visibleMessages"
            :key="m.id"
            class="msg"
            :class="`msg--${m.message_type}`"
          >
            <span class="msg__author">{{ m.author }}</span>
            <span class="msg__time">+{{ mmss(m.offset_seconds || 0) }}</span>
            <p class="msg__content">{{ m.content }}</p>
          </div>
          <p v-if="!visibleMessages.length" class="archive__empty">
            再生ボタンを押すと、当時のログが流れてきます。
          </p>
        </div>
      </section>

      <section v-else class="archive__placeholder">
        左のアーカイブを選ぶと、タイムシフト再生が始まります。
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { api } from '../api'

const sessions = ref([])
const current = ref(null)
const messages = ref([])
const tracks = ref([])
const elapsed = ref(0)
const duration = ref(0)
const playing = ref(false)
const logEl = ref(null)

let player = null
let ytReady = false
let timer = null
let loadedTrackId = null

const visibleMessages = computed(() =>
  messages.value.filter((m) => (m.offset_seconds || 0) <= elapsed.value)
)
const currentTrack = computed(() => {
  let t = null
  for (const tr of tracks.value) {
    if (tr.started_offset_sec <= elapsed.value) t = tr
    else break
  }
  return t
})

function pad(n) {
  return String(n).padStart(2, '0')
}
function mmss(s) {
  s = Math.max(0, Math.floor(s || 0))
  return `${pad(Math.floor(s / 60))}:${pad(s % 60)}`
}
function fmt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadSessions() {
  try {
    const res = await api('/archives')
    sessions.value = res.sessions || []
  } catch (e) {
    console.error(e)
  }
}

async function openSession(s) {
  stopTimer()
  playing.value = false
  current.value = s
  try {
    const res = await api(`/sessions/${s.id}`)
    messages.value = res.messages || []
    tracks.value = res.tracks || []
    const maxMsg = messages.value.reduce((a, m) => Math.max(a, m.offset_seconds || 0), 0)
    const maxTrk = tracks.value.reduce((a, t) => Math.max(a, t.started_offset_sec || 0), 0)
    duration.value = Math.max(res.session.duration_seconds || 0, maxMsg, maxTrk, 1)
    elapsed.value = 0
    loadedTrackId = null
    loadApi()
  } catch (e) {
    console.error(e)
  }
}

function loadApi() {
  if (window.YT && window.YT.Player) {
    ytReady = true
    createPlayer()
    return
  }
  if (window.__ytLoading) return
  window.__ytLoading = true
  const tag = document.createElement('script')
  tag.src = 'https://www.youtube.com/iframe_api'
  document.head.appendChild(tag)
  window.onYouTubeIframeAPIReady = () => {
    ytReady = true
    window.__ytLoading = false
    createPlayer()
  }
}

function createPlayer() {
  const el = document.getElementById('archive-player')
  if (!ytReady || !el || player) return
  player = new window.YT.Player('archive-player', {
    width: '100%',
    height: '100%',
    playerVars: { autoplay: 0, controls: 1, rel: 0 },
    events: { onReady: () => syncTrack(true) },
  })
}

function syncTrack(force) {
  const t = currentTrack.value
  if (!t || !player) return
  const start = Math.max(0, elapsed.value - t.started_offset_sec)
  if (loadedTrackId !== t.youtube_id) {
    player.loadVideoById({ videoId: t.youtube_id, startSeconds: start })
    loadedTrackId = t.youtube_id
  } else if (force) {
    player.seekTo(start, true)
  }
}

function togglePlay() {
  playing.value = !playing.value
  if (playing.value) {
    syncTrack(true)
    if (player && player.playVideo) player.playVideo()
    startTimer()
  } else {
    stopTimer()
    if (player && player.pauseVideo) player.pauseVideo()
  }
}

function startTimer() {
  stopTimer()
  timer = setInterval(() => {
    elapsed.value = Math.min(duration.value, elapsed.value + 1)
    syncTrack(false)
    if (elapsed.value >= duration.value) togglePlay()
  }, 1000)
}

function stopTimer() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

function seek(e) {
  elapsed.value = parseInt(e.target.value, 10) || 0
  syncTrack(true)
}

watch(
  () => visibleMessages.value.length,
  async () => {
    await nextTick()
    if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight
  }
)

onBeforeUnmount(() => {
  stopTimer()
  if (player) {
    try {
      player.destroy()
    } catch (e) {}
  }
})

loadSessions()
</script>

<style scoped>
.archive__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}
.archive__head h2 {
  margin: 0 0 4px;
  font-size: 22px;
  color: var(--green);
}
.archive__head p {
  margin: 0;
  font-size: 12px;
  color: var(--text-dim);
}
.archive__head strong {
  color: var(--green);
}
.archive__empty {
  color: var(--text-dim);
  font-size: 12px;
  padding: 8px 0;
}

.archive__layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 18px;
  align-items: start;
}
.archive__list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.session-card {
  display: flex;
  flex-direction: column;
  gap: 3px;
  text-align: left;
  font-family: inherit;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  padding: 12px 14px;
  cursor: pointer;
  color: var(--text);
  border-radius: 0;
}
.session-card:hover {
  border-color: var(--green);
}
.session-card.is-active {
  border-color: var(--green);
  background: #151515;
}
.session-card__title {
  font-size: 14px;
  color: var(--green);
}
.session-card__meta {
  font-size: 11px;
  color: var(--text-dim);
  font-variant-numeric: tabular-nums;
}
.session-card__live {
  font-size: 11px;
  color: var(--green);
  animation: blink 1.8s infinite;
}

.archive__placeholder {
  color: var(--text-dim);
  font-size: 13px;
  padding: 40px;
  text-align: center;
  border: 1px dashed var(--line-strong);
}

.replay {
  background: var(--panel);
  border: 1px solid var(--line-strong);
  padding: 16px;
}
.replay__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
}
.replay__title {
  font-size: 16px;
  color: var(--green);
}
.replay__meta {
  font-size: 12px;
  color: var(--text-dim);
  font-variant-numeric: tabular-nums;
}
.replay__player {
  position: relative;
  /* 高さ上限 46vh を基準に 16:9 の幅を逆算（巨大化を防ぎログが見える） */
  width: min(100%, calc(46vh * 16 / 9));
  aspect-ratio: 16 / 9;
  margin: 0 auto;
  background-color: #000;
  background-image: radial-gradient(rgba(255, 255, 255, 0.08) 1px, transparent 1px);
  background-size: 16px 16px;
  border: 1px solid var(--line-strong);
  overflow: hidden;
}
.replay__frame {
  position: absolute;
  inset: 0;
}
.replay__frame :deep(iframe) {
  width: 100%;
  height: 100%;
}
.replay__no-track {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: var(--text-dim);
  text-align: center;
  padding: 12px;
}
.replay__controls {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 12px 0;
}
.replay__seek {
  flex: 1;
  accent-color: var(--green);
}
.replay__time {
  font-size: 12px;
  color: var(--green);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.replay__log {
  max-height: 42vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px dashed var(--line-strong);
}
.msg {
  border-left: 2px solid var(--line-strong);
  padding-left: 10px;
}
.msg__author {
  font-size: 12px;
  color: var(--green);
  margin-right: 8px;
}
.msg__time {
  font-size: 11px;
  color: var(--faint);
  font-variant-numeric: tabular-nums;
}
.msg__content {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg--dj {
  border-left-color: var(--green);
}
.msg--dj .msg__content {
  color: var(--green);
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
}

@media (max-width: 900px) {
  .archive__layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  .archive__head {
    flex-direction: column;
    align-items: stretch;
  }
  .archive__head .btn {
    align-self: flex-start;
  }
  .replay__head {
    flex-direction: column;
    gap: 4px;
  }
  .replay__controls {
    flex-wrap: wrap;
  }
  .replay__seek {
    order: 3;
    flex-basis: 100%;
  }
  .replay__log {
    max-height: 240px;
  }
}
</style>
