/**
 * Cloudflare Worker — music.wawa-app.me のパス分岐
 *
 * - /Midair.io/*  → Midair.io（midair-origin.wawa-app.me トンネル）へプロキシ
 * - /sitemap.xml  → Midair.io の sitemap.xml をルート直下でも配信
 * - それ以外      → 既存オリジン（QuadTecho 等）へそのまま流す
 *
 * ▼ 設定手順（ダッシュボード）
 *   1. Workers & Pages → 新しい Worker を作成 → このコードを貼り付けて Deploy
 *   2. Worker の Settings → Triggers → Routes に以下を追加:
 *        music.wawa-app.me/Midair.io/*
 *        music.wawa-app.me/sitemap.xml
 *      （既存の QuadTecho 用ルートはそのまま残す。より具体的なこのルートが優先される）
 */

const MIDAIR_ORIGIN = 'https://midair-origin.wawa-app.me'
const MIDAIR_PREFIX = '/Midair.io'

// ルート直下のパス → Midair.io 側の実ファイルへマップ
const ROOT_ALIASES = {
  '/sitemap.xml': `${MIDAIR_PREFIX}/sitemap.xml`,
  '/llms.txt': `${MIDAIR_PREFIX}/llms.txt`,
}

export default {
  async fetch(request) {
    const url = new URL(request.url)
    const path = url.pathname

    let targetPath = null
    if (path === MIDAIR_PREFIX || path.startsWith(MIDAIR_PREFIX + '/')) {
      // パスはそのまま転送（バックエンドは ROOT_PATH=/Midair.io で受ける）
      targetPath = path
    } else if (ROOT_ALIASES[path]) {
      targetPath = ROOT_ALIASES[path]
    }

    if (targetPath) {
      const target = new URL(targetPath + url.search, MIDAIR_ORIGIN)

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
