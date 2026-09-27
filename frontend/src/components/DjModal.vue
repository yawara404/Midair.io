<template>
  <Teleport to="body">
    <div v-if="open" class="djmodal" @click.self="close">
      <div class="djmodal__panel" role="dialog" aria-modal="true" :aria-label="title">
        <div class="djmodal__head">
          <span class="djmodal__title">{{ title }}<template v-if="station"> — {{ station.callsign }}</template></span>
          <button class="djmodal__close" type="button" aria-label="閉じる" @click="close">✕</button>
        </div>

        <div class="djmodal__body">
          <p class="djmodal__lead">
            <template v-if="mode === 'call'">
              DJを呼ぶと、DJがしばらく滞在して<b>独り口</b>（無言のときのひとこと）も話します。
              呼ばないまま時間が過ぎると<b>自動退出</b>します。
            </template>
            <template v-else>
              DJの滞在時間（自動退出まで）を設定します。「DJを呼ぶ」と来て、この時間だけ
              独り口を話し、呼ばれなければ<b>自動退出</b>します。
            </template>
            <br />
            自動DJ局（DJ BOT / Vocaloid BOT / 管理者セレクト）は対象外で、いつもおしゃべりします。
          </p>

          <label v-if="mode === 'call'" class="djmodal__field">
            <span>DJへのひとこと（任意）</span>
            <input v-model="message" type="text" maxlength="200" placeholder="例: DJさん、こんばんは" />
          </label>

          <div class="djmodal__section">
            <p class="djmodal__section-title">滞在時間（この局の設定）</p>
            <p v-if="!canEdit" class="djmodal__note">
              滞在時間を変更できるのは開局者・管理者だけです（現在の設定が適用されます）。
            </p>
            <div class="djmodal__options">
              <label
                v-for="opt in OPTIONS"
                :key="String(opt.value)"
                class="djmodal__opt"
                :class="{ 'is-active': value === opt.value, 'is-disabled': !canEdit }"
              >
                <input
                  type="radio"
                  name="dj-stay"
                  :disabled="!canEdit"
                  :checked="value === opt.value"
                  @change="value = opt.value"
                />
                <span class="djmodal__opt-label">{{ opt.label }}</span>
                <span class="djmodal__opt-note">{{ opt.note }}</span>
              </label>
            </div>
          </div>

          <p v-if="error" class="djmodal__error">{{ error }}</p>
        </div>

        <div class="djmodal__foot">
          <span v-if="saved" class="djmodal__saved">保存しました</span>
          <button class="btn btn--ghost" type="button" @click="close">閉じる</button>
          <button
            v-if="mode === 'settings'"
            class="btn btn--primary"
            type="button"
            :disabled="saving || !canEdit"
            @click="saveSettings"
          >{{ saving ? '保存中…' : '保存' }}</button>
          <button
            v-else
            class="btn btn--primary"
            type="button"
            :disabled="sending"
            @click="submitCall"
          >{{ sending ? '呼んでいます…' : '🎙 DJを呼ぶ' }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>


<script setup>
// 「DJを呼ぶ」モーダル（呼び出し＋滞在時間の設定）。
// mode='call'    : DJを呼ぶ（任意でひとことも送れる。開局者なら滞在時間も同時に保存）
// mode='settings': 滞在時間だけを変更
import { computed, ref, watch } from 'vue'
import { api } from '../api'

const props = defineProps({
  open: { type: Boolean, default: false },
  mode: { type: String, default: 'call' },
  station: { type: Object, default: null },
  canEdit: { type: Boolean, default: false },
  // 「DJを呼ぶ」時にチャット欄へ入力済みのテキストを初期値として渡せる
  initialMessage: { type: String, default: '' },
})
const emit = defineEmits(['close', 'call', 'saved'])

// モードに応じたタイトル
const title = computed(() => (props.mode === 'settings' ? 'DJ設定' : 'DJを呼ぶ'))

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
const message = ref('')
const saving = ref(false)
const sending = ref(false)
const saved = ref(false)
const error = ref('')

// 開くたびに、その局の現在値へ合わせる（親が局データを差し替えても再初期化しない）
let lastKey = ''
watch(
  () => `${props.open}:${props.mode}:${props.station ? props.station.id : ''}`,
  (key) => {
    if (!props.open || key === lastKey) return
    lastKey = key
    const current = props.station ? props.station.dj_stay_minutes : null
    value.value = current === undefined ? null : current
    message.value = props.initialMessage || ''
    error.value = ''
    saved.value = false
  },
  { immediate: true }
)

// 滞在時間を保存する（開局者・管理者のみ。変更が無ければ何もしない）
async function persistStay() {
  if (!props.canEdit || !props.station) return
  if (props.station.dj_stay_minutes === value.value) return
  const res = await api(`/stations/${props.station.id}`, {
    method: 'PUT',
    body: JSON.stringify({ dj_stay_minutes: value.value }),
  })
  emit('saved', res.station)
}

async function saveSettings() {
  saving.value = true
  error.value = ''
  saved.value = false
  try {
    await persistStay()
    saved.value = true
  } catch (e) {
    error.value = e.message || '保存に失敗しました'
  } finally {
    saving.value = false
  }
}

// DJを呼ぶ（開局者なら滞在時間も同時に保存してから呼び出す）
async function submitCall() {
  sending.value = true
  error.value = ''
  try {
    await persistStay()
    emit('call', message.value)
    sending.value = false
    emit('close')
  } catch (e) {
    error.value = e.message || '呼び出しに失敗しました'
    sending.value = false
  }
}

function close() {
  emit('close')
}
</script>

<style scoped>
.djmodal {
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
.djmodal__panel {
  display: flex;
  flex-direction: column;
  width: min(540px, 100%);
  max-height: 86vh;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  border-top: 3px solid var(--green);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.8);
  margin: auto;
}
.djmodal__head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line-strong);
}
.djmodal__title {
  font-size: 15px;
  letter-spacing: 1px;
  color: var(--green);
}
.djmodal__close {
  background: none;
  border: none;
  color: var(--green);
  font-size: 14px;
  cursor: pointer;
  padding: 2px 6px;
}
.djmodal__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 14px 16px 6px;
}
.djmodal__lead {
  margin: 0 0 12px;
  font-size: 12px;
  line-height: 1.75;
  color: var(--text-dim);
}
.djmodal__lead b {
  color: var(--green);
}
.djmodal__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}
.djmodal__field span {
  font-size: 11px;
  color: var(--faint);
}
.djmodal__field input {
  background: var(--panel-deep);
  border: 1px solid var(--line-strong);
  color: var(--text);
  font-family: inherit;
  font-size: 13px;
  padding: 8px 10px;
  outline: none;
  border-radius: 0;
}
.djmodal__field input:focus {
  border-color: var(--green);
}
.djmodal__section-title {
  margin: 0 0 6px;
  font-size: 11px;
  letter-spacing: 0.06em;
  color: var(--faint);
}
.djmodal__note {
  margin: 0 0 8px;
  font-size: 11px;
  color: var(--faint);
}
.djmodal__options {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.djmodal__opt {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--line-strong);
  background: var(--panel-deep);
  cursor: pointer;
}
.djmodal__opt.is-active {
  border-color: var(--green);
}
.djmodal__opt.is-disabled {
  opacity: 0.55;
  cursor: default;
}
.djmodal__opt input {
  accent-color: var(--green);
}
.djmodal__opt-label {
  font-size: 13px;
  color: var(--text);
  min-width: 84px;
}
.djmodal__opt-note {
  font-size: 11px;
  color: var(--faint);
}
.djmodal__error {
  margin: 10px 0 0;
  font-size: 12px;
  color: #ff8080;
}
.djmodal__foot {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 16px;
  border-top: 1px solid var(--line-strong);
}
.djmodal__saved {
  margin-right: auto;
  font-size: 11px;
  color: var(--green);
}
</style>
