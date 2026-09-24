import { createRouter, createWebHistory, createWebHashHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import StationsView from '../views/StationsView.vue'
import FrequencyMapView from '../views/FrequencyMapView.vue'
import StationView from '../views/StationView.vue'
import LoginView from '../views/LoginView.vue'
import StudioView from '../views/StudioView.vue'
import TimetableView from '../views/TimetableView.vue'
import ArchiveView from '../views/ArchiveView.vue'
import ProfileView from '../views/ProfileView.vue'
import DedicatedView from '../views/DedicatedView.vue'
import AdminView from '../views/AdminView.vue'
import MidAirCard from '../components/MidAirCard.vue'

// スタンドアロン（Live Server 等の静的サーバー）ではハッシュルーティング、
// Vite dev / 通常ビルドでは履歴ルーティングを使う。
const router = createRouter({
  history: __STANDALONE__ ? createWebHashHistory() : createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/stations', component: StationsView },
    { path: '/frequencies', component: FrequencyMapView },
    { path: '/station/:id', component: StationView },
    { path: '/login', component: LoginView },
    { path: '/studio', component: StudioView },
    { path: '/timetable', component: TimetableView },
    { path: '/archive', component: ArchiveView },
    { path: '/profile', component: ProfileView },
    { path: '/dedicated', component: DedicatedView },
    { path: '/admin', component: AdminView },
    { path: '/preview', component: MidAirCard },
  ],
  // 履歴を行き来（back / forward）したときはスクロール位置を復元し、
  // 新規遷移では先頭へ戻す。
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0 }
  },
})

export default router
