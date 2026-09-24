<template>
  <div class="fmap">
    <div class="fmap__head">
      <div class="fmap__head-main">
        <h2>周波数マップ</h2>
        <p class="fmap__sub">
          76.0〜88.9MHz ・ 全{{ slots.length }}スロット ・ 空き検索 / 時間枠予約 / 開局 / ON AIR・停波
        </p>
        <p class="fmap__hint">
          ▼ 空き（EMPTY＝グレー）のスロットをクリック → 「時間枠を予約する」または「この周波数で開局」
        </p>
      </div>
      <div class="fmap__legend">
        <span class="lg lg--empty">EMPTY</span>
        <span class="lg lg--reserved">RESERVED</span>
        <span class="lg lg--live">LIVE</span>
        <span class="lg lg--off_air">OFF AIR</span>
      </div>
    </div>

    <div class="fmap__counts">
      <span class="count count--empty"><b>{{ counts.empty }}</b> 空き</span>
      <span class="count count--reserved"><b>{{ counts.reserved }}</b> 予約</span>
      <span class="count count--live"><b>{{ counts.live }}</b> 放送中</span>
      <span class="count count--off_air"><b>{{ counts.off_air }}</b> 停波</span>
    </div>

    <div class="fmap__grid">
      <button
        v-for="s in slots"
        :key="s.frequency"
        class="slot"
        :class="[`slot--${s.status}`, { 'is-selected': selected && selected.frequency === s.frequency }]"
        :title="`${s.frequency.toFixed(1)} MHz — ${statusLabel(s.status)}`"
        @click="select(s)"
      >
        <span class="slot__freq">{{ s.frequency.toFixed(1) }}</span>
      </button>
    </div>

    <!-- ===== 専用局（24時間常設）申請 ===== -->
    <section class="dedicated-block">
      <div class="dedicated-block__head">
        <div>
          <h3>専用局（24時間常設）を申請する</h3>
          <p>承認されると、希望周波数が固定され24時間ノンストップで自動送出される専用局になります。</p>
        </div>
        <router-link v-if="auth.isAdmin" class="btn btn--ghost" to="/admin">管理者ページ</router-link>
      </div>
      <DedicatedApplyForm @need-login="goLogin" />
    </section>

    <!-- ===== 選択スロットの詳細（右下に固定表示） ===== -->
    <template v-if="selected">
    <div class="detail-backdrop" @click="selected = null"></div>
    <div class="detail">
      <div class="detail__head">
        <span class="detail__freq">{{ selected.frequency.toFixed(1) }} MHz</span>
        <span class="detail__status" :class="`st--${selected.status}`">{{ statusLabel(selected.status) }}</span>
        <button class="btn btn--ghost detail__close" @click="selected = null">✕ 閉じる</button>
      </div>

      <div class="detail__body">
        <p v-if="selected.callsign" class="detail__callsign">{{ selected.callsign }}</p>
        <p v-if="selected.owner_username" class="detail__meta">DJ: {{ selected.owner_username }}</p>
        <p v-if="selected.status === 'live'" class="detail__meta">LISTENER {{ selected.listener_count }}</p>
        <p v-if="selected.reservation" class="detail__meta">
          予約: {{ fmt(selected.reservation.start_time) }} 〜 {{ fmt(selected.reservation.end_time) }}
        </p>
        <p v-if="selected.status === 'empty'" class="detail__meta">この周波数は空いています。</p>

        <p v-if="!auth.isLoggedIn" class="detail__note">操作にはログインが必要です。</p>

        <!-- 空きスロット: 開局 / 予約 -->
        <template v-if="selected.status === 'empty' && auth.isLoggedIn">
          <form class="reserve" @submit.prevent="openStation">
            <input v-model="openCallsign" class="field-input" placeholder="コールサイン（局名）" required />
            <button class="btn btn--primary" type="submit">この周波数で開局（ON AIR）</button>
          </form>
          <div class="detail__actions">
            <button class="btn btn--ghost" @click="showReserve = !showReserve">
              {{ showReserve ? '予約フォームを閉じる' : '時間枠を予約する' }}
            </button>
          </div>
          <form v-if="showReserve" class="reserve" @submit.prevent="doReserve">
            <input v-model="reserve.callsign" class="field-input" placeholder="枠名（任意）" />
            <label class="reserve__row">
              <span>開始</span>
              <input v-model="reserve.start_time" class="field-input" type="datetime-local" required />
            </label>
            <label class="reserve__row">
              <span>終了</span>
              <input v-model="reserve.end_time" class="field-input" type="datetime-local" required />
            </label>
            <p v-if="error" class="err">{{ error }}</p>
            <button class="btn btn--amber" type="submit">この枠を予約</button>
          </form>
        </template>

        <!-- 予約スロット -->
        <template v-else-if="selected.status === 'reserved'">
          <div class="detail__actions">
            <button
              v-if="selected.reservation && auth.user && selected.reservation.user_id === auth.user.id"
              class="btn btn--ghost"
              @click="cancelReservation"
            >予約をキャンセル</button>
            <span v-else class="detail__meta">他のユーザーが予約しています。</span>
          </div>
        </template>

        <!-- 放送中 / 停波中ステーション -->
        <template v-else-if="selected.station_id">
          <div class="detail__actions">
            <router-link class="btn btn--ghost" :to="`/station/${selected.station_id}`">チューナーで聴く</router-link>
            <template v-if="isMine">
              <button v-if="selected.status !== 'live'" class="btn btn--primary" @click="setLive('on-air')">ON AIR</button>
              <button v-else class="btn btn--amber" @click="setLive('off-air')">OFF AIR</button>
              <button class="btn btn--ghost" @click="closeStation">廃局（返還）</button>
            </template>
          </div>
        </template>
      </div>
    </div>
  </template>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, getToken, wsHost } from '../api'
