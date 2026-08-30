<script setup lang="ts">
import dayjs from 'dayjs'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import { useToast } from 'primevue/usetoast'
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useAttendanceStore } from '@/stores/attendance'
import { useAuthStore } from '@/stores/auth'
import { useNotificationHistoryStore } from '@/stores/notificationHistory'
import type { AppNotification, CorrectionRequestPayload, DailyRecordNote, NotificationCategory } from '@/types/domain'

const auth = useAuthStore()
const attendance = useAttendanceStore()
const history = useNotificationHistoryStore()
const toast = useToast()

onMounted(() => {
  attendance.fetchDashboard()
})

const todayLabel = computed(() => dayjs().format('YYYY年M月D日（ddd）'))

const punching = ref(false)

const statusMeta = computed(() => {
  const state = attendance.today?.state
  if (state === 'working') return { label: '出勤中', severity: 'warn' as const }
  if (state === 'finished') return { label: '退勤済み', severity: 'success' as const }
  return { label: '未出勤', severity: 'secondary' as const }
})

async function onPunch() {
  punching.value = true
  try {
    if (attendance.today?.state === 'working') {
      await attendance.clockOut()
      toast.add({ severity: 'success', summary: '退勤を記録しました', life: 2500 })
    } else {
      await attendance.clockIn()
      toast.add({ severity: 'success', summary: '出勤を記録しました', life: 2500 })
    }
  } finally {
    punching.value = false
  }
}

const overtimeRatio = computed(() => {
  const s = attendance.monthlySummary
  if (!s) return 0
  return Math.min(100, Math.round((s.overtimeHours / s.overtimeLimitHours) * 100))
})
const overtimeWarn = computed(() => overtimeRatio.value >= 80)

const noteMeta: Record<DailyRecordNote, { label: string; severity: 'success' | 'warn' | 'info' | 'secondary' }> = {
  normal: { label: '通常', severity: 'success' },
  pending: { label: '確認中', severity: 'warn' },
  leave: { label: '休暇', severity: 'info' },
  holiday: { label: '休日', severity: 'secondary' },
}

const categoryMeta: Record<NotificationCategory, { icon: string; tone: string }> = {
  approval: { icon: 'pi-check-circle', tone: 'notif--approval' },
  reminder: { icon: 'pi-exclamation-triangle', tone: 'notif--reminder' },
  info: { icon: 'pi-info-circle', tone: 'notif--info' },
}

function relativeTime(iso: string): string {
  const diffH = dayjs().diff(dayjs(iso), 'hour')
  if (diffH < 1) return 'たった今'
  if (diffH < 24) return `${diffH}時間前`
  return `${Math.floor(diffH / 24)}日前`
}

async function onNotificationClick(n: AppNotification) {
  if (n.read) return
  await attendance.markOneRead(n.id)
}

// --- 通知一覧（過去の通知）ダイアログ ---
const showHistory = ref(false)
const historyDays = ref(30)
const periodOptions = [
  { label: '過去7日', value: 7 },
  { label: '過去30日', value: 30 },
  { label: '過去90日', value: 90 },
]

function openHistory() {
  showHistory.value = true
  history.fetchHistory(historyDays.value)
}

function onSelectPeriod(days: number) {
  historyDays.value = days
  history.fetchHistory(days)
}

async function onHistoryNotificationClick(n: AppNotification) {
  if (n.read) return
  await history.markOneRead(n.id)
  // ダッシュボードの直近リストにも同じ通知が含まれていれば既読状態を合わせる
  const inRecent = attendance.notifications.find((r) => r.id === n.id)
  if (inRecent) inRecent.read = true
}

// --- 打刻修正依頼ダイアログ ---
const showCorrection = ref(false)
const submittingCorrection = ref(false)
const correctionForm = ref<CorrectionRequestPayload>({
  date: dayjs().format('YYYY-MM-DD'),
  type: 'clock_in',
  correctedTime: '',
  reason: '',
})
const correctionTypeOptions = [
  { label: '出勤', value: 'clock_in' },
  { label: '退勤', value: 'clock_out' },
]

function openCorrection() {
  correctionForm.value = {
    date: dayjs().format('YYYY-MM-DD'),
    type: 'clock_in',
    correctedTime: '',
    reason: '',
  }
  showCorrection.value = true
}

