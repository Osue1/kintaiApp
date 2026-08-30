import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'
import type { AppNotification } from '@/types/domain'

interface NotificationResponse {
  id: string
  category: AppNotification['category']
  title: string
  detail: string
  created_at: string
  read: boolean
}

function mapNotification(n: NotificationResponse): AppNotification {
  return { id: n.id, category: n.category, title: n.title, detail: n.detail, createdAt: n.created_at, read: n.read }
}

/** 「通知一覧」ダイアログ用。ダッシュボードの直近リスト（stores/attendance.ts）とは別に、
 * 期間を指定して過去の通知を検索する。 */
export const useNotificationHistoryStore = defineStore('notificationHistory', () => {
  const items = ref<AppNotification[]>([])
  const loading = ref(false)

  async function fetchHistory(days: number): Promise<void> {
    loading.value = true
    try {
      const data = await api.get<NotificationResponse[]>(`/notifications/?days=${days}`)
      items.value = data.map(mapNotification)
    } finally {
      loading.value = false
    }
  }

  async function markOneRead(id: string): Promise<void> {
    const target = items.value.find((n) => n.id === id)
    if (!target || target.read) return
    await api.post(`/notifications/${id}/read`)
    target.read = true
  }

  return { items, loading, fetchHistory, markOneRead }
})