import { useAuthStore } from '../stores/auth'
import DedicatedApplyForm from '../components/DedicatedApplyForm.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

// 専用局申請フォームからのログイン要求
function goLogin() {
  router.push('/login')
}

const slots = ref([])
const counts = reactive({ empty: 0, reserved: 0, live: 0, off_air: 0 })
const selected = ref(null)
const showReserve = ref(false)
const error = ref('')
const openCallsign = ref('')
const reserve = reactive({ callsign: '', start_time: '', end_time: '' })
const myStationIds = ref([])
let socket = null

// 自分の局判定: auth.user が未取得でも /stations/mine から判定できるようにする
const isMine = computed(
  () =>
    !!selected.value &&
    ((auth.user && selected.value.owner_username === auth.user.username) ||
      (selected.value.station_id != null && myStationIds.value.includes(selected.value.station_id)))
)

async function loadMine() {
  if (!auth.isLoggedIn) {
    myStationIds.value = []
    return
  }
  try {
    const res = await api('/stations/mine')
    myStationIds.value = (res.stations || []).map((s) => s.id)
  } catch (e) {
    myStationIds.value = []
  }
}

function statusLabel(s) {
  return { empty: 'EMPTY（空き）', reserved: 'RESERVED（予約）', live: 'ON AIR', off_air: 'OFF AIR' }[s] || s
}

function fmt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function load() {
  try {
    const res = await api('/frequencies')
    slots.value = res.slots || []
    Object.assign(counts, res.counts || {})
  } catch (e) {
    console.error(e)
  }
}

function select(slot) {
  selected.value = slot
  showReserve.value = false
  error.value = ''
}

async function openStation() {
  error.value = ''
  try {
    await api('/stations', {
      method: 'POST',
      body: JSON.stringify({
        frequency: selected.value.frequency,
        callsign: openCallsign.value || `${selected.value.frequency.toFixed(1)}MHzの局`,
      }),
    })
    openCallsign.value = ''
    await load()
    selected.value = slots.value.find((s) => s.frequency === selected.value.frequency)
  } catch (e) {
    error.value = e.message
  }
}

async function doReserve() {
  error.value = ''
  try {
    await api(`/frequencies/${selected.value.frequency}/reserve`, {
      method: 'POST',
      body: JSON.stringify({
        callsign: reserve.callsign,
        start_time: reserve.start_time,
        end_time: reserve.end_time,
      }),
    })
    reserve.callsign = ''
    reserve.start_time = ''
    reserve.end_time = ''
    showReserve.value = false
    await load()
    selected.value = slots.value.find((s) => s.frequency === selected.value.frequency)
  } catch (e) {
    error.value = e.message
  }
}

