<template>
  <div class="player">
    <div class="player__head">
      <span class="player__tag">NOW PLAYING</span>
      <MarqueeText class="player__program" :text="channelName || '—'" />
    </div>

    <div class="player__box">
      <div ref="playerEl" class="player__frame" :class="{ 'is-off': isOffAir }"></div>
      <div v-if="isOffAir" class="player__static">
        <div class="player__noise"></div>
        <div class="player__scan"></div>
        <span class="player__static-label">OFF AIR — 砂嵐</span>
      </div>
      <div v-else-if="!videoId" class="player__empty">
        曲はまだリクエストされていません。
      </div>
    </div>

    <div class="player__meta">
      <span class="player__elapsed">{{ elapsed }}</span>
      <button
        v-if="videoId && !playing && !isOffAir"
        class="btn btn--ghost player__unmute"
        @click="resumeWithSound"
      >
        ▶ 音を出して再生
      </button>
      <span class="player__sync" :class="{ 'is-on': !!videoId && !isOffAir }">SYNCED</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import MarqueeText from './MarqueeText.vue'

const props = defineProps({
  videoId: { type: String, default: null },
  startedAt: { type: String, default: null },
  channelName: { type: String, default: '' },
  status: { type: String, default: '' },
})
const emit = defineEmits(['player-error', 'ended'])

const isOffAir = computed(() => props.status === 'off_air')

const playerEl = ref(null)
const elapsed = ref('00:00')
const error = ref(false)
// 音あり再生が始まっているか（自動再生ブロック検知用）
const playing = ref(false)
let player = null
let ytReady = false
let timer = null

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
  if (!ytReady || !playerEl.value) return
  const opts = {
    width: '100%',
    height: '100%',
    playerVars: {
      autoplay: 1,
      // 音を出すのをデフォルトにする
      mute: 0,
      controls: 1,
      rel: 0,
      playsinline: 1,
      origin: window.location.origin,
    },
    events: {
      onReady: () => syncVideo(),
      onStateChange: (e) => {
        playing.value = e.data === 1 // 1 = PLAYING
        // 0 = ENDED: 曲が終わったら呼び出し側で次曲へ
        if (e.data === 0) emit('ended', { videoId: props.videoId })
      },
      onError: (e) => {
        error.value = true
        // 埋め込み不可(101/150)等を検知したら呼び出し側で次曲へ
        emit('player-error', { videoId: props.videoId, code: e && e.data })
      },
    },
  }
  if (props.videoId) opts.videoId = props.videoId
  player = new window.YT.Player(playerEl.value, opts)
}

// 音を出して再生する（自動再生がブロックされた場合の再開も兼ねる）
function resumeWithSound() {
  if (!player || isOffAir.value) return
  try {
    player.unMute()
    player.setVolume(100)
  } catch (e) {}
  try {
    player.playVideo()
  } catch (e) {}
}

// 最初のユーザー操作で、止まっていれば音あり再生を試みる
function onFirstGesture() {
  if (player && props.videoId && !playing.value && !isOffAir.value) resumeWithSound()
}

function offsetSeconds() {
  if (!props.startedAt) return 0
  const t = new Date(props.startedAt).getTime()
  if (isNaN(t)) return 0
  return Math.max(0, (Date.now() - t) / 1000)
}

function syncVideo() {
  if (!player || !props.videoId || isOffAir.value) return
  const data = player.getVideoData ? player.getVideoData() : null
  if (data && data.video_id === props.videoId) {
    player.seekTo(offsetSeconds(), true)
  } else {
    player.loadVideoById({
      videoId: props.videoId,
      startSeconds: Math.floor(offsetSeconds()),
    })
  }
  // 音ありで再生（自動再生ポリシーでブロックされた場合は、
  // 最初の操作時に resumeWithSound / onFirstGesture が再開する）
  try {
    player.unMute()
    player.setVolume(100)
  } catch (e) {}
  player.playVideo()
}

function updateElapsed() {
  const s = Math.floor(offsetSeconds())
  const m = Math.floor(s / 60)
  const sec = s % 60
  elapsed.value = `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

function startTimer() {
  stopTimer()
  updateElapsed()
  timer = setInterval(updateElapsed, 1000)
}

function stopTimer() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

// 停波（砂嵐）・曲なしのときは再生を止める
// （iframe を隠すだけでは音が鳴り続けてしまうため、明示的に停止する）
function stopPlayback() {
  stopTimer()
  elapsed.value = '00:00'
  playing.value = false
  if (!player) return
  try {
    player.stopVideo()
  } catch (e) {}
  try {
    player.mute()
  } catch (e) {}
}

watch(
  // 停波（砂嵐）になった瞬間にも止めたいので status も監視する
  () => [props.videoId, props.status],
  ([v]) => {
    error.value = false
    if (v && !isOffAir.value) {
      if (!ytReady) loadApi()
      else syncVideo()
      startTimer()
    } else {
      stopPlayback()
    }
  }
)

onMounted(() => {
  if (props.videoId && !isOffAir.value) loadApi()
  // 自動再生ブロック対策: 最初のクリック/キー操作で音あり再生を再開
  window.addEventListener('pointerdown', onFirstGesture)
  window.addEventListener('keydown', onFirstGesture)
})

onBeforeUnmount(() => {
  stopTimer()
  window.removeEventListener('pointerdown', onFirstGesture)
  window.removeEventListener('keydown', onFirstGesture)
  if (player) {
    try {
      player.destroy()
    } catch (e) {}
  }
})
</script>

<style scoped>
.player {
  background: var(--panel);
  border: 1px solid var(--line-strong);
  border-radius: 0;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.player__head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.player__tag {
  font-size: 10px;
  letter-spacing: 2px;
  color: var(--text-dim);
}
.player__program {
  font-size: 13px;
  color: var(--green);
  flex: 1;
  min-width: 0;
}

.player__box {
  position: relative;
  aspect-ratio: 16 / 9;
  background-color: #000;
  background-image: radial-gradient(rgba(255, 255, 255, 0.08) 1px, transparent 1px);
  background-size: 16px 16px;
  border: 1px solid var(--line-strong);
  overflow: hidden;
}
.player__frame {
  position: absolute;
  inset: 0;
}
.player__frame.is-off {
  visibility: hidden;
}
.player__frame :deep(iframe) {
  width: 100%;
  height: 100%;
}
.player__static {
  position: absolute;
  inset: 0;
  background: #050505;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.player__noise {
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(rgba(255, 255, 255, 0.06) 1px, transparent 1.5px),
    radial-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1.5px);
  background-size: 4px 4px, 7px 7px;
  animation: player-noise 0.4s steps(3) infinite;
}
.player__scan {
  position: absolute;
  inset: 0;
  background-image: repeating-linear-gradient(
    0deg,
    rgba(0, 0, 0, 0.28) 0 2px,
    transparent 2px 4px
  );
}
.player__static-label {
  position: relative;
  color: var(--text-dim);
  font-size: 12px;
  letter-spacing: 2px;
}
@keyframes player-noise {
  0% { background-position: 0 0, 3px 3px; }
  33% { background-position: 1px 2px, 5px 1px; }
  66% { background-position: 2px 1px, 4px 4px; }
  100% { background-position: 0 0, 3px 3px; }
}
.player__empty {
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

.player__meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}
.player__elapsed {
  color: var(--green);
  font-variant-numeric: tabular-nums;
  letter-spacing: 1px;
}
.player__unmute {
  font-size: 11px;
  padding: 3px 8px;
}
.player__sync {
  color: var(--faint);
  letter-spacing: 1px;
}
.player__sync.is-on {
  color: var(--green);
}
</style>
