import { FormEvent, useMemo, useState } from 'react'
import { Navigate, Route, Routes, Link, useNavigate } from 'react-router-dom'
import { ApiError, checkEmail, login as loginRequest, signup } from './api'
import { INDUSTRY_OPTIONS, REGION_OPTIONS } from './constants'
import type { Industry, Region, SignupPayload } from './types'
import './App.css'
import ChatPage from './ChatPage'
import MyPage from './MyPage'

type FormState = Omit<SignupPayload, 'age' | 'region' | 'industry'> & {
  age: string
  region: Region | ''
  industry: Industry | ''
}

const INITIAL_FORM: FormState = {
  email: '',
  password: '',
  name: '',
  age: '',
  region: '',
  industry: '',
}

const STEP_LABELS = ['계정', '프로필', '지역', '업종']
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PASSWORD_PATTERN = /^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/

function SignupPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [form, setForm] = useState<FormState>(INITIAL_FORM)
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isComplete, setIsComplete] = useState(false)

  const progress = useMemo(() => `${((step + 1) / STEP_LABELS.length) * 100}%`, [step])

  const updateField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }))
    setError('')
  }

  const validateStep = (): string => {
    if (step === 0) {
      if (!EMAIL_PATTERN.test(form.email)) return '올바른 이메일 주소를 입력해주세요.'
      if (!PASSWORD_PATTERN.test(form.password)) {
        return '비밀번호는 8자 이상이며 영문, 숫자, 특수문자를 포함해야 해요.'
      }
    }
    if (step === 1) {
      const age = Number(form.age)
      if (form.name.trim().length < 2 || form.name.trim().length > 20) {
        return '이름은 2자 이상 20자 이하로 입력해주세요.'
      }
      if (!Number.isInteger(age) || age < 18 || age > 99) {
        return '나이는 18세 이상 99세 이하로 입력해주세요.'
      }
    }
    if (step === 2 && !form.region) return '지역을 하나 선택해주세요.'
    if (step === 3 && !form.industry) return '업종을 하나 선택해주세요.'
    return ''
  }

  const handleNext = async (event: FormEvent) => {
    event.preventDefault()
    const validationError = validateStep()
    if (validationError) {
      setError(validationError)
      return
    }

    setIsLoading(true)
    setError('')
    try {
      if (step === 0) {
        const available = await checkEmail(form.email.trim().toLowerCase())
        if (!available) {
          setError('이미 사용 중인 이메일이에요.')
          return
        }
      }

      if (step < STEP_LABELS.length - 1) {
        setStep((current) => current + 1)
        return
      }

      const result = await signup({
        email: form.email.trim().toLowerCase(),
        password: form.password,
        name: form.name.trim(),
        age: Number(form.age),
        region: form.region as Region,
        industry: form.industry as Industry,
      })
      localStorage.setItem('accessToken', result.accessToken)
      localStorage.setItem('refreshToken', result.refreshToken)
      setIsComplete(true)
    } catch (caught) {
      console.error('[signup] 회원가입 API 요청 실패', caught)
      if (caught instanceof ApiError && caught.code === 'EMAIL_TAKEN') {
        setStep(0)
        setError('이미 사용 중인 이메일이에요.')
      } else if (caught instanceof ApiError && caught.code === 'VALIDATION_ERROR') {
        setError('입력한 정보를 다시 확인해주세요.')
      } else {
        setError('서버에 연결하지 못했어요. 잠시 후 다시 시도해주세요.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  if (isComplete) {
    return (
      <main className="signup-shell">
        <section className="signup-card complete-card" aria-labelledby="complete-title">
          <div className="complete-icon" aria-hidden="true">✓</div>
          <p className="eyebrow">가입 완료</p>
          <h1 id="complete-title">호주 생활 준비를 시작해볼까요?</h1>
          <p className="description">
            {form.name.trim()}님의 지역과 업종에 맞는 정보를 준비했어요.
          </p>
          <button className="primary-button" type="button" onClick={() => navigate('/chat')}>
            챗봇 시작하기
          </button>
        </section>
      </main>
    )
  }

  return (
    <main className="signup-shell">
      <section className="signup-card" aria-labelledby="signup-title">
        <header className="signup-header">
          <a className="brand" href="/signup" aria-label="Donwoly 회원가입 처음으로">
            <span className="brand-mark" aria-hidden="true">D</span>
            Donwoly
          </a>
          <div className="step-meta">
            <span>{step + 1} / {STEP_LABELS.length}</span>
            <span>{STEP_LABELS[step]}</span>
          </div>
          <div className="progress-track" aria-label={`회원가입 ${step + 1}단계`}>
            <span className="progress-value" style={{ width: progress }} />
          </div>
        </header>

        <form onSubmit={handleNext} noValidate>
          {step === 0 && (
            <div className="step-content">
              <p className="eyebrow">반가워요</p>
              <h1 id="signup-title">로그인에 사용할<br />정보를 알려주세요</h1>
              <p className="description">이메일 인증 없이 바로 시작할 수 있어요.</p>
              <label className="field-label" htmlFor="email">이메일</label>
              <input
                id="email"
                className="text-input"
                type="email"
                autoComplete="email"
                placeholder="name@example.com"
                value={form.email}
                onChange={(event) => updateField('email', event.target.value)}
                autoFocus
              />
              <label className="field-label" htmlFor="password">비밀번호</label>
              <input
                id="password"
                className="text-input"
                type="password"
                autoComplete="new-password"
                placeholder="영문, 숫자, 특수문자 포함 8자 이상"
                value={form.password}
                onChange={(event) => updateField('password', event.target.value)}
              />
            </div>
          )}

          {step === 1 && (
            <div className="step-content">
              <p className="eyebrow">프로필</p>
              <h1 id="signup-title">어떻게 불러드릴까요?</h1>
              <p className="description">나이에 맞는 워홀 정보를 안내해드릴게요.</p>
              <label className="field-label" htmlFor="name">이름</label>
              <input
                id="name"
                className="text-input"
                type="text"
                autoComplete="name"
                maxLength={20}
                placeholder="이름을 입력해주세요"
                value={form.name}
                onChange={(event) => updateField('name', event.target.value)}
                autoFocus
              />
              <label className="field-label" htmlFor="age">나이</label>
              <input
                id="age"
                className="text-input"
                type="number"
                inputMode="numeric"
                min="18"
                max="99"
                placeholder="만 나이를 입력해주세요"
                value={form.age}
                onChange={(event) => updateField('age', event.target.value)}
              />
              <p className="field-hint">워홀 비자는 국적에 따라 일반적으로 만 30세 또는 35세까지 신청할 수 있어요.</p>
            </div>
          )}

          {step === 2 && (
            <div className="step-content">
              <p className="eyebrow">지역 선택</p>
              <h1 id="signup-title">어디에서 지낼 예정인가요?</h1>
              <p className="description">지역에 맞는 생활 정보를 우선해서 보여드릴게요.</p>
              <div className="option-grid" role="radiogroup" aria-label="지역">
                {REGION_OPTIONS.map((option) => (
                  <button
                    key={option.code}
                    className={`option-card ${form.region === option.code ? 'selected' : ''}`}
                    type="button"
                    role="radio"
                    aria-checked={form.region === option.code}
                    onClick={() => updateField('region', option.code)}
                  >
                    <span>{option.label}</span>
                    <span className="option-check" aria-hidden="true">✓</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="step-content">
              <p className="eyebrow">업종 선택</p>
              <h1 id="signup-title">어떤 일을 찾고 있나요?</h1>
              <p className="description">관심 업종에 필요한 노동법과 세금 정보를 맞춰드릴게요.</p>
              <div className="option-grid industry-grid" role="radiogroup" aria-label="업종">
                {INDUSTRY_OPTIONS.map((option) => (
                  <button
                    key={option.code}
                    className={`option-card ${form.industry === option.code ? 'selected' : ''}`}
                    type="button"
                    role="radio"
                    aria-checked={form.industry === option.code}
                    onClick={() => updateField('industry', option.code)}
                  >
                    <span>{option.label}</span>
                    <span className="option-check" aria-hidden="true">✓</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="form-footer">
            <p className="error-message" role="alert" aria-live="polite">{error}</p>
            <div className="button-row">
              {step > 0 && (
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => { setStep((current) => current - 1); setError('') }}
                  disabled={isLoading}
                >
                  이전
                </button>
              )}
              <button className="primary-button" type="submit" disabled={isLoading}>
                {isLoading ? '확인 중...' : step === STEP_LABELS.length - 1 ? '가입 완료' : '계속하기'}
              </button>
            </div>
          </div>
          {step === 0 && (
            <p className="auth-switch">이미 계정이 있나요? <Link to="/login">로그인</Link></p>
          )}
        </form>
      </section>
      <aside className="signup-aside" aria-hidden="true">
        <div className="sun-shape" />
        <p>Australia<br />starts here.</p>
        <span>지역과 일에 맞춘 워홀 가이드</span>
      </aside>
    </main>
  )
}

function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const submitLogin = async (event: FormEvent) => {
    event.preventDefault()
    if (!EMAIL_PATTERN.test(email)) {
      setError('올바른 이메일 주소를 입력해주세요.')
      return
    }
    if (!password) {
      setError('비밀번호를 입력해주세요.')
      return
    }

    setIsLoading(true)
    setError('')
    try {
      const result = await loginRequest(email.trim().toLowerCase(), password)
      localStorage.setItem('accessToken', result.accessToken)
      localStorage.setItem('refreshToken', result.refreshToken)
      navigate('/chat', { replace: true })
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === 'INVALID_CREDENTIALS') {
        setError('이메일 또는 비밀번호가 올바르지 않아요.')
      } else {
        setError('서버에 연결하지 못했어요. 잠시 후 다시 시도해주세요.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="signup-shell">
      <section className="signup-card login-card" aria-labelledby="login-title">
        <header className="signup-header">
          <Link className="brand" to="/login">
            <span className="brand-mark" aria-hidden="true">D</span>
            Donwoly
          </Link>
        </header>
        <form onSubmit={submitLogin} noValidate>
          <div className="step-content">
            <p className="eyebrow">다시 만나서 반가워요</p>
            <h1 id="login-title">내 워홀 가이드를<br />이어서 만나보세요</h1>
            <p className="description">가입할 때 입력한 이메일로 로그인해주세요.</p>
            <label className="field-label" htmlFor="login-email">이메일</label>
            <input
              id="login-email"
              className="text-input"
              type="email"
              autoComplete="email"
              placeholder="name@example.com"
              value={email}
              onChange={(event) => { setEmail(event.target.value); setError('') }}
              autoFocus
            />
            <label className="field-label" htmlFor="login-password">비밀번호</label>
            <input
              id="login-password"
              className="text-input"
              type="password"
              autoComplete="current-password"
              placeholder="비밀번호를 입력해주세요"
              value={password}
              onChange={(event) => { setPassword(event.target.value); setError('') }}
            />
          </div>
          <div className="form-footer">
            <p className="error-message" role="alert" aria-live="polite">{error}</p>
            <button className="primary-button full-button" type="submit" disabled={isLoading}>
              {isLoading ? '로그인 중...' : '로그인'}
            </button>
          </div>
          <p className="auth-switch">아직 계정이 없나요? <Link to="/signup">회원가입</Link></p>
        </form>
      </section>
      <aside className="signup-aside" aria-hidden="true">
        <div className="sun-shape" />
        <p>Your guide<br />remembers.</p>
        <span>나에게 맞춘 호주 생활을 이어가세요</span>
      </aside>
    </main>
  )
}

function App() {
  const hasToken = Boolean(localStorage.getItem('accessToken'))
  return (
    <Routes>
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/chat" element={<ChatPage />} />
      <Route path="/mypage" element={<MyPage />} />
      <Route path="*" element={<Navigate to={hasToken ? '/chat' : '/login'} replace />} />
    </Routes>
  )
}

export default App
