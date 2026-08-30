import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api, newIdempotencyKey } from '@/api/client'
import type {
  AppNotification,
  CorrectionRequestPayload,
  DailyRecord,
  MonthlySummary,
  TodayPunch,
} from '@/types/domain'

interface DashboardResponse {
  today: { date: string; state: TodayPunch['state']; clock_in_at: string | null; clock_out_at: string | null }
  recent: {
    date: string
    weekday: string
    clock_in: string | null
    clock_out: string | null
    worked_minutes: number | null
    note: DailyRecord['note']
  }[]
  monthly_summary: {
    work_days: number
    worked_hours: number
    overtime_hours: number
    overtime_limit_hours: number
    paid_leave_remaining: number
  }
  notifications: {
    id: string
    category: AppNotification['category']
    title: string
    detail: string
    created_at: string
    read: boolean
  }[]
}

export const useAttendanceStore = defineStore('attendance', () => {
  const today = ref<TodayPunch | null>(null)
  const recent = ref<DailyRecord[]>([])
  const monthlySummary = ref<MonthlySummary | null>(null)
  const notifications = ref<AppNotification[]>([])
  const loading = ref(false)

  const unreadCount = computed(() => notifications.value.filter((n) => !n.read).length)

  async function fetchDashboard(): Promise<void> {
    loading.value = true
    try {
      const data = await api.get<DashboardResponse>('/attendance/dashboard')
      today.value = {
        date: data.today.date,
        state: data.today.state,
        clockInAt: data.today.clock_in_at,
        clockOutAt: data.today.clock_out_at,
      }
      recent.value = data.recent.map((r) => ({
        date: r.date,
        weekday: r.weekday,
        clockIn: r.clock_in,
        clockOut: r.clock_out,
        workedMinutes: r.worked_minutes,
        note: r.note,
      }))
      monthlySummary.value = {
        workDays: data.monthly_summary.work_days,
        workedHours: data.monthly_summary.worked_hours,
        overtimeHours: data.monthly_summary.overtime_hours,
        overtimeLimitHours: data.monthly_summary.overtime_limit_hours,
        paidLeaveRemaining: data.monthly_summary.paid_leave_remaining,
      }
      notifications.value = data.notifications.map((n) => ({
        id: n.id,
        category: n.category,
        title: n.title,
        detail: n.detail,
        createdAt: n.created_at,
        read: n.read,
      }))
    } finally {
      loading.value = false
    }
  }

  async function clockIn(): Promise<void> {
    // 打刻1回につき1つのキーを発行する。ネットワーク不調で応答が届かず自動再送された
    // 場合でも、サーバー側は同じキーを検知して二重に出勤打刻しない。
    await api.post('/attendance/punch', { action: 'in' }, { idempotencyKey: newIdempotencyKey() })
    await fetchDashboard()
  }

  async function clockOut(): Promise<void> {
    await api.post('/attendance/punch', { action: 'out' }, { idempotencyKey: newIdempotencyKey() })
    await fetchDashboard()
  }

  async function requestCorrection(payload: CorrectionRequestPayload): Promise<void> {
    await api.post('/attendance/corrections', {
      date: payload.date,
      type: payload.type,
      corrected_time: payload.correctedTime,
      reason: payload.reason,
    })
  }

  async function markAllRead(): Promise<void> {
    await api.post('/notifications/read-all')
    notifications.value = notifications.value.map((n) => ({ ...n, read: true }))
  }

  async function markOneRead(id: string): Promise<void> {
    const target = notifications.value.find((n) => n.id === id)
    if (!target || target.read) return
    await api.post(`/notifications/${id}/read`)
    target.read = true
  }

  return {
    today,
    recent,
    monthlySummary,
    notifications,
    loading,
    unreadCount,
    fetchDashboard,
    clockIn,
    clockOut,
    requestCorrection,
    markAllRead,
    markOneRead,
  }
})
