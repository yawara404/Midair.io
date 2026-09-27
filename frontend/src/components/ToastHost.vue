<template>
  <Teleport to="body">
    <div v-if="toasts.length" class="toasts" aria-live="polite">
      <button
        v-for="t in toasts"
        :key="t.id"
        class="toast"
        :class="`toast--${t.type}`"
        type="button"
        @click="dismiss(t.id)"
      >
        <span class="toast__icon">{{ t.type === 'ok' ? '✓' : t.type === 'err' ? '⚠' : 'ℹ' }}</span>
        <span class="toast__text">{{ t.message }}</span>
      </button>
    </div>
  </Teleport>
</template>

<script setup>
// 画面右下の通知（タップで閉じる。数秒で自動的に消える）
import { toasts, dismiss } from '../toast'
</script>

<style scoped>
.toasts {
  position: fixed;
  right: 14px;
  bottom: 14px;
  z-index: 200;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: min(360px, calc(100vw - 28px));
  pointer-events: none;
}
.toast {
  pointer-events: auto;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  text-align: left;
  font-family: inherit;
  font-size: 12px;
  line-height: 1.6;
  padding: 10px 12px;
  background: var(--panel);
  color: var(--text);
  border: 1px solid var(--line-strong);
  border-left: 3px solid var(--green);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.6);
  cursor: pointer;
}
.toast--ok {
  border-left-color: var(--green);
}
.toast--err {
  border-left-color: #ff6a6a;
}
.toast--info {
  border-left-color: var(--text-dim);
}
.toast__icon {
  color: var(--green);
}
.toast--err .toast__icon {
  color: #ff6a6a;
}
.toast__text {
  min-width: 0;
  word-break: break-word;
}
@media (max-width: 560px) {
  .toasts {
    left: 10px;
    right: 10px;
    bottom: 10px;
    max-width: none;
  }
}
</style>
