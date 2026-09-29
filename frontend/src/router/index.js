import { createRouter, createWebHistory, createWebHashHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'

// ホーム以外は遅延読み込み（初回表示のJSを小さくして負荷と待ち時間を減らす）
const StationsView = () => import('../views/StationsView.vue')
const FrequencyMapView = () => import('../views/FrequencyMapView.vue')
const StationView = () => import('../views/StationView.vue')
const LoginView = () => import('../views/LoginView.vue')
const StudioView = () => import('../views/StudioView.vue')
const TimetableView = () => import('../views/TimetableView.vue')
const ArchiveView = () => import('../views/ArchiveView.vue')
const ThreadView = () => import('../views/ThreadView.vue')
const ProfileView = () => import('../views/ProfileView.vue')
const DedicatedView = () => import('../views/DedicatedView.vue')
const AdminView = () => import('../views/AdminView.vue')
const MidAirCard = () => import('../components/MidAirCard.vue')

// スタンドアロン（Live Server 等の静的サーバー）ではハッシュルーティング、
// Vite dev / 通常ビルドでは履歴ルーティングを使う。
// サブパス配信（例: /Midair.io/）に戻した場合のみ base を合わせる。
// 公開中の radio.wawa-app.me/Midair.io/ はサブパス維持なので base は '/Midair.io/'。
const BASE_URL = !__STANDALONE__ && import.meta.env.BASE_URL ? import.meta.env.BASE_URL : '/'

const router = createRouter({
  history: __STANDALONE__
    ? createWebHashHistory()
    : createWebHistory(BASE_URL),
  routes: [
    { path: '/', component: HomeView },
    { path: '/stations', component: StationsView },
    { path: '/frequencies', component: FrequencyMapView },
    { path: '/station/:id', component: StationView },
    { path: '/login', component: LoginView },
    { path: '/studio', component: StudioView },
    { path: '/timetable', component: TimetableView },
    { path: '/archive', component: ArchiveView },
    { path: '/thread/:id', component: ThreadView },
    { path: '/profile', component: ProfileView },
    { path: '/dedicated', component: DedicatedView },
    { path: '/admin', component: AdminView },
    { path: '/preview', component: MidAirCard },
    // サイト情報（フッターのモーダルと同じ内容）。
    // ハッシュ（#privacy）ではなく通常のパスで開けるようにするため、
    // 背景にホームを描画しつつ SiteFooter 側でモーダルを開く。
    { path: '/about', component: HomeView },
    { path: '/privacy', component: HomeView },
    { path: '/terms', component: HomeView },
    { path: '/sitemap', component: HomeView },
  ],
  // 履歴を行き来（back / forward）したときはスクロール位置を復元し、
  // 新規遷移では先頭へ戻す。
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0 }
  },
})

export default router
