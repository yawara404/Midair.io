<template>
  <div class="login">
    <div class="login__card">
      <h2 class="login__title">{{ isRegister ? 'アカウント登録' : 'ログイン' }}</h2>
      <p class="login__sub">リスナー登録から、いずれパーソナリティ（開局者）へ。</p>
      <form @submit.prevent="submit">
        <label v-if="isRegister" class="field">
          <span>ユーザー名</span>
          <input v-model="username" type="text" placeholder="DJ名など" />
        </label>
        <label class="field">
          <span>メールアドレス / ユーザー名</span>
          <input v-model="email" type="text" placeholder="you@example.com" />
        </label>
        <label class="field">
          <span>パスワード</span>
          <input v-model="password" type="password" placeholder="6文字以上" />
        </label>
        <p v-if="error" class="login__error">{{ error }}</p>
        <button class="btn btn--primary login__submit" type="submit" :disabled="busy">
          {{ busy ? '処理中…' : (isRegister ? '登録する' : 'ログイン') }}
        </button>
      </form>
      <p class="login__switch">
        {{ isRegister ? 'すでにアカウントをお持ちですか？' : 'はじめての方はこちら' }}
        <a href="#" @click.prevent="isRegister = !isRegister">{{ isRegister ? 'ログイン' : '新規登録' }}</a>
      </p>
      <a class="login__discord" :href="discordUrl">Discordでログイン</a>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api, discordLoginUrl } from '../api'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const discordUrl = computed(() => discordLoginUrl())
const isRegister = ref(false)
const username = ref('')
const email = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    const path = isRegister.value ? '/auth/register' : '/auth/login'
    const data = isRegister.value
      ? { username: username.value, email: email.value, password: password.value }
      : { email: email.value, password: password.value }
    const res = await api(path, { method: 'POST', body: JSON.stringify(data) })
    auth.setAuth(res.access_token, res.user)
    router.push('/stations')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.login {
  max-width: 420px;
  margin: 40px auto;
}
.login__card {
  background: var(--panel);
  border: 1px solid var(--line-strong);
  padding: 26px;
}
.login__title {
  margin: 0 0 6px;
  font-size: 22px;
  color: var(--green);
}
.login__sub {
  margin: 0 0 20px;
  font-size: 12px;
  color: var(--text-dim);
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
}
.field span {
  font-size: 11px;
  color: var(--text-dim);
  letter-spacing: 1px;
}
.field input,
.field select {
  background: var(--panel-deep);
  border: 1px solid var(--line-strong);
  color: var(--text);
  font-family: inherit;
  font-size: 14px;
  padding: 10px 12px;
  outline: none;
  border-radius: 0;
}
.field input:focus {
  border-color: var(--green);
}
.login__error {
  color: var(--green);
  font-size: 12px;
  margin: 0 0 12px;
}
.login__submit {
  width: 100%;
}
.login__switch {
  margin-top: 14px;
  font-size: 12px;
  color: var(--text-dim);
  text-align: center;
}
.login__switch a {
  color: var(--green);
}
.login__discord {
  display: block;
  margin-top: 12px;
  text-align: center;
  font-size: 12px;
  color: var(--text-dim);
  text-decoration: none;
  border-top: 1px dashed var(--line-strong);
  padding-top: 12px;
}
.login__discord:hover {
  color: var(--green);
}

@media (max-width: 480px) {
  .login {
    margin: 16px auto;
  }
  .login__card {
    padding: 18px;
  }
  .login__title {
    font-size: 19px;
  }
}
</style>
