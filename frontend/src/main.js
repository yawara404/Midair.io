import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { initAnalytics } from './analytics'
import { initSeo } from './seo'

createApp(App).use(createPinia()).use(router).mount('#app')

// Google Analytics（GA4）: ルート遷移ごとに page_view を送る（VITE_GA_ID 未設定なら何もしない）
initAnalytics(router)

// Google 検索向け: ルート遷移ごとに canonical / og:url を新URLへ揃える
// （公開URL: https://radio.wawa-app.me/Midair.io/。旧URLは退役）
initSeo(router)

