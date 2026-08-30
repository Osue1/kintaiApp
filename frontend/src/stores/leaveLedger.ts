import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'
import type { LeaveLedger } from '@/types/domain'

interface LeaveLedgerResponse {
  employee: { id: number; name: string; hire_date: string | null }
  grants: {
    granted_on: string
    days: number
    expires_on: string
    consumed: number
    remaining: number
    is_expired: boolean
    consumptions: { date_label: string; days: number; leave_type_name: string }[]
  }[]
}

function mapLedger(r: LeaveLedgerResponse): LeaveLedger {
  return {
    employee: { id: String(r.employee.id), name: r.employee.name, hireDate: r.employee.hire_date },
    grants: r.grants.map((g) => ({
      grantedOn: g.granted_on,
      days: g.days,
      expiresOn: g.expires_on,
      consumed: g.consumed,
      remaining: g.remaining,
      isExpired: g.is_expired,
      consumptions: g.consumptions.map((c) => ({
        dateLabel: c.date_label,
        days: c.days,
        leaveTypeName: c.leave_type_name,
      })),
    })),
  }
}

export const useLeaveLedgerStore = defineStore('leaveLedger', () => {
  const ledger = ref<LeaveLedger | null>(null)
  const loading = ref(false)

  async function fetchLedger(userId: string): Promise<void> {
    loading.value = true
    try {
      const data = await api.get<LeaveLedgerResponse>(`/leave/admin/ledger?user_id=${userId}`)
      ledger.value = mapLedger(data)
    } finally {
      loading.value = false
    }
  }

  return { ledger, loading, fetchLedger }
})
