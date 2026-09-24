/**
 * Cloudflare Worker — music.wawa-app.me のパス分岐
 *
 * - /Midair.io/*  → Midair.io（midair-origin.wawa-app.me トンネル）へプロキシ
 * - それ以外      → 既存オリジン（QuadTecho 等）へそのまま流す
 *
 * ▼ 設定手順（ダッシュボード）
 *   1. Workers & Pages → 新しい Worker を作成 → このコードを貼り付けて Deploy
 *   2. Worker の Settings → Triggers → Routes に以下を追加:
 *        music.wawa-app.me/Midair.io/*
 *      （既存の QuadTecho 用ルートはそのまま残す。より具体的なこのルートが優先される）
 */

const MIDAIR_ORIGIN = 'https://midair-origin.wawa-app.me'
const MIDAIR_PREFIX = '/Midair.io'

export default {
  async fetch(request) {
    const url = new URL(request.url)

    if (url.pathname === MIDAIR_PREFIX || url.pathname.startsWith(MIDAIR_PREFIX + '/')) {
      // パスはそのまま転送（バックエンドは ROOT_PATH=/Midair.io で受ける）
      const target = new URL(url.pathname + url.search, MIDAIR_ORIGIN)

      const headers = new Headers(request.headers)
      // 転送先ホストに合わせる
      headers.set('Host', 'midair-origin.wawa-app.me')

      const init = { method: request.method, headers, redirect: 'manual' }
      if (!['GET', 'HEAD'].includes(request.method)) {
        init.body = request.body
      }
      return fetch(target.toString(), init)
    }

    // 既存オリジン（QuadTecho など）へそのまま
    return fetch(request)
  },
}
