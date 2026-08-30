import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'
import type { OvertimeAlertEntry, PaidLeaveAlertEntry } from '@/types/domain'

interface AlertsResponse {
  paid_leave_alerts: {
    employee_id: string
    employee_name: string
    granted_date: string
    used: number
    required: number
    deadline: string
  }[]
  overtime_alerts: {
    employee_id: string
    employee_name: string
    month: string
    overtime_hours: number
    limit_hours: number
    severity: OvertimeAlertEntry['severity']
    reasons: { kind: string; label: string; severity: OvertimeAlertEntry['severity'] }[]
  }[]
}

export const useAlertsStore = defineStore('alerts', () => {
  const paidLeaveAlerts = ref<PaidLeaveAlertEntry[]>([])
  const overtimeAlerts = ref<OvertimeAlertEntry[]>([])
  const loading = ref(false)

  async function fetchAlerts(): Promise<void> {
    loading.value = true
    try {
      const data = await api.get<AlertsResponse>('/admin/alerts')
      paidLeaveAlerts.value = data.paid_leave_alerts.map((a) => ({
        employeeId: a.employee_id,
        employeeName: a.employee_name,
        grantedDate: a.granted_date,
        used: a.used,
        required: a.required,
        deadline: a.deadline,
      }))
      overtimeAlerts.value = data.overtime_alerts.map((a) => ({
        employeeId: a.employee_id,
        employeeName: a.employee_name,
        month: a.month,
        overtimeHours: a.overtime_hours,
        limitHours: a.limit_hours,
        severity: a.severity,
        reasons: a.reasons.map((r) => ({ kind: r.kind, label: r.label, severity: r.severity })),
      }))
    } finally {
      loading.value = false
    }
  }

  return { paidLeaveAlerts, overtimeAlerts, loading, fetchAlerts }
})
