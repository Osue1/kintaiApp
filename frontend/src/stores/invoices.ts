import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, newIdempotencyKey } from '@/api/client'
import type { Invoice, WithholdingStatement } from '@/types/domain'

interface InvoiceResponse {
  id: number
  contractor_id: number
  contractor_name: string
  invoice_no: string
  period_start: string
  period_end: string
  quantity_label: string
  subtotal: string | number
  tax_amount: string | number
  withholding_amount: string | number
  payable_amount: string | number
  status: Invoice['status']
  issued_on: string
  confirm_deadline: string | null
  confirmed_at: string | null
  confirm_method: Invoice['confirmMethod']
}

interface GenerateResponse {
  created: InvoiceResponse[]
  created_count: number
  skipped_no_record_count: number
  already_exists_count: number
}

interface WithholdingStatementResponse {
  id: number
  contractor_id: number
  contractor_name: string
  year: number
  total_payment: string | number
  total_withholding: string | number
}

function mapStatement(r: WithholdingStatementResponse): WithholdingStatement {
  return {
    id: String(r.id),
    contractorId: String(r.contractor_id),
    contractorName: r.contractor_name,
    year: r.year,
    totalPayment: Number(r.total_payment),
    totalWithholding: Number(r.total_withholding),
  }
}

function mapInvoice(r: InvoiceResponse): Invoice {
  return {
    id: String(r.id),
    invoiceNo: r.invoice_no,
    contractorId: String(r.contractor_id),
    contractorName: r.contractor_name,
    yearMonth: r.period_end.slice(0, 7),
    quantityLabel: r.quantity_label,
    subtotal: Number(r.subtotal),
    tax: Number(r.tax_amount),
    withholding: Number(r.withholding_amount),
    payable: Number(r.payable_amount),
    status: r.status,
    issuedAt: r.issued_on,
    confirmDeadline: r.confirm_deadline,
    confirmedAt: r.confirmed_at,
    confirmMethod: r.confirm_method,
  }
}

export const useInvoicesStore = defineStore('invoices', () => {
  const invoices = ref<Invoice[]>([])
  const generating = ref(false)
  const sendingId = ref<string | null>(null)
  const voidingId = ref<string | null>(null)
  const confirmingId = ref<string | null>(null)
  const issuingStatements = ref(false)
  const statements = ref<WithholdingStatement[]>([])

  async function fetchInvoices(yearMonth?: string): Promise<void> {
    const path = yearMonth ? `/admin/invoices/?year_month=${yearMonth}` : '/admin/invoices/'
    const data = await api.get<InvoiceResponse[]>(path)
    invoices.value = data.map(mapInvoice)
  }

  async function generateForMonth(yearMonth: string): Promise<number> {
    generating.value = true
    try {
      // 一括生成ボタンの連打やネットワーク再送で同じ月を二重生成しないよう、
      // このクリック1回分のキーをサーバー側の二重実行防止機構に渡す。
      const result = await api.post<GenerateResponse>(
        '/admin/invoices/generate',
        { year_month: yearMonth },
        { idempotencyKey: newIdempotencyKey() },
      )
      for (const created of result.created) {
        invoices.value.unshift(mapInvoice(created))
      }
      return result.created_count
    } finally {
      generating.value = false
    }
  }

  async function sendInvoice(id: string): Promise<void> {
    sendingId.value = id
    try {
      const updated = await api.post<InvoiceResponse>(`/admin/invoices/${id}/send`)
      const mapped = mapInvoice(updated)
      const index = invoices.value.findIndex((i) => i.id === id)
      if (index >= 0) invoices.value[index] = mapped
    } finally {
      sendingId.value = null
    }
  }

  async function voidInvoice(id: string): Promise<Invoice> {
    voidingId.value = id
    try {
      const reversal = await api.post<InvoiceResponse>(`/admin/invoices/${id}/void`)
      const original = invoices.value.find((i) => i.id === id)
      if (original) original.status = 'void'
      const mapped = mapInvoice(reversal)
      invoices.value.unshift(mapped)
      return mapped
    } finally {
      voidingId.value = null
    }
  }

  async function confirmInvoice(id: string): Promise<void> {
    confirmingId.value = id
    try {
      const updated = await api.post<InvoiceResponse>(`/admin/invoices/${id}/confirm`)
      const mapped = mapInvoice(updated)
      const index = invoices.value.findIndex((i) => i.id === id)
      if (index >= 0) invoices.value[index] = mapped
    } finally {
      confirmingId.value = null
    }
  }

  async function fetchStatements(year: number): Promise<void> {
    const data = await api.get<WithholdingStatementResponse[]>(`/admin/invoices/withholding-statements?year=${year}`)
    statements.value = data.map(mapStatement)
  }

  async function issueAnnualStatements(year: number): Promise<number> {
    issuingStatements.value = true
    try {
      // 出力結果をそのまま一覧に反映する（以前は件数だけ返して結果を捨てており、
      // 出力した支払調書をこの画面から確認・ダウンロードする手段が無かった）。
      const data = await api.post<WithholdingStatementResponse[]>('/admin/invoices/withholding-statements', { year })
      statements.value = data.map(mapStatement)
      return data.length
    } finally {
      issuingStatements.value = false
    }
  }

  return {
    invoices,
    generating,
    sendingId,
    voidingId,
    confirmingId,
    issuingStatements,
    statements,
    fetchInvoices,
    generateForMonth,
    sendInvoice,
    voidInvoice,
    confirmInvoice,
    fetchStatements,
    issueAnnualStatements,
  }
})
