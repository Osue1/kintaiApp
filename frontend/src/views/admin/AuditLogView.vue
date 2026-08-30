<script setup lang="ts">
import dayjs from 'dayjs'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import { computed, onMounted, ref, watch } from 'vue'
import { useAuditLogsStore } from '@/stores/auditLogs'
import type { AuditLogEntry } from '@/types/domain'

const store = useAuditLogsStore()

// 設計書 第12.1章「承認・打刻修正・マスタ変更・請求書発行を記録する」に対応する、
// 実際にrecord_audit()から呼ばれているaction/target_typeの値と1対1で対応させている
// （バックエンド側で新しいactionが増えたときはここにも追記が必要）。
const actionLabel: Record<string, string> = {
  correction_approve: '打刻修正を承認',
  correction_reject: '打刻修正を差し戻し',
  monthly_approve: '月次勤怠を承認',
  monthly_reject: '月次勤怠を差し戻し',
  leave_approve: '休暇申請を承認',
  leave_reject: '休暇申請を差し戻し',
  employee_create: '従業員を登録',
  employee_update: '従業員情報を更新',
  contractor_create: '外注先を登録',
  contractor_work_record_save: '稼働実績を保存',
  invoice_generate: '請求書を一括生成',
  invoice_send: '請求書を送信',
  invoice_void: '請求書を取消（赤伝）',
  invoice_confirm: '仕入明細書の確認を記録',
  withholding_statements_issue: '支払調書を出力',
}
const targetTypeLabel: Record<string, string> = {
  TimeCorrectionRequest: '打刻修正依頼',
  MonthlyAttendance: '月次勤怠',
  LeaveRequest: '休暇申請',
  User: '従業員',
  Contractor: '外注先',
  ContractorWorkRecord: '外注稼働実績',
  Invoice: '請求書',
  WithholdingStatement: '支払調書',
}
const actionOptions = [
  { label: 'すべての操作', value: '' },
  ...Object.entries(actionLabel).map(([value, label]) => ({ label, value })),
]
const targetTypeOptions = [
  { label: 'すべての対象', value: '' },
  ...Object.entries(targetTypeLabel).map(([value, label]) => ({ label, value })),
]

const actionFilter = ref('')
const targetTypeFilter = ref('')
const dateFrom = ref('')
const dateTo = ref('')

function load() {
  store.fetchAuditLogs({
    action: actionFilter.value || undefined,
    targetType: targetTypeFilter.value || undefined,
    dateFrom: dateFrom.value || undefined,
    dateTo: dateTo.value || undefined,
  })
}

onMounted(load)
watch([actionFilter, targetTypeFilter, dateFrom, dateTo], load)

function describeAction(entry: AuditLogEntry): string {
  return actionLabel[entry.action] ?? entry.action
}
function describeTarget(entry: AuditLogEntry): string {
  const label = targetTypeLabel[entry.targetType] ?? entry.targetType
  return entry.targetId ? `${label} #${entry.targetId}` : label
}

// before/after は操作ごとに任意のキーを持つJSONなので、テーブルの1セルには
// 「フィールド名: 変更前 → 変更後」の一覧としてまとめて表示する。
const changesByEntry = computed(() =>
  store.entries.map((entry) => {
    const keys = new Set([...Object.keys(entry.before ?? {}), ...Object.keys(entry.after ?? {})])
    const lines = [...keys].map((key) => {
      const before = entry.before?.[key]
      const after = entry.after?.[key]
      if (before === undefined) return `${key}: ${after}`
      if (after === undefined) return `${key}: ${before}（削除）`
      return `${key}: ${before} → ${after}`
    })
    return { id: entry.id, lines }
  }),
)
function changesFor(entry: AuditLogEntry): string[] {
  return changesByEntry.value.find((c) => c.id === entry.id)?.lines ?? []
}
</script>

<template>
  <section class="page">
    <header class="page__head">
      <p class="eyebrow">管理者</p>
      <h1 class="page__title">監査ログ</h1>
      <p class="page__lede">承認・打刻修正・マスタ変更・請求書発行の操作履歴を確認できます。</p>
    </header>

    <Card class="controls">
      <template #content>
        <div class="controls__row">
          <label class="field">
            <span class="field__label">操作</span>
            <Select v-model="actionFilter" :options="actionOptions" option-label="label" option-value="value" />
          </label>
          <label class="field">
            <span class="field__label">対象</span>
            <Select v-model="targetTypeFilter" :options="targetTypeOptions" option-label="label" option-value="value" />
          </label>
          <label class="field">
            <span class="field__label">期間（開始）</span>
            <input v-model="dateFrom" type="date" />
          </label>
          <label class="field">
            <span class="field__label">期間（終了）</span>
            <input v-model="dateTo" type="date" />
          </label>
        </div>
      </template>
    </Card>

    <Card>
      <template #title>
        <div class="card-head">
          <span>操作履歴</span>
          <span class="card-head__count">
            {{ store.totalCount }}件
            <span v-if="store.truncated">（直近200件のみ表示）</span>
          </span>
        </div>
      </template>
      <template #content>
        <DataTable :value="store.entries" size="small" :loading="store.loading" paginator :rows="20">
          <Column header="日時" style="width: 150px" body-style="text-align: right" header-style="text-align: right">
            <template #body="{ data }">{{ dayjs(data.createdAt).format('YYYY/M/D HH:mm') }}</template>
          </Column>
          <Column header="操作者" style="width: 120px">
            <template #body="{ data }">{{ data.actorName ?? '（不明）' }}</template>
          </Column>
          <Column header="操作" style="width: 170px">
            <template #body="{ data }"><Tag :value="describeAction(data)" severity="info" /></template>
          </Column>
          <Column header="対象" style="width: 160px">
            <template #body="{ data }">{{ describeTarget(data) }}</template>
          </Column>
          <Column header="変更内容">
            <template #body="{ data }">
              <ul v-if="changesFor(data).length" class="changes">
                <li v-for="(line, i) in changesFor(data)" :key="i">{{ line }}</li>
              </ul>
              <span v-else class="changes__none">—</span>
            </template>
          </Column>
          <Column header="IPアドレス" style="width: 130px">
            <template #body="{ data }">{{ data.ip ?? '—' }}</template>
          </Column>
          <template #empty>該当する監査ログはありません。</template>
        </DataTable>
      </template>
    </Card>
  </section>
</template>

<style scoped>
.page__head { margin-bottom: 24px; }
.eyebrow { margin: 0 0 4px; font-size: 13px; color: var(--muted); font-weight: 600; }
.page__title { margin: 0 0 4px; font-size: 24px; }
.page__lede { margin: 0; font-size: 13px; color: var(--muted); }

.controls { margin-bottom: 20px; }
.controls__row { display: flex; align-items: flex-end; gap: 16px; flex-wrap: wrap; }
.field { display: flex; flex-direction: column; gap: 6px; min-width: 180px; }
.field__label { font-size: 13px; color: var(--muted); font-weight: 600; }
.field input[type='date'] {
  padding: 9px 11px; border: 1px solid var(--line); border-radius: 8px; font: inherit; background: var(--surface);
}

.card-head { display: flex; align-items: center; justify-content: space-between; font-size: 15px; }
.card-head__count { font-size: 12px; color: var(--muted); font-weight: 500; }

.changes { margin: 0; padding-left: 16px; font-size: 12.5px; color: var(--ink); }
.changes li { word-break: break-word; }
.changes__none { color: var(--muted); font-size: 12.5px; }
</style>
