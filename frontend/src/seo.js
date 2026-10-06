// Google 検索向けの正規URL（canonical）管理。
//
// 公開URLは 2026-09-28 に https://music.wawa-app.me/Midair.io/ から
// https://radio.wawa-app.me/Midair.io/ へ移行しました（旧URLは退役）。
//
// SPA なので index.html は全ルート共通ですが、サブドメインのルート側
// （例: https://radio.wawa-app.me/privacy）でも同じ画面が返るため、
// 何もしないと「/Midair.io/privacy」と「/privacy」が重複ページとして
// 見えかねません。そこでルート遷移ごとに <link rel="canonical"> と
// og:url を「新URLの現在のページ」に揃え、シグナルを新URLへ集約します。
//
// - スタンドアロン版（Live Server 等のローカル確認用）では何もしません。
// - クエリ（?freq= など）は正規URLに含めません（同一ページの重複を避けるため）。

// Vite の base（末尾スラッシュ付き）。通常ビルドでは '/Midair.io/'。
// ルート直下配信に変えた場合は '/' になり、それに追従します。
const BASE_URL = !__STANDALONE__ && import.meta.env.BASE_URL ? import.meta.env.BASE_URL : '/'

/** 現在のページの正規URL（絶対URL・クエリ／ハッシュ無し）。standalone では空文字 */
export function canonicalUrl(path) {
  if (__STANDALONE__) return ''
  if (typeof window === 'undefined') return ''
  // ルーターの fullPath（例: '/privacy?x=1'）からクエリ・ハッシュを落とす
  const clean = String(path || '/').split('?')[0].split('#')[0]
  const base = BASE_URL.replace(/\/+$/, '') // '/Midair.io/' → '/Midair.io'（ルート直下なら ''）
  const suffix = clean.startsWith('/') ? clean : `/${clean}`
  return `${window.location.origin}${base}${suffix}`
}

/** <head> の <link rel="..."> を取得（無ければ作る） */
function upsertLink(rel, href) {
  let el = document.head.querySelector(`link[rel="${rel}"]`)
  if (!el) {
    el = document.createElement('link')
    el.setAttribute('rel', rel)
    document.head.appendChild(el)
  }
  el.setAttribute('href', href)
}

/** <head> の <meta property="..."> を取得（無ければ作る） */
function upsertMetaProperty(property, content) {
  let el = document.head.querySelector(`meta[property="${property}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute('property', property)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

/** canonical / og:url を現在のルートに合わせて更新する */
export function applyCanonical(path) {
  if (typeof document === 'undefined') return ''
  const url = canonicalUrl(path)
  if (!url) return ''
  upsertLink('canonical', url)
  upsertMetaProperty('og:url', url)
  return url
}

/** ルーターと接続して、遷移のたびに canonical を更新する */
export function initSeo(router) {
  if (__STANDALONE__) return
  if (!router || typeof router.afterEach !== 'function') return
  applyCanonical(router.currentRoute.value.fullPath)
  router.afterEach((to) => {
    applyCanonical(to.fullPath)
  })
}
