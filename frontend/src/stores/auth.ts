import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'

export interface CompanyBrief {
  id: number
  name: string
  invoice_reg_no: string
}

export interface Me {
  id: number
  email: string
  name: string
  role: 'admin' | 'employee'
  is_admin: boolean
  hire_date: string | null
  work_pattern_id: number | null
  company?: CompanyBrief
}

export const useAuthStore = defineStore('auth', () => {
  const me = ref<Me | null>(null)
  const loading = ref(false)
  const initialized = ref(false)

  async function fetchMe(): Promise<void> {
    loading.value = true
    try {
      me.value = await api.get<Me>('/auth/me')
    } catch {
      me.value = null
    } finally {
      loading.value = false
      initialized.value = true
    }
  }

  async function login(email: string, password: string): Promise<void> {
    await api.post<Me>('/auth/login', { email, password })
    await fetchMe()
  }

  async function logout(): Promise<void> {
    await api.post<void>('/auth/logout')
    me.value = null
  }

  // パスワード再設定はログイン前の画面から呼ばれるため me を更新しない。
  // メールアドレスの在不在に関わらずバックエンドは常に204を返す（列挙攻撃対策）ので、
  // ここでも「成功した/失敗した」の分岐は行わず、常に同じ案内文を画面側で表示させる。
  async function requestPasswordReset(email: string): Promise<void> {
    const resetUrlBase = `${window.location.origin}/password-reset/confirm`
    await api.post<void>('/auth/password-reset/request', { email, reset_url_base: resetUrlBase })
  }

  async function confirmPasswordReset(token: string, password: string): Promise<void> {
    await api.post<void>('/auth/password-reset/confirm', { token, password })
  }

  return { me, loading, initialized, fetchMe, login, logout, requestPasswordReset, confirmPasswordReset }
})
