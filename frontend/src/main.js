import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { initAnalytics } from './analytics'

createApp(App).use(createPinia()).use(router).mount('#app')

// Google Analytics（GA4）: ルート遷移ごとに page_view を送る（VITE_GA_ID 未設定なら何もしない）
initAnalytics(router)
