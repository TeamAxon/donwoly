import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const outputDir = path.join(root, 'artifacts', 'ui-review')
const viewports = [
  { name: '375', width: 375, height: 812 },
  { name: '1440', width: 1440, height: 1000 },
]

await mkdir(outputDir, { recursive: true })
const browser = await chromium.launch()
const results = []

for (const viewport of viewports) {
  const context = await browser.newContext({ viewport })
  const page = await context.newPage()

  await page.route('**/api/auth/check-email?**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"available":true}' }),
  )
  await page.route('**/api/auth/signup', (route) =>
    route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        userId: 'onboarding-test-user',
        accessToken: 'onboarding-test-token',
        refreshToken: 'onboarding-test-refresh',
      }),
    }),
  )

  await page.goto('http://127.0.0.1:5173/signup', { waitUntil: 'networkidle' })
  await page.fill('#email', `onboarding-${viewport.name}@example.com`)
  await page.fill('#password', 'Test1234!')
  await page.getByRole('button', { name: '계속하기' }).click()
  await page.fill('#name', '테스트')
  await page.fill('#age', '25')
  await page.getByRole('button', { name: '계속하기' }).click()
  await page.locator('[role="radiogroup"][aria-label="지역"] .option-card').first().click()
  await page.getByRole('button', { name: '계속하기' }).click()
  await page.locator('[role="radiogroup"][aria-label="업종"] .option-card').first().click()
  await page.getByRole('button', { name: '가입 완료' }).click()
  await page.getByRole('heading', { name: '호주 생활 준비를 시작해볼까요?' }).waitFor()

  const metrics = await page.evaluate(() => {
    const shell = document.querySelector('.complete-shell')
    const card = document.querySelector('.complete-card')
    const title = document.querySelector('#complete-title')
    if (
      !(shell instanceof HTMLElement)
      || !(card instanceof HTMLElement)
      || !(title instanceof HTMLElement)
    ) return null
    const shellRect = shell.getBoundingClientRect()
    const cardRect = card.getBoundingClientRect()
    const shellStyle = getComputedStyle(shell)
    const cardStyle = getComputedStyle(card)
    const titleStyle = getComputedStyle(title)
    return {
      shellDisplay: shellStyle.display,
      shellColumns: shellStyle.gridTemplateColumns,
      shellWidth: Math.round(shellRect.width),
      shellHeight: Math.round(shellRect.height),
      placeItems: `${shellStyle.alignItems} ${shellStyle.justifyItems}`,
      cardMarginLeft: cardStyle.marginLeft,
      cardMarginRight: cardStyle.marginRight,
      position: cardStyle.position,
      transform: cardStyle.transform,
      titleWordBreak: titleStyle.wordBreak,
      titleOverflowWrap: titleStyle.overflowWrap,
      horizontalOffset: Math.round(
        cardRect.left + cardRect.width / 2 - (shellRect.left + shellRect.width / 2),
      ),
      verticalOffset: Math.round(
        cardRect.top + cardRect.height / 2 - (shellRect.top + shellRect.height / 2),
      ),
    }
  })

  await page.screenshot({
    path: path.join(outputDir, `onboarding-${viewport.name}.png`),
    fullPage: true,
  })
  results.push({ viewport: viewport.name, ...metrics })
  await context.close()
}

await browser.close()

for (const result of results) {
  if (result.horizontalOffset !== 0 || result.verticalOffset !== 0) {
    throw new Error(`${result.viewport}px onboarding card is not centered`)
  }
  if (result.titleWordBreak !== 'keep-all' || result.titleOverflowWrap !== 'break-word') {
    throw new Error(`${result.viewport}px onboarding title wrapping policy is incorrect`)
  }
}

console.log(JSON.stringify(results, null, 2))
