<script setup lang="ts">
import dayjs from 'dayjs'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import { computed, onMounted, ref, watch } from 'vue'
import { ApiRequestError, API_BASE } from '@/api/client'
import { useInvoicesStore } from '@/stores/invoices'
import type { Invoice } from '@/types/domain'

const invoices = useInvoicesStore()
const toast = useToast()

const targetMonth = ref(dayjs().subtract(1, 'month').format('YYYY-MM'))
const targetYear = computed(() => Number(targetMonth.value.slice(0, 4)))

onMounted(() => {
  invoices.fetchInvoices(targetMonth.value)
  invoices.fetchStatements(targetYear.value)
})
watch(targetMonth, (ym) => {
  invoices.fetchInvoices(ym)
})
watch(targetYear, (year) => {
  invoices.fetchStatements(year)
})

function errorDetail(e: unknown): string {
  return e instanceof ApiRequestError ? e.message : '通信に失敗しました。時間をおいてお試しください。'
}

async function onGenerate() {
  try {
    const created = await invoices.generateForMonth(targetMonth.value)
    if (created > 0) {
      toast.add({ severity: 'success', summary: `請求書を${created}件生成しました`, life: 2500 })
    } else {
      toast.add({ severity: 'info', summary: '対象月分の稼働実績がある未生成の外注先はありません', life: 3000 })
    }
  } catch (e) {
    toast.add({ severity: 'error', summary: '請求書の生成に失敗しました', detail: errorDetail(e), life: 5000 })
  }
}

async function onSend(id: string) {
  try {
    await invoices.sendInvoice(id)
    toast.add({ severity: 'success', summary: '請求書PDFを外注先へメール送信しました', life: 2500 })
  } catch (e) {
    toast.add({ severity: 'error', summary: '請求書の送信に失敗しました', detail: errorDetail(e), life: 5000 })
  }
}

async function onVoid(id: string, invoiceNo: string) {
  if (!window.confirm(`請求書「${invoiceNo}」を取消しますか？金額を反転した赤伝が発行され、この請求書は取消状態になります。`)) return
  try {
    const reversal = await invoices.voidInvoice(id)
    toast.add({ severity: 'success', summary: `請求書を取消しました（赤伝: ${reversal.invoiceNo}）`, life: 3500 })
  } catch (e) {
    toast.add({ severity: 'error', summary: '請求書の取消に失敗しました', detail: errorDetail(e), life: 5000 })
  }
}

async function onConfirm(id: string) {
  try {
    await invoices.confirmInvoice(id)
    toast.add({ severity: 'success', summary: '仕入明細書の確認を記録しました', life: 2500 })
  } catch (e) {
    toast.add({ severity: 'error', summary: '確認の記録に失敗しました', detail: errorDetail(e), life: 5000 })
  }
}

function confirmationLabel(inv: Invoice): string {
  if (inv.status === 'void') return '—'
  if (inv.confirmedAt) return inv.confirmMethod === 'manual' ? '確認済み' : 'みなし確認済み'
  if (inv.confirmDeadline) return `確認待ち（${dayjs(inv.confirmDeadline).format('M/D')}まで）`
  return '未送付'
}

function onDownload(id: string) {
  window.open(`${API_BASE}/admin/invoices/${id}/pdf`, '_blank')
}

function onDownloadStatement(id: string) {
  window.open(`${API_BASE}/admin/invoices/withholding-statements/${id}/pdf`, '_blank')
}

async function onIssueAnnual() {
  try {
    const count = await invoices.issueAnnualStatements(targetYear.value)
    if (count > 0) {
      toast.add({ severity: 'success', summary: `${targetYear.value}年分の支払調書を${count}件出力しました`, life: 3000 })
    } else {
      toast.add({ severity: 'info', summary: `${targetYear.value}年分は年間支払額が5万円を超える外注先がありません`, life: 3500 })
    }
  } catch (e) {
    toast.add({ severity: 'error', summary: '支払調書の出力に失敗しました', detail: errorDetail(e), life: 5000 })
  }
}

const monthInvoices = computed(() => invoices.invoices.filter((i) => i.yearMonth === targetMonth.value))

function yen(n: number): string {
  return `¥${n.toLocaleString()}`
}

const statusMeta: Record<Invoice['status'], { label: string; severity: 'success' | 'secondary' | 'info' | 'danger' }> = {
  draft: { label: '未送信', severity: 'secondary' },
  issued: { label: '発行確定', severity: 'info' },
  sent: { label: '送信済み', severity: 'success' },
  void: { label: '取消（赤伝）', severity: 'danger' },
}
</script>

