<script setup lang="ts">
import dayjs from 'dayjs'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tab from 'primevue/tab'
import TabList from 'primevue/tablist'
import TabPanel from 'primevue/tabpanel'
import TabPanels from 'primevue/tabpanels'
import Tabs from 'primevue/tabs'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import { useToast } from 'primevue/usetoast'
import { computed, onMounted, ref, watch } from 'vue'
import { ApiRequestError } from '@/api/client'
import { useContractorsStore } from '@/stores/contractors'
import type { Contractor, ContractorRateType } from '@/types/domain'

const store = useContractorsStore()
const toast = useToast()

onMounted(() => {
  store.fetchContractors()
})

const contractorSearch = ref('')
const filteredContractors = computed(() => {
  const q = contractorSearch.value.trim().toLowerCase()
  if (!q) return store.contractors
  return store.contractors.filter((c) => c.name.toLowerCase().includes(q))
})

const rateTypeLabel: Record<ContractorRateType, string> = { hourly: '時給制', daily: '日給制', fixed: '固定額制' }
const rateTypeSeverity: Record<ContractorRateType, 'info' | 'success' | 'secondary'> = { hourly: 'info', daily: 'success', fixed: 'secondary' }

function closingLabel(day: number): string {
  return day >= 31 ? '月末' : `${day}日`
}
function paymentLabel(c: Contractor): string {
  return `${c.paymentMonthOffset === 1 ? '翌月' : '当月'}${c.paymentDay}日`
}

// --- 外注先登録 ---
const showAddDialog = ref(false)
const rateTypeOptions = [
  { label: '時給制', value: 'hourly' },
  { label: '日給制', value: 'daily' },
  { label: '固定額制', value: 'fixed' },
]
const paymentOffsetOptions = [
  { label: '当月', value: 0 },
  { label: '翌月', value: 1 },
]
const addForm = ref({
  name: '',
  email: '',
  rateType: 'hourly' as ContractorRateType,
  rateAmount: 0,
  closingDay: 31,
  paymentMonthOffset: 1 as 0 | 1,
  paymentDay: 10,
})

const addError = ref('')

function openAddDialog() {
  addForm.value = {
    name: '',
    email: '',
    rateType: 'hourly',
    rateAmount: 0,
    closingDay: 31,
    paymentMonthOffset: 1,
    paymentDay: 10,
  }
  addError.value = ''
  showAddDialog.value = true
}

async function onSubmitAdd() {
  addError.value = ''
  if (!addForm.value.name.trim()) {
    addError.value = '名前・屋号を入力してください。'
    return
  }
  try {
    await store.addContractor({ ...addForm.value })
    showAddDialog.value = false
    toast.add({ severity: 'success', summary: `${addForm.value.name}を登録しました`, life: 2500 })
  } catch (e) {
    addError.value = e instanceof ApiRequestError ? e.message : '登録に失敗しました。時間をおいてお試しください。'
  }
}

// --- 稼働実績入力 ---
const targetMonth = ref(dayjs().subtract(1, 'month').format('YYYY-MM'))
const selectedContractorId = ref('')

watch(
  () => store.contractors,
  (list) => {
    if (list.length && !selectedContractorId.value) selectedContractorId.value = list[0]!.id
  },
  { immediate: true },
)

const selectedContractor = computed(() => store.contractors.find((c) => c.id === selectedContractorId.value) ?? null)
const contractorOptions = computed(() => store.contractors.map((c) => ({ label: c.name, value: c.id })))

const workForm = ref({ hours: null as number | null, days: null as number | null, fixedApplied: false, note: '' })

function syncWorkForm() {
  if (!selectedContractorId.value) return
  const existing = store.recordFor(selectedContractorId.value, targetMonth.value)
  workForm.value = {
    hours: existing?.hours ?? null,
    days: existing?.days ?? null,
    fixedApplied: existing?.fixedApplied ?? false,
    note: existing?.note ?? '',
  }
}
watch([selectedContractorId, targetMonth], syncWorkForm, { immediate: true })

const workError = ref('')

async function onSaveWorkRecord() {
  workError.value = ''
  if (!selectedContractor.value) return
  try {
    await store.saveWorkRecord({
      contractorId: selectedContractor.value.id,
      yearMonth: targetMonth.value,
      hours: selectedContractor.value.rateType === 'hourly' ? workForm.value.hours : null,
      days: selectedContractor.value.rateType === 'daily' ? workForm.value.days : null,
      fixedApplied: selectedContractor.value.rateType === 'fixed' ? workForm.value.fixedApplied : false,
      note: workForm.value.note,
    })
    toast.add({ severity: 'success', summary: '稼働実績を保存しました', life: 2500 })
  } catch (e) {
    workError.value = e instanceof ApiRequestError ? e.message : '保存に失敗しました。時間をおいてお試しください。'
  }
}

