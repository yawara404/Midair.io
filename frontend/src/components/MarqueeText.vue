<template>
  <div ref="wrap" class="marquee" :class="{ 'is-overflowing': overflowing }">
    <span ref="inner" class="marquee__inner" :style="innerStyle">
      <slot>{{ text }}</slot>
    </span>
  </div>
</template>
<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'

/**
 * テキストが入り切らないときだけ、左へ流れるように表示する。
 * - 収まっていれば通常表示（アニメーションなし）
 * - ホバーで一時停止、コピーも可能
 */
const props = defineProps({
  text: { type: String, default: '' },
  // 余白ぶん少し間を空ける（ループ時の継ぎ目対策）
  gap: { type: Number, default: 32 },
  duration: { type: Number, default: 0 }, // 秒（0なら距離から自動算出）
  speed: { type: Number, default: 38 }, // px/秒（ゆっくり）
  // 流れ始めるまでの停止時間（初期位置で少し止まる）
  startDelay: { type: Number, default: 1.5 }, // 秒
  // ループごとの停止時間（折り返し時にも少し止まる）
  loopDelay: { type: Number, default: 0.5 }, // 秒
})

const wrap = ref(null)
const inner = ref(null)
const overflowing = ref(false)
const distance = ref(0)
let ro = null

function measure() {
  const w = wrap.value
  const i = inner.value
  if (!w || !i) return
  // テキストの実幅（max-content）とコンテナ幅を比較
  const contentWidth = Math.max(i.scrollWidth, Math.round(i.getBoundingClientRect().width))
  const boxWidth = w.clientWidth
  distance.value = Math.max(0, contentWidth + props.gap)
  overflowing.value = contentWidth > boxWidth + 1
}

// 1周期の尺（停止→移動→停止）とタイムライン%。
// CSS の @keyframes は固定（0/25/90/100）なので、
// hold/move の比率が近くなるよう速度と待ち時間から尺を決める。
const innerStyle = computed(() => {
  if (!overflowing.value) return {}
  const dur = props.duration > 0 ? props.duration : Math.max(6, distance.value / props.speed)
  const total = dur + props.startDelay + props.loopDelay
  return {
    '--marquee-distance': `-${distance.value}px`,
    '--marquee-total': `${total.toFixed(2)}s`,
  }
})

let mo = null

function observe() {
  const w = wrap.value
  const i = inner.value
  if (typeof ResizeObserver !== 'undefined') {
    ro = new ResizeObserver(() => measure())
    if (w) ro.observe(w)
    if (i) ro.observe(i)
  }
  // テキストの差し替え（slot含む）でも再計測する
  if (typeof MutationObserver !== 'undefined' && i) {
    mo = new MutationObserver(() => measure())
    mo.observe(i, { childList: true, characterData: true, subtree: true })
  }
}

onMounted(async () => {
  await nextTick()
  measure()
  observe()
  // Webフォント読み込み後にも計測し直す
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => measure())
  }
  window.addEventListener('resize', measure)
})

onBeforeUnmount(() => {
  if (ro) ro.disconnect()
  if (mo) mo.disconnect()
  window.removeEventListener('resize', measure)
})

watch(() => props.text, async () => {
  await nextTick()
  measure()
})

defineExpose({ measure })
</script>

<style scoped>
.marquee {
  overflow: hidden;
  white-space: nowrap;
  min-width: 0;
  max-width: 100%;
  /* 親（リンク等）の文字色をそのまま継承する（青リンク色にしない） */
  color: inherit;
}
.marquee__inner {
  display: inline-block;
  width: max-content; /* テキストの実幅を保持（コンテナ幅に引き伸ばされない） */
  min-width: max-content;
  white-space: nowrap;
  color: inherit;
  text-decoration: inherit;
}
/* 収まらないときだけ流す（初期位置で少し止まってから、ゆっくり流れる） */
.marquee.is-overflowing .marquee__inner {
  animation: marquee-scroll var(--marquee-total, 14s) linear infinite;
  will-change: transform;
  transform: translateX(0);
}
/* ホバーで一時停止（読みやすさ優先） */
.marquee.is-overflowing:hover .marquee__inner {
  animation-play-state: paused;
}
/* 停止 → 移動 → 停止 の3段階。0〜25% は初期位置で停止、25〜90% で移動、90〜100% で停止 */
@keyframes marquee-scroll {
  0%,
  25% {
    transform: translateX(0);
  }
  90%,
  100% {
    transform: translateX(var(--marquee-distance, -50%));
  }
}
</style>
