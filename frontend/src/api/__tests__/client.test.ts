import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiRequestError, api } from '../client'

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response
}

describe('api client', () => {
  beforeEach(() => {
    document.cookie = 'csrftoken=test-token'
    vi.restoreAllMocks()
  })

  it('サーバーのエラー形式をそのまま画面で使える例外に変換する', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(400, {
          code: 'invalid',
          message: '入力内容を確認してください。',
          field_errors: { email: ['正しいメールアドレスを入力してください。'] },
        }),
      ),
    )

    await expect(api.post('/auth/login', {})).rejects.toBeInstanceOf(ApiRequestError)

    try {
      await api.post('/auth/login', {})
    } catch (e) {
      const err = e as ApiRequestError
      expect(err.message).toBe('入力内容を確認してください。')
      expect(err.fieldErrors.email[0]).toContain('メールアドレス')
      expect(err.status).toBe(400)
    }
  })

  it('書き込み系リクエストに CSRF トークンを載せる', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await api.post('/auth/logout')

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    const headers = init.headers as Headers
    expect(headers.get('X-CSRFToken')).toBe('test-token')
    expect(init.credentials).toBe('same-origin')
  })

  it('GET には CSRF トークンを載せない', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { id: 1 }))
    vi.stubGlobal('fetch', fetchMock)

    await api.get('/auth/me')

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect((init.headers as Headers).get('X-CSRFToken')).toBeNull()
  })

  it('204 は本文なしとして扱う', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 204 }) as Response))
    await expect(api.post('/auth/logout')).resolves.toBeUndefined()
  })

  it('idempotencyKey を渡すと Idempotency-Key ヘッダが送られる', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await api.post('/attendance/punch', { action: 'in' }, { idempotencyKey: 'abc-123' })

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect((init.headers as Headers).get('Idempotency-Key')).toBe('abc-123')
  })

  it('idempotencyKey を渡さない場合は Idempotency-Key ヘッダを送らない（後方互換）', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await api.post('/auth/logout')

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect((init.headers as Headers).get('Idempotency-Key')).toBeNull()
  })
})
