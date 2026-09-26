<template>
  <div class="daf">
    <p v-if="!auth.isLoggedIn" class="daf__note">
      専用局の申請にはログインが必要です。
      <button class="daf__link" type="button" @click="$emit('need-login')">ログイン</button>
    </p>

    <template v-else>
      <form class="daf__form" @submit.prevent="submit">
        <div class="daf__grid">
          <label class="daf__field">
            <span>希望周波数（MHz）</span>
            <input
              v-model="form.desired_frequency"
              type="number"
              :min="freqMin"
              :max="freqMax"
              step="0.1"
              :placeholder="`例: ${exampleFreq}`"
            />
            <small class="daf__hint">
              専用局を申請できるのは専用局帯（{{ freqMin.toFixed(1) }}〜{{ freqMax.toFixed(1) }}MHz）のみです。
            </small>
          </label>
          <label class="daf__field">
            <span>コールサイン（局名）</span>
            <input v-model="form.callsign" placeholder="例: JODR-FM Midair Chill" />
          </label>
        </div>
        <label class="daf__field">
          <span>ステーション名（番組名）</span>
          <input v-model="form.station_title" placeholder="例: Midnight Chill Session" />
        </label>
        <div class="daf__grid">
          <label class="daf__field">
            <span>ジャンル</span>
            <select v-model="form.genre">
              <option v-for="g in genres" :key="g" :value="g">{{ g }}</option>
            </select>
          </label>
          <label class="daf__field">
            <span>AI DJのキャラクター（任意）</span>
            <input v-model="form.ai_dj_concept" placeholder="例: 落ち着いた低音の深夜DJ" />
          </label>
        </div>
        <label class="daf__field">
          <span>放送コンセプト（審査されます）</span>
          <textarea v-model="form.concept_description" rows="3" placeholder="どんな24時間局にしたいか、コンセプトを書いてください"></textarea>
        </label>
        <label class="daf__field">
          <span>初期音源リスト（YouTube URL / 動画ID を1行1つ・任意）</span>
          <textarea v-model="form.tracksText" rows="4" placeholder="https://youtu.be/xxxx&#10;yyyyyyyyyyy"></textarea>
        </label>

        <p v-if="error" class="daf__err">{{ error }}</p>
        <p v-if="ok" class="daf__ok">{{ ok }}</p>

        <button class="btn btn--primary" type="submit" :disabled="busy">
          {{ busy ? '送信中…' : '専用局を申請する' }}
        </button>
      </form>

      <div v-if="mine.length" class="daf__mine">
        <div class="daf__mine-head">
          <span>自分の申請状況</span>
          <button class="btn btn--ghost daf__refresh" type="button" @click="loadMine">↻</button>
        </div>
        <div v-for="a in mine" :key="a.id" class="daf__row">
          <span class="daf__freq">{{ a.desired_frequency.toFixed(1) }} MHz</span>
          <span class="daf__name">{{ a.callsign }}</span>
          <span class="daf__status" :class="`st--${a.status}`">{{ statusLabel(a.status) }}</span>
          <span v-if="a.review_note" class="daf__review">{{ a.review_note }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const emit = defineEmits(['need-login'])

// 帯域（専用局帯）の範囲: 親から渡される（未指定ならサーバー既定の 76.0〜79.9）
const props = defineProps({
  band: { type: Object, default: null },
  // 周波数マップで「専用局を申請」したときに自動入力する周波数
  prefillFrequency: { type: [Number, String], default: null },
})

const auth = useAuthStore()
const genres = ref(['general'])
const mine = ref([])
const error = ref('')
const ok = ref('')
const busy = ref(false)

const freqMin = computed(() => Number(props.band?.min ?? 76.0))
const freqMax = computed(() => Number(props.band?.max ?? 79.9))
const exampleFreq = computed(() => ((freqMin.value + freqMax.value) / 2).toFixed(1))

const form = reactive({
  desired_frequency: '',
  callsign: '',
  station_title: '',
  genre: 'general',
  concept_description: '',
  ai_dj_concept: '',
  tracksText: '',
})

// 周波数マップで「専用局を申請」した周波数を自動入力する
watch(
  () => props.prefillFrequency,
  (f) => {
    if (f === null || f === undefined || f === '') return
    form.desired_frequency = Number(f)
    error.value = ''
    ok.value = ''
  }
)

function statusLabel(s) {
  return { pending: '審査待ち', approved: '承認済み', rejected: '却下' }[s] || s
}

function parseTracks(text) {
  return (text || '')
    .split(/\s+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

async function submit() {
  error.value = ''
  ok.value = ''
  busy.value = true
  try {
    const res = await api('/dedicated/apply', {
      method: 'POST',
      body: JSON.stringify({
        desired_frequency: Number(form.desired_frequency),
        callsign: form.callsign,
        station_title: form.station_title,
        genre: form.genre,
        concept_description: form.concept_description,
        ai_dj_concept: form.ai_dj_concept,
        initial_tracks: parseTracks(form.tracksText),
      }),
    })
    ok.value = `申請を受け付けました（申請ID: ${res.application.id}）。管理者の審査をお待ちください。`
    form.desired_frequency = ''
    form.callsign = ''
    form.station_title = ''
    form.concept_description = ''
    form.ai_dj_concept = ''
    form.tracksText = ''
    await loadMine()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function loadMine() {
  if (!auth.isLoggedIn) return
  try {
    const res = await api('/dedicated/applications/mine')
    mine.value = res.applications || []
  } catch (e) {
    mine.value = []
  }
}

async function loadGenres() {
  try {
    const res = await api('/dedicated/genres')
    genres.value = res.genres || ['general']
    if (genres.value.length) form.genre = genres.value[0]
  } catch (e) {}
}

onMounted(async () => {
  await loadGenres()
  await loadMine()
})

defineExpose({ loadMine })
</script>

<style scoped>
.daf__note {
  color: var(--text-dim);
  font-size: 13px;
}
.daf__link {
  background: none;
  border: none;
  color: var(--green);
  cursor: pointer;
  font-family: inherit;
  font-size: 13px;
  padding: 0;
  text-decoration: underline;
}
.daf__form {
  display: flex;
  flex-direction: column;
}
.daf__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}
.daf__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
}
.daf__field span {
  font-size: 11px;
  letter-spacing: 1px;
  color: var(--text-dim);
}
.daf__field input,
.daf__field select,
.daf__field textarea {
  background: var(--panel-deep);
  border: 1px solid var(--line-strong);
  color: var(--text);
  font-family: inherit;
  font-size: 14px;
  padding: 10px 12px;
  outline: none;
  border-radius: 0;
  resize: vertical;
}
.daf__field input:focus,
.daf__field textarea:focus,
.daf__field select:focus {
  border-color: var(--green);
}
.daf__hint {
  font-size: 11px;
  color: var(--faint);
  line-height: 1.6;
}
.daf__err {
  color: var(--green);
  font-size: 12px;
}
.daf__ok {
  color: var(--green);
  font-size: 13px;
}
.daf__mine {
  margin-top: 16px;
  border-top: 1px dashed var(--line-strong);
  padding-top: 12px;
}
.daf__mine-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  letter-spacing: 1px;
  color: var(--text-dim);
  margin-bottom: 8px;
}
.daf__refresh {
  font-size: 11px;
  padding: 2px 8px;
}
.daf__row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid var(--line);
  flex-wrap: wrap;
  font-size: 13px;
}
.daf__freq {
  color: var(--green);
  font-variant-numeric: tabular-nums;
}
.daf__name {
  color: var(--text);
}
.daf__status {
  font-size: 11px;
  border: 1px solid var(--line-strong);
  padding: 2px 8px;
  color: var(--text-dim);
}
.st--pending {
  color: var(--green);
}
.st--approved {
  color: var(--green);
  border-color: var(--green);
}
.daf__review {
  flex-basis: 100%;
  font-size: 12px;
  color: var(--text-dim);
}

@media (max-width: 640px) {
  .daf__grid {
    grid-template-columns: 1fr;
  }
}
</style>
