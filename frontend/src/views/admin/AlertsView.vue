<script setup lang="ts">
import dayjs from 'dayjs'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Tag from 'primevue/tag'
import { onMounted } from 'vue'
import { useAlertsStore } from '@/stores/alerts'
import type { OvertimeAlertSeverity, PaidLeaveAlertEntry } from '@/types/domain'

const alerts = useAlertsStore()

onMounted(() => {
  alerts.fetchAlerts()
})

function daysUntil(date: string): number {
  return dayjs(date).diff(dayjs(), 'day')
}

function paidLeaveSeverity(entry: PaidLeaveAlertEntry): 'danger' | 'warn' {
  return daysUntil(entry.deadline) <= 30 ? 'danger' : 'warn'
}

const overtimeSeverityMeta: Record<OvertimeAlertSeverity, { label: string; tag: 'warn' | 'danger' }> = {
  warning: { label: '注意', tag: 'warn' },
  critical: { label: '超過', tag: 'danger' },
  violation: { label: '協定違反', tag: 'danger' },
}
</script>

<template>
  <section class="page">
    <header class="page__head">
      <p class="eyebrow">管理者</p>
      <h1 class="page__title">有給・残業アラート</h1>
    </header>

    <Card class="section">
      <template #title>
        <div class="card-head">
          <span><i class="pi pi-calendar-times" aria-hidden="true" /> 年5日 有給休暇 未取得アラート</span>
          <span class="card-head__count">{{ alerts.paidLeaveAlerts.length }}名</span>
        </div>
      </template>
      <template #content>
        <p class="lede">年10日以上の有給が付与される従業員には、企業側が時季を指定して年5日を取得させる義務があります。</p>
        <DataTable :value="alerts.paidLeaveAlerts" size="small" :loading="alerts.loading">
          <Column field="employeeName" header="従業員" style="width: 140px" />
          <Column field="grantedDate" header="付与日" style="width: 110px">
            <template #body="{ data }">{{ dayjs(data.grantedDate).format('YYYY/M/D') }}</template>
          </Column>
          <Column header="取得状況">
            <template #body="{ data }">
              <div class="progress">
                <div class="bar"><div class="bar__fill" :style="{ width: (data.used / data.required) * 100 + '%' }" /></div>
                <span class="progress__text">{{ data.used }} / {{ data.required }}日</span>
              </div>
            </template>
          </Column>
          <Column header="期限" style="width: 140px">
            <template #body="{ data }">
              {{ dayjs(data.deadline).format('YYYY/M/D') }}
              <span class="days-left">（あと{{ daysUntil(data.deadline) }}日）</span>
            </template>
          </Column>
          <Column header="状態" style="width: 90px">
            <template #body="{ data }">
              <Tag :value="paidLeaveSeverity(data) === 'danger' ? '要対応' : '注意'" :severity="paidLeaveSeverity(data)" />
            </template>
          </Column>
          <template #empty>対象者はいません。</template>
        </DataTable>
      </template>
    </Card>

    <Card class="section">
      <template #title>
        <div class="card-head">
          <span><i class="pi pi-exclamation-triangle" aria-hidden="true" /> 36協定 残業時間アラート</span>
          <span class="card-head__count">{{ alerts.overtimeAlerts.length }}名</span>
        </div>
      </template>
      <template #content>
        <p class="lede">36協定の上限（原則月45時間）に達した、または達する見込みの従業員を表示しています。</p>
        <DataTable :value="alerts.overtimeAlerts" size="small" :loading="alerts.loading">
          <Column field="employeeName" header="従業員" style="width: 140px" />
          <Column field="month" header="対象月" style="width: 100px">
            <template #body="{ data }">{{ dayjs(data.month).format('YYYY年M月') }}</template>
          </Column>
          <Column header="残業時間">
            <template #body="{ data }">
              <div class="progress">
                <div class="bar"><div class="bar__fill bar__fill--warn" :style="{ width: Math.min(100, (data.overtimeHours / data.limitHours) * 100) + '%' }" /></div>
                <span class="progress__text">{{ data.overtimeHours }}h / {{ data.limitHours }}h</span>
              </div>
            </template>
          </Column>
          <Column header="状態" style="width: 100px">
            <template #body="{ data }">
              <Tag :value="overtimeSeverityMeta[data.severity as OvertimeAlertSeverity].label" :severity="overtimeSeverityMeta[data.severity as OvertimeAlertSeverity].tag" />
            </template>
          </Column>
          <Column header="理由">
            <template #body="{ data }">
              <div class="reasons">
                <span v-for="r in data.reasons" :key="r.kind" class="reason-chip">{{ r.label }}</span>
              </div>
            </template>
          </Column>
          <template #empty>対象者はいません。</template>
        </DataTable>
      </template>
    </Card>
  </section>
</template>

<style scoped>
.page__head { margin-bottom: 28px; }
.eyebrow { margin: 0 0 4px; font-size: 13px; color: var(--muted); font-weight: 600; }
.page__title { margin: 0; font-size: 24px; }
.section + .section { margin-top: 20px; }

.card-head { display: flex; align-items: center; justify-content: space-between; font-size: 15px; }
.card-head__count { font-size: 12px; color: var(--muted); font-weight: 500; }
.lede { margin: -4px 0 14px; font-size: 12.5px; color: var(--muted); }

.progress { display: flex; align-items: center; gap: 10px; min-width: 160px; }
.bar { flex: 1; height: 6px; background: var(--paper); border-radius: 3px; overflow: hidden; }
.bar__fill { height: 100%; background: var(--accent); border-radius: 3px; }
.bar__fill--warn { background: var(--warning); }
.progress__text { font-size: 12.5px; color: var(--muted); white-space: nowrap; }
.days-left { font-size: 12px; color: var(--muted); }

.reasons { display: flex; flex-wrap: wrap; gap: 4px; }
.reason-chip {
  font-size: 12px; color: var(--muted); background: var(--paper); border: 1px solid var(--line);
  border-radius: 999px; padding: 2px 8px; white-space: nowrap;
}
</style>
