/**
 * API クライアント。
 *
 * SPA と API を同一オリジンで配信し、セッション Cookie + CSRF トークンで認証する
 * （設計書 第3.1章）。トークンを localStorage に置かないので XSS で盗まれない。
 */
export const API_BASE = import.meta.env.VITE_API_BASE ?? '/api/v1'
const BASE = API_BASE

export interface ApiError {
  code: string
  message: string
  field_errors: Record<string, string[]>
  status: number
}

export class ApiRequestError extends Error {
  readonly code: string
  readonly fieldErrors: Record<string, string[]>
  readonly status: number

  constructor(error: ApiError) {
    super(error.message)
    this.name = 'ApiRequestError'
    this.code = error.code
    this.fieldErrors = error.field_errors
    this.status = error.status
  }
}

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(^|;\\s*)${name}=([^;]*)`))
  return match ? decodeURIComponent(match[2]) : null
}

/** CSRF Cookie を確実に持ってから書き込み系リクエストを送るための初期化。 */
export async function ensureCsrfToken(): Promise<void> {
  if (readCookie('csrftoken')) return
  await fetch(`${BASE}/auth/csrf`, { credentials: 'same-origin' })
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')

  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    await ensureCsrfToken()
    const token = readCookie('csrftoken')
    if (token) headers.set('X-CSRFToken', token)
    if (init.body && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
  }

  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers,
    credentials: 'same-origin',
  })

  if (res.status === 204) return undefined as T

  const payload = await res.json().catch(() => null)

  if (!res.ok) {
    throw new ApiRequestError({
      code: payload?.code ?? 'unknown',
      message: payload?.message ?? '通信に失敗しました。時間をおいてお試しください。',
      field_errors: payload?.field_errors ?? {},
      status: res.status,
    })
  }
  return payload as T
}

/**
 * 打刻・請求書生成などの二重実行防止に使う Idempotency-Key を1件生成する。
 * 呼び出し側（store のアクション関数）が「ユーザー操作1回につき1つ」生成し、
 * api.post の idempotencyKey に渡すことで、ネットワーク再送やリクエストの重複到達が
 * あってもサーバー側（apps.common.idempotency）で二重処理を防げる（バックエンドは
 * 対応済みだったが、フロントエンドがヘッダを一切送っておらず機能していなかった）。
 * ボタンの二重クリックを防ぐ用途ではない点に注意 — それは各画面側の :loading/:disabled
 * が担う。あくまで「同一の1操作」がネットワーク越しに重複して処理されることへの防御線。
 */
export function newIdempotencyKey(): string {
  return crypto.randomUUID()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown, opts?: { idempotencyKey?: string }) => {
    const headers = new Headers()
    if (opts?.idempotencyKey) headers.set('Idempotency-Key', opts.idempotencyKey)
    return request<T>(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
      headers,
    })
  },
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
