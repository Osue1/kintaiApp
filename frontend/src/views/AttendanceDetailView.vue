<script setup lang="ts">
import dayjs from 'dayjs'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import { computed, onMounted, ref, watch } from 'vue'
import { ApiRequestError } from '@/api/client'
import { useAttendanceMonthlyStore } from '@/stores/attendanceMonthly'
import type { DailyRecordNote, MonthlyStatus } from '@/types/domain'

const store = useAttendanceMonthlyStore()
const toast = useToast()

const targetMonth = ref(dayjs().format('YYYY-MM'))

onMounted(() => {
  store.fetchMonthly(targetMonth.value)
})
watch(targetMonth, (ym) => {
  store.fetchMonthly(ym)
})

const statusMeta: Record<MonthlyStatus, { label: string; severity: 'secondary' | 'warn' | 'success' }> = {
  draft: { label: '未申請', severity: 'secondary' },
  submitted: { label: '申請中', severity: 'warn' },
  approved: { label: '承認済み', severity: 'success' },
}

const noteMeta: Record<DailyRecordNote, { label: string; severity: 'success' | 'warn' | 'info' | 'secondary' }> = {
  normal: { label: '通常', severity: 'success' },
  pending: { label: '確認中', severity: 'warn' },
  leave: { label: '休暇', severity: 'info' },
  holiday: { label: '休日', severity: 'secondary' },
}

const canSubmit = computed(() => !!store.detail && store.detail.status === 'draft' && !store.detail.locked)

async function onSubmit() {
  try {
    await store.submitMonthly(targetMonth.value)
    toast.add({ severity: 'success', summary: '月次確定を申請しました', detail: '管理者の承認をお待ちください。', life: 3000 })
  } catch (e) {
    const detail = e instanceof ApiRequestError ? e.message : '通信に失敗しました。時間をおいてお試しください。'
    toast.add({ severity: 'error', summary: '月次確定申請に失敗しました', detail, life: 5000 })
  }
}
</script>

<template>
  <section class="page">
    <header class="page__head">
      <p class="eyebrow">勤怠</p>
      <h1 class="page__title">勤怠明細・月次締め申請</h1>
    </header>

    <div class="controls">
      <label class="field">
        <span class="field__label">対象月</span>
        <input v-model="targetMonth" type="month" />
      </label>
      <Tag v-if="store.detail" :value="statusMeta[store.detail.status].label" :severity="statusMeta[store.detail.status].severity" />
      <span v-if="store.detail?.locked" class="locked-note"><i class="pi pi-lock" /> ロック済み（変更不可）</span>
      <Button
        label="月次を確定申請する"
        icon="pi pi-send"
        class="controls__submit"
        :disabled="!canSubmit"
        :loading="store.submitting"
        @click="onSubmit"
      />
    </div>

    <div class="stats" v-if="store.detail">
      <div class="stat">
        <p class="stat__label">出勤日数</p>
        <p class="stat__value">{{ store.detail.totals.workDays }}<span class="stat__unit">日</span></p>
      </div>
      <div class="stat">
        <p class="stat__label">実働時間</p>
        <p class="stat__value">{{ store.detail.totals.workedHours }}<span class="stat__unit">h</span></p>
      </div>
      <div class="stat">
        <p class="stat__label">残業時間（36協定対象）</p>
        <p class="stat__value">{{ store.detail.totals.overtimeHours }}<span class="stat__unit">h</span></p>
      </div>
    </div>

    <Card>
      <template #title>日次一覧</template>
      <template #content>
        <DataTable :value="store.detail?.days ?? []" size="small" :loading="store.loading">
          <Column header="日付" style="width: 110px">
            <template #body="{ data }">{{ dayjs(data.date).format('M/D') }}（{{ data.weekday }}）</template>
          </Column>
          <Column field="clockIn" header="出勤" bodyStyle="text-align: right" headerStyle="text-align: right">
            <template #body="{ data }">{{ data.clockIn ?? '—' }}</template>
          </Column>
          <Column field="clockOut" header="退勤" bodyStyle="text-align: right" headerStyle="text-align: right">
            <template #body="{ data }">{{ data.clockOut ?? '—' }}</template>
          </Column>
          <Column header="実働" bodyStyle="text-align: right" headerStyle="text-align: right">
            <template #body="{ data }">{{ data.workedMinutes ? (data.workedMinutes / 60).toFixed(1) + 'h' : '—' }}</template>
          </Column>
          <Column header="状態">
            <template #body="{ data }">
              <Tag :value="noteMeta[data.note as DailyRecordNote].label" :severity="noteMeta[data.note as DailyRecordNote].severity" />
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>
  </section>
</template>

<style scoped>
.page__head { margin-bottom: 24px; }
.eyebrow { margin: 0 0 4px; font-size: 13px; color: var(--muted); font-weight: 600; }
.page__title { margin: 0; font-size: 24px; }

.controls { display: flex; align-items: flex-end; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
.controls__submit { margin-left: auto; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field__label { font-size: 13px; color: var(--muted); font-weight: 600; }
.field input[type='month'] {
  padding: 9px 11px; border: 1px solid var(--line); border-radius: 8px; font: inherit; background: var(--surface);
}
.locked-note { font-size: 13px; color: var(--muted); display: inline-flex; align-items: center; gap: 6px; }

.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px; }
@media (max-width: 640px) { .stats { grid-template-columns: 1fr; } }
.stat {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-lg);
  padding: 18px; box-shadow: var(--shadow-sm);
}
.stat__label { margin: 0 0 6px; font-size: 12px; color: var(--muted); font-weight: 600; }
.stat__value { margin: 0; font-size: 24px; font-weight: 700; }
.stat__unit { font-size: 13px; font-weight: 500; color: var(--muted); margin-left: 2px; }
</style>
