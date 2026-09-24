<template>
  <div class="archive">
    <div class="archive__head">
      <div>
        <h2>過去スレッド（アーカイブ）</h2>
        <p>
          掲示板のスレッドを保存しています（1スレ {{ maxPosts }} 投稿で自動的に新スレへ）。
          <strong>ログイン不要</strong>で過去の掲示板を読めます。
        </p>
      </div>
      <button class="btn btn--ghost" @click="loadThreads">↻ 更新</button>
    </div>

    <div v-if="stationFilter" class="archive__filter">
      <span>表示中: {{ stationFilterName }}</span>
      <router-link class="archive__filter-clear" to="/archive">すべて表示</router-link>
    </div>

    <div class="archive__layout">
      <aside class="archive__list">
        <button
          v-for="t in threads"
          :key="t.id"
          class="session-card"
          :class="{ 'is-active': current && current.id === t.id }"
          @click="openThread(t)"
        >
          <span class="session-card__title">{{ t.title }}</span>
          <span class="session-card__meta">
            {{ t.frequency != null ? t.frequency.toFixed(1) : '—' }}MHz
            ・ {{ t.post_count }} / {{ maxPosts }} 投稿
            ・ {{ fmt(t.created_at) }}
          </span>
          <span v-if="t.is_archived" class="session-card__archived">過去ログ</span>
        </button>
        <p v-if="!threads.length" class="archive__empty">まだスレッドがありません。</p>
      </aside>

      <section v-if="current" class="thread">
        <div class="thread__head">
          <span class="thread__no">第{{ current.number }}スレ</span>
          <span class="thread__title">{{ current.title }}</span>
          <span class="thread__meta">
            {{ current.frequency != null ? current.frequency.toFixed(1) : '—' }}MHz
            ・ {{ messages.length }}投稿
            ・ {{ fmt(current.created_at) }}〜
          </span>
        </div>

        <div ref="logEl" class="thread__log">
          <div
            v-for="(m, i) in messages"
            :key="m.id"
            class="post"
            :class="`post--${m.message_type}`"
          >
            <span class="post__no">{{ i + 1 }}</span>
            <span class="post__author">{{ m.author }}</span>
            <span class="post__time">{{ fmtTime(m.created_at) }}</span>
            <p class="post__content">{{ m.content }}</p>
          </div>
          <p v-if="!messages.length" class="archive__empty">このスレッドにはまだ投稿がありません。</p>
        </div>
      </section>

      <section v-else class="archive__placeholder">
        左のスレッドを選ぶと、当時の掲示板が表示されます。
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'

const route = useRoute()
const threads = ref([])
const current = ref(null)
const messages = ref([])
const maxPosts = ref(1000)
const logEl = ref(null)

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
function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadThreads() {
  try {
    const q = stationFilter.value ? `?station=${stationFilter.value}` : ''
    // station フィルタは station のスレッド一覧を使う
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

async function openThread(t) {
  current.value = t
  messages.value = []
  try {
    const res = await api(`/threads/${t.id}`)
    current.value = res.thread || t
    messages.value = res.messages || []
    maxPosts.value = res.max_posts || 1000
    await new Promise((r) => setTimeout(r, 0))
    if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight
  } catch (e) {
    console.error(e)
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
  max-height: 74vh;
  overflow-y: auto;
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
.session-card__archived {
  font-size: 10px;
  color: var(--text-dim);
  border: 1px solid var(--line-strong);
  padding: 1px 5px;
  margin-left: 4px;
}
.session-card__meta {
  font-size: 11px;
  color: var(--text-dim);
  font-variant-numeric: tabular-nums;
}

.archive__placeholder {
  color: var(--text-dim);
  font-size: 13px;
  padding: 40px;
  text-align: center;
  border: 1px dashed var(--line-strong);
}

/* 過去の掲示板（スレッド） */
.thread {
  background: var(--panel);
  border: 1px solid var(--line-strong);
  padding: 16px;
}
.thread__head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line-strong);
}
.thread__no {
  color: #000;
  background: var(--green);
  font-weight: 700;
  font-size: 12px;
  padding: 2px 8px;
}
.thread__title {
  font-size: 15px;
  color: var(--green);
  flex: 1;
  min-width: 0;
}
.thread__meta {
  font-size: 12px;
  color: var(--text-dim);
  font-variant-numeric: tabular-nums;
}
.thread__log {
  max-height: 66vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: var(--panel-deep);
  border: 1px solid var(--line);
}
.post {
  border-left: 2px solid var(--line-strong);
  padding: 2px 0 2px 10px;
}
.post__no {
  font-size: 11px;
  color: var(--faint);
  font-variant-numeric: tabular-nums;
  margin-right: 8px;
}
.post__author {
  font-size: 12px;
  color: var(--green);
  margin-right: 8px;
}
.post__time {
  font-size: 11px;
  color: var(--faint);
  font-variant-numeric: tabular-nums;
}
.post__content {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.post--dj {
  border-left-color: var(--green);
}
.post--dj .post__content {
  color: var(--green);
}

@media (max-width: 900px) {
  .archive__layout {
    grid-template-columns: 1fr;
  }
  .archive__list {
    max-height: 40vh;
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
  .thread__log {
    max-height: 50vh;
  }
}
</style>
