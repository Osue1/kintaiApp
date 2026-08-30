import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'
import type { LeaveBalance, LeaveRequest, LeaveRequestPayload, LeaveType } from '@/types/domain'

interface LeaveTypeResponse {
  id: number
  name: string
  is_paid: boolean
  supports_half_day: boolean
  requires_reason: boolean
}

interface LeaveRequestResponse {
  id: number
  type_id: number
  type_name: string
  start_date: string
  end_date: string
  unit: LeaveRequest['unit']
  days: string
  reason: string
  status: LeaveRequest['status']
  rejected_reason: string
  created_at: string
}

interface LeaveBalanceResponse {
  paid_total: number
  paid_used: number
  paid_remaining: number
  carry_over: number
  next_grant: { date: string; days: number }
  mandatory_five_days: { used: number; required: number; deadline: string }
  others: { type_id: string; type_name: string; remaining: number | null }[]
}

function mapType(t: LeaveTypeResponse): LeaveType {
  return {
    id: String(t.id),
    name: t.name,
    paid: t.is_paid,
    supportsHalfDay: t.supports_half_day,
    requiresReason: t.requires_reason,
  }
}

function mapRequest(r: LeaveRequestResponse): LeaveRequest {
  return {
    id: String(r.id),
    typeId: String(r.type_id),
    typeName: r.type_name,
    startDate: r.start_date,
    endDate: r.end_date,
    unit: r.unit,
    days: Number(r.days),
    reason: r.reason,
    status: r.status,
    appliedAt: r.created_at,
    rejectedReason: r.rejected_reason || undefined,
  }
}

export const useLeaveStore = defineStore('leave', () => {
  const leaveTypes = ref<LeaveType[]>([])
  const balance = ref<LeaveBalance | null>(null)
  const requests = ref<LeaveRequest[]>([])
  const loading = ref(false)
  const submitting = ref(false)

  async function fetchLeaveData(): Promise<void> {
    loading.value = true
    try {
      const [types, balanceRes, requestsRes] = await Promise.all([
        api.get<LeaveTypeResponse[]>('/leave/types'),
        api.get<LeaveBalanceResponse>('/leave/balance'),
        api.get<LeaveRequestResponse[]>('/leave/requests'),
      ])
      leaveTypes.value = types.map(mapType)
      balance.value = {
        paidTotal: balanceRes.paid_total,
        paidUsed: balanceRes.paid_used,
        paidRemaining: balanceRes.paid_remaining,
        carryOver: balanceRes.carry_over,
        nextGrant: balanceRes.next_grant,
        mandatoryFiveDays: balanceRes.mandatory_five_days,
        others: balanceRes.others.map((o) => ({ typeId: o.type_id, typeName: o.type_name, remaining: o.remaining })),
      }
      requests.value = requestsRes.map(mapRequest)
    } finally {
      loading.value = false
    }
  }

  async function submitRequest(payload: LeaveRequestPayload): Promise<void> {
    submitting.value = true
    try {
      const created = await api.post<LeaveRequestResponse>('/leave/requests', {
        type_id: Number(payload.typeId),
        start_date: payload.startDate,
        end_date: payload.endDate,
        unit: payload.unit,
        reason: payload.reason,
      })
      requests.value.unshift(mapRequest(created))
    } finally {
      submitting.value = false
    }
  }

  return { leaveTypes, balance, requests, loading, submitting, fetchLeaveData, submitRequest }
})
