// Google Analytics（GA4）連携。
//
// - 測定IDはビルド時の `VITE_GA_ID`（例: G-XXXXXXXXXX）。index.html が
//   `window.__MIDAIR_GA_ID__` に入れ、gtag の読み込みも行う（未設定なら何もしない）。
// - SPAなので、ルート遷移ごとに page_view を手動で送る（index.html 側は send_page_view: false）。
// - プライバシーポリシーの「アクセス解析を無効にする」で localStorage に
//   midair_ga_optout = 1 を保存すると、以降は読み込みも送信もしない。

const OPT_OUT_KEY = 'midair_ga_optout'
const ID_RE = /^G-[A-Z0-9]{4,}$/i

/** ビルドに埋め込まれた測定ID（未設定なら空文字） */
export function analyticsId() {
  if (typeof window === 'undefined') return ''
  return window.__MIDAIR_GA_ID__ || ''
}

/** 測定IDが設定されているか（無効化の有無は問わない） */
export function isAnalyticsConfigured() {
  return ID_RE.test(analyticsId())
}

/** ユーザーが「無効にする」を選んでいるか */
export function isAnalyticsOptOut() {
  try {
    return localStorage.getItem(OPT_OUT_KEY) === '1'
  } catch (e) {
    return false
  }
}

/** 計測してよい状態か（ID設定済み・未オプトアウト・gtag あり） */
export function isAnalyticsEnabled() {
  return (
    isAnalyticsConfigured() &&
    !isAnalyticsOptOut() &&
    typeof window !== 'undefined' &&
    typeof window.gtag === 'function'
  )
}

/**
 * アクセス解析の無効化／有効化。
 * 読み込み済みの gtag を完全に止めるため、切り替え後はページを再読み込みする。
 */
export function setAnalyticsOptOut(on) {
  try {
    if (on) localStorage.setItem(OPT_OUT_KEY, '1')
    else localStorage.removeItem(OPT_OUT_KEY)
  } catch (e) {
    return false
  }
  // 読み込み済みの計測タグを確実に止めるため再読み込みする
  try {
    if (typeof window !== 'undefined' && window.location && window.location.reload) {
      window.location.reload()
    }
  } catch (e) {
    /* リロードできない環境（テスト等）では設定だけ保存する */
  }
  return true
}

/** ページビューを送る（SPAのルート遷移ごと） */
export function trackPageView(path) {
  if (!isAnalyticsEnabled()) return
  window.gtag('event', 'page_view', {
    page_path: path || window.location.pathname,
    page_location: window.location.href,
    page_title: document.title,
  })
}

/** 任意のイベントを送る（局の切り替え・リクエスト・DJ呼び出しなど） */
export function trackEvent(name, params) {
  if (!isAnalyticsEnabled()) return
  window.gtag('event', name, params || {})
}

/** ルーターと接続して、遷移のたびに page_view を送る */
export function initAnalytics(router) {
  if (!router || typeof router.afterEach !== 'function') return
  router.afterEach((to) => {
    trackPageView(to.fullPath)
  })
}
