import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ApiError,
  deleteConversation,
  getConversations,
  getMessages,
  getProfile,
  streamChat,
} from './api'
import type { ChatCategory, ChatMessage, Conversation, UserProfile } from './types'
import './ChatPage.css'

const CATEGORY_OPTIONS: { code: ChatCategory; label: string; icon: string }[] = [
  { code: 'visa', label: '비자', icon: '✦' },
  { code: 'departure', label: '출국준비', icon: '✈' },
  { code: 'labor', label: '노동법', icon: '⚒' },
  { code: 'tax', label: '세금', icon: '％' },
  { code: 'life', label: '생활', icon: '⌂' },
]

function ChatPage() {
  const navigate = useNavigate()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [profile, setProfile] = useState<UserProfile>()
  const [conversationId, setConversationId] = useState<string>()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [category, setCategory] = useState<ChatCategory>()
  const [isLoading, setIsLoading] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [error, setError] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const token = localStorage.getItem('accessToken')

  const handleAuthError = (caught: unknown) => {
    if (caught instanceof ApiError && caught.status === 401) {
      localStorage.removeItem('accessToken')
      localStorage.removeItem('refreshToken')
      navigate('/signup', { replace: true })
      return true
    }
    return false
  }

  const loadConversations = async () => {
    if (!token) return
    try {
      setConversations(await getConversations(token))
    } catch (caught) {
      if (!handleAuthError(caught)) setError('최근 대화를 불러오지 못했어요.')
    }
  }

  useEffect(() => {
    if (!token) {
      navigate('/signup', { replace: true })
      return
    }
    void Promise.all([getConversations(token), getProfile(token)])
      .then(([loadedConversations, loadedProfile]) => {
        setConversations(loadedConversations)
        setProfile(loadedProfile)
      })
      .catch((caught: unknown) => {
        if (caught instanceof ApiError && caught.status === 401) {
          localStorage.removeItem('accessToken')
          localStorage.removeItem('refreshToken')
          navigate('/signup', { replace: true })
        } else {
          setError('최근 대화를 불러오지 못했어요.')
        }
      })
    return () => abortRef.current?.abort()
  }, [navigate, token])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const openConversation = async (id: string) => {
    if (!token || isLoading) return
    setError('')
    try {
      const loaded = await getMessages(id, token)
      setMessages(loaded)
      setConversationId(id)
      setIsSidebarOpen(false)
    } catch (caught) {
      if (!handleAuthError(caught)) setError('대화를 불러오지 못했어요.')
    }
  }

  const newConversation = () => {
    if (isLoading) return
    setConversationId(undefined)
    setMessages([])
    setCategory(undefined)
    setError('')
    setIsSidebarOpen(false)
  }

  const removeConversation = async (id: string) => {
    if (!token || isLoading) return
    try {
      await deleteConversation(id, token)
      setConversations((current) => current.filter((item) => item.id !== id))
      if (conversationId === id) newConversation()
    } catch (caught) {
      if (!handleAuthError(caught)) setError('대화를 삭제하지 못했어요.')
    }
  }

  const sendMessage = async (event?: FormEvent) => {
    event?.preventDefault()
    const message = input.trim()
    if (!message || !token || isLoading) return

    const now = new Date().toISOString()
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: message,
      sources: [],
      createdAt: now,
    }
    const pendingId = `assistant-${Date.now()}`
    const pendingMessage: ChatMessage = {
      id: pendingId,
      role: 'assistant',
      content: '',
      sources: [],
      createdAt: now,
    }
    setMessages((current) => [...current, userMessage, pendingMessage])
    setInput('')
    setError('')
    setIsLoading(true)
    abortRef.current = new AbortController()
    let activeAssistantId = pendingId

    try {
      await streamChat(
        { message, category, conversationId },
        token,
        {
          onMeta: (meta) => {
            setConversationId(meta.conversationId)
            setMessages((current) =>
              current.map((item) =>
                item.id === pendingId ? { ...item, id: meta.messageId } : item,
              ),
            )
            activeAssistantId = meta.messageId
          },
          onChunk: (chunk) => {
            setMessages((current) =>
              current.map((item) =>
                item.id === activeAssistantId
                  ? { ...item, content: item.content + chunk }
                  : item,
              ),
            )
          },
          onSources: (sources) => {
            setMessages((current) =>
              current.map((item, index) =>
                index === current.length - 1 ? { ...item, sources } : item,
              ),
            )
          },
          onDone: () => undefined,
        },
        abortRef.current.signal,
      )
      setCategory(undefined)
      await loadConversations()
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === 'AbortError') return
      if (!handleAuthError(caught)) {
        const messageText =
          caught instanceof ApiError && caught.code === 'SEARCH_SERVICE_UNAVAILABLE'
            ? '검색 서비스에 연결하지 못했어요. 잠시 후 다시 시도해주세요.'
            : '답변을 가져오지 못했어요. 잠시 후 다시 시도해주세요.'
        setMessages((current) =>
          current.map((item, index) =>
            index === current.length - 1 ? { ...item, content: messageText } : item,
          ),
        )
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void sendMessage()
    }
  }

  return (
    <main className="chat-layout">
      <aside className={`chat-sidebar ${isSidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <a className="brand" href="/chat">
            <span className="brand-mark" aria-hidden="true">D</span>
            Donwoly
          </a>
          <button className="icon-button mobile-only" type="button" onClick={() => setIsSidebarOpen(false)} aria-label="메뉴 닫기">×</button>
        </div>
        <button className="new-chat-button" type="button" onClick={newConversation}>＋ 새 대화</button>
        <p className="sidebar-label">최근 대화</p>
        <nav className="conversation-list" aria-label="최근 대화">
          {conversations.length === 0 && <p className="empty-history">아직 대화가 없어요.</p>}
          {conversations.map((item) => (
            <div className={`conversation-item ${conversationId === item.id ? 'active' : ''}`} key={item.id}>
              <button type="button" onClick={() => void openConversation(item.id)}>{item.title}</button>
              <button className="delete-button" type="button" aria-label={`${item.title} 삭제`} onClick={() => void removeConversation(item.id)}>×</button>
            </div>
          ))}
        </nav>
        {profile && (
          <Link className="sidebar-profile" to="/mypage">
            <span aria-hidden="true">{profile.name.slice(0, 1)}</span>
            <div>
              <strong>{profile.name}</strong>
              <small>{profile.region} · {profile.industry}</small>
            </div>
            <b aria-hidden="true">›</b>
          </Link>
        )}
        <button
          className="logout-button"
          type="button"
          onClick={() => {
            localStorage.removeItem('accessToken')
            localStorage.removeItem('refreshToken')
            navigate('/signup', { replace: true })
          }}
        >로그아웃</button>
      </aside>

      {isSidebarOpen && <button className="sidebar-backdrop" type="button" aria-label="메뉴 닫기" onClick={() => setIsSidebarOpen(false)} />}

      <section className="chat-main">
        <header className="chat-header">
          <button className="icon-button mobile-only" type="button" onClick={() => setIsSidebarOpen(true)} aria-label="최근 대화 열기">☰</button>
          <div>
            <strong>워홀 가이드</strong>
            <span><i /> 근거 기반 답변</span>
          </div>
          <div className="header-actions">
            <Link className="mypage-link" to="/mypage" aria-label="마이페이지">내 정보</Link>
            <button className="header-new-button" type="button" onClick={newConversation}>새 대화</button>
          </div>
        </header>

        <div className="message-scroll" aria-live="polite">
          {messages.length === 0 ? (
            <section className="chat-welcome">
              <p className="eyebrow">Australia starts here</p>
              <h1>무엇이든 물어보세요.<br />호주 생활의 첫 달을 함께할게요.</h1>
              <p className="description">회원가입 때 알려준 지역과 업종에 맞춰, 신뢰할 수 있는 문서를 바탕으로 답해드려요.</p>
              <div className="quick-categories" aria-label="빠른 카테고리">
                {CATEGORY_OPTIONS.map((item) => (
                  <button
                    className={category === item.code ? 'selected' : ''}
                    key={item.code}
                    type="button"
                    aria-pressed={category === item.code}
                    onClick={() => setCategory((current) => current === item.code ? undefined : item.code)}
                  >
                    <span aria-hidden="true">{item.icon}</span>
                    {item.label}
                  </button>
                ))}
              </div>
            </section>
          ) : (
            <div className="message-list">
              {messages.map((message) => (
                <article className={`message-row ${message.role}`} key={message.id}>
                  {message.role === 'assistant' && <div className="assistant-avatar" aria-hidden="true">D</div>}
                  <div className="message-content">
                    <div className="message-bubble">
                      {message.content || <span className="typing-indicator"><i /><i /><i /></span>}
                    </div>
                    {message.sources.length > 0 && (
                      <div className="source-list">
                        <p>참고한 출처</p>
                        {message.sources.map((source, index) => (
                          <a href={source.url} target="_blank" rel="noreferrer" key={`${source.title}-${index}`}>
                            <span>{index + 1}</span>
                            {source.title}
                            <b aria-hidden="true">↗</b>
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                </article>
              ))}
              <div ref={endRef} />
            </div>
          )}
        </div>

        <footer className="composer-area">
          {error && <p className="chat-error" role="alert">{error}</p>}
          {category && (
            <button className="selected-category" type="button" onClick={() => setCategory(undefined)}>
              {CATEGORY_OPTIONS.find((item) => item.code === category)?.label} ×
            </button>
          )}
          <form className="chat-composer" onSubmit={(event) => void sendMessage(event)}>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              maxLength={2000}
              rows={1}
              placeholder="호주 워홀에 대해 궁금한 점을 물어보세요"
              aria-label="질문 입력"
              disabled={isLoading}
            />
            <button type="submit" disabled={!input.trim() || isLoading} aria-label="질문 보내기">↑</button>
          </form>
          <p className="composer-hint">Enter로 전송 · Shift + Enter로 줄바꿈</p>
        </footer>
      </section>
    </main>
  )
}

export default ChatPage
