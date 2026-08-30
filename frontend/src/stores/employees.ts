import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'
import type {
  Employee,
  EmployeeCreatePayload,
  EmployeeOption,
  EmployeeUpdatePayload,
} from '@/types/domain'

interface EmployeeResponse {
  id: number
  email: string
  name: string
  role: Employee['role']
  is_admin: boolean
  hire_date: string | null
  retired_at: string | null
  is_active: boolean
  team: number | null
  team_name: string | null
  work_pattern: number | null
  work_pattern_name: string | null
  leave_policy: number | null
  leave_policy_name: string | null
}

interface OptionsResponse {
  work_patterns: { id: number; name: string }[]
  leave_policies: { id: number; name: string }[]
  teams: { id: number; name: string }[]
}

function mapEmployee(e: EmployeeResponse): Employee {
  return {
    id: String(e.id),
    email: e.email,
    name: e.name,
    role: e.role,
    isAdmin: e.is_admin,
    hireDate: e.hire_date,
    retiredAt: e.retired_at,
    isActive: e.is_active,
    teamId: e.team === null ? null : String(e.team),
    teamName: e.team_name,
    workPatternId: e.work_pattern === null ? null : String(e.work_pattern),
    workPatternName: e.work_pattern_name,
    leavePolicyId: e.leave_policy === null ? null : String(e.leave_policy),
    leavePolicyName: e.leave_policy_name,
  }
}

export const useEmployeesStore = defineStore('employees', () => {
  const employees = ref<Employee[]>([])
  const workPatterns = ref<EmployeeOption[]>([])
  const leavePolicies = ref<EmployeeOption[]>([])
  const teams = ref<EmployeeOption[]>([])
  const loading = ref(false)
  const saving = ref(false)

  async function fetchEmployees(): Promise<void> {
    loading.value = true
    try {
      const [list, options] = await Promise.all([
        api.get<EmployeeResponse[]>('/admin/employees/'),
        api.get<OptionsResponse>('/admin/employees/options'),
      ])
      employees.value = list.map(mapEmployee)
      workPatterns.value = options.work_patterns.map((w) => ({ id: String(w.id), name: w.name }))
      leavePolicies.value = options.leave_policies.map((p) => ({ id: String(p.id), name: p.name }))
      teams.value = options.teams.map((t) => ({ id: String(t.id), name: t.name }))
    } finally {
      loading.value = false
    }
  }

  async function createEmployee(payload: EmployeeCreatePayload): Promise<void> {
    saving.value = true
    try {
      const created = await api.post<EmployeeResponse>('/admin/employees/', {
        email: payload.email,
        name: payload.name,
        password: payload.password,
        role: payload.role,
        hire_date: payload.hireDate,
        team: payload.teamId ? Number(payload.teamId) : null,
        work_pattern: payload.workPatternId ? Number(payload.workPatternId) : null,
        leave_policy: payload.leavePolicyId ? Number(payload.leavePolicyId) : null,
      })
      employees.value.unshift(mapEmployee(created))
    } finally {
      saving.value = false
    }
  }

  async function updateEmployee(id: string, payload: EmployeeUpdatePayload): Promise<void> {
    saving.value = true
    try {
      const body: Record<string, unknown> = {}
      if (payload.name !== undefined) body.name = payload.name
      if (payload.role !== undefined) body.role = payload.role
      if (payload.hireDate !== undefined) body.hire_date = payload.hireDate
      if (payload.retiredAt !== undefined) body.retired_at = payload.retiredAt
      if (payload.isActive !== undefined) body.is_active = payload.isActive
      if (payload.teamId !== undefined) {
        body.team = payload.teamId ? Number(payload.teamId) : null
      }
      if (payload.workPatternId !== undefined) {
        body.work_pattern = payload.workPatternId ? Number(payload.workPatternId) : null
      }
      if (payload.leavePolicyId !== undefined) {
        body.leave_policy = payload.leavePolicyId ? Number(payload.leavePolicyId) : null
      }
      if (payload.password) body.password = payload.password

      const updated = await api.patch<EmployeeResponse>(`/admin/employees/${id}`, body)
      const mapped = mapEmployee(updated)
      const index = employees.value.findIndex((e) => e.id === id)
      if (index >= 0) employees.value[index] = mapped
    } finally {
      saving.value = false
    }
  }

  return {
    employees,
    workPatterns,
    leavePolicies,
    teams,
    loading,
    saving,
    fetchEmployees,
    createEmployee,
    updateEmployee,
  }
})
