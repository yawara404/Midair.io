<template>
  <div class="input">
    <form class="input__chat" @submit.prevent="submit">
      <input
        v-model="text"
        class="input__field"
        type="text"
        :disabled="disabled"
        placeholder="ひとこと送信…（匿名）"
        maxlength="500"
      />
      <button class="btn btn--primary" type="submit" :disabled="disabled || !text.trim()">
        送信
      </button>
    </form>

    <div class="input__row">
      <input
        v-model="youtube"
        class="input__field input__field--yt"
        type="text"
        :disabled="disabled"
        placeholder="YouTube URL / 動画ID で曲をリクエスト"
      />
      <button
        class="btn btn--amber"
        :disabled="disabled || !youtube.trim()"
        @click="request"
      >
        ♪ リクエスト
      </button>
      <button class="btn btn--ghost" :disabled="disabled" @click="callDj">
        DJを呼ぶ
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['send', 'request-youtube', 'call-dj'])

const text = ref('')
const youtube = ref('')

function submit() {
  const t = text.value.trim()
  if (!t) return
  emit('send', t)
  text.value = ''
}

function request() {
  const v = youtube.value.trim()
  if (!v) return
  emit('request-youtube', v)
  youtube.value = ''
}

function callDj() {
  emit('call-dj', text.value)
}
</script>

<style scoped>
.input {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.input__chat {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.input__row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.input__field {
  flex: 1;
  min-width: 0;
  background: var(--panel-deep);
  border: 1px solid var(--line-strong);
  color: var(--text);
  font-family: inherit;
  font-size: 14px;
  padding: 10px 12px;
  outline: none;
  border-radius: 0;
}
.input__field::placeholder {
  color: var(--faint);
}
.input__field:focus {
  border-color: var(--green);
}
.input__field:disabled {
  opacity: 0.4;
}
.input__field--yt {
  font-size: 13px;
}

@media (max-width: 640px) {
  /* チャット入力は全幅、ボタンは等幅で折り返し */
  .input__chat .input__field,
  .input__row .input__field {
    flex-basis: 100%;
  }
  .input__chat .btn,
  .input__row .btn {
    flex: 1;
  }
}
</style>
