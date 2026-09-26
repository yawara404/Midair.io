<template>
  <aside class="tuner">
    <div class="tuner__meter">
      <div class="tuner__label">FREQUENCY</div>
      <div class="tuner__display">{{ display }}</div>
      <div class="tuner__unit">MHz</div>
    </div>

    <div
      class="knob"
      :style="{ transform: `rotate(${knobAngle}deg)` }"
      @pointerdown="startDrag"
      title="ドラッグで周波数を合わせる"
    >
      <div class="knob__notch"></div>
    </div>

    <div class="tuner__fine">
      <button
        class="tuner__step"
        type="button"
        aria-label="周波数を0.1下げる"
        @pointerdown="startStep(-0.1, $event)"
        @pointerup="stopStep"
        @pointerleave="stopStep"
        @pointercancel="stopStep"
        @contextmenu.prevent
      >−0.1</button>
      <input
        class="tuner__slider"
        type="range"
        min="76"
        max="89.0"
        step="0.1"
        :value="currentFrequency"
        @input="onSlider"
        @change="onSliderEnd"
      />
      <button
        class="tuner__step"
        type="button"
        aria-label="周波数を0.1上げる"
        @pointerdown="startStep(0.1, $event)"
        @pointerup="stopStep"
        @pointerleave="stopStep"
        @pointercancel="stopStep"
        @contextmenu.prevent
      >＋0.1</button>
    </div>

    <!-- ダイヤルを合わせたあと、このボタンで受信を決定する（履歴にも残る） -->
    <template v-if="showCommit">
      <button
        class="btn btn--primary tuner__commit"
        type="button"
        :disabled="!canCommit"
        :title="canCommit ? 'この周波数に切り替える' : 'いま受信中の周波数です'"
        @click="$emit('commit')"
      >{{ commitLabel }}</button>
      <p v-if="canCommit && tunedFrequency != null" class="tuner__pending">
        受信中 {{ tunedFrequency.toFixed(1) }} MHz → {{ display }} MHz へ切り替え
      </p>
    </template>

    <div class="tuner__status">
      <span class="tuner__live">● ON AIR</span>
      <span class="tuner__listeners">LISTENER {{ listenerCount }}</span>
    </div>

    <div class="tuner__program">
      <MarqueeText class="tuner__program-name" :text="currentChannel ? currentChannel.name : '—'" />
      <MarqueeText class="tuner__program-desc" :text="currentChannel ? currentChannel.description : ''" />
    </div>

    <!-- 周波数ページ（＝アーカイブ／過去スレッド一覧）へ -->
    <router-link class="btn btn--ghost tuner__map" to="/archive">
      🗺 周波数ページへ
    </router-link>

    <div class="tuner__presets">
      <button
        v-for="ch in channels"
        :key="ch.id"
        class="preset"
        :title="ch.name"
        :class="{ 'is-active': Math.abs(ch.frequency - currentFrequency) < 0.05 }"
        @click="$emit('change-frequency', ch.frequency)"
      >
        {{ ch.frequency.toFixed(1) }}
      </button>
    </div>
  </aside>
</template>

<script setup>
import { computed, watch, onBeforeUnmount } from 'vue'
import MarqueeText from './MarqueeText.vue'

const props = defineProps({
  channels: { type: Array, default: () => [] },
  currentFrequency: { type: Number, default: 80.0 },
  listenerCount: { type: Number, default: 0 },
  // ダイヤルは合わせただけでは切り替えず、決定ボタンで受信を切り替えるモード
  showCommit: { type: Boolean, default: false },
  canCommit: { type: Boolean, default: false },
  // いま実際に受信している周波数（ダイヤルと違うときだけ「受信中」を表示する）
  tunedFrequency: { type: Number, default: null },
  commitLabel: { type: String, default: '▶ この周波数で受信' },
})
const emit = defineEmits(['change-frequency', 'commit'])

