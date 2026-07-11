import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const outputDir = path.join(root, 'artifacts', 'ui-review')
const viewports = [
  { name: '375', width: 375, height: 812 },
  { name: '768', width: 768, height: 1024 },
  { name: '1440', width: 1440, height: 1000 },
]

await mkdir(outputDir, { recursive: true })
const browser = await chromium.launch()
const results = []

for (const viewport of viewports) {
  const context = await browser.newContext({ viewport })
  const page = await context.newPage()

  await page.goto('http://127.0.0.1:5173/signup', { waitUntil: 'networkidle' })
  await page.waitForTimeout(350)
  const signupMetrics = await page.evaluate(() => ({
    viewport: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    font: getComputedStyle(document.body).fontFamily,
  }))
  await page.screenshot({
    path: path.join(outputDir, `signup-${viewport.name}.png`),
    fullPage: true,
  })

  await page.addInitScript(() => localStorage.setItem('accessToken', 'visual-test-token'))
  await page.route('**/api/chat/conversations', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
  )
  await page.route('**/api/users/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'visual-user',
        email: 'hello@donwoly.app',
        name: '워홀러',
        age: 25,
        region: 'sydney',
        industry: 'hospitality',
      }),
    }),
  )
  await page.goto('http://127.0.0.1:5173/chat', { waitUntil: 'networkidle' })
  const chatMetrics = await page.evaluate(() => {
    const parent = document.querySelector('.message-scroll')?.getBoundingClientRect()
    const welcome = document.querySelector('.chat-welcome')?.getBoundingClientRect()
    return {
      viewport: window.innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
      centerOffset: parent && welcome
        ? Math.round((welcome.left + welcome.width / 2) - (parent.left + parent.width / 2))
        : null,
    }
  })
  await page.screenshot({
    path: path.join(outputDir, `chat-${viewport.name}.png`),
    fullPage: true,
  })

  results.push({ viewport: viewport.name, signup: signupMetrics, chat: chatMetrics })
  await context.close()
}

await browser.close()

for (const result of results) {
  if (result.signup.scrollWidth > result.signup.viewport) {
    throw new Error(`signup ${result.viewport}px: horizontal overflow detected`)
  }
  if (result.chat.scrollWidth > result.chat.viewport) {
    throw new Error(`chat ${result.viewport}px: horizontal overflow detected`)
  }
  if (result.chat.centerOffset !== 0) {
    throw new Error(`chat ${result.viewport}px: welcome center offset ${result.chat.centerOffset}px`)
  }
}

console.log(JSON.stringify(results, null, 2))
