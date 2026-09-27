<template>
  <Teleport to="body">
    <div v-if="open" class="djset" @click.self="close">
      <div class="djset__panel" role="dialog" aria-modal="true" aria-label="DJ設定">
        <div class="djset__head">
          <span class="djset__title">DJ設定 — {{ station ? station.callsign : '' }}</span>
          <button class="djset__close" type="button" aria-label="閉じる" @click="close">✕</button>
        </div>

        <div class="djset__body">
          <p class="djset__lead">
            「DJを呼ぶ」を押す（または「DJさん」と呼びかける）とDJが来て、しばらくの間ひとりごとを
            話します。呼ばれないまま時間が過ぎると<b>自動退出</b>して黙ります。
            <br />
            自動DJ局（DJ BOT / Vocaloid BOT / 管理者セレクト）は対象外で、いつもおしゃべりします。
          </p>

          <div class="djset__options">
            <label
              v-for="opt in OPTIONS"
              :key="String(opt.value)"
              class="djset__opt"
              :class="{ 'is-active': value === opt.value }"
            >
              <input
                type="radio"
                name="dj-stay"
                :checked="value === opt.value"
                @change="value = opt.value"
              />
              <span class="djset__opt-label">{{ opt.label }}</span>
              <span class="djset__opt-note">{{ opt.note }}</span>
            </label>
          </div>

          <p v-if="error" class="djset__error">{{ error }}</p>
        </div>

        <div class="djset__foot">
          <span v-if="saved" class="djset__saved">保存しました</span>
          <button class="btn btn--ghost" type="button" @click="close">閉じる</button>
          <button class="btn btn--primary" type="button" :disabled="saving" @click="save">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>


<script setup>
// 局のDJ設定（自動退出までの時間）を変更するモーダル。
// 「DJを呼ぶ」でDJが滞在し、呼ばれなければ自動退出する仕組みの調整用。
import { ref, watch } from 'vue'
import { api } from '../api'

const props = defineProps({
  open: { type: Boolean, default: false },
  station: { type: Object, default: null },
})
const emit = defineEmits(['close', 'saved'])

const OPTIONS = [
  { value: null, label: '既定', note: 'サーバー既定（10分）' },
  { value: 5, label: '5分', note: 'すぐ退出' },
  { value: 10, label: '10分', note: '標準' },
  { value: 15, label: '15分', note: 'やや長め' },
  { value: 30, label: '30分', note: '長め' },
  { value: 60, label: '60分', note: 'じっくり' },
  { value: 0, label: '退出しない', note: '常時おしゃべり（従来の動作）' },
]

const value = ref(null)
const saving = ref(false)
const saved = ref(false)
const error = ref('')

// モーダルを開くたびに、その局の現在値へ合わせる
// （親が局データを差し替えても再初期化しないよう、open と局IDの文字列で判定する）
let lastKey = ''
watch(
  () => `${props.open}:${props.station ? props.station.id : ''}`,
  (key) => {
    if (!props.open || key === lastKey) return
    lastKey = key
    const current = props.station ? props.station.dj_stay_minutes : null
    value.value = current === undefined ? null : current
    error.value = ''
    saved.value = false
  },
  { immediate: true }
)

async function save() {
  if (!props.station) return
  saving.value = true
  error.value = ''
  saved.value = false
  try {
    const res = await api(`/stations/${props.station.id}`, {
      method: 'PUT',
      body: JSON.stringify({ dj_stay_minutes: value.value }),
    })
    saved.value = true
    emit('saved', res.station)
  } catch (e) {
    error.value = e.message || '保存に失敗しました'
  } finally {
    saving.value = false
  }
}

function close() {
  emit('close')
}
</script>


<style scoped>
.djset {
  position: fixed;
  inset: 0;
  z-index: 110;
  background: rgba(0, 0, 0, 0.72);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px 14px;
  overflow-y: auto;
}
.djset__panel {
  display: flex;
  flex-direction: column;
  width: min(520px, 100%);
  max-height: 86vh;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  border-top: 3px solid var(--green);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.8);
  margin: auto;
}
.djset__head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line-strong);
}
.djset__title {
  font-size: 15px;
  letter-spacing: 1px;
  color: var(--green);
}
.djset__close {
  background: none;
  border: none;
  color: var(--green);
  font-size: 14px;
  cursor: pointer;
  padding: 2px 6px;
}
.djset__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 14px 16px 6px;
}
.djset__lead {
  margin: 0 0 12px;
  font-size: 12px;
  line-height: 1.75;
  color: var(--text-dim);
}
.djset__lead b {
  color: var(--green);
}
.djset__options {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.djset__opt {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--line-strong);
  background: var(--panel-deep);
  cursor: pointer;
}
.djset__opt.is-active {
  border-color: var(--green);
}
.djset__opt input {
  accent-color: var(--green);
}
.djset__opt-label {
  font-size: 13px;
  color: var(--text);
  min-width: 84px;
}
.djset__opt-note {
  font-size: 11px;
  color: var(--faint);
}
.djset__error {
  margin: 10px 0 0;
  font-size: 12px;
  color: #ff8080;
}
.djset__foot {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 16px;
  border-top: 1px solid var(--line-strong);
}
.djset__saved {
  margin-right: auto;
  font-size: 11px;
  color: var(--green);
}
</style>
