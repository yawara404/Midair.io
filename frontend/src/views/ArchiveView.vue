<template>
  <div class="archive">
    <div class="archive__head">
      <div>
        <h2>過去スレッド（アーカイブ）</h2>
        <p>
          掲示板のスレッド一覧です（1スレ {{ maxPosts }} 投稿で自動的に新スレへ）。
          <strong>ログイン不要</strong>で過去ログを読めます。
        </p>
      </div>
      <button class="btn btn--ghost" @click="loadThreads">↻ 更新</button>
    </div>

    <div v-if="stationFilter" class="archive__filter">
      <span>表示中: {{ stationFilterName }}</span>
      <router-link class="archive__filter-clear" to="/archive">すべて表示</router-link>
    </div>

    <p v-if="!threads.length" class="archive__empty">まだスレッドがありません。</p>

    <div v-else class="archive__grid">
      <router-link
        v-for="t in threads"
        :key="t.id"
        class="thread-card"
        :class="{ 'is-archived': t.is_archived }"
        :to="`/thread/${t.id}`"
      >
        <span class="thread-card__title">{{ t.title }}</span>
        <span class="thread-card__meta">
          {{ t.frequency != null ? t.frequency.toFixed(1) : '—' }}MHz
          ・ {{ t.post_count }} / {{ maxPosts }} 投稿
          ・ {{ fmt(t.created_at) }}
        </span>
        <span v-if="t.is_archived" class="thread-card__badge">過去ログ</span>
        <span v-else class="thread-card__badge thread-card__badge--live">現行スレ</span>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'

const route = useRoute()
const threads = ref([])
const maxPosts = ref(1000)

const stationFilter = computed(() => {
  const s = parseInt(route.query.station, 10)
  return Number.isFinite(s) ? s : null
})
const stationFilterName = computed(() => {
  const t = threads.value.find((x) => x.station_id === stationFilter.value)
  return t ? `${t.frequency != null ? t.frequency.toFixed(1) : '—'}MHz ${t.station_callsign}` : '—'
})

function pad(n) {
  return String(n).padStart(2, '0')
}
function fmt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadThreads() {
  try {
    if (stationFilter.value) {
      const res = await api(`/stations/${stationFilter.value}/threads`)
      threads.value = res.threads || []
      maxPosts.value = res.max_posts || 1000
    } else {
      const res = await api('/threads?limit=200')
      threads.value = res.threads || []
      maxPosts.value = res.max_posts || 1000
    }
  } catch (e) {
    console.error(e)
    threads.value = []
  }
}

onMounted(loadThreads)
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
.archive__filter {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--text-dim);
  margin-bottom: 12px;
}
.archive__filter-clear {
  color: var(--green);
  text-decoration: none;
  border: 1px solid var(--line-strong);
  padding: 2px 8px;
}
.archive__filter-clear:hover {
  background: var(--green);
  color: #000;
}
.archive__empty {
  color: var(--text-dim);
  font-size: 12px;
  padding: 8px 0;
}

/* 2ch風のカード一覧 */
.archive__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.archive__grid > * {
  min-width: 0;
}
.thread-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  border-left: 3px solid var(--green);
  text-decoration: none;
  color: var(--text);
  transition: border-color 0.12s ease, background 0.12s ease;
}
.thread-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background-image: repeating-linear-gradient(45deg, #1c1c1c 0 6px, #0a0a0a 6px 12px);
}
.thread-card:hover {
  background: #151515;
  border-color: var(--green);
}
.thread-card.is-archived {
  border-left-color: var(--line-strong);
}
.thread-card__title {
  font-size: 15px;
  font-weight: 700;
  color: var(--green);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.thread-card__meta {
  font-size: 11px;
  color: var(--text-dim);
  font-variant-numeric: tabular-nums;
}
.thread-card__badge {
  align-self: flex-start;
  font-size: 10px;
  letter-spacing: 1px;
  color: var(--text-dim);
  border: 1px solid var(--line-strong);
  padding: 2px 6px;
}
.thread-card__badge--live {
  color: #000;
  background: var(--green);
  border-color: var(--green);
}

@media (max-width: 600px) {
  .archive__head {
    flex-direction: column;
    align-items: stretch;
  }
  .archive__head .btn {
    align-self: flex-start;
  }
}
</style>
