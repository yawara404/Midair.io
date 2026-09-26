<template>
  <div class="home">
    <div class="home__row">
      <div class="tv">
        <div class="tv__screen">
          <div class="tv__noise"></div>
          <div class="tv__scanlines"></div>
          <div class="tv__osd">
            <div class="tv__label">CHANNEL / FREQUENCY</div>
            <div class="tv__freq">{{ display }}<span class="tv__mhz">MHz</span></div>
            <div class="tv__name">{{ currentStation ? currentStation.callsign : 'NO SIGNAL' }}</div>
            <div class="tv__desc">
              {{ currentStation ? currentStation.description : '砂嵐の向こうに、誰かがいる。' }}
            </div>
            <div v-if="currentStation" class="tv__meta">
              <span class="tv__live">● {{ currentStation.status === 'live' ? 'ON AIR' : 'OFF AIR' }}</span>
              <span class="tv__listeners">LISTENER {{ currentStation.listener_count || 0 }}</span>
              <span class="tv__dj">{{ currentStation.is_bot ? '🤖 AUTO DJ' : 'DJ ' + currentStation.owner_username }}</span>
            </div>
            <div v-if="dialBand" class="tv__band">{{ dialBand }}</div>
          </div>
        </div>

        <div class="tv__panel">
          <div class="tv__dial">
            <div
              class="knob"
              :style="{ transform: `rotate(${knobAngle}deg)` }"
              @pointerdown="startDrag"
              title="ドラッグで周波数を合わせる"
            >
              <div class="knob__notch"></div>
            </div>
            <div class="tv__fine">
              <button
                class="tv__step"
                type="button"
                aria-label="周波数を0.1下げる"
                @pointerdown="startStep(-0.1, $event)"
                @pointerup="stopStep"
                @pointerleave="stopStep"
                @pointercancel="stopStep"
                @contextmenu.prevent
              >−0.1</button>
              <input
                class="tv__slider"
                type="range"
                min="76"
                max="89.0"
                step="0.1"
                :value="frequency"
                @input="onSlider"
              />
              <button
                class="tv__step"
                type="button"
                aria-label="周波数を0.1上げる"
                @pointerdown="startStep(0.1, $event)"
                @pointerup="stopStep"
                @pointerleave="stopStep"
                @pointercancel="stopStep"
                @contextmenu.prevent
              >＋0.1</button>
            </div>
            <button v-if="currentStation" class="btn btn--primary tv__enter" @click="enterBoard">
              ▶ 掲示板へ
            </button>
            <button v-else class="btn btn--ghost tv__enter" @click="openArchive">
              アーカイブを開く
            </button>
          </div>

          <div class="tv__presets">
            <button
              v-for="ch in stations"
              :key="ch.id"
              class="preset"
              :class="{ 'is-active': Math.abs(ch.frequency - frequency) < 0.05 }"
              @click="changeFrequency(ch.frequency)"
            >{{ ch.frequency.toFixed(1) }}</button>
          </div>
        </div>
      </div>

      <aside class="schedule">
        <div class="schedule__head">
          <span>番組表</span>
          <span class="schedule__date">{{ today }}</span>
        </div>
        <div class="schedule__body">
          <div v-for="p in programs" :key="p.id" class="schedule__item">
            <span class="schedule__time">{{ formatTime(p.start_time) }}–{{ formatTime(p.end_time) }}</span>
            <span class="schedule__title">{{ p.title }}</span>
            <span class="schedule__freq">{{ p.frequency.toFixed(1) }}</span>
          </div>
          <div v-if="!programs.length" class="schedule__empty">本日の番組はまだありません</div>
        </div>
      </aside>
    </div>

    <!-- フッター（プライバシーポリシー / 利用規約 / サイトマップ / 運営情報のモーダル） -->
    <SiteFooter />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import SiteFooter from '../components/SiteFooter.vue'

const route = useRoute()
const router = useRouter()
const stations = ref([])
const programs = ref([])
const frequency = ref(80.0)
// 周波数帯（専用局帯 / 自由な周波数）
const bands = ref([])

// ダイヤルの現在位置がどの帯域かを示す（エリア分けの可視化）
const dialBand = computed(() => {
  const f = frequency.value
  const b = bands.value.find((x) => f >= x.min - 1e-6 && f <= x.max + 1e-6)
  if (!b) return ''
  return b.dedicated ? 'DEDICATED AREA / 専用局エリア' : 'FREE AREA / 自由な周波数'
})

const currentStation = computed(
  () => stations.value.find((s) => Math.abs(s.frequency - frequency.value) < 0.05) || null
)
const display = computed(() => (frequency.value || 80).toFixed(1))
const knobAngle = computed(() => ((frequency.value - 76) / 12.9) * 270 - 135)
const today = computed(() => {
  const d = new Date()
  const w = ['日', '月', '火', '水', '木', '金', '土'][d.getDay()]
  return `${d.getMonth() + 1}/${d.getDate()} (${w})`
})

