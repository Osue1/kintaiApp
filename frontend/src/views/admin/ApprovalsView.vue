<script setup lang="ts">
import dayjs from 'dayjs'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import { useToast } from 'primevue/usetoast'
import { computed, onMounted, ref } from 'vue'
import { ApiRequestError } from '@/api/client'
import { useApprovalsStore } from '@/stores/approvals'
import type { ApprovalItem, ApprovalStatus, ApprovalType } from '@/types/domain'

const approvals = useApprovalsStore()
const toast = useToast()

onMounted(() => {
  approvals.fetchApprovals()
})

const typeMeta: Record<ApprovalType, { label: string; icon: string }> = {
  leave: { label: '休暇申請', icon: 'pi-calendar' },
  correction: { label: '打刻修正', icon: 'pi-clock' },
  monthly: { label: '月次確定', icon: 'pi-file-check' },
}
const statusMeta: Record<ApprovalStatus, { label: string; severity: 'warn' | 'success' | 'danger' }> = {
  pending: { label: '承認待ち', severity: 'warn' },
  approved: { label: '承認済み', severity: 'success' },
  rejected: { label: '差し戻し', severity: 'danger' },
}

const typeFilter = ref<ApprovalType | 'all'>('all')
const showResolved = ref(false)
const search = ref('')

const filtered = computed(() =>
  approvals.items.filter((i) => {
    if (typeFilter.value !== 'all' && i.type !== typeFilter.value) return false
    if (!showResolved.value && i.status !== 'pending') return false
    const q = search.value.trim().toLowerCase()
    if (q && !i.employeeName.toLowerCase().includes(q) && !i.summary.toLowerCase().includes(q)) return false
    return true
  }),
)

const processingId = ref<string | null>(null)

// 承認・差し戻しの二重クリックや、2人の管理者が同時に処理した場合に
// サーバー側が409 already_processedを返すことがある（apps/leave/views.py の
// select_for_update による排他制御）。ここで捕捉せず放置すると、ボタンは
// 押せる状態に戻るのに何が起きたか画面に一切表示されず、ユーザーが
// 何度もクリックし続けてしまうため、必ずトーストで結果を伝える。
function approvalErrorDetail(e: unknown): string {
  if (e instanceof ApiRequestError && e.code === 'already_processed') return e.message
  if (e instanceof ApiRequestError && e.code === 'insufficient_balance') return e.message
  return '通信に失敗しました。時間をおいてお試しください。'
}

async function onApprove(item: ApprovalItem) {
  processingId.value = item.id
  try {
    await approvals.approve(item.id)
    toast.add({ severity: 'success', summary: `${item.employeeName}さんの申請を承認しました`, life: 2500 })
  } catch (e) {
    toast.add({ severity: 'error', summary: '承認に失敗しました', detail: approvalErrorDetail(e), life: 5000 })
    await approvals.fetchApprovals()
  } finally {
    processingId.value = null
  }
}

const rejectTarget = ref<ApprovalItem | null>(null)
const rejectReason = ref('')
const rejecting = ref(false)

function openReject(item: ApprovalItem) {
  rejectTarget.value = item
  rejectReason.value = ''
}

async function onConfirmReject() {
  if (!rejectTarget.value || !rejectReason.value.trim()) return
  rejecting.value = true
  try {
    await approvals.reject(rejectTarget.value.id, rejectReason.value.trim())
    toast.add({ severity: 'info', summary: `${rejectTarget.value.employeeName}さんの申請を差し戻しました`, life: 2500 })
    rejectTarget.value = null
  } catch (e) {
    toast.add({ severity: 'error', summary: '差し戻しに失敗しました', detail: approvalErrorDetail(e), life: 5000 })
    await approvals.fetchApprovals()
  } finally {
    rejecting.value = false
  }
}
</script>

