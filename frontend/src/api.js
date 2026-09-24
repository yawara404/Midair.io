// 軽量なAPIクライアント（JWTを自動付与）
//
// Vite dev / 通常ビルド（__STANDALONE__ = false）:
//   API は base 配下の相対パス（既定 /api、サブパス配信時は /Midair.io/api）を使う。
// スタンドアロン（Live Server, __STANDALONE__ = true）:
//   バックエンドは <現在のホスト>:8000 で直接起動している前提なので、
//   API・WebSocket の接続先を明示的に組み立てる。

// Vite の base（末尾スラッシュ付き）。例: '/' または '/Midair.io/'
const BASE_URL = !__STANDALONE__ && import.meta.env.BASE_URL ? import.meta.env.BASE_URL : '/'
// base からサブパス部分だけを取り出す（末尾スラッシュ除去）→ '' または '/Midair.io'
const BASE_PATH = BASE_URL.replace(/\/$/, '')

const API_BASE = __STANDALONE__ ? `http://${location.hostname || 'localhost'}:8000` : BASE_PATH

export function getToken() {
  return localStorage.getItem('midair_token') || ''
}

/** APIのベースURL（相対時は空でない場合がある） */
export function apiBase() {
  return API_BASE
}

/** API の完全なベースURL（スタンドアロンは http://host:8000/api、通常は /api または /Midair.io/api） */
export function apiRoot() {
  return __STANDALONE__ ? `${API_BASE}/api` : `${BASE_PATH}/api`
}

/** WebSocket の接続先 host:port */
export function wsHost() {
  return __STANDALONE__ ? `${location.hostname || 'localhost'}:8000` : location.host
}

/** WebSocket のパス（base 配下） */
export function wsPath() {
  return __STANDALONE__ ? '/ws' : `${BASE_PATH}/ws`
}

/** Discord OAuth ログインURL */
export function discordLoginUrl(redirect) {
  const target = redirect || location.href
  return `${apiRoot()}/auth/discord/login?redirect=${encodeURIComponent(target)}`
}

export async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(`${apiRoot()}${path}`, { ...options, headers })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(body.detail || body.error || `HTTP ${res.status}`)
  }
  return body
}
