import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'
import type { TeamMemberStatus, TeamStatusResult, TeamStatusScope } from '@/types/domain'

interface TeamStatusResponse {
  scope: TeamStatusScope
  fallback_to_all: boolean
  team_name: string | null
  members: {
    id: number
    name: string
    team_name: string | null
    is_admin: boolean
    state: TeamMemberStatus['state']
    clock_in_at: string | null
    clock_out_at: string | null
    on_leave: boolean
  }[]
}

function mapResult(r: TeamStatusResponse): TeamStatusResult {
  return {
    scope: r.scope,
    fallbackToAll: r.fallback_to_all,
    teamName: r.team_name,
    members: r.members.map((m) => ({
      id: String(m.id),
      name: m.name,
      teamName: m.team_name,
      isAdmin: m.is_admin,
      state: m.state,
      clockInAt: m.clock_in_at,
      clockOutAt: m.clock_out_at,
      onLeave: m.on_leave,
    })),
  }
}

export const useTeamStatusStore = defineStore('teamStatus', () => {
  const result = ref<TeamStatusResult | null>(null)
  const loading = ref(false)

  async function fetchStatus(scope: TeamStatusScope): Promise<void> {
    loading.value = true
    try {
      const data = await api.get<TeamStatusResponse>(`/attendance/status?scope=${scope}`)
      result.value = mapResult(data)
    } finally {
      loading.value = false
    }
  }

  return { result, loading, fetchStatus }
})