const monthRecords = computed(() =>
  store.contractors.map((c) => ({ contractor: c, record: store.recordFor(c.id, targetMonth.value) ?? null })),
)

function entered(row: (typeof monthRecords.value)[number]): boolean {
  const r = row.record
  if (!r) return false
  if (row.contractor.rateType === 'hourly') return r.hours != null
  if (row.contractor.rateType === 'daily') return r.days != null
  return r.fixedApplied
}
function recordLabel(row: (typeof monthRecords.value)[number]): string {
  const r = row.record
  if (!entered(row) || !r) return '—'
  if (row.contractor.rateType === 'hourly') return `${r.hours}時間`
  if (row.contractor.rateType === 'daily') return `${r.days}日`
  return '適用'
}
</script>

<template>
  <section class="page">
    <header class="page__head">
      <p class="eyebrow">管理者</p>
      <h1 class="page__title">外注管理</h1>
    </header>

    <Tabs value="master">
      <TabList>
        <Tab value="master">外注マスタ</Tab>
        <Tab value="work">稼働実績入力</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="master">
          <div class="panel-head">
            <p class="lede">外注先ごとに単価タイプ・締め日・支払日を設定します。設定内容は翌月以降もデフォルトとして引き継がれます。</p>
            <div class="panel-head__actions">
              <IconField>
                <InputIcon class="pi pi-search" />
                <InputText v-model="contractorSearch" placeholder="外注先名で検索" size="small" />
              </IconField>
              <Button label="外注先を登録" icon="pi pi-plus" @click="openAddDialog" />
            </div>
          </div>
          <DataTable :value="filteredContractors" size="small" :loading="store.loading" paginator :rows="10">
            <Column field="name" header="外注先" sortable />
            <Column header="単価タイプ" style="width: 110px">
              <template #body="{ data }">
                <Tag :value="rateTypeLabel[data.rateType as ContractorRateType]" :severity="rateTypeSeverity[data.rateType as ContractorRateType]" />
              </template>
            </Column>
            <Column header="単価額" style="width: 130px" bodyStyle="text-align: right" headerStyle="text-align: right">
              <template #body="{ data }">¥{{ data.rateAmount.toLocaleString() }}<span v-if="data.rateType !== 'fixed'">{{ data.rateType === 'hourly' ? ' / 時間' : ' / 日' }}</span></template>
            </Column>
            <Column header="締め日" style="width: 90px">
              <template #body="{ data }">{{ closingLabel(data.closingDay) }}</template>
            </Column>
            <Column header="支払日" style="width: 100px">
              <template #body="{ data }">{{ paymentLabel(data) }}</template>
            </Column>
          </DataTable>
        </TabPanel>

        <TabPanel value="work">
          <div class="work">
            <Card class="work__form">
              <template #title>稼働実績を入力</template>
              <template #content>
                <form class="form" @submit.prevent="onSaveWorkRecord">
                  <label class="field">
                    <span class="field__label">対象月</span>
                    <input v-model="targetMonth" type="month" />
                  </label>
                  <label class="field">
                    <span class="field__label">外注先</span>
                    <Select v-model="selectedContractorId" :options="contractorOptions" option-label="label" option-value="value" />
                  </label>

                  <label v-if="selectedContractor?.rateType === 'hourly'" class="field">
                    <span class="field__label">稼働時間（時間）</span>
                    <InputNumber v-model="workForm.hours" :min="0" :max-fraction-digits="1" suffix=" h" />
                  </label>
                  <label v-else-if="selectedContractor?.rateType === 'daily'" class="field">
                    <span class="field__label">稼働日数（日）</span>
                    <InputNumber v-model="workForm.days" :min="0" :max-fraction-digits="1" suffix=" 日" />
                  </label>
                  <label v-else-if="selectedContractor?.rateType === 'fixed'" class="toggle">
                    <input v-model="workForm.fixedApplied" type="checkbox" />
                    今月分の固定額（¥{{ selectedContractor.rateAmount.toLocaleString() }}）を適用する
                  </label>

                  <label class="field">
                    <span class="field__label">備考（任意）</span>
                    <Textarea v-model="workForm.note" rows="2" />
                  </label>

                  <p v-if="workError" class="form__error" role="alert">{{ workError }}</p>

                  <Button type="submit" label="保存する" :loading="store.saving" class="form__submit" />
                </form>
              </template>
            </Card>

            <Card class="work__list">
              <template #title>{{ dayjs(targetMonth).format('YYYY年M月') }}分の入力状況</template>
              <template #content>
                <DataTable :value="monthRecords" size="small">
                  <Column header="外注先" style="width: 160px">
                    <template #body="{ data }">{{ data.contractor.name }}</template>
                  </Column>
                  <Column header="単価タイプ" style="width: 100px">
                    <template #body="{ data }">
                      <Tag :value="rateTypeLabel[data.contractor.rateType as ContractorRateType]" :severity="rateTypeSeverity[data.contractor.rateType as ContractorRateType]" />
                    </template>
                  </Column>
                  <Column header="実績" style="width: 90px">
                    <template #body="{ data }">{{ recordLabel(data) }}</template>
                  </Column>
                  <Column header="状態" style="width: 90px">
                    <template #body="{ data }">
                      <Tag :value="entered(data) ? '入力済み' : '未入力'" :severity="entered(data) ? 'success' : 'secondary'" />
                    </template>
                  </Column>
                </DataTable>
              </template>
            </Card>
          </div>
        </TabPanel>
      </TabPanels>
    </Tabs>

    <Dialog v-model:visible="showAddDialog" header="外注先を登録" modal :style="{ width: '440px' }">
      <form class="form" @submit.prevent="onSubmitAdd">
        <label class="field">
          <span class="field__label">名前・屋号</span>
          <InputText v-model="addForm.name" required />
        </label>
        <label class="field">
          <span class="field__label">メールアドレス（請求書送信先）</span>
          <InputText v-model="addForm.email" type="email" />
        </label>
        <label class="field">
          <span class="field__label">単価タイプ</span>
          <Select v-model="addForm.rateType" :options="rateTypeOptions" option-label="label" option-value="value" />
        </label>
        <label class="field">
          <span class="field__label">単価額（円）</span>
          <InputNumber v-model="addForm.rateAmount" :min="0" />
        </label>
        <div class="field-row">
          <label class="field">
            <span class="field__label">締め日</span>
            <InputNumber v-model="addForm.closingDay" :min="1" :max="31" suffix=" 日（31=月末）" />
          </label>
        </div>
        <div class="field-row">
          <label class="field">
            <span class="field__label">支払月</span>
            <Select v-model="addForm.paymentMonthOffset" :options="paymentOffsetOptions" option-label="label" option-value="value" />
          </label>
          <label class="field">
            <span class="field__label">支払日</span>
            <InputNumber v-model="addForm.paymentDay" :min="1" :max="31" suffix=" 日" />
          </label>
        </div>
        <p v-if="addError" class="form__error" role="alert">{{ addError }}</p>
        <div class="reject-form__actions">
          <Button type="button" label="キャンセル" severity="secondary" text @click="showAddDialog = false" />
          <Button type="submit" label="登録する" :loading="store.saving" />
        </div>
      </form>
    </Dialog>
  </section>
