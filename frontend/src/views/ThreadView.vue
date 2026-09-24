<template>
  <div class="thread-page">
    <div class="thread-page__grid">
      <!-- 左：同じ局のスレッド一覧 -->
      <aside class="thread-page__list">
        <div class="thread-page__list-head">この局のスレッド</div>
        <router-link
          v-for="t in threads"
          :key="t.id"
          class="thread-page__item"
          :class="{ 'is-active': thread && thread.id === t.id }"
          :to="`/thread/${t.id}`"
        >
          <span class="thread-page__item-title">{{ t.title }}</span>
          <span class="thread-page__item-meta">
            {{ t.post_count }} / {{ maxPosts }} 投稿
            <span v-if="t.is_archived" class="thread-page__archived">過去ログ</span>
          </span>
        </router-link>
      </aside>

      <!-- 右：過去ログ（掲示板に似たUI） -->
      <section class="thread-page__stream">
        <div class="now">
          <span class="now__dot" :class="{ 'is-live': thread && !thread.is_archived }"></span>
          {{ thread ? thread.station_callsign : '—' }}
          <span class="now__freq">{{ thread && thread.frequency != null ? thread.frequency.toFixed(1) : '—' }} MHz</span>
          <router-link class="now__back" to="/archive">← 一覧</router-link>
        </div>

        <div class="thread-bar">
          <span class="thread-bar__no">第{{ thread ? thread.number : '—' }}スレ</span>
          <span class="thread-bar__title">{{ thread ? thread.title : '読み込み中…' }}</span>
          <span class="thread-bar__count">{{ thread ? thread.post_count : 0 }} / {{ maxPosts }}</span>
          <span v-if="thread && thread.is_archived" class="thread-bar__archived">過去ログ</span>
        </div>

        <ChatStream :messages="messages" :my-handle="''" />

        <p class="thread-page__note">
          過去ログ（読み取り専用）です。投稿はできません。
          <router-link :to="thread ? `/station/${thread.station_id}` : '/stations'">
            現在の掲示板へ →
          </router-link>
        </p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import ChatStream from '../components/ChatStream.vue'
import { api } from '../api'

const route = useRoute()
const thread = ref(null)
const messages = ref([])
const threads = ref([])
const maxPosts = ref(1000)

async function load(id) {
  thread.value = null
  messages.value = []
  threads.value = []
  try {
    const res = await api(`/threads/${id}`)
    thread.value = res.thread || null
    messages.value = res.messages || []
    maxPosts.value = res.max_posts || 1000
    if (thread.value) {
      const list = await api(`/stations/${thread.value.station_id}/threads`)
      threads.value = list.threads || []
    }
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => load(route.params.id))
watch(() => route.params.id, (id) => load(id))
</script>

<style scoped>
.thread-page {
  height: 100%;
  min-height: 0;
  display: flex;
}
.thread-page__grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 16px;
}
.thread-page__grid > * {
  min-width: 0;
}

/* 左：スレッド一覧 */
.thread-page__list {
  background: var(--panel);
  border: 1px solid var(--line-strong);
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
}
.thread-page__list-head {
  padding: 10px 12px;
  border-bottom: 1px solid var(--line-strong);
  font-size: 12px;
  letter-spacing: 1px;
  color: var(--green);
}
.thread-page__item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
  text-decoration: none;
  color: var(--text);
}
.thread-page__item:hover {
  background: #151515;
}
.thread-page__item.is-active {
  border-left: 3px solid var(--green);
  background: #151515;
}
.thread-page__item-title {
  font-size: 13px;
  color: var(--green);
}
.thread-page__item-meta {
  font-size: 11px;
  color: var(--text-dim);
  font-variant-numeric: tabular-nums;
}
.thread-page__archived {
  font-size: 10px;
  border: 1px solid var(--line-strong);
  padding: 1px 5px;
  margin-left: 4px;
}

/* 右：掲示板に似たUI */
.thread-page__stream {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.now {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  font-size: 14px;
  color: var(--hi);
}
.now__dot {
  width: 10px;
  height: 10px;
  background: var(--dim);
}
.now__dot.is-live {
  background: var(--hi);
  animation: blink 1.6s infinite;
}
.now__freq {
  margin-left: auto;
  color: var(--green);
  font-variant-numeric: tabular-nums;
}
.now__back {
  color: var(--green);
  text-decoration: none;
  border: 1px solid var(--line-strong);
  padding: 2px 8px;
  font-size: 12px;
}
.now__back:hover {
  background: var(--green);
  color: #000;
}

.thread-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  margin: 8px 0 10px;
  background: var(--panel-deep);
  border: 1px solid var(--line-strong);
  font-size: 12px;
  flex-wrap: wrap;
}
.thread-bar__no {
  color: #000;
  background: var(--green);
  font-weight: 700;
  padding: 2px 8px;
  letter-spacing: 1px;
}
.thread-bar__title {
  color: var(--text);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.thread-bar__count {
  color: var(--text-dim);
  font-variant-numeric: tabular-nums;
}
.thread-bar__archived {
  font-size: 10px;
  color: var(--text-dim);
  border: 1px solid var(--line-strong);
  padding: 2px 6px;
}

.thread-page__note {
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-dim);
}
.thread-page__note a {
  color: var(--green);
}

@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.25;
  }
}

@media (max-width: 900px) {
  .thread-page {
    height: auto;
  }
  .thread-page__grid {
    grid-template-columns: 1fr;
  }
  .thread-page__list {
    max-height: 32vh;
  }
  .thread-page__stream {
    height: 72vh;
    min-height: 420px;
  }
}
</style>
