<template>
  <div class="playlog">
    <div class="playlog__head">
      <span class="playlog__tag">再生ログ</span>
      <button class="playlog__toggle" type="button" @click="open = !open">
        {{ open ? '閉じる' : `開く（${tracks.length}）` }}
      </button>
    </div>
    <ul v-if="open" class="playlog__list">
      <li v-if="!tracks.length" class="playlog__empty">まだ再生ログがありません。</li>
      <li v-for="t in tracks" :key="t.id" class="playlog__item">
        <span class="playlog__time">{{ fmt(t.played_at) }}</span>
        <a
          class="playlog__track"
          :href="`https://youtu.be/${t.youtube_id}`"
          target="_blank"
          rel="noopener"
        >♪ {{ t.title || t.youtube_id }}</a>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { api } from '../api'

const props = defineProps({
  stationId: { type: [Number, String], default: null },
  // WebSocket の track_update で届いた最新曲（あればリロードなしで先頭に差し込む）
  latest: { type: Object, default: null },
  // track が付かない更新（BGM切替・番組開始など）では再取得する
  reloadKey: { type: Number, default: 0 },
})

const tracks = ref([])
const open = ref(false)
const MAX_TRACKS = 30

function pad(n) {
  return String(n).padStart(2, '0')
}
function fmt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function load() {
  if (!props.stationId) {
    tracks.value = []
    return
  }
  try {
    const res = await api(`/stations/${props.stationId}/tracks?limit=${MAX_TRACKS}`)
    tracks.value = res.tracks || []
  } catch (e) {
    tracks.value = []
  }
}

// WebSocket で届いた曲を先頭に差し込む（同じIDは積み増さない）
function prepend(track) {
  if (!track || !track.youtube_id) return
  const id = track.id
  const rest = id ? tracks.value.filter((t) => t.id !== id) : tracks.value
  if (!id && rest[0] && rest[0].youtube_id === track.youtube_id) return
  tracks.value = [
    {
      id: id || `ws-${Date.now()}`,
      youtube_id: track.youtube_id,
      title: track.title,
      played_at: track.played_at || new Date().toISOString(),
    },
    ...rest,
  ].slice(0, MAX_TRACKS)
}

watch(() => props.latest, (t) => {
  if (t) prepend(t)
})
watch(() => props.reloadKey, load)
watch(() => props.stationId, load)
onMounted(load)
</script>

<style scoped>
.playlog {
  margin-top: 12px;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  border-radius: 10px;
  overflow: hidden;
}
.playlog__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--line);
}
.playlog__tag {
  font-size: 10px;
  letter-spacing: 2px;
  color: var(--text-dim);
}
.playlog__toggle {
  background: none;
  border: 1px solid var(--line-strong);
  color: var(--text);
  font-size: 11px;
  border-radius: 999px;
  padding: 3px 10px;
  cursor: pointer;
}
.playlog__toggle:hover {
  border-color: var(--green);
  color: var(--green);
}
.playlog__list {
  list-style: none;
  margin: 0;
  padding: 4px 0;
  max-height: 260px;
  overflow-y: auto;
}
.playlog__item {
  display: flex;
  gap: 8px;
  align-items: baseline;
  padding: 6px 12px;
  border-bottom: 1px solid var(--line);
  font-size: 12px;
}
.playlog__item:last-child {
  border-bottom: none;
}
.playlog__time {
  color: var(--text-dim);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  font-size: 11px;
}
.playlog__track {
  color: var(--text);
  text-decoration: none;
  word-break: break-word;
}
.playlog__track:hover {
  color: var(--green);
}
.playlog__empty {
  padding: 10px 12px;
  color: var(--text-dim);
  font-size: 12px;
}
</style>
