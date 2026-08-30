import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { api, ApiRequestError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import AlertsView from '@/views/admin/AlertsView.vue'
import ApprovalsView from '@/views/admin/ApprovalsView.vue'
import AuditLogView from '@/views/admin/AuditLogView.vue'
import ContractorsView from '@/views/admin/ContractorsView.vue'
import EmployeesView from '@/views/admin/EmployeesView.vue'
import InvoicesView from '@/views/admin/InvoicesView.vue'
import LeaveLedgerView from '@/views/admin/LeaveLedgerView.vue'

const toastAddSpy = vi.fn()
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: toastAddSpy }) }))

// ストア→バックエンドAPIの配線は各 stores/*.ts の責務。ここでは画面が API 由来の
// データ形（snake_case のレスポンス）を正しくマッピングして描画できることだけを検証する。
vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  const fixtures: Record<string, unknown> = {
    '/admin/approvals': [
      {
        id: 'leave-1',
        employee_name: '佐藤花子',
        type: 'leave',
        summary: '年次有給休暇（全日）9/3',
        detail: '',
        requested_at: '2026-08-26T00:00:00+09:00',
        status: 'pending',
        rejected_reason: '',
      },
    ],
    '/admin/alerts': {
      paid_leave_alerts: [],
      overtime_alerts: [
        {
          employee_id: '3',
          employee_name: '鈴木一郎',
          month: '2026-08',
          overtime_hours: 85,
          limit_hours: 45,
          severity: 'violation',
          reasons: [{ kind: 'multi_month_avg', label: '直近3ヶ月平均が80時間を超過', severity: 'violation' }],
        },
      ],
    },
    '/admin/contractors/': [
      {
        id: 1,
        name: '合同会社ノースデザイン',
        email: 'contact@example.com',
        rate_type: 'hourly',
        rate_amount: '4500',
        closing_day: 31,
        payment_month_offset: 1,
        payment_day: 10,
      },
    ],
    '/admin/contractors/work-records': [],
    '/admin/employees/': [
      {
        id: 1,
        email: 'sato@example.com',
        name: '佐藤花子',
        role: 'employee',
        is_admin: false,
        hire_date: '2024-04-01',
        retired_at: null,
        is_active: true,
        team: 1,
        team_name: '開発チーム',
        work_pattern: 1,
        work_pattern_name: '標準（週休2日）',
        leave_policy: 1,
        leave_policy_name: '標準（法定どおり）',
      },
    ],
    '/admin/employees/options': {
      work_patterns: [{ id: 1, name: '標準（週休2日）' }],
      leave_policies: [{ id: 1, name: '標準（法定どおり）' }],
      teams: [{ id: 1, name: '開発チーム' }],
    },
    '/admin/audit-logs': {
      results: [
        {
          id: 1,
          actor_name: '開発用管理者',
          action: 'employee_update',
          target_type: 'User',
          target_id: 2,
          before: { name: '旧氏名' },
          after: { name: '新氏名' },
          ip: '127.0.0.1',
          user_agent: 'pytest',
          created_at: '2026-08-30T01:00:00+09:00',
        },
      ],
      total_count: 1,
      truncated: false,
    },
  }
  return {
    ...actual,
    api: {
      get: vi.fn((path: string) => {
        if (path.startsWith('/admin/invoices/withholding-statements')) {
          // 画面側は「対象月（先月）の年」で絞り込むため、1月に実行された場合でも
          // ズレないよう同じ計算方法（先月の年）でフィクスチャの year を合わせる。
          const lastMonthYear = new Date(new Date().getFullYear(), new Date().getMonth() - 1, 1).getFullYear()
          return Promise.resolve([
            {
              id: 3,
              contractor_id: 1,
              contractor_name: '合同会社ノースデザイン',
              year: lastMonthYear,
              total_payment: '600000',
              total_withholding: '61260',
            },
          ])
        }
        if (path.startsWith('/admin/invoices/')) {
          const now = new Date()
          const lastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1)
          const periodEnd = `${lastMonth.getFullYear()}-${String(lastMonth.getMonth() + 1).padStart(2, '0')}-28`
          return Promise.resolve([
            {
              id: 9,
              contractor_id: 1,
              contractor_name: '合同会社ノースデザイン',
              invoice_no: 'INV-TEST-0001',
              period_start: periodEnd,
              period_end: periodEnd,
              quantity_label: '40.0時間',
              subtotal: '180000',
              tax_amount: '18000',
              withholding_amount: '18378',
              payable_amount: '179622',
              status: 'sent',
              issued_on: periodEnd,
              confirm_deadline: periodEnd,
              confirmed_at: null,
              confirm_method: null,
            },
          ])
        }
        if (path.startsWith('/leave/admin/ledger')) {
          return Promise.resolve({
            employee: { id: 1, name: '佐藤花子', hire_date: '2024-04-01' },
            grants: [
              {
                granted_on: '2026-04-01',
                days: 20,
                expires_on: '2028-04-01',
                consumed: 1,
                remaining: 19,
                is_expired: false,
                consumptions: [{ date_label: '2026-05-01', days: 1, leave_type_name: '年次有給休暇' }],
              },
            ],
          })
        }
        return Promise.resolve(fixtures[path] ?? [])
      }),
      post: vi.fn(() => Promise.resolve({})),
      patch: vi.fn(() => Promise.resolve({})),
    },
  }
})

