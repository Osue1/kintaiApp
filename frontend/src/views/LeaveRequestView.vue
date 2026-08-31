<script setup lang="ts">
import dayjs from 'dayjs'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import { useToast } from 'primevue/usetoast'
import { computed, onMounted, ref, watch } from 'vue'
import { ApiRequestError } from '@/api/client'
import { useLeaveStore } from '@/stores/leave'
import type { LeaveRequestStatus, LeaveUnit } from '@/types/domain'

const leave = useLeaveStore()
const toast = useToast()

onMounted(() => {
  leave.fetchLeaveData()
})

const unitOptions: { label: string; value: LeaveUnit }[] = [
  { label: '全日', value: 'full' },
  { label: '午前半休', value: 'half_am' },
  { label: '午後半休', value: 'half_pm' },
]

const statusMeta: Record<LeaveRequestStatus, { label: string; severity: 'warn' | 'success' | 'danger' }> = {
  pending: { label: '申請中', severity: 'warn' },
  approved: { label: '承認済み', severity: 'success' },
  rejected: { label: '却下', severity: 'danger' },
}

const unitLabel: Record<LeaveUnit, string> = { full: '全日', half_am: '午前半休', half_pm: '午後半休' }

// --- 申請フォーム ---
const form = ref({
  typeId: '',
  unit: 'full' as LeaveUnit,
  startDate: dayjs().add(7, 'day').format('YYYY-MM-DD'),
  endDate: dayjs().add(7, 'day').format('YYYY-MM-DD'),
  reason: '',
})
const submitError = ref('')

watch(
  () => leave.leaveTypes,
  (types) => {
    if (types.length && !form.value.typeId) form.value.typeId = types[0]!.id
  },
  { immediate: true },
)

const selectedType = computed(() => leave.leaveTypes.find((t) => t.id === form.value.typeId) ?? null)

watch(
  () => form.value.unit,
  (unit) => {
    if (unit !== 'full') form.value.endDate = form.value.startDate
  },
)
watch(
  () => form.value.startDate,
  (start) => {
    if (form.value.unit !== 'full') form.value.endDate = start
  },
)
watch(selectedType, (type) => {
  if (type && !type.supportsHalfDay) form.value.unit = 'full'
})

const typeOptions = computed(() => leave.leaveTypes.map((t) => ({ label: t.name, value: t.id })))

async function onSubmit() {
  submitError.value = ''
  if (dayjs(form.value.endDate).isBefore(dayjs(form.value.startDate))) {
    submitError.value = '終了日は開始日以降を指定してください。'
    return
  }
  if (selectedType.value?.requiresReason && !form.value.reason.trim()) {
    submitError.value = '理由を入力してください。'
    return
  }
  try {
    await leave.submitRequest({
      typeId: form.value.typeId,
      startDate: form.value.startDate,
      endDate: form.value.endDate,
      unit: form.value.unit,
      reason: form.value.reason,
    })
    toast.add({ severity: 'success', summary: '休暇を申請しました', detail: '管理者の承認をお待ちください。', life: 3000 })
    form.value.reason = ''
  } catch (e) {
    submitError.value = e instanceof ApiRequestError ? e.message : '通信に失敗しました。時間をおいてお試しください。'
  }
}
</script>

