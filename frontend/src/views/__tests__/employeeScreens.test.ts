import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import AttendanceDetailView from '@/views/AttendanceDetailView.vue'
import LeaveRequestView from '@/views/LeaveRequestView.vue'
import MyPageView from '@/views/MyPageView.vue'
import TeamStatusView from '@/views/TeamStatusView.vue'

// ストア→バックエンドAPIの配線は各 stores/*.ts の責務。ここでは画面が API 由来の
// データ形（snake_case のレスポンス）を正しくマッピングして描画できることだけを検証する。
vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  const fixtures: Record<string, unknown> = {
    '/attendance/dashboard': {
      today: { date: '2026-08-27', state: 'not_started', clock_in_at: null, clock_out_at: null },
      recent: [],
      monthly_summary: { work_days: 10, worked_hours: 80, overtime_hours: 2, overtime_limit_hours: 45, paid_leave_remaining: 10 },
      notifications: [
        { id: 'n1', category: 'info', title: '未読の通知', detail: '未読の本文', created_at: '2026-08-26T00:00:00+09:00', read: false },
        { id: 'n2', category: 'info', title: '既読の通知', detail: '既読の本文', created_at: '2026-08-25T00:00:00+09:00', read: true },
      ],
    },
    '/leave/types': [{ id: 1, name: '年次有給休暇', is_paid: true, supports_half_day: true, requires_reason: false }],
    '/leave/balance': {
      paid_total: 20,
      paid_used: 5,
      paid_remaining: 15,
      carry_over: 0,
      next_grant: { date: '2027-01-01', days: 20 },
      mandatory_five_days: { used: 1, required: 5, deadline: '2027-01-01' },
      others: [],
    },
    '/leave/requests': [],
  }
  return {
    ...actual,
    api: {
      get: vi.fn((path: string) => {
        if (path.startsWith('/attendance/monthly')) {
          return Promise.resolve({
            year_month: '2026-08',
            status: 'draft',
            locked: false,
            totals: { work_days: 10, worked_hours: 80, overtime_hours: 2 },
            days: [
              { date: '2026-08-03', weekday: '月', clock_in: '09:00', clock_out: '18:00', worked_minutes: 480, note: 'normal' },
            ],
          })
        }
        if (path.startsWith('/notifications/?days=')) {
          return Promise.resolve([
            { id: 'n3', category: 'info', title: '過去の通知', detail: '過去の本文', created_at: '2026-07-01T00:00:00+09:00', read: false },
          ])
        }
        if (path.startsWith('/attendance/status')) {
          const scope = path.includes('scope=all') ? 'all' : 'team'
          return Promise.resolve({
            scope,
            fallback_to_all: false,
            team_name: '開発チーム',
            members: [
              { id: 1, name: '山田太郎', team_name: '開発チーム', is_admin: false, state: 'working', clock_in_at: '09:00', clock_out_at: null, on_leave: false },
              { id: 2, name: '鈴木花子', team_name: scope === 'all' ? '営業チーム' : '開発チーム', is_admin: false, state: 'not_started', clock_in_at: null, clock_out_at: null, on_leave: false },
            ],
          })
        }
        return Promise.resolve(fixtures[path] ?? [])
      }),
      post: vi.fn(() => Promise.resolve({})),
    },
  }
})

// jsdom は matchMedia を実装していない。PrimeVue の Select が mount 時に参照するため最小限のスタブを用意する。
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

function mountView(
  component: typeof MyPageView | typeof LeaveRequestView | typeof AttendanceDetailView | typeof TeamStatusView,
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
  auth.me = { id: 1, email: 'a@example.com', name: '山田太郎', role: 'employee', is_admin: false, hire_date: null, work_pattern_id: null }
  return wrapper
}

describe('employee screens', () => {
  it('マイページがモックデータで打刻カードを描画する', async () => {
    const wrapper = mountView(MyPageView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()
    expect(wrapper.text()).toContain('出勤する')
  })

  it('出勤打刻に Idempotency-Key を付与してリクエストする', async () => {
    const wrapper = mountView(MyPageView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()
    vi.mocked(api.post).mockClear()

    const punchButton = wrapper.findAll('button').find((b) => b.text() === '出勤する')
    await punchButton!.trigger('click')
    await flushMicrotasks()

    const call = vi.mocked(api.post).mock.calls.find(([path]) => path === '/attendance/punch')
    expect(call).toBeTruthy()
    const [, , opts] = call as [string, unknown, { idempotencyKey?: string } | undefined]
    expect(opts?.idempotencyKey).toBeTruthy()
  })

  it('既読の通知は縮小表示になり、未読はクリックで既読化できる', async () => {
    const wrapper = mountView(MyPageView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()

    // 未読は本文まで表示、既読は本文が消えてタイトル+時刻の1行だけになる
    expect(wrapper.text()).toContain('未読の本文')
    expect(wrapper.text()).not.toContain('既読の本文')
    expect(wrapper.find('.notif--read').exists()).toBe(true)
    expect(wrapper.find('.notif--unread').exists()).toBe(true)

    await wrapper.find('.notif--unread').trigger('click')
    await flushMicrotasks()
    expect(wrapper.text()).not.toContain('未読の本文')

    // 通知一覧ボタンで過去の通知を開ける（PrimeVue の Dialog は document.body にテレポートされる）
    const historyButton = wrapper.findAll('button').find((b) => b.text() === '通知一覧')
    expect(historyButton).toBeTruthy()
    await historyButton!.trigger('click')
    await flushMicrotasks()
    expect(document.body.textContent).toContain('過去の通知')
  })

  it('休暇申請画面がモックデータで残日数を描画する', async () => {
    const wrapper = mountView(LeaveRequestView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()
    expect(wrapper.text()).toContain('休暇を申請する')
    expect(wrapper.text()).toContain('残日数')
  })

  it('勤怠明細画面が日次一覧と月次確定申請ボタンを描画する', async () => {
    const wrapper = mountView(AttendanceDetailView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()
    expect(wrapper.text()).toContain('月次を確定申請する')
    expect(wrapper.text()).toContain('未申請')
  })

  it('出勤状況画面が既定でグループのメンバーを表示し、全社員に切り替えられる', async () => {
    const wrapper = mountView(TeamStatusView)
    await wrapper.vm.$nextTick()
    await flushMicrotasks()

    expect(wrapper.text()).toContain('山田太郎')
    expect(wrapper.text()).toContain('鈴木花子')
    expect(wrapper.text()).not.toContain('営業チーム')

    const allButton = wrapper.findAll('button').find((b) => b.text().includes('全社員'))
    expect(allButton).toBeTruthy()
    await allButton!.trigger('click')
    await flushMicrotasks()
    expect(wrapper.text()).toContain('営業チーム')
  })
})

function flushMicrotasks(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 400))
}