async function onSubmitCorrection() {
  submittingCorrection.value = true
  try {
    await attendance.requestCorrection(correctionForm.value)
    showCorrection.value = false
    toast.add({ severity: 'info', summary: '修正依頼を送信しました', life: 2500 })
    await attendance.fetchDashboard()
  } finally {
    submittingCorrection.value = false
  }
}
</script>

<template>
  <section class="page">
    <header class="page__head">
      <p class="eyebrow">{{ todayLabel }}</p>
      <h1 class="page__title">おはようございます、{{ auth.me?.name }}さん</h1>
    </header>

    <div class="row row--top">
      <Card class="punch-card">
        <template #content>
          <div class="punch">
            <div class="punch__status">
              <Tag :value="statusMeta.label" :severity="statusMeta.severity" />
              <p class="punch__times">
                <span v-if="attendance.today?.clockInAt">出勤 {{ attendance.today.clockInAt }}</span>
                <span v-if="attendance.today?.clockOutAt"> ・ 退勤 {{ attendance.today.clockOutAt }}</span>
                <span v-if="!attendance.today?.clockInAt" class="punch__times--muted">まだ打刻していません</span>
              </p>
            </div>
            <Button
              v-if="attendance.today?.state !== 'finished'"
              :label="attendance.today?.state === 'working' ? '退勤する' : '出勤する'"
              :icon="`pi ${attendance.today?.state === 'working' ? 'pi-sign-out' : 'pi-sign-in'}`"
              :severity="attendance.today?.state === 'working' ? 'danger' : undefined"
              size="large"
              :loading="punching"
              class="punch__btn"
              @click="onPunch"
            />
            <p v-else class="punch__done">本日の勤務は終了しました。お疲れさまでした。</p>
          </div>
          <button type="button" class="linklike" @click="openCorrection">打刻の修正を依頼する</button>
        </template>
      </Card>

      <div class="stats">
        <div class="stat">
          <p class="stat__label">今月の出勤日数</p>
          <p class="stat__value">{{ attendance.monthlySummary?.workDays ?? '—' }}<span class="stat__unit">日</span></p>
        </div>
        <div class="stat">
          <p class="stat__label">今月の実働時間</p>
          <p class="stat__value">{{ attendance.monthlySummary?.workedHours ?? '—' }}<span class="stat__unit">h</span></p>
        </div>
        <div class="stat">
          <p class="stat__label">有給休暇 残日数</p>
          <p class="stat__value">{{ attendance.monthlySummary?.paidLeaveRemaining ?? '—' }}<span class="stat__unit">日</span></p>
          <RouterLink :to="{ name: 'leave' }" class="stat__link">申請する →</RouterLink>
        </div>
        <div class="stat">
          <p class="stat__label">今月の残業時間（36協定）</p>
          <p class="stat__value" :class="{ 'stat__value--warn': overtimeWarn }">
            {{ attendance.monthlySummary?.overtimeHours ?? '—' }}<span class="stat__unit"
              >h / {{ attendance.monthlySummary?.overtimeLimitHours }}h</span
            >
          </p>
          <div class="bar">
            <div class="bar__fill" :class="{ 'bar__fill--warn': overtimeWarn }" :style="{ width: overtimeRatio + '%' }" />
          </div>
        </div>
      </div>
    </div>

    <div class="row row--two">
      <Card class="notif-card">
        <template #title>
          <div class="card-head">
            <span>通知</span>
            <div class="card-head__actions">
              <button
                v-if="attendance.unreadCount > 0"
                type="button"
                class="linklike"
                @click="attendance.markAllRead()"
              >
                すべて既読にする
              </button>
              <button type="button" class="linklike" @click="openHistory">通知一覧</button>
            </div>
          </div>
        </template>
        <template #content>
          <ul v-if="attendance.notifications.length" class="notif-list">
            <li
              v-for="n in attendance.notifications"
              :key="n.id"
              class="notif"
              :class="{ 'notif--unread': !n.read, 'notif--read': n.read }"
              @click="onNotificationClick(n)"
            >
              <i class="pi notif__icon" :class="[categoryMeta[n.category].icon, categoryMeta[n.category].tone]" aria-hidden="true" />
              <div class="notif__body">
                <template v-if="n.read">
                  <p class="notif__compact">
                    <span class="notif__title">{{ n.title }}</span>
                    <span class="notif__time"> ・ {{ relativeTime(n.createdAt) }}</span>
                  </p>
                </template>
                <template v-else>
                  <p class="notif__title">{{ n.title }}</p>
                  <p class="notif__detail">{{ n.detail }}</p>
                  <p class="notif__time">{{ relativeTime(n.createdAt) }}</p>
                </template>
              </div>
            </li>
          </ul>
          <p v-else class="empty">通知はありません。</p>
        </template>
      </Card>

      <Card class="history-card">
        <template #title>直近の打刻履歴</template>
        <template #content>
          <DataTable :value="attendance.recent" size="small" :loading="attendance.loading">
            <Column field="weekday" header="曜日" style="width: 56px">
              <template #body="{ data }">{{ dayjs(data.date).format('M/D') }}（{{ data.weekday }}）</template>
            </Column>
            <Column field="clockIn" header="出勤">
              <template #body="{ data }">{{ data.clockIn ?? '—' }}</template>
            </Column>
            <Column field="clockOut" header="退勤">
              <template #body="{ data }">{{ data.clockOut ?? '—' }}</template>
            </Column>
            <Column field="workedMinutes" header="実働">
              <template #body="{ data }">
                {{ data.workedMinutes ? (data.workedMinutes / 60).toFixed(1) + 'h' : '—' }}
              </template>
            </Column>
            <Column field="note" header="状態">
              <template #body="{ data }">
                <Tag :value="noteMeta[data.note as DailyRecordNote].label" :severity="noteMeta[data.note as DailyRecordNote].severity" />
              </template>
            </Column>
          </DataTable>
        </template>
      </Card>
    </div>

    <Dialog v-model:visible="showCorrection" header="打刻の修正を依頼する" modal :style="{ width: '420px' }">
      <form class="correction" @submit.prevent="onSubmitCorrection">
        <label class="field">
          <span class="field__label">対象日</span>
          <input v-model="correctionForm.date" type="date" required />
        </label>
        <label class="field">
          <span class="field__label">種別</span>
          <Select v-model="correctionForm.type" :options="correctionTypeOptions" option-label="label" option-value="value" />
        </label>
        <label class="field">
          <span class="field__label">修正後の時刻</span>
          <input v-model="correctionForm.correctedTime" type="time" required />
        </label>
        <label class="field">
          <span class="field__label">理由</span>
          <Textarea v-model="correctionForm.reason" rows="3" placeholder="打刻を忘れた経緯など" required />
        </label>
        <div class="correction__actions">
          <Button type="button" label="キャンセル" severity="secondary" text @click="showCorrection = false" />
          <Button type="submit" label="申請する" :loading="submittingCorrection" />
        </div>
      </form>
    </Dialog>

    <Dialog v-model:visible="showHistory" header="通知一覧" modal :style="{ width: '520px' }">
      <div class="history">
        <div class="history__filters">
          <button
            v-for="opt in periodOptions"
            :key="opt.value"
            type="button"
            class="chip"
            :class="{ 'chip--active': historyDays === opt.value }"
            @click="onSelectPeriod(opt.value)"
          >
            {{ opt.label }}
          </button>
        </div>
        <ul v-if="history.items.length" class="notif-list">
          <li
            v-for="n in history.items"
            :key="n.id"
            class="notif"
            :class="{ 'notif--unread': !n.read, 'notif--read': n.read }"
            @click="onHistoryNotificationClick(n)"
          >
            <i class="pi notif__icon" :class="[categoryMeta[n.category].icon, categoryMeta[n.category].tone]" aria-hidden="true" />
            <div class="notif__body">
              <template v-if="n.read">
                <p class="notif__compact">
                  <span class="notif__title">{{ n.title }}</span>
                  <span class="notif__time"> ・ {{ dayjs(n.createdAt).format('M/D HH:mm') }}</span>
                </p>
              </template>
              <template v-else>
                <p class="notif__title">{{ n.title }}</p>
                <p class="notif__detail">{{ n.detail }}</p>
                <p class="notif__time">{{ dayjs(n.createdAt).format('M/D HH:mm') }}</p>
              </template>
            </div>
          </li>
        </ul>
        <p v-else-if="history.loading" class="empty">読み込み中…</p>
        <p v-else class="empty">この期間の通知はありません。</p>
      </div>
    </Dialog>
  </section>
