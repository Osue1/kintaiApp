import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'
import type { DailyRecord, MonthlyDetail } from '@/types/domain'

interface MonthlyDetailResponse {
  year_month: string
  status: MonthlyDetail['status']
  locked: boolean
  totals: { work_days: number; worked_hours: number; overtime_hours: number }
  days: {
    date: string
    weekday: string
    clock_in: string | null
    clock_out: string | null
    worked_minutes: number | null
    note: DailyRecord['note']
  }[]
}

function mapDetail(r: MonthlyDetailResponse): MonthlyDetail {
  return {
    yearMonth: r.year_month,
    status: r.status,
    locked: r.locked,
    totals: {
      workDays: r.totals.work_days,
      workedHours: r.totals.worked_hours,
      overtimeHours: r.totals.overtime_hours,
    },
    days: r.days.map((d) => ({
      date: d.date,
      weekday: d.weekday,
      clockIn: d.clock_in,
      clockOut: d.clock_out,
      workedMinutes: d.worked_minutes,
      note: d.note,
    })),
  }
}

export const useAttendanceMonthlyStore = defineStore('attendanceMonthly', () => {
  const detail = ref<MonthlyDetail | null>(null)
  const loading = ref(false)
  const submitting = ref(false)

  async function fetchMonthly(yearMonth: string): Promise<void> {
    loading.value = true
    try {
      const data = await api.get<MonthlyDetailResponse>(`/attendance/monthly?ym=${yearMonth}`)
      detail.value = mapDetail(data)
    } finally {
      loading.value = false
    }
  }

  async function submitMonthly(yearMonth: string): Promise<void> {
    submitting.value = true
    try {
      await api.post('/attendance/monthly/submit', { year_month: yearMonth })
      await fetchMonthly(yearMonth)
    } finally {
      submitting.value = false
    }
  }

  return { detail, loading, submitting, fetchMonthly, submitMonthly }
})