async function cancelReservation() {
  if (!selected.value.reservation) return
  try {
    await api(`/reservations/${selected.value.reservation.id}`, { method: 'DELETE' })
    await load()
    selected.value = slots.value.find((s) => s.frequency === selected.value.frequency)
  } catch (e) {
    error.value = e.message
  }
}

async function setLive(action) {
  try {
    await api(`/stations/${selected.value.station_id}/${action}`, { method: 'POST' })
    await load()
    selected.value = slots.value.find((s) => s.frequency === selected.value.frequency)
  } catch (e) {
    error.value = e.message
  }
}

async function closeStation() {
  if (!confirm('廃局して周波数を返還しますか？（チャット・番組も削除されます）')) return
  try {
    await api(`/stations/${selected.value.station_id}`, { method: 'DELETE' })
    await load()
    selected.value = slots.value.find((s) => s.frequency === selected.value.frequency)
  } catch (e) {
    error.value = e.message
  }
}

function connectSocket() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const token = getToken()
  const qs = token ? `?token=${encodeURIComponent(token)}` : ''
  socket = new WebSocket(`${proto}://${wsHost()}/ws${qs}`)
  socket.onmessage = (event) => {
    let d
    try {
      d = JSON.parse(event.data)
    } catch {
      return
    }
    if (d.type === 'frequency_status') {
      const slot = slots.value.find((s) => Math.abs(s.frequency - d.frequency) < 0.05)
      if (slot) {
        slot.status = d.status
        slot.station_id = d.station_id
      }
      counts.empty = slots.value.filter((s) => s.status === 'empty').length
      counts.reserved = slots.value.filter((s) => s.status === 'reserved').length
      counts.live = slots.value.filter((s) => s.status === 'live').length
      counts.off_air = slots.value.filter((s) => s.status === 'off_air').length
    }
  }
}

onMounted(async () => {
  await Promise.all([load(), loadMine()])
  // ?freq=XX.X があればそのスロットを選択（未開局でもページを開ける）
  const f = parseFloat(route.query.freq)
  if (Number.isFinite(f)) {
    const slot = slots.value.find((s) => Math.abs(s.frequency - f) < 0.05)
    if (slot) select(slot)
  }
  connectSocket()
})
// 戻る/進むで ?freq= が変わっても選択スロットを追従させる（history traversal 対応）
watch(
  () => route.query.freq,
  (v) => {
    const f = parseFloat(v)
    if (!Number.isFinite(f)) return
    const slot = slots.value.find((s) => Math.abs(s.frequency - f) < 0.05)
    if (slot) select(slot)
  }
)
onBeforeUnmount(() => {
  if (socket) socket.close()
})
</script>

<style scoped>
/* ===== ヘッダー ===== */
.fmap__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  border-left: 3px solid var(--green);
  padding: 16px 18px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.fmap__head-main {
  min-width: 0;
}
.fmap__head h2 {
  margin: 0 0 6px;
  font-size: 22px;
  color: var(--green);
  letter-spacing: 1px;
}
.fmap__sub {
  margin: 0;
  font-size: 12px;
  color: var(--text-dim);
  line-height: 1.7;
}
.fmap__hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--green);
  line-height: 1.6;
}

/* ===== 凡例 ===== */
.fmap__legend {
  display: flex;
  gap: 6px;
  font-size: 10px;
  letter-spacing: 1px;
}
.lg {
  padding: 4px 9px;
  border: 1px solid var(--line-strong);
  color: var(--text-dim);
  white-space: nowrap;
}
.lg--empty {
  color: var(--faint);
}
.lg--live {
  background: var(--green);
  color: #000;
  border-color: var(--green);
  font-weight: 700;
}
.lg--reserved {
  border-style: dashed;
  color: var(--text);
}
.lg--off_air {
  color: var(--text-dim);
}

/* ===== 集計チップ ===== */
.fmap__counts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}
.count {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
  color: var(--text-dim);
  border: 1px solid var(--line-strong);
  padding: 6px 12px;
  background: var(--panel-deep);
  font-variant-numeric: tabular-nums;
}
.count b {
  font-size: 15px;
  color: var(--text);
  font-weight: 700;
}
.count--live {
  border-color: var(--green);
}
.count--live b {
  color: var(--green);
}
.count--reserved {
  border-style: dashed;
}

