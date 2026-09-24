<template>
  <div class="studio">
    <h2 class="studio__title">スタジオ</h2>
    <p v-if="!auth.isLoggedIn" class="studio__guest">
      スタジオを使うにはログインしてください。
      <router-link to="/login">ログイン</router-link>
    </p>

    <p v-else-if="!mine.length" class="studio__guest">
      まだ開局していません。<router-link to="/stations">開局する</router-link>
    </p>

    <div v-for="s in mine" :key="s.id" class="panel">
      <div class="panel__head">
        <span class="panel__freq">{{ s.frequency.toFixed(1) }} MHz</span>
        <span class="panel__name">{{ s.callsign }}</span>
        <span class="panel__live" :class="{ 'is-live': s.is_live }">{{ s.is_live ? '● ON AIR' : '○ OFF' }}</span>
      </div>

      <div class="panel__controls">
        <div class="row">
          <input v-model="s.callsign" class="field-input" placeholder="コールサイン" />
          <input v-model="s.description" class="field-input" placeholder="放送方針" />
          <button class="btn btn--ghost" @click="saveStation(s)">保存</button>
        </div>
        <div class="row">
          <input v-model="bgmUrl[s.id]" class="field-input" placeholder="YouTube URL / 動画ID" />
          <button class="btn btn--amber" @click="setBgm(s)">♪ BGM切替</button>
          <button class="btn btn--ghost" @click="mute(s)">ミュート</button>
          <button v-if="s.status !== 'live'" class="btn btn--ghost" @click="setAir(s, 'on-air')">ON AIR</button>
          <button v-else class="btn btn--ghost" @click="setAir(s, 'off-air')">OFF AIR</button>
          <button class="btn btn--ghost" @click="closeStation(s)">廃局</button>
        </div>
        <div class="row">
          <label class="row__check">
            <input type="checkbox" v-model="s.ai_dj_enabled" @change="saveStation(s)" />
            <span>AI DJ</span>
          </label>
          <input v-model="s.ai_dj_prompt" class="field-input" placeholder="AI DJのキャラクター設定" @change="saveStation(s)" />
        </div>
      </div>

      <div class="panel__programs">
        <div class="panel__subhead">番組表</div>
        <div v-for="p in s.programs" :key="p.id" class="prog">
          <span class="prog__title">{{ p.title }}</span>
          <span class="prog__time">{{ fmt(p.start_time) }} - {{ fmtTime(p.end_time) }}</span>
          <button class="btn btn--ghost" @click="deleteProgram(p)">削除</button>
        </div>
        <form class="prog-form" @submit.prevent="addProgram(s)">
          <input v-model="newProg[s.id].title" class="field-input" placeholder="番組名" required />
          <input v-model="newProg[s.id].start_time" class="field-input" type="datetime-local" required />
          <input v-model="newProg[s.id].end_time" class="field-input" type="datetime-local" required />
          <input v-model="newProg[s.id].default_youtube_id" class="field-input" placeholder="BGM動画ID（任意）" />
          <button class="btn btn--primary" type="submit">番組を追加</button>
        </form>
      </div>

      <!-- DJ BOT（自動DJ局） -->
      <div v-if="s.is_bot" class="panel__programs">
        <div class="panel__subhead">🤖 DJ BOT — 人気曲からランダム再生</div>
        <p class="prog__empty">
          流行りの曲（YouTube 人気チャート）からランダムに選曲して流し続けます。プリセット登録は不要です。
        </p>
        <div class="row">
          <span class="prog__time">再生中: {{ s.current_youtube_id || '—' }}</span>
          <button class="btn btn--ghost" type="button" @click="nextBotTrack(s)">⏭ 次の曲へ</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const mine = ref([])
const bgmUrl = reactive({})
const newProg = reactive({})

function fmt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function load() {
  if (!auth.isLoggedIn) return
  try {
    const res = await api('/stations/mine')
    mine.value = res.stations || []
    for (const s of mine.value) {
      const pr = await api(`/stations/${s.id}/programs`)
      s.programs = pr.programs || []
      if (bgmUrl[s.id] === undefined) bgmUrl[s.id] = ''
      if (!newProg[s.id]) {
        newProg[s.id] = { title: '', start_time: '', end_time: '', default_youtube_id: '' }
      }
    }
  } catch (e) {
    console.error(e)
  }
}

async function nextBotTrack(s) {
  try {
    await api(`/stations/${s.id}/bot/next`, { method: 'POST' })
  } catch (e) {
    console.error(e)
  }
}

