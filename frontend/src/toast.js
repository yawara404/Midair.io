// 画面右下に出す軽い通知（トースト）。
// 失敗が無反応だと「押しても何も起きない」ように見えるため、成功/失敗を必ず出す。
import { reactive } from 'vue'

export const toasts = reactive([])

let seq = 0

function push(type, message, timeout) {
  const id = ++seq
  toasts.push({ id, type, message })
  const ms = timeout === undefined ? (type === 'err' ? 6000 : 3200) : timeout
  if (ms > 0) {
    setTimeout(() => dismiss(id), ms)
  }
  return id
}

export function dismiss(id) {
  const i = toasts.findIndex((t) => t.id === id)
  if (i >= 0) toasts.splice(i, 1)
}

export function toastOk(message) {
  return push('ok', message)
}

export function toastInfo(message) {
  return push('info', message)
}

export function toastError(message) {
  return push('err', message || 'エラーが発生しました')
}

/**
 * API 呼び出しなどの定型処理。成功時・失敗時に通知する。
 *   await withToast(() => api('/x', { method: 'POST' }), '保存しました')
 */
export async function withToast(fn, okMessage, errPrefix) {
  try {
    const res = await fn()
    if (okMessage) toastOk(okMessage)
    return res
  } catch (e) {
    toastError(`${errPrefix ? errPrefix + ': ' : ''}${e && e.message ? e.message : e}`)
    return undefined
  }
}
