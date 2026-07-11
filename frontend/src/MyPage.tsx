import { FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError, getProfile, updateProfile } from './api'
import { INDUSTRY_OPTIONS, REGION_OPTIONS } from './constants'
import type { Industry, Region, UserProfile } from './types'
import './MyPage.css'


function MyPage() {
  const navigate = useNavigate()
  const token = localStorage.getItem('accessToken')
  const [profile, setProfile] = useState<UserProfile>()
  const [name, setName] = useState('')
  const [age, setAge] = useState('')
  const [region, setRegion] = useState<Region>()
  const [industry, setIndustry] = useState<Industry>()
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    document.title = '마이페이지 | Donwoly'
    if (!token) {
      navigate('/login', { replace: true })
      return
    }
    void getProfile(token)
      .then((loaded) => {
        setProfile(loaded)
        setName(loaded.name)
        setAge(String(loaded.age))
        setRegion(loaded.region)
        setIndustry(loaded.industry)
      })
      .catch((caught: unknown) => {
        if (caught instanceof ApiError && caught.status === 401) {
          localStorage.removeItem('accessToken')
          localStorage.removeItem('refreshToken')
          navigate('/login', { replace: true })
        } else {
          setError('프로필을 불러오지 못했어요.')
        }
      })
      .finally(() => setIsLoading(false))
  }, [navigate, token])

  const saveProfile = async (event: FormEvent) => {
    event.preventDefault()
    const normalizedName = name.trim()
    const parsedAge = Number(age)
    if (normalizedName.length < 2 || normalizedName.length > 20) {
      setError('이름은 2자 이상 20자 이하로 입력해주세요.')
      return
    }
    if (!Number.isInteger(parsedAge) || parsedAge < 18 || parsedAge > 99) {
      setError('나이는 18세 이상 99세 이하로 입력해주세요.')
      return
    }
    if (!region || !industry || !token) {
      setError('지역과 업종을 선택해주세요.')
      return
    }

    setIsSaving(true)
    setError('')
    setSuccess('')
    try {
      const updated = await updateProfile(
        { name: normalizedName, age: parsedAge, region, industry },
        token,
      )
      setProfile(updated)
      setSuccess('프로필을 저장했어요. 다음 답변부터 바로 반영돼요.')
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        localStorage.removeItem('accessToken')
        localStorage.removeItem('refreshToken')
        navigate('/login', { replace: true })
      } else {
        setError('프로필을 저장하지 못했어요. 잠시 후 다시 시도해주세요.')
      }
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <main className="mypage-shell">
      <header className="mypage-header">
        <Link className="brand" to="/chat">
          <span className="brand-mark" aria-hidden="true">D</span>
          Donwoly
        </Link>
        <Link className="back-to-chat" to="/chat">← 챗봇으로 돌아가기</Link>
      </header>

      <section className="mypage-content">
        <div className="mypage-intro">
          <p className="eyebrow">My profile</p>
          <h1>나에게 맞는 워홀 정보로<br />더 정확하게 안내할게요.</h1>
          <p className="description">변경한 정보는 다음 챗봇 답변부터 바로 반영됩니다.</p>
        </div>

        {isLoading ? (
          <div className="profile-card profile-loading" aria-label="프로필 불러오는 중">프로필을 불러오고 있어요...</div>
        ) : profile ? (
          <form className="profile-card" onSubmit={saveProfile}>
            <div className="profile-avatar" aria-hidden="true">{profile.name.slice(0, 1)}</div>
            <div className="profile-heading">
              <strong>{profile.name}님</strong>
              <span>{profile.email}</span>
            </div>

            <div className="profile-fields">
              <div>
                <label className="field-label" htmlFor="profile-email">이메일</label>
                <input id="profile-email" className="text-input" value={profile.email} disabled />
              </div>
              <div>
                <label className="field-label" htmlFor="profile-name">이름</label>
                <input id="profile-name" className="text-input" value={name} maxLength={20} onChange={(event) => { setName(event.target.value); setSuccess('') }} />
              </div>
              <div>
                <label className="field-label" htmlFor="profile-age">나이</label>
                <input id="profile-age" className="text-input" type="number" min="18" max="99" value={age} onChange={(event) => { setAge(event.target.value); setSuccess('') }} />
              </div>
            </div>

            <fieldset className="profile-options">
              <legend>지역</legend>
              <div className="profile-option-grid">
                {REGION_OPTIONS.map((option) => (
                  <button key={option.code} type="button" className={region === option.code ? 'selected' : ''} aria-pressed={region === option.code} onClick={() => { setRegion(option.code); setSuccess('') }}>
                    {option.label}
                  </button>
                ))}
              </div>
            </fieldset>

            <fieldset className="profile-options">
              <legend>관심 업종</legend>
              <div className="profile-option-grid industry-options">
                {INDUSTRY_OPTIONS.map((option) => (
                  <button key={option.code} type="button" className={industry === option.code ? 'selected' : ''} aria-pressed={industry === option.code} onClick={() => { setIndustry(option.code); setSuccess('') }}>
                    {option.label}
                  </button>
                ))}
              </div>
            </fieldset>

            <div className="profile-feedback" aria-live="polite">
              {error && <p className="profile-error" role="alert">{error}</p>}
              {success && <p className="profile-success">{success}</p>}
            </div>
            <button className="primary-button save-profile" type="submit" disabled={isSaving}>
              {isSaving ? '저장 중...' : '변경사항 저장'}
            </button>
          </form>
        ) : (
          <div className="profile-card profile-loading">
            <p>{error || '프로필을 표시할 수 없어요.'}</p>
            <button type="button" className="secondary-button" onClick={() => window.location.reload()}>다시 시도</button>
          </div>
        )}
      </section>
    </main>
  )
}

export default MyPage