function changeFrequency(f) {
  frequency.value = Math.min(89.0, Math.max(76, Math.round(f * 10) / 10))
}
function nudge(d) {
  changeFrequency(frequency.value + d)
}

// 長押しで連続的に増減（押した瞬間に1回、その後は一定間隔でリピート）
let stepTimer = null
let stepRepeat = null
let stepDelta = 0
function startStep(delta, e) {
  if (e && e.currentTarget && e.currentTarget.setPointerCapture) {
    try {
      e.currentTarget.setPointerCapture(e.pointerId)
    } catch (_) {}
  }
  stopStep()
  stepDelta = delta
  nudge(delta)
  stepTimer = setTimeout(() => {
    stepRepeat = setInterval(() => nudge(stepDelta), 90)
  }, 380)
}
function stopStep() {
  if (stepTimer) {
    clearTimeout(stepTimer)
    stepTimer = null
  }
  if (stepRepeat) {
    clearInterval(stepRepeat)
    stepRepeat = null
  }
}

function onSlider(e) {
  changeFrequency(parseFloat(e.target.value))
}

let dragging = false
let startY = 0
let startFreq = 0
function startDrag(e) {
  dragging = true
  startY = e.clientY
  startFreq = frequency.value
  window.addEventListener('pointermove', onDrag)
  window.addEventListener('pointerup', stopDrag)
}
function onDrag(e) {
  if (!dragging) return
  changeFrequency(startFreq - (e.clientY - startY) * 0.02)
}
function stopDrag() {
  dragging = false
  window.removeEventListener('pointermove', onDrag)
  window.removeEventListener('pointerup', stopDrag)
}

function enterBoard() {
  if (currentStation.value) router.push(`/station/${currentStation.value.id}`)
}

function openArchive() {
  // 「周波数ページ」ボタンからはアーカイブページを開く
  router.push('/archive')
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function load() {
  try {
    const [s, t] = await Promise.all([api('/stations'), api('/timetable')])
    stations.value = s.stations || []
    programs.value = t.programs || []
    // ?freq=XX.X が指定されていればその周波数に合わせる（未開局でも可）
    const initFreq = parseFloat(route.query.freq)
    if (Number.isFinite(initFreq) && initFreq >= 76 && initFreq <= 89.0) {
      frequency.value = Math.round(initFreq * 10) / 10
    } else if (stations.value.length) {
      frequency.value = stations.value[0].frequency
    }
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  load()
  // 帯域の区分（専用局帯 / 自由な周波数）は表示にしか使わないので失敗しても無視する
  api('/bands')
    .then((res) => {
      bands.value = res.bands || []
    })
    .catch(() => {
      bands.value = []
    })
})
onBeforeUnmount(() => {
  stopStep()
})

// 戻る/進むで ?freq= が変わっても追従する（history traversal 対応）
watch(
  () => route.query.freq,
  (v) => {
    const f = parseFloat(v)
    if (Number.isFinite(f) && f >= 76 && f <= 89.0) {
      frequency.value = Math.round(f * 10) / 10
    }
  }
)
</script>

<style scoped>
.home {
  min-height: 0;
}
.home__row {
  display: flex;
  align-items: center;
  gap: 24px;
}

/* ===== アナログTV ===== */
.tv {
  width: 900px;
  flex: none;
  display: flex;
  flex-direction: column;
  background: #151515;
  border: 1px solid #3a3a3a;
  padding: 20px;
  border-radius: 20px;
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.7);
}
.tv__screen {
  position: relative;
  height: 480px;
  background: #050505;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid #000;
  box-shadow: inset 0 0 120px rgba(0, 0, 0, 0.8);
}
.tv__noise {
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(rgba(255, 255, 255, 0.06) 1px, transparent 1.5px),
    radial-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1.5px);
  background-size: 4px 4px, 7px 7px;
  background-position: 0 0, 3px 3px;
  animation: noise-shift 0.4s steps(3) infinite;
}
.tv__scanlines {
  position: absolute;
  inset: 0;
  background-image: repeating-linear-gradient(0deg, rgba(0, 0, 0, 0.28) 0 2px, transparent 2px 4px);
  pointer-events: none;
}
.tv__osd {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 20px;
  color: var(--green);
}
.tv__label {
  font-size: 11px;
  letter-spacing: 4px;
  color: var(--text-dim);
  margin-bottom: 6px;
}
.tv__freq {
  font-size: 84px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: 2px;
  color: var(--green);
  text-shadow: 0 0 18px rgba(255, 255, 255, 0.35);
  font-variant-numeric: tabular-nums;
}
.tv__mhz {
  font-size: 22px;
  font-weight: 400;
  color: var(--text-dim);
  margin-left: 8px;
  letter-spacing: 2px;
}
.tv__name {
  font-size: 20px;
  font-weight: 700;
  color: var(--green);
  margin-top: 12px;
}
.tv__desc {
  font-size: 12px;
  color: var(--text-dim);
  margin-top: 6px;
  max-width: 420px;
  line-height: 1.6;
}
.tv__meta {
  display: flex;
  gap: 18px;
  margin-top: 14px;
  font-size: 12px;
  letter-spacing: 1px;
  color: var(--text-dim);
}
.tv__live {
  color: var(--green);
  animation: blink 1.8s infinite;
}
.tv__band {
  margin-top: 8px;
  font-size: 10px;
  letter-spacing: 2px;
  color: var(--faint);
  border-top: 1px dashed var(--line-strong);
  padding-top: 6px;
  max-width: 420px;
}