const display = computed(() => (props.currentFrequency ?? 80).toFixed(1))
const currentChannel = computed(
  () => props.channels.find((c) => Math.abs(c.frequency - props.currentFrequency) < 0.05) || null
)
// 76.0 → -135deg, 89.0 → +135deg
const knobAngle = computed(() => ((props.currentFrequency - 76) / 13.0) * 270 - 135)

// 直近で合わせた周波数（プロパティ更新は非同期なので自前で保持する）
let lastFreq = props.currentFrequency
watch(
  () => props.currentFrequency,
  (v) => {
    lastFreq = v
  }
)

function emitFreq(f) {
  // 開局可能なレンジ（76.0〜89.0MHz）を扱う
  const clamped = Math.min(89.0, Math.max(76, Math.round(f * 10) / 10))
  lastFreq = clamped
  emit('change-frequency', clamped)
}

function nudge(delta) {
  emitFreq((lastFreq ?? props.currentFrequency) + delta)
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
  nudge(delta) // 押した瞬間に1回
  // 長押し判定後、連続リピート開始
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

onBeforeUnmount(() => {
  stopStep()
  if (dragging) {
    window.removeEventListener('pointermove', onDrag)
    window.removeEventListener('pointerup', stopDrag)
  }
})

function onSlider(e) {
  emitFreq(parseFloat(e.target.value))
}

// スライダーを離したときに近くの局へスナップする
function onSliderEnd(e) {
  if (e && e.target) lastFreq = parseFloat(e.target.value)
  snapToStation()
}

// ダイヤル（ノブ/スライダー）が局の近くにあれば、その局に合わせて移動する
function snapToStation() {
  let best = null
  let bestDist = Infinity
  for (const ch of props.channels) {
    const d = Math.abs(ch.frequency - lastFreq)
    if (d < bestDist) {
      bestDist = d
      best = ch
    }
  }
  // 0.6MHz 以内なら最寄りの局にスナップ（他の局へダイヤルをセットして移動）
  if (best && bestDist > 0.001 && bestDist <= 0.6) {
    lastFreq = best.frequency
    emit('change-frequency', best.frequency)
  }
}

// ノブのドラッグ操作（縦方向でチューニング）
let dragging = false
let startY = 0
let startFreq = 0

function startDrag(e) {
  dragging = true
  startY = e.clientY
  startFreq = props.currentFrequency
  window.addEventListener('pointermove', onDrag)
  window.addEventListener('pointerup', stopDrag)
}

function onDrag(e) {
  if (!dragging) return
  const dy = e.clientY - startY
  emitFreq(startFreq - dy * 0.02)
}

function stopDrag() {
  dragging = false
  window.removeEventListener('pointermove', onDrag)
  window.removeEventListener('pointerup', stopDrag)
  // ドラッグ終了時に近くの局へスナップ
  snapToStation()
}
</script>

<style scoped>
.tuner {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  padding: 16px;
  border-radius: 0;
}
/* 高さが足りないときでも各パーツを潰さない
   （flex の縮小で丸いダイヤルが楕円になるのを防ぐ。あふれた分はパネル内スクロール） */
.tuner > * {
  flex: 0 0 auto;
}

.tuner__meter {
  background-color: #060606;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
  background-size: 14px 14px;
  border: 1px solid var(--line-strong);
  padding: 10px;
  text-align: center;
}
.tuner__label {
  font-size: 10px;
  letter-spacing: 3px;
  color: var(--text-dim);
}
.tuner__display {
  font-size: 32px;
  line-height: 1.15;
  color: var(--green);
  letter-spacing: 1px;
  font-variant-numeric: tabular-nums;
}
.tuner__unit {
  font-size: 10px;
  color: var(--text-dim);
  letter-spacing: 2px;
}

/* ノブ：目盛りの刻み（conicグラデーション）。常に正円を保つ */
.knob {
  flex: 0 0 auto;
  width: 120px;
  height: 120px;
  aspect-ratio: 1 / 1;
  margin: 0 auto;
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
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  width: 6px;
  height: 22px;
  background: var(--green);
}

.tuner__fine {
  display: flex;
  align-items: center;
  gap: 8px;
}
/* ±0.1 ステップボタン（統一スタイル・長押し対応） */
.tuner__step {
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
.tuner__step:hover {
  color: var(--green);
  border-color: var(--green);
}
.tuner__step:active {
  background: var(--green);
  color: #000;
  border-color: var(--green);
}
.tuner__slider {
  flex: 1;
  min-width: 0;
  accent-color: var(--green);
}

.tuner__status {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}
.tuner__live {
  color: var(--green);
  letter-spacing: 1px;
  animation: blink 1.8s infinite;
}
.tuner__listeners {
  color: var(--text-dim);
  letter-spacing: 1px;
}

.tuner__map {
  width: 100%;
  text-align: center;
  text-decoration: none;
  white-space: nowrap;
}

/* ダイヤルを合わせたあとの「決定」ボタン（履歴にも残る切り替え） */
.tuner__commit {
  width: 100%;
  white-space: nowrap;
}
.tuner__pending {
  margin: -4px 0 0;
  font-size: 11px;
  text-align: center;
  color: var(--amber, var(--green));
  letter-spacing: 0.04em;
}

.tuner__program {
  border-top: 1px dashed var(--line-strong);
  padding-top: 12px;
}
.tuner__program-name {
  font-size: 16px;
  color: var(--green);
  margin-bottom: 6px;
}
.tuner__program-desc {
  font-size: 12px;
  color: var(--text-dim);
  line-height: 1.6;
}
/* マーキー時に文字が潰れないよう、行内での折返しを無効化 */
.tuner__program-name,
.tuner__program-desc {
  --marquee-duration: 10s;
}

.tuner__presets {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}
.preset {
  font-family: inherit;
  font-size: 12px;
  min-height: 34px;
  padding: 6px 2px;
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

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
}

/* ===== モバイル最適化 ===== */
@media (max-width: 1080px) {
  .tuner {
    gap: 12px;
    padding: 14px;
  }
}

@media (max-width: 640px) {
  /* チューナーを横並びコンパクト化（メーター + ノブ + ±） */
  .tuner {
    display: grid;
    grid-template-columns: 1fr auto;
    grid-template-areas:
      'meter knob'
      'fine fine'
      'status status'
      'program program'
      'map map'
      'presets presets';
    align-items: center;
    gap: 8px 10px;
    padding: 10px;
  }
  .tuner__meter {
    grid-area: meter;
    padding: 8px 10px;
    text-align: left;
  }
  .tuner__display {
    font-size: 26px;
    letter-spacing: 1px;
    line-height: 1.1;
  }
  .tuner__label {
    font-size: 9px;
    letter-spacing: 2px;
  }
  .tuner__unit {
    font-size: 10px;
  }
  .knob {
    grid-area: knob;
    width: 60px;
    height: 60px;
    margin: 0;
  }
  .knob__notch {
    top: 5px;
    width: 4px;
    height: 13px;
  }
  .tuner__fine {
    grid-area: fine;
  }
  .tuner__step {
    width: 50px;
    height: 36px;
    font-size: 12px;
  }
  .tuner__status {
    grid-area: status;
  }
  .tuner__program {
    grid-area: program;
    padding-top: 8px;
  }
  .tuner__program-name {
    font-size: 14px;
    margin-bottom: 4px;
  }
  .tuner__program-desc {
    font-size: 11px;
    line-height: 1.5;
  }
  .tuner__map {
    grid-area: map;
  }
  .tuner__presets {
    grid-area: presets;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
  }
  .preset {
    font-size: 12px;
    min-height: 36px;
    padding: 6px 2px;
  }
}
</style>