<template>
  <section class="page">
    <header class="page__head">
      <p class="eyebrow">管理者</p>
      <h1 class="page__title">請求書・支払調書発行</h1>
    </header>

    <Card class="controls">
      <template #content>
        <div class="controls__row">
          <label class="field">
            <span class="field__label">対象月（締め日到来分）</span>
            <input v-model="targetMonth" type="month" />
          </label>
          <Button label="締め日到来分を一括生成" icon="pi pi-file-plus" :loading="invoices.generating" @click="onGenerate" />
          <Button label="年間支払調書を一括出力" icon="pi pi-download" severity="secondary" outlined @click="onIssueAnnual" />
        </div>
        <p class="note">
          インボイス制度対応（登録番号・税率区分ごとの消費税額）、報酬・料金にかかる源泉徴収税額の自動計算に対応します。
          源泉徴収額はデモ用の概算値です。
        </p>
      </template>
    </Card>

    <Card class="table-card">
      <template #title>{{ dayjs(targetMonth).format('YYYY年M月') }}分の請求書</template>
      <template #content>
        <DataTable :value="monthInvoices" size="small">
          <Column field="invoiceNo" header="請求書番号" style="width: 150px" />
          <Column field="contractorName" header="外注先" style="width: 160px" />
          <Column field="quantityLabel" header="内訳" style="width: 150px" />
          <Column header="小計" style="width: 100px" bodyStyle="text-align: right" headerStyle="text-align: right">
            <template #body="{ data }">{{ yen(data.subtotal) }}</template>
          </Column>
          <Column header="消費税" style="width: 90px" bodyStyle="text-align: right" headerStyle="text-align: right">
            <template #body="{ data }">{{ yen(data.tax) }}</template>
          </Column>
          <Column header="源泉徴収" style="width: 100px" bodyStyle="text-align: right" headerStyle="text-align: right">
            <template #body="{ data }">−{{ yen(data.withholding) }}</template>
          </Column>
          <Column header="振込金額" style="width: 110px" bodyStyle="text-align: right" headerStyle="text-align: right">
            <template #body="{ data }"><strong>{{ yen(data.payable) }}</strong></template>
          </Column>
          <Column header="ステータス" style="width: 110px">
            <template #body="{ data }">
              <Tag :value="statusMeta[data.status as Invoice['status']].label" :severity="statusMeta[data.status as Invoice['status']].severity" />
            </template>
          </Column>
          <Column header="仕入明細書の確認" style="width: 160px">
            <template #body="{ data }">
              <span class="confirm-label" :class="{ 'confirm-label--done': data.confirmedAt }">{{ confirmationLabel(data) }}</span>
            </template>
          </Column>
          <Column header="操作" style="width: 280px">
            <template #body="{ data }">
              <div class="actions" v-if="data.status !== 'void'">
                <Button label="PDF" icon="pi pi-download" size="small" severity="secondary" text @click="onDownload(data.id)" />
                <Button
                  v-if="data.status !== 'sent'"
                  label="送信"
                  icon="pi pi-send"
                  size="small"
                  :loading="invoices.sendingId === data.id"
                  @click="onSend(data.id)"
                />
                <Button
                  v-if="data.status === 'sent' && !data.confirmedAt"
                  label="確認済みにする"
                  icon="pi pi-check"
                  size="small"
                  severity="secondary"
                  text
                  :loading="invoices.confirmingId === data.id"
                  @click="onConfirm(data.id)"
                />
                <Button
                  label="取消"
                  icon="pi pi-times-circle"
                  size="small"
                  severity="danger"
                  text
                  :loading="invoices.voidingId === data.id"
                  @click="onVoid(data.id, data.invoiceNo)"
                />
              </div>
            </template>
          </Column>
          <template #empty>この月の請求書はまだ生成されていません。「締め日到来分を一括生成」から作成してください。</template>
        </DataTable>
      </template>
    </Card>

    <Card class="table-card">
      <template #title>{{ targetYear }}年分の支払調書</template>
      <template #content>
        <DataTable :value="invoices.statements" size="small">
          <Column field="contractorName" header="外注先" style="width: 200px" />
          <Column header="年間支払金額" style="width: 140px" bodyStyle="text-align: right" headerStyle="text-align: right">
            <template #body="{ data }">{{ yen(data.totalPayment) }}</template>
          </Column>
          <Column header="源泉徴収税額合計" style="width: 140px" bodyStyle="text-align: right" headerStyle="text-align: right">
            <template #body="{ data }">{{ yen(data.totalWithholding) }}</template>
          </Column>
          <Column header="操作" style="width: 120px">
            <template #body="{ data }">
              <Button label="PDF" icon="pi pi-download" size="small" severity="secondary" text @click="onDownloadStatement(data.id)" />
            </template>
          </Column>
          <template #empty>この年の支払調書はまだ出力されていません。「年間支払調書を一括出力」から作成してください。</template>
        </DataTable>
      </template>
    </Card>
  </section>
</template>

<style scoped>
.page__head { margin-bottom: 24px; }
.eyebrow { margin: 0 0 4px; font-size: 13px; color: var(--muted); font-weight: 600; }
.page__title { margin: 0; font-size: 24px; }

.controls { margin-bottom: 20px; }
.controls__row { display: flex; align-items: flex-end; gap: 16px; flex-wrap: wrap; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field__label { font-size: 13px; color: var(--muted); font-weight: 600; }
.field input[type='month'] {
  padding: 9px 11px; border: 1px solid var(--line); border-radius: 8px; font: inherit; background: var(--surface);
}
.note { margin: 12px 0 0; font-size: 12px; color: var(--muted); }

.actions { display: flex; gap: 4px; flex-wrap: wrap; }
.confirm-label { font-size: 13px; color: var(--muted); }
.confirm-label--done { color: var(--accent-dark); font-weight: 600; }
</style>
