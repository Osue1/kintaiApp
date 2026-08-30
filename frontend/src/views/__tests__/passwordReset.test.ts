import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { api, ApiRequestError } from '@/api/client'
import LoginView from '@/views/LoginView.vue'
import PasswordResetConfirmView from '@/views/PasswordResetConfirmView.vue'
import PasswordResetRequestView from '@/views/PasswordResetRequestView.vue'

// パスワード再設定画面は useRoute/useRouter を直接使う（LoginViewと同様）ため、
// 他の画面テストのように RouterLink をスタブするだけでは足りず、実際の Router インスタンスが要る。
vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    api: { ...actual.api, post: vi.fn(() => Promise.resolve(undefined)) },
  }
})

beforeAll(() => {
  window.matchMedia =
    window.matchMedia ??
    ((query: string) =>
      ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }) as unknown as MediaQueryList)
})

async function mountWithRouter(component: typeof LoginView | typeof PasswordResetRequestView | typeof PasswordResetConfirmView, path: string) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: LoginView },
      { path: '/password-reset', name: 'password-reset-request', component: PasswordResetRequestView },
      { path: '/password-reset/confirm', name: 'password-reset-confirm', component: PasswordResetConfirmView },
    ],
  })
  router.push(path)
  await router.isReady()

  const wrapper = mount(component, {
    global: { plugins: [pinia, router, [PrimeVue, { theme: { preset: {} } }], ToastService] },
  })
  await wrapper.vm.$nextTick()
  return wrapper
}

describe('パスワード再設定', () => {
  it('ログイン画面に「パスワードをお忘れですか？」のリンクがある', async () => {
    const wrapper = await mountWithRouter(LoginView, '/login')
    const link = wrapper.findComponent({ name: 'RouterLink' })
    expect(wrapper.text()).toContain('パスワードをお忘れですか？')
    expect(link.exists()).toBe(true)
  })

  it('再設定リクエスト画面はメールアドレスの在不在を問わず同じ案内文を表示する', async () => {
    const wrapper = await mountWithRouter(PasswordResetRequestView, '/password-reset')

    const emailInput = wrapper.find('input[type="email"]')
    await emailInput.setValue('someone@example.com')
    await wrapper.find('form').trigger('submit.prevent')
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(vi.mocked(api.post)).toHaveBeenCalledWith(
      '/auth/password-reset/request',
      expect.objectContaining({ email: 'someone@example.com' }),
    )
    expect(wrapper.text()).toContain('送信しました')
  })

  it('再設定リクエスト画面はAPIエラー時も同じ案内文を表示する（メールアドレスの存在を推測させない）', async () => {
    vi.mocked(api.post).mockRejectedValueOnce(new Error('network error'))
    const wrapper = await mountWithRouter(PasswordResetRequestView, '/password-reset')

    await wrapper.find('input[type="email"]').setValue('someone@example.com')
    await wrapper.find('form').trigger('submit.prevent')
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(wrapper.text()).toContain('送信しました')
  })

  it('確認画面はURLのtokenクエリを読み取ってAPIに渡し、成功後ログイン画面へ遷移する', async () => {
    vi.useFakeTimers()
    const wrapper = await mountWithRouter(PasswordResetConfirmView, '/password-reset/confirm?token=abc-123')

    const [passwordInput, confirmInput] = wrapper.findAll('input[type="password"]')
    await passwordInput!.setValue('brand-new-password-123')
    await confirmInput!.setValue('brand-new-password-123')
    await wrapper.find('form').trigger('submit.prevent')
    await vi.runOnlyPendingTimersAsync()

    expect(api.post).toHaveBeenCalledWith('/auth/password-reset/confirm', {
      token: 'abc-123',
      password: 'brand-new-password-123',
    })
    expect(wrapper.text()).toContain('ログイン画面に移動します')
    vi.useRealTimers()
  })

  it('確認画面は新しいパスワードの不一致をAPI呼び出し前にエラー表示する', async () => {
    vi.mocked(api.post).mockClear()
    const wrapper = await mountWithRouter(PasswordResetConfirmView, '/password-reset/confirm?token=abc-123')

    const [passwordInput, confirmInput] = wrapper.findAll('input[type="password"]')
    await passwordInput!.setValue('brand-new-password-123')
    await confirmInput!.setValue('typo-password-456')
    await wrapper.find('form').trigger('submit.prevent')

    expect(wrapper.text()).toContain('一致しません')
    expect(api.post).not.toHaveBeenCalled()
  })

  it('確認画面はサーバーのエラーメッセージ（無効・期限切れトークン等）をそのまま表示する', async () => {
    vi.mocked(api.post).mockRejectedValueOnce(
      new ApiRequestError({ code: 'invalid_token', message: 'このリンクの有効期限が切れています。', field_errors: {}, status: 400 }),
    )
    const wrapper = await mountWithRouter(PasswordResetConfirmView, '/password-reset/confirm?token=expired')

    const [passwordInput, confirmInput] = wrapper.findAll('input[type="password"]')
    await passwordInput!.setValue('brand-new-password-123')
    await confirmInput!.setValue('brand-new-password-123')
    await wrapper.find('form').trigger('submit.prevent')
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(wrapper.text()).toContain('有効期限が切れています')
  })

  it('確認画面はtokenクエリが無い場合フォームを出さずやり直しを案内する', async () => {
    const wrapper = await mountWithRouter(PasswordResetConfirmView, '/password-reset/confirm')
    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.text()).toContain('リンクが正しくありません')
  })
})
