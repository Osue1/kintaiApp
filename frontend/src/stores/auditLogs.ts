import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'
import type { AuditLogEntry, AuditLogFilter } from '@/types/domain'

interface AuditLogResponse {
  id: number
  actor_name: string | null
  action: string
  target_type: string
  target_id: number | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  ip: string | null
  user_agent: string
  created_at: string
}

interface AuditLogListResponse {
  results: AuditLogResponse[]
  total_count: number
  truncated: boolean
}

function mapEntry(r: AuditLogResponse): AuditLogEntry {
  return {
    id: r.id,
    actorName: r.actor_name,
    action: r.action,
    targetType: r.target_type,
    targetId: r.target_id,
    before: r.before,
    after: r.after,
    ip: r.ip,
    userAgent: r.user_agent,
    createdAt: r.created_at,
  }
}

export const useAuditLogsStore = defineStore('auditLogs', () => {
  const entries = ref<AuditLogEntry[]>([])
  const totalCount = ref(0)
  const truncated = ref(false)
  const loading = ref(false)

  async function fetchAuditLogs(filter: AuditLogFilter = {}): Promise<void> {
    loading.value = true
    try {
      const params = new URLSearchParams()
      if (filter.action) params.set('action', filter.action)
      if (filter.targetType) params.set('target_type', filter.targetType)
      if (filter.dateFrom) params.set('date_from', filter.dateFrom)
      if (filter.dateTo) params.set('date_to', filter.dateTo)
      const query = params.toString()
      const data = await api.get<AuditLogListResponse>(`/admin/audit-logs${query ? `?${query}` : ''}`)
      entries.value = data.results.map(mapEntry)
      totalCount.value = data.total_count
      truncated.value = data.truncated
    } finally {
      loading.value = false
    }
  }

  return { entries, totalCount, truncated, loading, fetchAuditLogs }
})
