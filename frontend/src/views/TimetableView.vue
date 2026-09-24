<template>
  <div class="timetable">
    <div class="timetable__head">
      <h2>番組表</h2>
      <label class="field">
        <span>日付（空欄で直近7日）</span>
        <input type="date" v-model="date" @change="load" />
      </label>
    </div>

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
          <tr v-for="p in rows" :key="p.id">
            <td class="epg__time">{{ fmt(p.start_time) }} - {{ fmtTime(p.end_time) }}</td>
            <td class="epg__freq">{{ p.frequency.toFixed(1) }} MHz</td>
            <td class="epg__title">{{ p.title }}</td>
            <td class="epg__station">{{ p.callsign }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const rows = ref([])
const date = ref('')

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
    console.error(e)
  }
}

onMounted(load)
</script>

<style scoped>
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
