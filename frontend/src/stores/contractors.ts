import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'
import type { Contractor, ContractorPayload, ContractorWorkRecord, ContractorWorkRecordPayload } from '@/types/domain'

interface ContractorResponse {
  id: number
  name: string
  email: string
  rate_type: Contractor['rateType'] | null
  rate_amount: string | number | null
  closing_day: number
  payment_month_offset: 0 | 1
  payment_day: number
}

interface WorkRecordResponse {
  id: number
  contractor_id: number
  year_month: string
  hours: string | number | null
  days: string | number | null
  fixed_applied: boolean
  note: string
}

function mapContractor(c: ContractorResponse): Contractor {
  return {
    id: String(c.id),
    name: c.name,
    email: c.email,
    rateType: c.rate_type ?? 'hourly',
    rateAmount: Number(c.rate_amount ?? 0),
    closingDay: c.closing_day,
    paymentMonthOffset: c.payment_month_offset,
    paymentDay: c.payment_day,
  }
}

function mapWorkRecord(r: WorkRecordResponse): ContractorWorkRecord {
  return {
    id: String(r.id),
    contractorId: String(r.contractor_id),
    yearMonth: r.year_month,
    hours: r.hours === null ? null : Number(r.hours),
    days: r.days === null ? null : Number(r.days),
    fixedApplied: r.fixed_applied,
    note: r.note,
    enteredAt: new Date().toISOString(),
  }
}

export const useContractorsStore = defineStore('contractors', () => {
  const contractors = ref<Contractor[]>([])
  const workRecords = ref<ContractorWorkRecord[]>([])
  const loading = ref(false)
  const saving = ref(false)

  async function fetchContractors(): Promise<void> {
    loading.value = true
    try {
      const [contractorsRes, recordsRes] = await Promise.all([
        api.get<ContractorResponse[]>('/admin/contractors/'),
        api.get<WorkRecordResponse[]>('/admin/contractors/work-records'),
      ])
      contractors.value = contractorsRes.map(mapContractor)
      workRecords.value = recordsRes.map(mapWorkRecord)
    } finally {
      loading.value = false
    }
  }

  async function addContractor(payload: ContractorPayload): Promise<void> {
    saving.value = true
    try {
      const created = await api.post<ContractorResponse>('/admin/contractors/', {
        name: payload.name,
        email: payload.email,
        rate_type: payload.rateType,
        rate_amount: payload.rateAmount,
        closing_day: payload.closingDay,
        payment_month_offset: payload.paymentMonthOffset,
        payment_day: payload.paymentDay,
      })
      contractors.value.push(mapContractor(created))
    } finally {
      saving.value = false
    }
  }

  function recordFor(contractorId: string, yearMonth: string): ContractorWorkRecord | undefined {
    return workRecords.value.find((r) => r.contractorId === contractorId && r.yearMonth === yearMonth)
  }

  async function saveWorkRecord(payload: ContractorWorkRecordPayload): Promise<void> {
    saving.value = true
    try {
      const saved = await api.post<WorkRecordResponse>('/admin/contractors/work-records', {
        contractor_id: Number(payload.contractorId),
        year_month: payload.yearMonth,
        hours: payload.hours,
        days: payload.days,
        fixed_applied: payload.fixedApplied,
        note: payload.note,
      })
      const mapped = mapWorkRecord(saved)
      const index = workRecords.value.findIndex((r) => r.id === mapped.id)
      if (index >= 0) {
        workRecords.value[index] = mapped
      } else {
        workRecords.value.push(mapped)
      }
    } finally {
      saving.value = false
    }
  }

  return { contractors, workRecords, loading, saving, fetchContractors, addContractor, recordFor, saveWorkRecord }
})