// jsdom は matchMedia / ResizeObserver を実装していない。PrimeVue の Select・Tabs が
// mount 時に参照するため最小限のスタブを用意する。
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

  window.ResizeObserver =
    window.ResizeObserver ??
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
})

function mountView(
  component:
    | typeof AlertsView
    | typeof ApprovalsView
    | typeof AuditLogView
    | typeof ContractorsView
    | typeof InvoicesView
    | typeof EmployeesView
    | typeof LeaveLedgerView,
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mount(component, {
    global: {
      plugins: [pinia, [PrimeVue, { theme: { preset: {} } }], ToastService],
      stubs: { RouterLink: true },
    },
  })
  const auth = useAuthStore()
  auth.me = { id: 999, email: 'admin@example.com', name: '開発用管理者', role: 'admin', is_admin: true, hire_date: null, work_pattern_id: null }
  return wrapper
}

function flushMicrotasks(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 400))
}

describe('admin screens', () => {
  it('勤怠承認画面がモックの申請一覧を描画する', async () => {
    const wrapper = mountView(ApprovalsView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()
    expect(wrapper.text()).toContain('佐藤花子')
    expect(wrapper.text()).toContain('承認待ち')
  })

  it('承認が二重クリック等で既に処理済みだった場合、エラーをトーストで通知して一覧を再取得する', async () => {
    // apps/leave/views.py の select_for_update による排他制御が409を返したケース。
    // ここでUIが握りつぶすと、ユーザーは何が起きたか分からず連打し続けてしまう。
    const wrapper = mountView(ApprovalsView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()
    toastAddSpy.mockClear()
    vi.mocked(api.get).mockClear()

    vi.mocked(api.post).mockRejectedValueOnce(
      new ApiRequestError({ code: 'already_processed', message: 'この申請は既に処理済みです。', field_errors: {}, status: 409 }),
    )
    const approveButton = wrapper.findAll('button').find((b) => b.text() === '承認')
    await approveButton!.trigger('click')
    await flushMicrotasks()

    expect(toastAddSpy).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', summary: '承認に失敗しました', detail: 'この申請は既に処理済みです。' }),
    )
    // 一覧を再取得して最新状態を画面に反映する
    expect(api.get).toHaveBeenCalledWith('/admin/approvals')
  })

  it('アラート画面が有給・残業の対象者と超過理由を描画する', async () => {
    const wrapper = mountView(AlertsView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()
    expect(wrapper.text()).toContain('年5日')
    expect(wrapper.text()).toContain('36協定')
    expect(wrapper.text()).toContain('鈴木一郎')
    expect(wrapper.text()).toContain('協定違反')
    expect(wrapper.text()).toContain('直近3ヶ月平均が80時間を超過')
  })

  it('外注管理画面が外注マスタを描画する', async () => {
    const wrapper = mountView(ContractorsView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()
    expect(wrapper.text()).toContain('外注先を登録')
    expect(wrapper.text()).toContain('合同会社ノースデザイン')
  })

  it('外注先登録に失敗した場合、ダイアログにエラーメッセージを表示する', async () => {
    const wrapper = mountView(ContractorsView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()

    const addButton = wrapper.findAll('button').find((b) => b.text() === '外注先を登録')
    await addButton!.trigger('click')
    await wrapper.vm.$nextTick()

    // PrimeVue の Dialog は document.body にテレポートされる
    const nameInput = document.body.querySelector('.p-dialog input[type="text"], .p-dialog input:not([type])') as HTMLInputElement
    nameInput.value = '新規外注先'
    nameInput.dispatchEvent(new Event('input'))
    await wrapper.vm.$nextTick()

    vi.mocked(api.post).mockRejectedValueOnce(
      new ApiRequestError({ code: 'duplicate', message: 'このメールアドレスは既に登録されています。', field_errors: {}, status: 400 }),
    )
    const form = document.body.querySelector('.p-dialog form') as HTMLFormElement
    form.dispatchEvent(new Event('submit', { cancelable: true }))
    await flushMicrotasks()

    expect(document.body.textContent).toContain('このメールアドレスは既に登録されています。')
  })

  it('請求書発行画面が対象月の操作UIを描画する', async () => {
    const wrapper = mountView(InvoicesView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()
    expect(wrapper.text()).toContain('締め日到来分を一括生成')
  })

  it('請求書発行画面が出力済みの支払調書一覧とPDFダウンロードボタンを描画する', async () => {
    // 以前は支払調書を出力してもこの画面から確認・ダウンロードする手段が無かった欠陥の修正確認。
    const wrapper = mountView(InvoicesView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()
    expect(wrapper.text()).toContain('合同会社ノースデザイン')
    expect(wrapper.text()).toContain('¥600,000')
    const pdfButtons = wrapper.findAll('button').filter((b) => b.text() === 'PDF')
    expect(pdfButtons.length).toBeGreaterThan(0)
  })

  it('請求書の一括生成に Idempotency-Key を付与してリクエストする', async () => {
    const wrapper = mountView(InvoicesView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()
    vi.mocked(api.post).mockClear()

    const generateButton = wrapper.findAll('button').find((b) => b.text() === '締め日到来分を一括生成')
    await generateButton!.trigger('click')
    await flushMicrotasks()

    const call = vi.mocked(api.post).mock.calls.find(([path]) => path === '/admin/invoices/generate')
    expect(call).toBeTruthy()
    const [, , opts] = call as [string, unknown, { idempotencyKey?: string } | undefined]
    expect(opts?.idempotencyKey).toBeTruthy()
  })

  it('請求書を取消すると赤伝が発行され、一覧に追加される', async () => {
    const wrapper = mountView(InvoicesView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()
    toastAddSpy.mockClear()

    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(api.post).mockResolvedValueOnce({
      id: 10,
      contractor_id: 1,
      contractor_name: '合同会社ノースデザイン',
      invoice_no: 'INV-TEST-0001-R',
      period_start: '2026-07-01',
      period_end: '2026-07-28',
      quantity_label: '40.0時間',
      subtotal: '-180000',
      tax_amount: '-18000',
      withholding_amount: '-18378',
      payable_amount: '-179622',
      status: 'void',
      issued_on: '2026-07-28',
    })

    const voidButton = wrapper.findAll('button').find((b) => b.text() === '取消')
    await voidButton!.trigger('click')
    await flushMicrotasks()

    expect(api.post).toHaveBeenCalledWith('/admin/invoices/9/void')
    expect(toastAddSpy).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'success', summary: expect.stringContaining('INV-TEST-0001-R') }),
    )
    expect(wrapper.text()).toContain('INV-TEST-0001-R')
  })

  it('仕入明細書の確認を手動で記録できる', async () => {
    const wrapper = mountView(InvoicesView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()
    toastAddSpy.mockClear()

    expect(wrapper.text()).toContain('確認待ち')

    vi.mocked(api.post).mockResolvedValueOnce({
      id: 9,
      contractor_id: 1,
      contractor_name: '合同会社ノースデザイン',
      invoice_no: 'INV-TEST-0001',
      period_start: '2026-07-01',
      period_end: '2026-07-28',
      quantity_label: '40.0時間',
      subtotal: '180000',
      tax_amount: '18000',
      withholding_amount: '18378',
      payable_amount: '179622',
      status: 'sent',
      issued_on: '2026-07-28',
      confirm_deadline: '2026-07-28',
      confirmed_at: '2026-08-01T00:00:00+09:00',
      confirm_method: 'manual',
    })

    const confirmButton = wrapper.findAll('button').find((b) => b.text() === '確認済みにする')
    await confirmButton!.trigger('click')
    await flushMicrotasks()

    expect(api.post).toHaveBeenCalledWith('/admin/invoices/9/confirm')
    expect(toastAddSpy).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'success', summary: '仕入明細書の確認を記録しました' }),
    )
    expect(wrapper.text()).toContain('確認済み')
  })

  it('請求書の一括生成に失敗した場合、エラーをトーストで通知する', async () => {
    const wrapper = mountView(InvoicesView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()
    toastAddSpy.mockClear()

    vi.mocked(api.post).mockRejectedValueOnce(
      new ApiRequestError({ code: 'locked', message: '対象月は既に締め処理済みです。', field_errors: {}, status: 409 }),
    )
    const generateButton = wrapper.findAll('button').find((b) => b.text() === '締め日到来分を一括生成')
    await generateButton!.trigger('click')
    await flushMicrotasks()

    expect(toastAddSpy).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', summary: '請求書の生成に失敗しました', detail: '対象月は既に締め処理済みです。' }),
    )
  })

  it('従業員管理画面が従業員一覧を描画する', async () => {
    const wrapper = mountView(EmployeesView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()
    expect(wrapper.text()).toContain('従業員を登録')
    expect(wrapper.text()).toContain('佐藤花子')
    // 入社日はISOの生文字列(2024-04-01)ではなく日本語で読みやすい表記(2024/4/1)で表示する
    expect(wrapper.text()).toContain('2024/4/1')
    expect(wrapper.text()).not.toContain('2024-04-01')
  })

  it('年次有給休暇管理簿画面が付与ロットを描画する', async () => {
    const wrapper = mountView(LeaveLedgerView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()
    expect(wrapper.text()).toContain('基準日 2026/4/1')
    expect(wrapper.text()).toContain('残 19')
  })

  it('監査ログ画面が操作履歴と変更内容を日本語ラベルで描画する', async () => {
    const wrapper = mountView(AuditLogView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()
    // action/target_typeの生コードではなく、日本語ラベルに変換して表示すること
    expect(wrapper.text()).toContain('従業員情報を更新')
    expect(wrapper.text()).toContain('従業員 #2')
    expect(wrapper.text()).not.toContain('employee_update')
    // before/afterの変更差分が「フィールド名: 変更前 → 変更後」の形で見えること
    expect(wrapper.text()).toContain('name: 旧氏名 → 新氏名')
    expect(wrapper.text()).toContain('開発用管理者')
  })
})
