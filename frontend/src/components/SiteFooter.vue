<template>
  <footer class="site-footer">
    <div class="site-footer__links">
      <!-- URL はハッシュ（#privacy）ではなく通常のパス（/privacy）を使う -->
      <router-link
        v-for="key in KEYS"
        :key="key"
        class="site-footer__link"
        :to="PAGES[key].path"
      >
        {{ PAGES[key].title }}
      </router-link>
    </div>
    <p class="site-footer__copy">
      © {{ year }} Midair<span>.io</span> — 深夜ラジオのアジト
    </p>
  </footer>

  <!-- 情報モーダル（プライバシーポリシー / 利用規約 / サイトマップ / 運営情報） -->
  <Teleport to="body">
    <div v-if="current" class="info-modal" @click.self="close">
      <div
        class="info-modal__panel"
        role="dialog"
        aria-modal="true"
        :aria-label="current.title"
      >
        <div class="info-modal__head">
          <span class="info-modal__title">{{ current.title }}</span>
          <button class="info-modal__close" type="button" aria-label="閉じる" @click="close">✕</button>
        </div>
        <div class="info-modal__body">
          <InfoSections :page="current" />
        </div>
        <div class="info-modal__foot">
          
          <button class="btn btn--ghost" type="button" @click="close">閉じる</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import InfoSections from './InfoSections.vue'
import { KEYS, PAGES, pageByPath } from '../siteInfo'

const route = useRoute()
const router = useRouter()

const current = ref(null)
const year = new Date().getFullYear()

// ルート（/privacy /terms /sitemap /about）とモーダルの表示を同期する。
//  - フッターのリンク・直リンクでパスが変わったらモーダルを開く
//  - 他のパスへ移動したら閉じる（ブラウザの戻る/進むにも追従）
watch(
  () => route.path,
  (path) => {
    current.value = pageByPath(path)
  },
  { immediate: true }
)

function close() {
  if (!current.value) return
  // 直前のページがサイト内なら「戻る」で戻す（履歴を増やさない）。
  // 直リンクで開いた場合などは URL をホームに差し替える。
  const state = window.history.state
  const back = state ? state.back : null
  if (pageByPath(route.path) && back) router.back()
  else {
    if (pageByPath(route.path)) router.replace('/')
    current.value = null
  }
}

function onKeydown(e) {
  if (e.key === 'Escape') close()
}

// モーダル表示中は Esc で閉じ、背面のスクロールを止める
watch(current, (page) => {
  if (page) {
    document.addEventListener('keydown', onKeydown)
    document.body.style.overflow = 'hidden'
  } else {
    document.removeEventListener('keydown', onKeydown)
    document.body.style.overflow = ''
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})

</script>

<style scoped>
/* ===== フッター（ホーム下部。全文字を白で統一） ===== */
.site-footer {
  margin-top: 22px;
  padding: 14px 16px 18px;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px 16px;
}
.site-footer__links {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
}
.site-footer__link {
  background: none;
  border: none;
  text-decoration: none;
  padding: 0;
  font-family: inherit;
  font-size: 12px;
  letter-spacing: 0.02em;
  color: var(--green);
  cursor: pointer;
  border-bottom: 1px dashed var(--line-strong);
}
.site-footer__link:hover {
  color: var(--green);
  border-bottom-color: var(--green);
  border-bottom-style: solid;
}
.site-footer__copy {
  margin: 0;
  font-size: 11px;
  letter-spacing: 1px;
  color: var(--green);
}

/* ===== 情報モーダル ===== */
.info-modal {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.72);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px 14px;
  overflow-y: auto;
}
.info-modal__panel {
  display: flex;
  flex-direction: column;
  width: min(660px, 100%);
  max-height: 86vh;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  border-top: 3px solid var(--green);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.8);
  margin: auto;
}
.info-modal__head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line-strong);
}
.info-modal__title {
  font-size: 15px;
  letter-spacing: 1px;
  color: var(--green);
}
.info-modal__close {
  background: none;
  border: none;
  color: var(--green);
  font-size: 14px;
  cursor: pointer;
  padding: 2px 6px;
}
.info-modal__close:hover {
  color: var(--green);
}
.info-modal__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  padding: 14px 16px 6px;
}
.info-modal__foot {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  padding: 10px 16px;
  border-top: 1px solid var(--line-strong);
}

@media (max-width: 560px) {
  .site-footer {
    flex-direction: column;
    align-items: flex-start;
    padding: 12px;
  }
  .info-modal {
    padding: 12px 10px;
  }
  .info-modal__panel {
    max-height: 90vh;
  }
  .info-modal__body {
    padding: 12px 12px 4px;
  }
}
</style>

