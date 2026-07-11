export type Region =
  | 'SYDNEY'
  | 'MELBOURNE'
  | 'BRISBANE'
  | 'PERTH'
  | 'GOLD_COAST'
  | 'OTHER'

export type Industry =
  | 'FARM'
  | 'HOSPITALITY'
  | 'CONSTRUCTION'
  | 'CLEANING'
  | 'FACTORY'
  | 'OFFICE'
  | 'TOURISM'
  | 'OTHER'

export interface SignupPayload {
  email: string
  name: string
  password: string
  age: number
  region: Region
  industry: Industry
}

export interface SignupResponse {
  userId: string
  accessToken: string
  refreshToken: string
}

export interface UserProfile {
  id: string
  email: string
  name: string
  age: number
  region: Region
  industry: Industry
}

export interface LoginResponse {
  accessToken: string
  refreshToken: string
  user: UserProfile
}

export interface ProfileUpdatePayload {
  name?: string
  age?: number
  region?: Region
  industry?: Industry
}

export interface ApiErrorBody {
  error?: string
  details?: unknown
}

export type ChatCategory = 'visa' | 'departure' | 'labor_law' | 'tax' | 'life'

export interface ChatSource {
  title: string
  url?: string
  category?: ChatCategory
  score?: number
}

export interface Conversation {
  id: string
  title: string
  createdAt: string
  updatedAt: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources: ChatSource[]
  createdAt: string
}

export interface ChatStreamMeta {
  conversationId: string
  messageId: string
}
