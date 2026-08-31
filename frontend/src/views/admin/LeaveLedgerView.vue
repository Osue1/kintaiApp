<script setup lang="ts">
import dayjs from 'dayjs'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import { computed, onMounted, ref, watch } from 'vue'
import { API_BASE } from '@/api/client'
import { useEmployeesStore } from '@/stores/employees'
import { useLeaveLedgerStore } from '@/stores/leaveLedger'

const employees = useEmployeesStore()
const ledger = useLeaveLedgerStore()

const selectedId = ref<string | null>(null)

onMounted(async () => {
  await employees.fetchEmployees()
  if (employees.employees.length) {
    selectedId.value = employees.employees[0]!.id
  }
})

watch(selectedId, (id) => {
  if (id) ledger.fetchLedger(id)
})

const employeeOptions = computed(() => employees.employees.map((e) => ({ label: e.name, value: e.id })))

function onDownloadPdf() {
  if (!selectedId.value) return
  window.open(`${API_BASE}/leave/admin/ledger/pdf?user_id=${selectedId.value}`, '_blank')
}
</script>

<template>
  <section class="page">
    <header class="page__head">
      <p class="eyebrow">管理者</p>
      <h1 class="page__title">年次有給休暇管理簿</h1>
    </header>

    <Card class="controls">
      <template #content>
        <div class="controls__row">
          <label class="field">
            <span class="field__label">従業員</span>
            <Select v-model="selectedId" :options="employeeOptions" option-label="label" option-value="value" filter />
          </label>
          <Button label="PDF出力" icon="pi pi-download" severity="secondary" outlined :disabled="!selectedId" @click="onDownloadPdf" />
        </div>
        <p class="note">
          労働基準法施行規則第24条の7に基づく法定帳簿。基準日（付与日）ごとに時季・日数を記録し、3年間保存する。
        </p>
      </template>
    </Card>

    <p v-if="ledger.loading" class="loading">読み込み中…</p>

    <template v-else-if="ledger.ledger">
      <Card v-for="grant in ledger.ledger.grants" :key="grant.grantedOn" class="grant-card">
        <template #title>
          <div class="grant-head">
            <span>基準日 {{ dayjs(grant.grantedOn).format('YYYY/M/D') }}（付与 {{ grant.days }}日）</span>
            <div class="grant-head__right">
              <Tag v-if="grant.isExpired" value="失効済み" severity="secondary" />
              <span class="grant-head__remaining">残 {{ grant.remaining }}日</span>
            </div>
          </div>
        </template>
        <template #content>
          <DataTable :value="grant.consumptions" size="small">
            <Column field="dateLabel" header="時季（取得日）" style="width: 220px" />
            <Column field="leaveTypeName" header="休暇種類" style="width: 160px" />
            <Column header="日数" style="width: 80px" bodyStyle="text-align: right" headerStyle="text-align: right">
              <template #body="{ data }">{{ data.days }}日</template>
            </Column>
            <template #empty>取得実績なし</template>
          </DataTable>
        </template>
      </Card>
      <p v-if="!ledger.ledger.grants.length" class="empty">付与記録がありません。</p>
    </template>
  </section>
</template>

<style scoped>
.page__head { margin-bottom: 24px; }
.eyebrow { margin: 0 0 4px; font-size: 13px; color: var(--muted); font-weight: 600; }
.page__title { margin: 0; font-size: 24px; }

.controls { margin-bottom: 20px; }
.controls__row { display: flex; align-items: flex-end; gap: 16px; flex-wrap: wrap; }
.field { display: flex; flex-direction: column; gap: 6px; min-width: 220px; }
.field__label { font-size: 13px; color: var(--muted); font-weight: 600; }
.note { margin: 12px 0 0; font-size: 12px; color: var(--muted); }

.loading, .empty { color: var(--muted); font-size: 13px; }

.grant-card + .grant-card { margin-top: 16px; }
.grant-head { display: flex; align-items: center; justify-content: space-between; font-size: 14px; flex-wrap: wrap; gap: 4px 12px; }
.grant-head__right { display: flex; align-items: center; gap: 10px; }
.grant-head__remaining { font-size: 13px; color: var(--muted); font-weight: 600; }
</style>