</template>

<style scoped>
.page__head { margin-bottom: 28px; }
.eyebrow { margin: 0 0 4px; font-size: 13px; color: var(--muted); font-weight: 600; }
.page__title { margin: 0; font-size: 24px; }

.row { display: grid; gap: 20px; margin-bottom: 20px; }
.row--top { grid-template-columns: minmax(260px, 1fr) 2fr; }
.row--two { grid-template-columns: 1fr 1fr; }
@media (max-width: 860px) {
  .row--top, .row--two { grid-template-columns: 1fr; }
}

.punch-card :deep(.p-card-body) { height: 100%; display: flex; flex-direction: column; }
.punch-card :deep(.p-card-content) { display: flex; flex-direction: column; gap: 14px; flex: 1; }
.punch { display: flex; flex-direction: column; gap: 14px; align-items: flex-start; flex: 1; justify-content: center; }
.punch__status { display: flex; flex-direction: column; gap: 6px; }
.punch__times { margin: 0; font-size: 14px; color: var(--muted); }
.punch__times--muted { color: var(--muted); }
.punch__btn { width: 100%; justify-content: center; }
.punch__done { margin: 0; font-size: 14px; color: var(--muted); }
.linklike {
  background: none; border: 0; padding: 0; color: var(--accent-dark); font: inherit; font-size: 13px;
  cursor: pointer; text-decoration: underline; text-underline-offset: 2px; align-self: flex-start;
}

.stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
@media (max-width: 560px) { .stats { grid-template-columns: 1fr; } }
.stat {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-lg);
  padding: 18px; box-shadow: var(--shadow-sm); display: flex; flex-direction: column; gap: 6px;
}
.stat__label { margin: 0; font-size: 12px; color: var(--muted); font-weight: 600; }
.stat__value { margin: 0; font-size: 24px; font-weight: 700; }
.stat__value--warn { color: var(--warning); }
.stat__unit { font-size: 13px; font-weight: 500; color: var(--muted); margin-left: 2px; }
.stat__link { font-size: 12px; color: var(--accent-dark); text-decoration: none; }
.stat__link:hover { text-decoration: underline; }
.bar { height: 6px; background: var(--paper); border-radius: 3px; overflow: hidden; margin-top: 2px; }
.bar__fill { height: 100%; background: var(--accent); border-radius: 3px; transition: width 0.3s; }
.bar__fill--warn { background: var(--warning); }

.card-head { display: flex; align-items: center; justify-content: space-between; font-size: 15px; }
.card-head__actions { display: flex; align-items: center; gap: 14px; }

.notif-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.notif { display: flex; gap: 12px; padding: 12px 4px; border-bottom: 1px solid var(--line); position: relative; }
.notif:last-child { border-bottom: 0; }
.notif--unread { cursor: pointer; }
.notif--unread:hover { background: var(--paper); border-radius: 8px; }
.notif--unread::before {
  content: ''; position: absolute; left: -4px; top: 18px; width: 6px; height: 6px; border-radius: 50%; background: var(--accent);
}
.notif--read { padding: 7px 4px; cursor: default; }
.notif__icon { font-size: 16px; margin-top: 3px; }
.notif--read .notif__icon { font-size: 13px; margin-top: 1px; color: var(--muted); }
.notif--approval { color: var(--accent-dark); }
.notif--reminder { color: var(--warning); }
.notif--info { color: #475467; }
.notif__body { flex: 1; min-width: 0; }
.notif__title { margin: 0 0 2px; font-size: 13.5px; font-weight: 700; }
.notif__detail { margin: 0 0 4px; font-size: 13px; color: var(--muted); }
.notif__time { margin: 0; font-size: 12px; color: var(--muted); }
.notif__compact {
  margin: 0; font-size: 12px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.notif__compact .notif__title { font-size: 12px; font-weight: 500; margin: 0; color: var(--muted); }
.notif__compact .notif__time { font-size: 12px; }
.empty { color: var(--muted); font-size: 13px; }

.history { display: flex; flex-direction: column; gap: 14px; }
.history__filters { display: flex; gap: 8px; }
.chip {
  border: 1px solid var(--line); background: var(--surface); color: var(--muted);
  border-radius: 999px; padding: 6px 14px; font: inherit; font-size: 13px; cursor: pointer;
}
.chip--active { background: var(--accent-soft); border-color: var(--accent); color: var(--accent-dark); font-weight: 600; }

.correction { display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field__label { font-size: 13px; color: var(--muted); font-weight: 600; }
.field input {
  padding: 9px 11px; border: 1px solid var(--line); border-radius: 8px; font: inherit; background: var(--surface);
}
.field input:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.correction__actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }
</style>
