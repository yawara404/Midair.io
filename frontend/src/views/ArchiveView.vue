<template>
  <div class="archive">
    <div class="archive__head">
      <div>
        <h2>過去スレッド（アーカイブ）</h2>
        <p>
          周波数ごとのスレッド一覧です（1スレ {{ maxPosts }} 投稿で自動的に新スレへ）。
          <strong>ログイン不要</strong>で過去ログを読めます。
        </p>
      </div>
      <button class="btn btn--ghost" @click="loadThreads">↻ 更新</button>
    </div>

    <p v-if="!groups.length" class="archive__empty">まだスレッドがありません。</p>

    <div v-else class="archive__layout">
      <!-- 左：周波数一覧 -->
      <aside class="archive__freqs">
        <div class="archive__freqs-head">周波数</div>
        <button
          v-for="g in groups"
          :key="g.station_id"
          class="freq-item"
          :class="{ 'is-active': g.station_id === selectedStationId }"
          @click="selectStation(g.station_id)"
        >
          <span class="freq-item__freq">{{ g.frequency != null ? g.frequency.toFixed(1) : '—' }}<span class="freq-item__unit">MHz</span></span>
          <span class="freq-item__name">{{ g.callsign || '—' }}</span>
          <span class="freq-item__meta">{{ g.threads.length }} スレ</span>
        </button>
      </aside>

      <!-- 右：選択した周波数のスレッドカード -->
      <section class="archive__cards">
        <div v-if="currentGroup" class="archive__cards-head">
          <span class="archive__cards-freq">{{ currentGroup.frequency != null ? currentGroup.frequency.toFixed(1) : '—' }} MHz</span>
          <span class="archive__cards-name">{{ currentGroup.callsign }}</span>
          <span class="archive__cards-count">{{ currentGroup.threads.length }} スレッド</span>
        </div>

        <div class="archive__grid">
          <router-link
            v-for="t in currentThreads"
            :key="t.id"
            class="thread-card"
            :class="{ 'is-archived': t.is_archived }"
            :to="`/thread/${t.id}`"
          >
            <span class="thread-card__title">{{ t.title }}</span>
            <span class="thread-card__meta">
              {{ t.post_count }} / {{ maxPosts }} 投稿 ・ {{ fmt(t.created_at) }}
            </span>
            <span v-if="t.is_archived" class="thread-card__badge">過去ログ</span>
            <span v-else class="thread-card__badge thread-card__badge--live">現行スレ</span>
          </router-link>
          <p v-if="!currentThreads.length" class="archive__empty">この周波数にはスレッドがありません。</p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'

const route = useRoute()
const threads = ref([])
const maxPosts = ref(1000)
const selectedStationId = ref(null)

// 周波数（ステーション）ごとにスレッドをまとめる
const groups = computed(() => {
  const map = new Map()
  for (const t of threads.value) {
    if (!map.has(t.station_id)) {
      map.set(t.station_id, {
        station_id: t.station_id,
        frequency: t.frequency,
        callsign: t.station_callsign,
        threads: [],
      })
    }
    map.get(t.station_id).threads.push(t)
  }
  // 周波数順
  return [...map.values()].sort((a, b) => (a.frequency ?? 0) - (b.frequency ?? 0))
})

const currentGroup = computed(
  () => groups.value.find((g) => g.station_id === selectedStationId.value) || null
)
const currentThreads = computed(() =>
  currentGroup.value ? currentGroup.value.threads : []
)

function selectStation(id) {
  selectedStationId.value = id
}

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
    const res = await api('/threads?limit=300')
    threads.value = res.threads || []
    maxPosts.value = res.max_posts || 1000
    // 選択の確定（?station= → 既存選択 → 先頭）
    const q = parseInt(route.query.station, 10)
    if (Number.isFinite(q) && groups.value.some((g) => g.station_id === q)) {
      selectedStationId.value = q
    } else if (!groups.value.some((g) => g.station_id === selectedStationId.value)) {
      selectedStationId.value = groups.value.length ? groups.value[0].station_id : null
    }
  } catch (e) {
    console.error(e)
    threads.value = []
  }
}

onMounted(loadThreads)
watch(() => route.query.station, loadThreads)
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
  grid-template-columns: 240px 1fr;
  gap: 18px;
  align-items: start;
}

/* 左：周波数一覧 */
.archive__freqs {
  background: var(--panel);
  border: 1px solid var(--line-strong);
  display: flex;
  flex-direction: column;
  max-height: 74vh;
  overflow-y: auto;
}
.archive__freqs-head {
  padding: 10px 12px;
  border-bottom: 1px solid var(--line-strong);
  font-size: 12px;
  letter-spacing: 1px;
  color: var(--green);
}
.freq-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  text-align: left;
  font-family: inherit;
  padding: 10px 12px;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--line);
  color: var(--text);
  cursor: pointer;
}
.freq-item:hover {
  background: #151515;
}
.freq-item.is-active {
  border-left: 3px solid var(--green);
  background: #151515;
}
.freq-item__freq {
  font-size: 16px;
  color: var(--green);
  font-variant-numeric: tabular-nums;
}
.freq-item__unit {
  font-size: 10px;
  color: var(--text-dim);
  margin-left: 4px;
}
.freq-item__name {
  font-size: 12px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.freq-item__meta {
  font-size: 11px;
  color: var(--text-dim);
}

/* 右：スレッドカード */
.archive__cards-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--line-strong);
}
.archive__cards-freq {
  font-size: 18px;
  color: var(--green);
  font-variant-numeric: tabular-nums;
}
.archive__cards-name {
  font-size: 14px;
  color: var(--text);
  flex: 1;
  min-width: 0;
}
.archive__cards-count {
  font-size: 12px;
  color: var(--text-dim);
}
.archive__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
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

@media (max-width: 900px) {
  .archive__layout {
    grid-template-columns: 1fr;
  }
  .archive__freqs {
    max-height: 32vh;
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
}
</style>
