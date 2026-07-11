import type { Industry, Region } from './types'

export const REGION_OPTIONS: { code: Region; label: string }[] = [
  { code: 'SYDNEY', label: '⭐ 시드니 (Sydney, NSW)' },
  { code: 'MELBOURNE', label: '⭐ 멜버른 (Melbourne, VIC)' },
  { code: 'BRISBANE', label: '⭐ 브리즈번 (Brisbane, QLD)' },
  { code: 'PERTH', label: '⭐ 퍼스 (Perth, WA)' },
  { code: 'GOLD_COAST', label: '⭐ 골드코스트 (Gold Coast, QLD)' },
  { code: 'OTHER', label: '기타 지역' },
]

export const INDUSTRY_OPTIONS: { code: Industry; label: string }[] = [
  { code: 'FARM', label: '🌾 농장/과수원' },
  { code: 'HOSPITALITY', label: '☕ 카페/레스토랑/바' },
  { code: 'CONSTRUCTION', label: '🏗️ 건설/현장' },
  { code: 'CLEANING', label: '🧹 청소/하우스키핑' },
  { code: 'FACTORY', label: '🏭 공장/육가공' },
  { code: 'OFFICE', label: '💼 사무직/인턴' },
  { code: 'TOURISM', label: '🧳 관광/투어' },
  { code: 'OTHER', label: '기타' },
]
