// 軽量なAPIクライアント（JWTを自動付与）
import { defineStore } from 'pinia'
import { apiRoot } from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('midair_token') || '',
    user: JSON.parse(localStorage.getItem('midair_user') || 'null'),
  }),
  getters: {
    isLoggedIn: (state) => !!state.token,
    isAdmin: (state) => !!state.user && state.user.role === 'admin',
    isDedicatedOwner: (state) =>
      !!state.user &&
      (state.user.role === 'dedicated_owner' || state.user.role === 'admin'),
    isBroadcaster: (state) =>
      !!state.user && (state.user.role === 'broadcaster' || state.user.role === 'admin'),
  },
  actions: {
    setAuth(token, user) {
      this.token = token
      this.user = user
      localStorage.setItem('midair_token', token)
      localStorage.setItem('midair_user', JSON.stringify(user))
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('midair_token')
      localStorage.removeItem('midair_user')
    },
    // トークンはあるがユーザー情報が無い場合に /auth/me で取得する。
    // （旧スタンドアロン版は midair_user を保存していなかったため、
    //   user が null のままになり「自分の局」判定が失敗することがあった）
    async ensureUser() {
      if (!this.token) {
        this.user = null
        return
      }
      if (this.user) return
      try {
        const res = await fetch(`${apiRoot()}/auth/me`, {
          headers: { Authorization: `Bearer ${this.token}` },
        })
        const body = await res.json().catch(() => ({}))
        if (res.ok && body.success && body.user) {
          this.user = body.user
          localStorage.setItem('midair_user', JSON.stringify(body.user))
        } else {
          this.logout()
        }
      } catch (e) {
        /* ネットワーク不通などはトークンを保持したままにする */
      }
    },

    // Discord OAuth 後の ?token= を処理する
    async hydrateFromUrl() {
      const params = new URLSearchParams(window.location.search)
      const token = params.get('token')
      if (!token) return
      localStorage.setItem('midair_token', token)
      this.token = token
      history.replaceState({}, '', window.location.pathname + window.location.hash)
      try {
        const res = await fetch(`${apiRoot()}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        const body = await res.json()
        if (body.success && body.user) {
          this.user = body.user
          localStorage.setItem('midair_user', JSON.stringify(body.user))
        }
      } catch (e) {
        /* 無効なトークンは無視 */
      }
    },
  },
})