</template>

<style scoped>
.page__head { margin-bottom: 24px; }
.eyebrow { margin: 0 0 4px; font-size: 13px; color: var(--muted); font-weight: 600; }
.page__title { margin: 0; font-size: 24px; }

.panel-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin: 16px 0; flex-wrap: wrap; }
.panel-head__actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.lede { margin: 0; font-size: 12.5px; color: var(--muted); max-width: 560px; }

@media (max-width: 480px) {
  .panel-head__actions { width: 100%; }
  .panel-head__actions > * { width: 100%; }
}

.work { display: grid; grid-template-columns: minmax(280px, 360px) 1fr; gap: 20px; margin-top: 16px; }
@media (max-width: 860px) { .work { grid-template-columns: 1fr; } }

.form { display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field-row { display: flex; gap: 12px; }
.field-row .field { flex: 1; min-width: 0; }
@media (max-width: 480px) { .field-row { flex-direction: column; } }
.field__label { font-size: 13px; color: var(--muted); font-weight: 600; }
.field input[type='month'] {
  padding: 9px 11px; border: 1px solid var(--line); border-radius: 8px; font: inherit; background: var(--surface);
}
.toggle { display: flex; align-items: center; gap: 8px; font-size: 13.5px; }
.form__submit { align-self: flex-start; }
.form__error { color: var(--danger); font-size: 13px; margin: 0; }
.reject-form__actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