/* ===== スロットグリッド ===== */
.fmap__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(56px, 1fr));
  gap: 5px;
  margin-bottom: 28px;
}
.slot {
  font-family: inherit;
  font-size: 11px;
  min-width: 0;
  padding: 10px 2px;
  background: var(--panel-deep);
  border: 1px solid var(--line);
  color: var(--faint);
  cursor: pointer;
  border-radius: 0;
  font-variant-numeric: tabular-nums;
  transition: background 0.1s ease, color 0.1s ease, border-color 0.1s ease;
}
.slot:hover {
  border-color: var(--green);
  color: var(--green);
  background: #141414;
}
.slot--empty {
  color: var(--faint);
}
.slot--reserved {
  border-style: dashed;
  border-color: var(--text-dim);
  color: var(--text);
}
.slot--live {
  background: var(--green);
  color: #000;
  border-color: var(--green);
  font-weight: 700;
}
.slot--live:hover {
  color: #000;
  background: #d6d6d6;
}
.slot--off_air {
  color: var(--text-dim);
  border-color: var(--line-strong);
}
.slot.is-selected {
  outline: 2px solid var(--green);
  outline-offset: 2px;
}

/* ===== 専用局（申請）セクション ===== */
.dedicated-block {
  background: var(--panel);
  border: 1px solid var(--line-strong);
  border-left: 3px solid var(--green);
  padding: 20px;
  margin: 28px 0;
}
.dedicated-block__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px dashed var(--line-strong);
}
.dedicated-block__head h3 {
  margin: 0 0 4px;
  font-size: 16px;
  color: var(--green);
  letter-spacing: 1px;
}
.dedicated-block__head p {
  margin: 0;
  font-size: 12px;
  color: var(--text-dim);
}

/* ===== 詳細パネル（右下に固定表示） ===== */
.detail-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 90;
}
.detail {
  position: fixed;
  right: 24px;
  bottom: 24px;
  width: min(420px, calc(100vw - 32px));
  max-height: calc(100vh - 48px);
  overflow-y: auto;
  background: var(--panel);
  border: 1px solid var(--green);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.7);
  z-index: 91;
}
.detail__head {
  position: sticky;
  top: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #0b0b0b;
  border-bottom: 1px solid var(--line-strong);
}
.detail__freq {
  font-size: 20px;
  color: var(--green);
  font-variant-numeric: tabular-nums;
}
.detail__status {
  font-size: 11px;
  letter-spacing: 1px;
  color: var(--text-dim);
}
.st--live {
  color: var(--green);
}
.detail__close {
  margin-left: auto;
  font-size: 12px;
  padding: 6px 10px;
}
.detail__body {
  padding: 16px;
}
.detail__callsign {
  margin: 0 0 6px;
  font-size: 16px;
  color: var(--text);
}
.detail__meta {
  margin: 0 0 4px;
  font-size: 12px;
  color: var(--text-dim);
}
.detail__note {
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--text-dim);
}
.detail__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}
.reserve {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed var(--line-strong);
}
.reserve__row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.reserve__row span {
  font-size: 12px;
  color: var(--text-dim);
  width: 40px;
}
.field-input {
  flex: 1;
  min-width: 0;
  background: var(--panel-deep);
  border: 1px solid var(--line-strong);
  color: var(--text);
  font-family: inherit;
  font-size: 13px;
  padding: 8px 10px;
  outline: none;
  border-radius: 0;
}
.err {
  color: var(--green);
  font-size: 12px;
  margin: 0;
}

@media (max-width: 640px) {
  .fmap__head {
    flex-direction: column;
    align-items: flex-start;
  }
  .fmap__legend {
    flex-wrap: wrap;
  }
  .fmap__grid {
    grid-template-columns: repeat(auto-fill, minmax(48px, 1fr));
    gap: 4px;
  }
  /* モバイルは全画面シート風 */
  .detail {
    right: 0;
    bottom: 0;
    left: 0;
    width: 100%;
    max-height: 82vh;
    border-left: none;
    border-right: none;
    border-bottom: none;
  }
}
</style>
