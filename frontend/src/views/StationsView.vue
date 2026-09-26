<template>
  <div class="stations">
    <div class="stations__head">
      <div>
        <h2>周波数を探す</h2>
        <p>
          76.0〜89.0MHz の放送局。自由な周波数（{{ freeRangeText }}）の空きを取得して開局できます。
          <!-- 専用局帯は24時間常設の申請専用 -->
          <router-link class="stations__link" to="/frequencies">周波数マップ</router-link>
        </p>
      </div>
      <button class="btn btn--primary" @click="showCreate = !showCreate">
        {{ showCreate ? '閉じる' : '＋ 開局する' }}
      </button>
    </div>

    <form v-if="showCreate" class="create" @submit.prevent="createStation">
      <div class="create__grid">
        <label class="field">
          <span>周波数（空き・{{ freeRangeText }}）</span>
          <select v-model="form.frequency">
            <option v-for="f in available" :key="f" :value="f">{{ f.toFixed(1) }} MHz</option>
          </select>
        </label>
        <label class="field">
          <span>コールサイン（局名）</span>
          <input v-model="form.callsign" placeholder="例: JODR-FM Midnight Tokyo" />
        </label>
      </div>
      <label class="field">
        <span>放送方針（説明）</span>
        <input v-model="form.description" placeholder="どんな局ですか？" />
      </label>
      <label class="field">
        <span>AI DJのキャラクター設定（任意）</span>
        <input v-model="form.ai_dj_prompt" placeholder="例: クールで渋い深夜DJ" />
      </label>
      <p v-if="createError" class="err">{{ createError }}</p>
      <button class="btn btn--amber" type="submit" :disabled="!auth.isLoggedIn">
        {{ auth.isLoggedIn ? 'この周波数で開局する' : '開局にはログインが必要です' }}
      </button>
    </form>

    <div class="stations__grid">
      <router-link
        v-for="s in stations"
        :key="s.id"
        :to="`/station/${s.id}`"
        class="station-card"
      >
        <div class="station-card__top">
          <span class="station-card__live" :class="{ 'is-live': s.is_live }">
            {{ s.is_live ? '● LIVE' : '○ OFF' }}
          </span>
          <span v-if="s.is_bot" class="station-card__bot">🤖 AUTO DJ</span>
          <span class="station-card__freq">{{ s.frequency.toFixed(1) }} MHz</span>
        </div>
        <div class="station-card__name">{{ s.callsign }}</div>
        <div class="station-card__desc">{{ s.description }}</div>
        <div class="station-card__meta">
          <span>DJ: {{ s.owner_username }}</span>
          <span>LISTENER {{ s.listener_count }}</span>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const stations = ref([])
const available = ref([])
// 開局できる帯域（自由な周波数）の情報
const band = ref(null)
const bands = ref([])
const showCreate = ref(false)
const createError = ref('')
const form = reactive({ frequency: null, callsign: '', description: '', ai_dj_prompt: '' })

const freeRangeText = computed(() => {
  const free = bands.value.filter((b) => !b.dedicated)
  if (!free.length) return band.value ? `${band.value.min.toFixed(1)}〜${band.value.max.toFixed(1)}MHz` : '80.0〜89.0MHz'
  return free.map((b) => `${b.min.toFixed(1)}〜${b.max.toFixed(1)}MHz`).join(' と ')
})

async function load() {
  try {
    const [s, a] = await Promise.all([api('/stations'), api('/stations/available')])
    stations.value = s.stations || []
    available.value = a.available || []
    band.value = a.band || null
    bands.value = a.bands || []
    if (!form.frequency && available.value.length) form.frequency = available.value[0]
  } catch (e) {
    console.error(e)
  }
}

async function createStation() {
  createError.value = ''
  try {
    const res = await api('/stations', {
      method: 'POST',
      body: JSON.stringify({ ...form, frequency: Number(form.frequency) }),
    })
    router.push(`/station/${res.station.id}`)
  } catch (e) {
    createError.value = e.message
  }
}

onMounted(load)
</script>

<style scoped>
.stations__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}
.stations__head h2 {
  margin: 0 0 6px;
  font-size: 22px;
  color: var(--green);
}
.stations__head p {
  margin: 0;
  font-size: 12px;
  color: var(--text-dim);
  line-height: 1.7;
}
.stations__link {
  color: var(--green);
  text-decoration: none;
  border-bottom: 1px dashed var(--line-strong);
  margin-left: 6px;
  white-space: nowrap;
}
.stations__link:hover {
  border-bottom-color: var(--green);
}
.create {
  background: var(--panel);
  border: 1px solid var(--line-strong);
  padding: 18px;
  margin-bottom: 20px;
}
.create__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
}
.field span {
  font-size: 11px;
  color: var(--text-dim);
  letter-spacing: 1px;
}
.field input,
.field select {
  background: var(--panel-deep);
  border: 1px solid var(--line-strong);
  color: var(--text);
  font-family: inherit;
  font-size: 14px;
  padding: 10px 12px;
  outline: none;
  border-radius: 0;
}
.field input:focus {
  border-color: var(--green);
}
.err {
  color: var(--green);
  font-size: 12px;
}
.stations__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
}
.stations__grid > * {
  min-width: 0;
}
.station-card {
  position: relative;
  display: block;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  padding: 16px;
  text-decoration: none;
  color: var(--text);
  transition: border-color 0.12s ease;
}
.station-card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background-image: repeating-linear-gradient(45deg, #1c1c1c 0 6px, #0a0a0a 6px 12px);
}
.station-card:hover {
  border-color: var(--green);
}
.station-card__top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.station-card__live {
  font-size: 11px;
  color: var(--text-dim);
  letter-spacing: 1px;
  white-space: nowrap;
}
.station-card__live.is-live {
  color: var(--green);
  animation: blink 1.8s infinite;
}
.station-card__bot {
  flex-shrink: 0;
  font-size: 10px;
  line-height: 1;
  letter-spacing: 1px;
  color: var(--green);
  border: 1px solid var(--line-strong);
  padding: 3px 7px;
  white-space: nowrap;
}
.station-card__freq {
  margin-left: auto;
  padding-left: 10px;
  font-size: 18px;
  color: var(--green);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.station-card__name {
  font-size: 16px;
  font-weight: 700;
  color: var(--green);
  margin-bottom: 6px;
}
.station-card__desc {
  font-size: 12px;
  color: var(--text-dim);
  line-height: 1.6;
  margin-bottom: 12px;
  min-height: 38px;
}
.station-card__meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-dim);
  border-top: 1px dashed var(--line-strong);
  padding-top: 10px;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
}

@media (max-width: 640px) {
  .stations__head {
    flex-direction: column;
    align-items: stretch;
  }
  .create__grid {
    grid-template-columns: 1fr;
  }
  .stations__grid {
    grid-template-columns: 1fr;
  }
}
</style>
