import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/api/client'
import type { ApprovalItem, ApprovalStatus, ApprovalType } from '@/types/domain'

interface ApprovalItemResponse {
  id: string
  employee_name: string
  type: ApprovalType
  summary: string
  detail: string
  requested_at: string
  status: ApprovalStatus
  rejected_reason: string
}

const APPROVE_PATH: Record<ApprovalType, (numId: string) => string> = {
  correction: (id) => `/attendance/admin/corrections/${id}/approve`,
  monthly: (id) => `/attendance/admin/monthly/${id}/approve`,
  leave: (id) => `/leave/admin/requests/${id}/approve`,
}
const REJECT_PATH: Record<ApprovalType, (numId: string) => string> = {
  correction: (id) => `/attendance/admin/corrections/${id}/reject`,
  monthly: (id) => `/attendance/admin/monthly/${id}/reject`,
  leave: (id) => `/leave/admin/requests/${id}/reject`,
}

/** id は "correction-5" のように種別を含む複合キー。数値部分だけ取り出す。 */
function numericId(id: string): string {
  const parts = id.split('-')
  return parts[parts.length - 1] ?? id
}

function mapItem(r: ApprovalItemResponse): ApprovalItem {
  return {
    id: r.id,
    employeeName: r.employee_name,
    type: r.type,
    summary: r.summary,
    detail: r.detail,
    requestedAt: r.requested_at,
    status: r.status,
    rejectedReason: r.rejected_reason || undefined,
  }
}

export const useApprovalsStore = defineStore('approvals', () => {
  const items = ref<ApprovalItem[]>([])
  const loading = ref(false)

  const pendingCount = computed(() => items.value.filter((i) => i.status === 'pending').length)
  const pendingByType = (type: ApprovalType) =>
    items.value.filter((i) => i.type === type && i.status === 'pending').length

  async function fetchApprovals(): Promise<void> {
    loading.value = true
    try {
      const data = await api.get<ApprovalItemResponse[]>('/admin/approvals')
      items.value = data.map(mapItem)
    } finally {
      loading.value = false
    }
  }

  async function approve(id: string): Promise<void> {
    const item = items.value.find((i) => i.id === id)
    if (!item) return
    await api.post(APPROVE_PATH[item.type](numericId(id)))
    item.status = 'approved'
  }

  async function reject(id: string, reason: string): Promise<void> {
    const item = items.value.find((i) => i.id === id)
    if (!item) return
    await api.post(REJECT_PATH[item.type](numericId(id)), { reason })
    item.status = 'rejected'
    item.rejectedReason = reason
  }

  return { items, loading, pendingCount, pendingByType, fetchApprovals, approve, reject }
})