async function saveStation(s) {
  try {
    await api(`/stations/${s.id}`, {
      method: 'PUT',
      body: JSON.stringify({
        callsign: s.callsign,
        description: s.description,
        ai_dj_enabled: s.ai_dj_enabled,
        ai_dj_prompt: s.ai_dj_prompt,
      }),
    })
  } catch (e) {
    console.error(e)
  }
}

async function setBgm(s) {
  const url = bgmUrl[s.id] || ''
  if (!url) return
  try {
    await api(`/stations/${s.id}/youtube`, { method: 'POST', body: JSON.stringify({ url }) })
    bgmUrl[s.id] = ''
    s.is_live = true
  } catch (e) {
    console.error(e)
  }
}

async function mute(s) {
  try {
    await api(`/stations/${s.id}/mute`, { method: 'POST' })
  } catch (e) {
    console.error(e)
  }
}

async function setAir(s, action) {
  try {
    const res = await api(`/stations/${s.id}/${action}`, { method: 'POST' })
    s.status = res.status
    s.is_live = res.status === 'live'
  } catch (e) {
    console.error(e)
  }
}

async function closeStation(s) {
  if (!confirm('廃局して周波数を返還しますか？（チャット・番組も削除されます）')) return
  try {
    await api(`/stations/${s.id}`, { method: 'DELETE' })
    mine.value = mine.value.filter((x) => x.id !== s.id)
  } catch (e) {
    console.error(e)
  }
}

async function addProgram(s) {
  const f = newProg[s.id]
  if (!f || !f.title || !f.start_time || !f.end_time) return
  try {
    await api(`/stations/${s.id}/programs`, {
      method: 'POST',
      body: JSON.stringify({
        title: f.title,
        start_time: f.start_time,
        end_time: f.end_time,
        default_youtube_id: f.default_youtube_id,
      }),
    })
    f.title = ''
    f.start_time = ''
    f.end_time = ''
    f.default_youtube_id = ''
    const pr = await api(`/stations/${s.id}/programs`)
    s.programs = pr.programs || []
  } catch (e) {
    console.error(e)
  }
}

async function deleteProgram(p) {
  try {
    await api(`/programs/${p.id}`, { method: 'DELETE' })
    const s = mine.value.find((x) => x.id === p.station_id)
    if (s) {
      const pr = await api(`/stations/${s.id}/programs`)
      s.programs = pr.programs || []
    }
  } catch (e) {
    console.error(e)
  }
}

onMounted(load)
</script>

<style scoped>
.studio__title {
  margin: 0 0 14px;
  font-size: 22px;
  color: var(--green);
}
.studio__guest {
  color: var(--text-dim);
  font-size: 14px;
}
.studio__guest a {
  color: var(--green);
}
.panel {
  background: var(--panel);
  border: 1px solid var(--line-strong);
  margin-bottom: 16px;
}
.panel__head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line-strong);
}
.panel__freq {
  color: var(--green);
  font-variant-numeric: tabular-nums;
}
.panel__name {
  font-weight: 700;
  color: var(--green);
}
.panel__live {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-dim);
}
.panel__live.is-live {
  color: var(--green);
  animation: blink 1.8s infinite;
}
.panel__controls {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.field-input {
  flex: 1;
  background: var(--panel-deep);
  border: 1px solid var(--line-strong);
  color: var(--text);
  font-family: inherit;
  font-size: 13px;
  padding: 8px 10px;
  outline: none;
  border-radius: 0;
}
.field-input:focus {
  border-color: var(--green);
}
.row__check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-dim);
}
.panel__programs {
  border-top: 1px dashed var(--line-strong);
  padding: 14px 16px;
}
.panel__subhead {
  font-size: 12px;
  color: var(--text-dim);
  letter-spacing: 2px;
  margin-bottom: 10px;
}
.prog {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}
.prog__title {
  color: var(--green);
}
.prog__time {
  color: var(--text-dim);
  font-variant-numeric: tabular-nums;
  text-decoration: none;
}
a.prog__time:hover {
  color: var(--green);
  text-decoration: underline;
}
.prog__empty {
  color: var(--text-dim);
  font-size: 12px;
  padding: 8px 0;
}
.prog .btn {
  margin-left: auto;
}
.prog-form {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}
.prog-form .field-input {
  flex: 1;
  min-width: 120px;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
}

@media (max-width: 640px) {
  .panel__head {
    flex-wrap: wrap;
    gap: 8px;
  }
  .panel__live {
    margin-left: auto;
  }
  .row .field-input {
    flex-basis: 100%;
  }
  .row .btn {
    flex: 1;
  }
  .prog {
    flex-wrap: wrap;
  }
}
</style>
