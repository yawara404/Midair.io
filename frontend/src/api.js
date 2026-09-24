// 軽量なAPIクライアント（JWTを自動付与）
//
// Vite dev / 通常ビルド（__STANDALONE__ = false）:
//   API は相対パス /api を使い、開発サーバーの proxy に任せる。
// スタンドアロン（Live Server, __STANDALONE__ = true）:
//   バックエンドは <現在のホスト>:8000 で直接起動している前提なので、
//   API・WebSocket の接続先を明示的に組み立てる。

const API_BASE = __STANDALONE__ ? `http://${location.hostname || 'localhost'}:8000` : ''

export function getToken() {
  return localStorage.getItem('midair_token') || ''
}

/** APIのベースURL（スタンドアロン時は空文字でない） */
export function apiBase() {
  return API_BASE
}

/** WebSocket の接続先 host:port */
export function wsHost() {
  return __STANDALONE__ ? `${location.hostname || 'localhost'}:8000` : location.host
}

/** Discord OAuth ログインURL */
export function discordLoginUrl(redirect) {
  const target = redirect || location.href
  return `${API_BASE}/api/auth/discord/login?redirect=${encodeURIComponent(target)}`
}

export async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(`${API_BASE}/api${path}`, { ...options, headers })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(body.detail || body.error || `HTTP ${res.status}`)
  }
  return body
}
