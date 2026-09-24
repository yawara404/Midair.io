<template>
  <a class="card" :href="stationUrl" target="_blank" rel="noopener">
    <div class="card__top">
      <span class="card__badge" :class="{ 'is-live': isLive }">
        {{ isLive ? '● LIVE' : '○ OFF' }}
      </span>
      <span class="card__freq">{{ displayFrequency }} MHz</span>
    </div>
    <div class="card__name">{{ data.name || 'Midair.io' }}</div>
    <div class="card__desc">{{ data.description || '深夜ラジオのアジト。' }}</div>
    <div class="card__foot">Midair.io — 深夜ラジオのアジト</div>
  </a>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiBase } from '../api'

// エコシステム用の埋め込みプレビューカード。
// 他サービス（TuneDrop / vocaloid.hz など）にURLを貼る際の表示イメージ。
// ?preview=1&frequency=82.5 で表示でき、/api/preview から情報を取得する。
const props = defineProps({
  frequency: { type: Number, default: null },
  name: { type: String, default: '' },
  description: { type: String, default: '' },
  isLive: { type: Boolean, default: true },
})

const data = ref({
  frequency: props.frequency,
  name: props.name,
  description: props.description,
  is_live: props.isLive,
})

const displayFrequency = computed(() =>
  data.value.frequency != null ? Number(data.value.frequency).toFixed(1) : '—'
)
const isLive = computed(() => data.value.is_live !== false)
const stationUrl = computed(() => {
  // スタンドアロンはハッシュルーティングなので #/?freq=... を指す
  const query = `?freq=${displayFrequency.value}`
  return __STANDALONE__
    ? `${location.origin}${location.pathname}#/${query}`
    : `${location.origin}/${query}`
})

onMounted(async () => {
  const params = new URLSearchParams(location.search)
  const freq =
    props.frequency != null
      ? props.frequency
      : params.get('frequency')
        ? parseFloat(params.get('frequency'))
        : null
  if (freq == null) return
  try {
    const res = await fetch(`${apiBase()}/api/preview?frequency=${freq}`)
    const json = await res.json()
    if (json.success) data.value = json
  } catch (e) {
    /* 取得失敗時は props の表示を維持 */
  }
})
</script>

<style scoped>
.card {
  position: relative;
  display: block;
  max-width: 360px;
  padding: 20px 16px 16px;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  border-radius: 0;
  text-decoration: none;
  color: var(--text);
}
/* 上端の斜線帯（幾何学模様） */
.card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 5px;
  background-image: repeating-linear-gradient(45deg, #1c1c1c 0 6px, #0a0a0a 6px 12px);
}
.card:hover {
  border-color: var(--green);
}
.card__top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.card__badge {
  font-size: 11px;
  letter-spacing: 1px;
  color: var(--text-dim);
}
.card__badge.is-live {
  color: var(--green);
  animation: blink 1.8s infinite;
}
.card__freq {
  margin-left: auto;
  font-size: 18px;
  color: var(--green);
  font-variant-numeric: tabular-nums;
}
.card__name {
  font-size: 18px;
  font-weight: 700;
  color: var(--green);
  margin-bottom: 6px;
}
.card__desc {
  font-size: 13px;
  color: var(--text-dim);
  line-height: 1.6;
  margin-bottom: 12px;
}
.card__foot {
  font-size: 10px;
  letter-spacing: 2px;
  color: var(--text-dim);
  border-top: 1px dashed var(--line-strong);
  padding-top: 10px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
}
</style>
