<template>
  <div class="timetable">
    <div class="timetable__head">
      <h2>番組表</h2>
      <label class="field">
        <span>日付（空欄で直近7日）</span>
        <input type="date" v-model="date" @change="load" />
      </label>
    </div>

    <!-- ★ お気に入り局（掲示板で星を付けた局＝自分のプリセット） -->
    <section class="favs">
      <div class="favs__head">
        <h3>★ お気に入り局</h3>
        <span v-if="auth.isLoggedIn && favorites.length" class="favs__count">{{ favorites.length }}局</span>
      </div>
      <p v-if="!auth.isLoggedIn" class="favs__note">
        ログインすると、星（★）を付けた局がここに並びます。
        <router-link to="/login">ログイン</router-link>
      </p>
      <p v-else-if="!favorites.length" class="favs__note">
        まだお気に入りがありません。局の掲示板で「☆」を押すと登録できます
        （<router-link to="/">チューナー</router-link> から周波数を合わせてください）。
      </p>
      <ul v-else class="favs__list">
        <li v-for="f in favorites" :key="f.id" class="favs__item">
          <router-link class="favs__link" :to="`/station/${f.id}`" :title="`${f.callsign} の掲示板へ`">
            <span class="favs__star">★</span>
            <span class="favs__freq">{{ f.frequency.toFixed(1) }} MHz</span>
            <span class="favs__name">{{ f.callsign }}</span>
            <span v-if="f.is_bot" class="favs__bot">🤖 AUTO DJ</span>
            <span class="favs__live" :class="{ 'is-live': f.is_live }">{{ f.is_live ? '● ON AIR' : '○ OFF' }}</span>
            <span class="favs__go">▶</span>
          </router-link>
        </li>
      </ul>
    </section>

    <p v-if="!rows.length" class="empty">この期間の番組はありません。</p>
    <div v-else class="epg-wrap">
      <table class="epg">
        <thead>
          <tr>
            <th>日時</th>
            <th>周波数</th>
            <th>番組名</th>
            <th>コールサイン</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in rows" :key="p.id" :class="{ 'is-favorite': isFavorite(p) }">
            <td class="epg__time">{{ fmt(p.start_time) }} - {{ fmtTime(p.end_time) }}</td>
            <td class="epg__freq">
              <span v-if="isFavorite(p)" class="epg__star" title="お気に入り局">★</span>
              {{ p.frequency.toFixed(1) }} MHz
            </td>
            <td class="epg__title">{{ p.title }}</td>
            <td class="epg__station">
              <router-link v-if="p.station_id" :to="`/station/${p.station_id}`" :title="`${p.callsign} の掲示板へ`">
                {{ p.callsign }}
              </router-link>
              <template v-else>{{ p.callsign }}</template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { api } from '../api'
import { toastError } from '../toast'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const rows = ref([])
const date = ref('')
// ★ お気に入り局（掲示板で星を付けた局）
const favorites = ref([])
const favoriteIds = computed(() => new Set(favorites.value.map((f) => f.id)))

function isFavorite(p) {
  return p && p.station_id != null && favoriteIds.value.has(p.station_id)
}

function pad(n) {
  return String(n).padStart(2, '0')
}
function fmt(iso) {
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
function fmtTime(iso) {
  const d = new Date(iso)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function load() {
  try {
    const q = date.value ? `?date=${date.value}` : ''
    const res = await api(`/timetable${q}`)
    rows.value = res.programs || []
  } catch (e) {
    toastError(`番組表の読み込みに失敗しました: ${e.message}`)
  }
}

// ★ お気に入り局（ログイン時のみ）
async function loadFavorites() {
  if (!auth.isLoggedIn) {
    favorites.value = []
    return
  }
  try {
    const res = await api('/favorites')
    favorites.value = res.favorites || []
  } catch (e) {
    favorites.value = []
  }
}

onMounted(() => {
  load()
  loadFavorites()
})
</script>

<style scoped>
/* ★ お気に入り局（自分のプリセット） */
.favs {
  background: var(--panel);
  border: 1px solid var(--line-strong);
  border-left: 3px solid var(--green);
  padding: 12px 14px;
  margin-bottom: 18px;
}
.favs__head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 8px;
}
.favs__head h3 {
  margin: 0;
  font-size: 14px;
  letter-spacing: 1px;
  color: var(--green);
}
.favs__count {
  font-size: 11px;
  color: var(--text-dim);
}
.favs__note {
  margin: 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-dim);
}
.favs__note a {
  color: var(--green);
}
.favs__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.favs__item {
  min-width: 0;
}
.favs__link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  background: var(--panel-deep);
  border: 1px solid var(--line-strong);
  color: var(--text);
  text-decoration: none;
  font-size: 12px;
  white-space: nowrap;
}
.favs__link:hover {
  border-color: var(--green);
}
.favs__star,
.favs__freq,
.favs__go {
  color: var(--green);
}
.favs__freq {
  font-variant-numeric: tabular-nums;
}
.favs__bot {
  font-size: 10px;
  color: var(--text-dim);
}
.favs__live {
  font-size: 11px;
  color: var(--text-dim);
}
.favs__live.is-live {
  color: var(--green);
}
/* 番組表: お気に入り局の行を強調 */
.epg tr.is-favorite {
  background: rgba(0, 255, 130, 0.045);
}
.epg__star {
  color: var(--green);
  margin-right: 4px;
}
.epg__station a {
  color: var(--green);
  text-decoration: none;
  border-bottom: 1px dashed var(--line-strong);
}
.epg__station a:hover {
  border-bottom-style: solid;
}

.timetable__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 18px;
}
.timetable__head h2 {
  margin: 0;
  font-size: 22px;
  color: var(--green);
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field span {
  font-size: 11px;
  color: var(--text-dim);
  letter-spacing: 1px;
}
.field input {
  background: var(--panel-deep);
  border: 1px solid var(--line-strong);
  color: var(--text);
  font-family: inherit;
  padding: 8px 10px;
  border-radius: 0;
}
.empty {
  color: var(--text-dim);
}
.epg-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.epg {
  width: 100%;
  min-width: 560px;
  border-collapse: collapse;
  background: var(--panel);
  border: 1px solid var(--line-strong);
}
.epg th,
.epg td {
  text-align: left;
  padding: 12px 14px;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}
.epg th {
  color: var(--text-dim);
  font-weight: 400;
  letter-spacing: 2px;
  font-size: 11px;
  border-bottom: 1px solid var(--line-strong);
}
.epg__time {
  color: var(--text-dim);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.epg__freq {
  color: var(--green);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.epg__title {
  color: var(--text);
}
.epg__station {
  color: var(--text-dim);
}

@media (max-width: 640px) {
  .timetable__head {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
