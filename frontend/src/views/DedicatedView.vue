<template>
  <div class="dedicated">
    <div class="dedicated__head">
      <div>
        <h2>専用局を申請する</h2>
        <p>承認されると、希望周波数が固定され24時間ノンストップで自動送出される専用局になります。</p>
      </div>
      <div class="dedicated__links">
        <router-link class="btn btn--ghost" to="/frequencies">周波数マップへ</router-link>
        <router-link v-if="isAdmin" class="btn btn--ghost" to="/admin">管理者ページ</router-link>
      </div>
    </div>

    <DedicatedApplyForm @need-login="goLogin" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import DedicatedApplyForm from '../components/DedicatedApplyForm.vue'

const router = useRouter()
const auth = useAuthStore()
const isAdmin = computed(() => !!auth.user && auth.user.role === 'admin')
function goLogin() {
  router.push('/login')
}
</script>

<style scoped>
.dedicated__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}
.dedicated__head h2 {
  margin: 0 0 4px;
  font-size: 22px;
  color: var(--green);
}
.dedicated__head p {
  margin: 0;
  font-size: 12px;
  color: var(--text-dim);
}
.dedicated__links {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
