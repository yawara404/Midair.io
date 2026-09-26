<template>
  <div class="info-sections">
    <p v-if="page.updated" class="info-sections__updated">最終更新: {{ page.updated }}</p>
    <section v-for="(sec, i) in page.sections" :key="i" class="info-sections__sec">
      <h4 v-if="sec.h">{{ sec.h }}</h4>
      <p v-if="sec.p" class="info-sections__p">{{ sec.p }}</p>
      <ul v-if="sec.items">
        <li v-for="(item, j) in sec.items" :key="j">{{ item }}</li>
      </ul>
      <div v-if="sec.links" class="info-sections__links">
        <template v-for="(link, j) in sec.links" :key="j">
          <router-link v-if="link.to" class="info-sections__link" :to="link.to">
            → {{ link.label }}
          </router-link>
          <a
            v-else
            class="info-sections__link"
            :href="link.href"
            target="_blank"
            rel="noopener"
          >→ {{ link.label }}</a>
        </template>
      </div>
    </section>
  </div>
</template>

<script setup>
// フッターの情報モーダルと /about /privacy /terms /sitemap の各ページで共用する本文
defineProps({
  page: { type: Object, required: true },
})
</script>

<style scoped>
.info-sections__updated {
  margin: 0 0 12px;
  font-size: 11px;
  color: var(--green);
}
.info-sections__sec {
  margin-bottom: 16px;
}
.info-sections__sec h4 {
  margin: 0 0 6px;
  font-size: 12px;
  letter-spacing: 1px;
  color: var(--green);
  border-left: 2px solid var(--green);
  padding-left: 8px;
}
.info-sections__sec ul {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.info-sections__sec li,
.info-sections__p {
  font-size: 12px;
  line-height: 1.75;
  color: var(--green);
}
.info-sections__p {
  margin: 0;
}
.info-sections__links {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.info-sections__link {
  font-size: 12px;
  line-height: 1.7;
  color: var(--green);
  text-decoration: none;
  border-bottom: 1px dashed var(--line-strong);
  padding: 2px 0;
}
.info-sections__link:hover {
  color: var(--green);
  border-bottom-color: var(--green);
}
</style>
