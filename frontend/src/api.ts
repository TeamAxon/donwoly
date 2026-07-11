import type {
  ApiErrorBody,
  ChatCategory,
  ChatMessage,
  ChatSource,
  ChatStreamMeta,
  Conversation,
  LoginResponse,
  ProfileUpdatePayload,
  SignupPayload,
  SignupResponse,
  UserProfile,
} from './types'

const API_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  status: number
  code?: string

  constructor(status: number, body: ApiErrorBody) {
    super(body.error ?? 'API_ERROR')
    this.status = status
    this.code = body.error
  }
}

async function parseError(response: Response): Promise<never> {
  const body = (await response.json().catch(() => ({}))) as ApiErrorBody
  throw new ApiError(response.status, body)
}

export async function checkEmail(email: string): Promise<boolean> {
  const response = await fetch(
    `${API_URL}/api/auth/check-email?email=${encodeURIComponent(email)}`,
  )
  if (!response.ok) return parseError(response)
  const body = (await response.json()) as { available: boolean }
  return body.available
}

export async function signup(payload: SignupPayload): Promise<SignupResponse> {
  const response = await fetch(`${API_URL}/api/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return parseError(response)
  return response.json() as Promise<SignupResponse>
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${API_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!response.ok) return parseError(response)
  return response.json() as Promise<LoginResponse>
}

function bearerHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` }
}

export interface ChatStreamHandlers {
  onMeta: (meta: ChatStreamMeta) => void
  onChunk: (chunk: string) => void
  onSources: (sources: ChatSource[]) => void
  onDone: () => void
}

export function parseSseBlock(block: string): { event: string; data: unknown } | null {
  let event = ''
  const dataLines: string[] = []
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }
  if (!event || dataLines.length === 0) return null
  return { event, data: JSON.parse(dataLines.join('\n')) as unknown }
}

export async function streamChat(
  payload: {
    message: string
    category?: ChatCategory
    conversationId?: string
  },
  token: string,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_URL}/api/chat/query`, {
    method: 'POST',
    headers: {
      ...bearerHeaders(token),
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    signal,
  })
  if (!response.ok) return parseError(response)
  if (!response.body) throw new Error('STREAM_NOT_SUPPORTED')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n')
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      const parsed = parseSseBlock(block)
      if (!parsed) continue
      if (parsed.event === 'meta') handlers.onMeta(parsed.data as ChatStreamMeta)
      if (parsed.event === 'chunk') {
        handlers.onChunk((parsed.data as { answerChunk: string }).answerChunk)
      }
      if (parsed.event === 'sources') {
        handlers.onSources((parsed.data as { sources: ChatSource[] }).sources)
      }
      if (parsed.event === 'done') handlers.onDone()
    }
    if (done) break
  }
}

export async function getConversations(token: string): Promise<Conversation[]> {
  const response = await fetch(`${API_URL}/api/chat/conversations`, {
    headers: bearerHeaders(token),
  })
  if (!response.ok) return parseError(response)
  return response.json() as Promise<Conversation[]>
}

export async function getMessages(
  conversationId: string,
  token: string,
): Promise<ChatMessage[]> {
  const response = await fetch(
    `${API_URL}/api/chat/conversations/${conversationId}/messages`,
    { headers: bearerHeaders(token) },
  )
  if (!response.ok) return parseError(response)
  return response.json() as Promise<ChatMessage[]>
}

export async function deleteConversation(
  conversationId: string,
  token: string,
): Promise<void> {
  const response = await fetch(`${API_URL}/api/chat/conversations/${conversationId}`, {
    method: 'DELETE',
    headers: bearerHeaders(token),
  })
  if (!response.ok) return parseError(response)
}

export async function getProfile(token: string): Promise<UserProfile> {
  const response = await fetch(`${API_URL}/api/users/me`, {
    headers: bearerHeaders(token),
  })
  if (!response.ok) return parseError(response)
  return response.json() as Promise<UserProfile>
}

export async function updateProfile(
  payload: ProfileUpdatePayload,
  token: string,
): Promise<UserProfile> {
  const response = await fetch(`${API_URL}/api/users/me`, {
    method: 'PATCH',
    headers: {
      ...bearerHeaders(token),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  if (!response.ok) return parseError(response)
  return response.json() as Promise<UserProfile>
}