<template>
  <section class="page">
    <header class="page__head">
      <p class="eyebrow">管理者</p>
      <h1 class="page__title">勤怠承認</h1>
    </header>

    <div class="stats">
      <div class="stat">
        <p class="stat__label">承認待ち（全体）</p>
        <p class="stat__value">{{ approvals.pendingCount }}<span class="stat__unit">件</span></p>
      </div>
      <div class="stat">
        <p class="stat__label">休暇申請</p>
        <p class="stat__value">{{ approvals.pendingByType('leave') }}<span class="stat__unit">件</span></p>
      </div>
      <div class="stat">
        <p class="stat__label">打刻修正</p>
        <p class="stat__value">{{ approvals.pendingByType('correction') }}<span class="stat__unit">件</span></p>
      </div>
      <div class="stat">
        <p class="stat__label">月次確定</p>
        <p class="stat__value">{{ approvals.pendingByType('monthly') }}<span class="stat__unit">件</span></p>
      </div>
    </div>

    <Card>
      <template #content>
        <div class="filters">
          <div class="filters__types">
            <button
              v-for="opt in [{ value: 'all', label: 'すべて' }, { value: 'leave', label: '休暇申請' }, { value: 'correction', label: '打刻修正' }, { value: 'monthly', label: '月次確定' }]"
              :key="opt.value"
              type="button"
              class="chip"
              :class="{ 'chip--active': typeFilter === opt.value }"
              @click="typeFilter = opt.value as ApprovalType | 'all'"
            >
              {{ opt.label }}
            </button>
          </div>
          <IconField class="filters__search">
            <InputIcon class="pi pi-search" />
            <InputText v-model="search" placeholder="従業員名・内容で検索" size="small" />
          </IconField>
          <label class="toggle">
            <input v-model="showResolved" type="checkbox" />
            処理済みも表示
          </label>
        </div>

        <DataTable :value="filtered" size="small" :loading="approvals.loading" paginator :rows="10" sort-field="requestedAt" :sort-order="-1">
          <Column field="employeeName" header="従業員" style="width: 120px" sortable />
          <Column header="種別" style="width: 110px">
            <template #body="{ data }">
              <span class="type-badge"><i class="pi" :class="typeMeta[data.type as ApprovalType].icon" /> {{ typeMeta[data.type as ApprovalType].label }}</span>
            </template>
          </Column>
          <Column header="内容">
            <template #body="{ data }">
              <p class="summary">{{ data.summary }}</p>
              <p v-if="data.detail" class="detail">{{ data.detail }}</p>
              <p v-if="data.status === 'rejected' && data.rejectedReason" class="reject-note">差し戻し理由: {{ data.rejectedReason }}</p>
            </template>
          </Column>
          <Column field="requestedAt" header="申請日時" style="width: 100px" sortable>
            <template #body="{ data }">{{ dayjs(data.requestedAt).format('M/D HH:mm') }}</template>
          </Column>
          <Column header="ステータス" style="width: 100px">
            <template #body="{ data }">
              <Tag :value="statusMeta[data.status as ApprovalStatus].label" :severity="statusMeta[data.status as ApprovalStatus].severity" />
            </template>
          </Column>
          <Column header="操作" style="width: 180px">
            <template #body="{ data }">
              <div v-if="data.status === 'pending'" class="actions">
                <Button label="承認" size="small" :loading="processingId === data.id" @click="onApprove(data)" />
                <Button label="差し戻し" size="small" severity="secondary" text @click="openReject(data)" />
              </div>
            </template>
          </Column>
          <template #empty>該当する申請はありません。</template>
        </DataTable>
      </template>
    </Card>

    <Dialog :visible="!!rejectTarget" header="差し戻し理由を入力" modal :style="{ width: '420px' }" @update:visible="(v) => { if (!v) rejectTarget = null }">
      <form class="reject-form" @submit.prevent="onConfirmReject">
        <p class="reject-form__target">{{ rejectTarget?.employeeName }}さん ・ {{ rejectTarget?.summary }}</p>
        <Textarea v-model="rejectReason" rows="3" placeholder="差し戻す理由を入力してください" required autofocus />
        <div class="reject-form__actions">
          <Button type="button" label="キャンセル" severity="secondary" text @click="rejectTarget = null" />
          <Button type="submit" label="差し戻す" severity="danger" :loading="rejecting" :disabled="!rejectReason.trim()" />
        </div>
      </form>
    </Dialog>
  </section>
</template>

<style scoped>
.page__head { margin-bottom: 28px; }
.eyebrow { margin: 0 0 4px; font-size: 13px; color: var(--muted); font-weight: 600; }
.page__title { margin: 0; font-size: 24px; }

.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }
@media (max-width: 760px) { .stats { grid-template-columns: repeat(2, 1fr); } }
.stat {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-lg);
  padding: 18px; box-shadow: var(--shadow-sm);
}
.stat__label { margin: 0 0 6px; font-size: 12px; color: var(--muted); font-weight: 600; }
.stat__value { margin: 0; font-size: 24px; font-weight: 700; }
.stat__unit { font-size: 13px; font-weight: 500; color: var(--muted); margin-left: 2px; }

.filters { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; }
.filters__types { display: flex; gap: 8px; flex-wrap: wrap; }
.filters__search { width: 220px; max-width: 100%; }
.chip {
  border: 1px solid var(--line); background: var(--surface); color: var(--muted);
  border-radius: 999px; padding: 6px 14px; font: inherit; font-size: 13px; cursor: pointer;
}
.chip--active { background: var(--accent-soft); border-color: var(--accent); color: var(--accent-dark); font-weight: 600; }
.toggle { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--muted); cursor: pointer; }

.type-badge { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--muted); }
.summary { margin: 0; font-size: 13.5px; font-weight: 600; }
.detail { margin: 2px 0 0; font-size: 12.5px; color: var(--muted); }
.reject-note { margin: 4px 0 0; font-size: 12px; color: var(--danger); }
.actions { display: flex; gap: 4px; }

.reject-form { display: flex; flex-direction: column; gap: 14px; }
.reject-form__target { margin: 0; font-size: 13px; color: var(--muted); }
.reject-form__actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
