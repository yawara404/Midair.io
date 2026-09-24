<template>
  <div class="admin">
    <div class="admin__head">
      <div>
        <h2>管理者 — 専用局の申請審査</h2>
        <p>専用局（24時間常設）の開設申請を承認・却下します。</p>
      </div>
      <button class="btn btn--ghost" @click="load">↻ 更新</button>
    </div>

    <p v-if="!auth.isLoggedIn" class="note">ログインしてください。 <router-link to="/login">ログイン</router-link></p>
    <p v-else-if="auth.user && !isAdmin" class="note">管理者権限が必要です。</p>
    <p v-else-if="!auth.user" class="note">読み込み中…</p>

    <template v-else>
      <div class="stats">
        <span>審査待ち {{ stats.pending }}</span>
        <span>承認 {{ stats.approved }}</span>
        <span>却下 {{ stats.rejected }}</span>
      </div>

      <div class="filters">
        <button
          v-for="f in filters"
          :key="f.value"
          class="btn btn--ghost"
          :class="{ 'is-active': filter === f.value }"
          @click="filter = f.value; load()"
        >{{ f.label }}</button>
      </div>

      <p v-if="!applications.length" class="note">申請はありません。</p>

      <div v-for="a in applications" :key="a.id" class="card" :class="`card--${a.status}`">
        <div class="card__top">
          <span class="card__freq">{{ a.desired_frequency.toFixed(1) }} MHz</span>
          <span class="card__callsign">{{ a.callsign }}</span>
          <span class="card__status" :class="`st--${a.status}`">{{ statusLabel(a.status) }}</span>
        </div>
        <div class="card__title">{{ a.station_title }}<span class="card__genre">{{ a.genre }}</span></div>
        <p class="card__concept">{{ a.concept_description }}</p>
        <p class="card__meta">申請者: {{ a.applicant_username }} ・ 初期音源 {{ a.track_count }}曲 ・ {{ fmt(a.created_at) }}</p>
        <p v-if="a.ai_dj_concept" class="card__meta">AI DJ: {{ a.ai_dj_concept }}</p>

        <details class="card__tracks" v-if="a.initial_tracks && a.initial_tracks.length">
          <summary>初期音源リスト（{{ a.track_count }}）</summary>
          <a
            v-for="(t, i) in a.initial_tracks"
            :key="i"
            :href="`https://youtu.be/${t.youtube_id}`"
            target="_blank"
            rel="noopener"
            class="track"
          >♪ {{ t.title || t.youtube_id }}</a>
        </details>

        <p v-if="a.status === 'rejected' && a.review_note" class="card__note">理由: {{ a.review_note }}</p>

        <div v-if="a.status === 'pending'" class="card__actions">
          <input v-model="notes[a.id]" class="field-input" placeholder="審査コメント（却下理由など）" />
          <button class="btn btn--primary" :disabled="busy[a.id]" @click="approve(a)">承認</button>
          <button class="btn btn--ghost" :disabled="busy[a.id]" @click="reject(a)">却下</button>
        </div>
        <p v-if="errors[a.id]" class="err">{{ errors[a.id] }}</p>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const applications = ref([])
const stats = reactive({ pending: 0, approved: 0, rejected: 0 })
const notes = reactive({})
const busy = reactive({})
const errors = reactive({})
const filter = ref('pending')
const filters = [
  { value: 'pending', label: '審査待ち' },
  { value: 'approved', label: '承認済み' },
  { value: 'rejected', label: '却下' },
  { value: '', label: 'すべて' },
]

const isAdmin = computed(() => !!auth.user && auth.user.role === 'admin')

function statusLabel(s) {
  return { pending: '審査待ち', approved: '承認済み', rejected: '却下' }[s] || s
}
function fmt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function load() {
  if (!isAdmin.value) return
  try {
    const q = filter.value ? `?status=${filter.value}` : ''
    const [list, st] = await Promise.all([
      api(`/admin/applications${q}`),
      api('/admin/applications/stats'),
    ])
    applications.value = list.applications || []
    Object.assign(stats, st.counts || {})
  } catch (e) {
    console.error(e)
  }
}

async function approve(a) {
  errors[a.id] = ''
  busy[a.id] = true
  try {
    await api(`/admin/applications/${a.id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ note: notes[a.id] || '' }),
    })
    await load()
  } catch (e) {
    errors[a.id] = e.message
  } finally {
    busy[a.id] = false
  }
}

async function reject(a) {
  if (!confirm('この申請を却下しますか？')) return
  errors[a.id] = ''
  busy[a.id] = true
  try {
    await api(`/admin/applications/${a.id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ note: notes[a.id] || '' }),
    })
    await load()
  } catch (e) {
    errors[a.id] = e.message
  } finally {
    busy[a.id] = false
  }
}

onMounted(load)

// ユーザー情報が後から取得されたら読み込む（isAdmin 判定の確定後）
watch(
  () => auth.user,
  () => {
    if (isAdmin.value) load()
  }
)
</script>

<style scoped>
.admin__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}
.admin__head h2 {
  margin: 0 0 4px;
  font-size: 22px;
  color: var(--green);
}
.admin__head p {
  margin: 0;
  font-size: 12px;
  color: var(--text-dim);
}
.note {
  color: var(--text-dim);
  font-size: 13px;
}
.note a {
  color: var(--green);
}
.stats {
  display: flex;
  gap: 18px;
  font-size: 13px;
  color: var(--text-dim);
  margin-bottom: 12px;
}
.filters {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.filters .btn.is-active {
  color: var(--green);
  border-color: var(--green);
}
.card {
  background: var(--panel);
  border: 1px solid var(--line-strong);
  padding: 14px 16px;
  margin-bottom: 14px;
}
.card--approved {
  border-left: 3px solid var(--green);
}
.card--rejected {
  opacity: 0.7;
}
.card__top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.card__freq {
  color: var(--green);
  font-variant-numeric: tabular-nums;
}
.card__callsign {
  font-weight: 700;
  color: var(--text);
}
.card__status {
  margin-left: auto;
  font-size: 11px;
  letter-spacing: 1px;
  border: 1px solid var(--line-strong);
  padding: 2px 8px;
  color: var(--text-dim);
}
.st--approved {
  color: var(--green);
  border-color: var(--green);
}
.card__title {
  font-size: 15px;
  color: var(--text);
  margin-bottom: 4px;
}
.card__genre {
  margin-left: 10px;
  font-size: 11px;
  color: var(--text-dim);
  border: 1px solid var(--line-strong);
  padding: 1px 6px;
}
.card__concept {
  margin: 6px 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text);
  white-space: pre-wrap;
}
.card__meta {
  margin: 0 0 4px;
  font-size: 11px;
  color: var(--text-dim);
}
.card__tracks {
  margin: 8px 0;
  font-size: 12px;
}
.card__tracks summary {
  cursor: pointer;
  color: var(--green);
}
.track {
  display: block;
  padding: 3px 0 3px 12px;
  color: var(--text);
  text-decoration: none;
  font-size: 12px;
}
.track:hover {
  color: var(--green);
  text-decoration: underline;
}
.card__note {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--text-dim);
}
.card__actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}
.field-input {
  flex: 1;
  min-width: 160px;
  background: var(--panel-deep);
  border: 1px solid var(--line-strong);
  color: var(--text);
  font-family: inherit;
  font-size: 13px;
  padding: 8px 10px;
  outline: none;
  border-radius: 0;
}
.err {
  color: var(--green);
  font-size: 12px;
  margin: 8px 0 0;
}
</style>