<template>
  <section class="page">
    <header class="page__head">
      <p class="eyebrow">休暇</p>
      <h1 class="page__title">休暇申請・残日数照会</h1>
    </header>

    <div class="stats">
      <div class="stat">
        <p class="stat__label">有給休暇 残日数</p>
        <p class="stat__value">{{ leave.balance?.paidRemaining ?? '—' }}<span class="stat__unit">日</span></p>
        <p class="stat__caption" v-if="leave.balance">
          付与{{ leave.balance.paidTotal }}日 ・繰越{{ leave.balance.carryOver }}日 ・使用{{ leave.balance.paidUsed }}日
        </p>
      </div>
      <div class="stat">
        <p class="stat__label">次回付与予定</p>
        <p class="stat__value stat__value--sm">{{ leave.balance ? dayjs(leave.balance.nextGrant.date).format('YYYY/M/D') : '—' }}</p>
        <p class="stat__caption" v-if="leave.balance">付与予定 {{ leave.balance.nextGrant.days }}日</p>
      </div>
      <div class="stat">
        <p class="stat__label">年5日取得義務</p>
        <p class="stat__value">
          {{ leave.balance?.mandatoryFiveDays.used ?? '—' }}<span class="stat__unit">/ {{ leave.balance?.mandatoryFiveDays.required }}日</span>
        </p>
        <div class="bar" v-if="leave.balance">
          <div
            class="bar__fill"
            :class="{ 'bar__fill--warn': leave.balance.mandatoryFiveDays.used < leave.balance.mandatoryFiveDays.required }"
            :style="{ width: Math.min(100, (leave.balance.mandatoryFiveDays.used / leave.balance.mandatoryFiveDays.required) * 100) + '%' }"
          />
        </div>
        <p class="stat__caption" v-if="leave.balance">期限 {{ dayjs(leave.balance.mandatoryFiveDays.deadline).format('YYYY/M/D') }}</p>
      </div>
      <div class="stat">
        <p class="stat__label">その他休暇の残数</p>
        <ul class="stat__list" v-if="leave.balance">
          <li v-for="o in leave.balance.others" :key="o.typeId">
            <span>{{ o.typeName }}</span>
            <strong>{{ o.remaining === null ? '上限なし' : `${o.remaining}日` }}</strong>
          </li>
        </ul>
      </div>
    </div>

    <div class="row row--two">
      <Card class="form-card">
        <template #title>休暇を申請する</template>
        <template #content>
          <form class="form" @submit.prevent="onSubmit">
            <label class="field">
              <span class="field__label">休暇種類</span>
              <Select v-model="form.typeId" :options="typeOptions" option-label="label" option-value="value" />
            </label>

            <label class="field" v-if="selectedType?.supportsHalfDay">
              <span class="field__label">単位</span>
              <Select v-model="form.unit" :options="unitOptions" option-label="label" option-value="value" />
            </label>

            <div class="field-row">
              <label class="field">
                <span class="field__label">{{ form.unit === 'full' ? '開始日' : '対象日' }}</span>
                <input v-model="form.startDate" type="date" required />
              </label>
              <label class="field" v-if="form.unit === 'full'">
                <span class="field__label">終了日</span>
                <input v-model="form.endDate" type="date" required />
              </label>
            </div>

            <label class="field">
              <span class="field__label">理由{{ selectedType?.requiresReason ? '（必須）' : '（任意）' }}</span>
              <Textarea v-model="form.reason" rows="3" :required="selectedType?.requiresReason" />
            </label>

            <p v-if="submitError" class="form__error" role="alert">{{ submitError }}</p>

            <Button type="submit" label="申請する" :loading="leave.submitting" class="form__submit" />
          </form>
        </template>
      </Card>

      <Card class="history-card">
        <template #title>申請履歴</template>
        <template #content>
          <DataTable :value="leave.requests" size="small" :loading="leave.loading">
            <Column field="typeName" header="種類" style="width: 120px" />
            <Column header="期間">
              <template #body="{ data }">
                <span v-if="data.unit === 'full'">
                  {{ dayjs(data.startDate).format('M/D') }}<template v-if="data.startDate !== data.endDate">〜{{ dayjs(data.endDate).format('M/D') }}</template>
                </span>
                <span v-else>{{ dayjs(data.startDate).format('M/D') }}（{{ unitLabel[data.unit as LeaveUnit] }}）</span>
              </template>
            </Column>
            <Column field="days" header="日数" style="width: 64px" bodyStyle="text-align: right" headerStyle="text-align: right">
              <template #body="{ data }">{{ data.days }}日</template>
            </Column>
            <Column field="appliedAt" header="申請日" style="width: 96px">
              <template #body="{ data }">{{ dayjs(data.appliedAt).format('M/D') }}</template>
            </Column>
            <Column header="ステータス" style="width: 110px">
              <template #body="{ data }">
                <Tag :value="statusMeta[data.status as LeaveRequestStatus].label" :severity="statusMeta[data.status as LeaveRequestStatus].severity" />
                <p v-if="data.status === 'rejected' && data.rejectedReason" class="reject-note">{{ data.rejectedReason }}</p>
              </template>
            </Column>
          </DataTable>
        </template>
      </Card>
    </div>
  </section>
</template>

<style scoped>
.page__head { margin-bottom: 28px; }
.eyebrow { margin: 0 0 4px; font-size: 13px; color: var(--muted); font-weight: 600; }
.page__title { margin: 0; font-size: 24px; }

.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
@media (max-width: 960px) { .stats { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 560px) { .stats { grid-template-columns: 1fr; } }
.stat {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-lg);
  padding: 18px; box-shadow: var(--shadow-sm); display: flex; flex-direction: column; gap: 6px;
}
.stat__label { margin: 0; font-size: 12px; color: var(--muted); font-weight: 600; }
.stat__value { margin: 0; font-size: 24px; font-weight: 700; }
.stat__value--sm { font-size: 18px; }
.stat__unit { font-size: 13px; font-weight: 500; color: var(--muted); margin-left: 2px; }
.stat__caption { margin: 0; font-size: 12px; color: var(--muted); }
.stat__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.stat__list li { display: flex; justify-content: space-between; font-size: 13px; }
.bar { height: 6px; background: var(--paper); border-radius: 3px; overflow: hidden; }
.bar__fill { height: 100%; background: var(--accent); border-radius: 3px; transition: width 0.3s; }
.bar__fill--warn { background: var(--warning); }

.row { display: grid; gap: 20px; }
.row--two { grid-template-columns: minmax(280px, 380px) 1fr; }
@media (max-width: 860px) { .row--two { grid-template-columns: 1fr; } }

.form { display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field-row { display: flex; gap: 12px; }
.field-row .field { flex: 1; min-width: 0; }
@media (max-width: 400px) { .field-row { flex-direction: column; } }
.field__label { font-size: 13px; color: var(--muted); font-weight: 600; }
.field input {
  padding: 9px 11px; border: 1px solid var(--line); border-radius: 8px; font: inherit; background: var(--surface);
}
.field input:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.form__error { color: var(--danger); font-size: 13px; margin: 0; }
.form__submit { align-self: flex-start; }

.reject-note { margin: 4px 0 0; font-size: 12px; color: var(--danger); }
</style>