.tv__panel {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.tv__dial {
  display: flex;
  align-items: center;
  gap: 16px;
}
.knob {
  width: 80px;
  height: 80px;
  flex-shrink: 0;
  border-radius: 50%;
  background:
    repeating-conic-gradient(from 0deg, #2b2b2b 0deg 2deg, #101010 2deg 30deg),
    radial-gradient(circle at 35% 30%, #2c2c2c, #0b0b0b 70%);
  border: 2px solid var(--line-strong);
  box-shadow: inset 0 0 14px #000;
  cursor: ns-resize;
  position: relative;
  transition: transform 0.08s linear;
  touch-action: none;
}
.knob__notch {
  position: absolute;
  top: 6px;
  left: 50%;
  transform: translateX(-50%);
  width: 5px;
  height: 15px;
  background: var(--green);
}
.tv__fine {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
}
/* ±0.1 ステップボタン（チューナーと統一・長押し対応） */
.tv__step {
  flex-shrink: 0;
  width: 56px;
  height: 38px;
  font-family: inherit;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.5px;
  color: var(--text);
  background: var(--panel-deep);
  border: 1px solid var(--line-strong);
  border-radius: 0;
  cursor: pointer;
  user-select: none;
  touch-action: manipulation;
  transition: background 0.1s ease, color 0.1s ease, border-color 0.1s ease;
}
.tv__step:hover {
  color: var(--green);
  border-color: var(--green);
}
.tv__step:active {
  background: var(--green);
  color: #000;
  border-color: var(--green);
}
.tv__slider {
  flex: 1;
  min-width: 0;
  accent-color: var(--green);
}
.tv__enter {
  flex-shrink: 0;
  font-size: 14px;
  padding: 10px 16px;
}
.tv__presets {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 8px;
}
.preset {
  font-family: inherit;
  font-size: 13px;
  min-width: 0;
  padding: 9px 4px;
  background: var(--panel-deep);
  border: 1px solid var(--line-strong);
  color: var(--text-dim);
  cursor: pointer;
  border-radius: 0;
  font-variant-numeric: tabular-nums;
}
.preset:hover {
  color: var(--green);
}
.preset.is-active {
  border-color: var(--green);
  color: var(--green);
  background: #1a1a1a;
}

/* ===== 番組表 ===== */
.schedule {
  flex: 1;
  min-width: 0;
  max-width: 540px;
  align-self: stretch;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  display: flex;
  flex-direction: column;
}
.schedule__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line-strong);
  font-size: 13px;
  color: var(--green);
  letter-spacing: 1px;
}
.schedule__date {
  color: var(--text-dim);
  font-size: 12px;
}
.schedule__body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}
.schedule__item {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 8px 16px;
  border-bottom: 1px solid var(--line);
  font-size: 12px;
}
.schedule__time {
  color: var(--text-dim);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.schedule__title {
  color: var(--text);
  flex: 1;
}
.schedule__freq {
  color: var(--green);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.schedule__empty {
  padding: 24px 16px;
  color: var(--text-dim);
  font-size: 12px;
  text-align: center;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
}
@keyframes noise-shift {
  0% { background-position: 0 0, 3px 3px; }
  33% { background-position: 1px 2px, 5px 1px; }
  66% { background-position: 2px 1px, 4px 4px; }
  100% { background-position: 0 0, 3px 3px; }
}

@media (max-width: 1240px) {
  .home__row {
    flex-direction: column;
  }
  .tv {
    width: min(900px, 100%);
  }
  .schedule {
    max-width: none;
    width: 100%;
    min-height: 220px;
  }
}

@media (max-width: 640px) {
  .home__row {
    gap: 16px;
  }
  .tv {
    padding: 12px;
    border-radius: 14px;
  }
  .tv__screen {
    height: 320px;
  }
  .tv__freq {
    font-size: 56px;
  }
  .tv__mhz {
    font-size: 16px;
    margin-left: 4px;
  }
  .tv__name {
    font-size: 16px;
    margin-top: 8px;
  }
  .tv__desc {
    font-size: 11px;
  }
  .tv__meta {
    gap: 12px;
    font-size: 11px;
    flex-wrap: wrap;
    justify-content: center;
  }
  .tv__dial {
    flex-wrap: wrap;
  }
  .tv__fine {
    order: 3;
    width: 100%;
  }
  .knob {
    width: 64px;
    height: 64px;
  }
  .tv__enter {
    flex: 1;
  }
  .tv__presets {
    grid-template-columns: repeat(4, 1fr);
  }
}
</style>
