<template>
  <div class="chat">
    <div ref="log" class="chat__log" @scroll.passive="onScroll">
      <div v-if="!messages.length" class="chat__empty">
        まだ誰もいない…。周波数を合わせて、最初のひとことをどうぞ。
      </div>
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="msg"
        :class="`msg--${msg.message_type}`"
      >
        <span class="msg__author" :class="{ 'is-me': msg.author === myHandle }">
          {{ msg.author }}
        </span>
        <span class="msg__time">{{ formatTime(msg.created_at) }}</span>
        <p class="msg__content">{{ msg.content }}</p>
      </div>
    </div>

    <!-- 最新コメントへジャンプ -->
    <button
      v-if="messages.length && !atBottom"
      class="chat__jump"
      type="button"
      @click="scrollToBottom(true)"
    >
      ↓ 最新へ
    </button>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  myHandle: { type: String, default: '' },
})

const log = ref(null)
// 最下部（最新）にいるかどうか
const atBottom = ref(true)

function isNearBottom() {
  const el = log.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight < 48
}

function onScroll() {
  atBottom.value = isNearBottom()
}

function scrollToBottom(smooth) {
  const el = log.value
  if (!el) return
  el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
  atBottom.value = true
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// 新着時: 最下部にいれば追従、読んでいる途中ならボタンで知らせる
watch(
  () => props.messages.length,
  async () => {
    const stick = atBottom.value
    await nextTick()
    if (stick) scrollToBottom(false)
  }
)

onMounted(async () => {
  await nextTick()
  scrollToBottom(false)
})
</script>

<style scoped>
.chat {
  flex: 1;
  min-height: 0;
  position: relative;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  border-radius: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.chat__log {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chat__empty {
  margin: auto;
  color: var(--text-dim);
  font-size: 13px;
  text-align: center;
  line-height: 1.8;
}

.chat__jump {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 2;
  font-family: inherit;
  font-size: 11px;
  letter-spacing: 0.5px;
  padding: 6px 12px;
  background: #0b0b0b;
  border: 1px solid var(--green);
  color: var(--green);
  cursor: pointer;
  border-radius: 0;
}
.chat__jump:hover {
  background: var(--green);
  color: #000;
}

.msg {
  border-left: 2px solid var(--line-strong);
  padding-left: 10px;
}
.msg__author {
  font-size: 12px;
  color: var(--green);
  margin-right: 8px;
  letter-spacing: 0.02em;
}
.msg__author.is-me {
  color: var(--text-dim);
  text-decoration: underline;
}
.msg__time {
  font-size: 11px;
  color: var(--faint);
  font-variant-numeric: tabular-nums;
}
.msg__content {
  margin: 4px 0 0;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
}

/* DJ：斜線ハッチ背景＋白罫線 */
.msg--dj {
  border-left: 2px solid var(--green);
  background-image: repeating-linear-gradient(
    45deg,
    transparent 0 6px,
    rgba(255, 255, 255, 0.03) 6px 12px
  );
  padding: 8px 10px;
}
.msg--dj .msg__author {
  color: var(--green);
}
.msg--dj .msg__content {
  color: var(--text);
}

.msg--system {
  border-left: none;
  opacity: 0.6;
  font-size: 12px;
}
.msg--system .msg__content {
  color: var(--text-dim);
  font-size: 12px;
}

.msg--youtube {
  border-left-color: var(--green);
}
</style>
