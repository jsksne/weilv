/**
 * Production E2E runtime smoke（真实 backend + ES + DashScope）。
 *
 * 流程：boot → B6 onboarding（consent OFF）→ PUT /profile → Today(B1) →
 * task action(B2) → Profile Memory(B4) → Weekly(B5) → Assistant(agentic)。
 * 输出：mode 判定、network summary（method/path/status）、页面断言、console 摘要。
 * 用法：node scripts/production-e2e-smoke.mjs <appUrl> [apiHost]
 */
import puppeteer from 'puppeteer-core'
import { existsSync, readdirSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

function findExecutable() {
  if (process.env.PUPPETEER_EXECUTABLE_PATH) return process.env.PUPPETEER_EXECUTABLE_PATH
  const root = join(homedir(), 'AppData', 'Local', 'ms-playwright')
  if (existsSync(root)) {
    for (const entry of readdirSync(root)) {
      const exe = join(root, entry, 'chrome-win64', 'chrome.exe')
      if (existsSync(exe)) return exe
    }
  }
  throw new Error('未找到 Chromium 可执行文件。')
}

const appUrl = process.argv[2] ?? 'http://localhost:5173/'
const apiHost = process.argv[3] ?? '127.0.0.1:8000'

const browser = await puppeteer.launch({
  executablePath: findExecutable(),
  headless: true,
  args: ['--disable-gpu', '--no-sandbox'],
})
const page = await browser.newPage()
const consoleMessages = []
const network = []
page.on('console', msg => consoleMessages.push(`${msg.type()}: ${msg.text()}`))
page.on('response', res => {
  const url = res.url()
  if (url.includes(apiHost)) {
    network.push(`${res.request().method()} ${url.replace(`http://${apiHost}`, '').split('?')[0]} -> ${res.status()}`)
  }
})

async function click(selector) {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const el = await page.$(selector)
    if (!el) throw new Error(`missing selector: ${selector}`)
    try {
      await el.evaluate(node => node.click())
      return
    } catch {
      await new Promise(r => setTimeout(r, 500))
    }
  }
  throw new Error(`could not click: ${selector}`)
}

async function waitFor(selector, ms = 30000) {
  await page.waitForSelector(selector, { timeout: ms })
}

async function completeOnboarding() {
  await waitFor('[data-testid="onboarding"]', 10000)
  await click('[data-action="onboarding-next"]') // welcome → basics
  await waitFor('[data-option="junior_high"]')
  await click('[data-option="junior_high"]') // grade
  await click('[data-action="onboarding-next"]') // basics → issues
  await waitFor('[data-option="tired_eyes"]', 5000)
  await click('[data-action="onboarding-next"]') // issues → behavior
  await waitFor('[data-option="under_3"]', 5000)
  await click('[data-action="onboarding-next"]') // behavior → generation
  await waitFor('[data-action="onboarding-consent"]', 5000)
  // consent 保持 OFF（memory_enabled=false 用户）
  await click('[data-action="onboarding-next"]') // 进入微律 → PUT /profile
  await page.waitForSelector('[data-testid="onboarding"]', { hidden: true, timeout: 30000 })
  await waitFor('nav.navbar', 30000)
}

await page.goto(appUrl, { waitUntil: 'networkidle0' })
await new Promise(r => setTimeout(r, 1200))

const result = {}

if (await page.$('[data-testid="onboarding"]')) {
  result.onboarding = 'SHOWN (new user 404)'
  await completeOnboarding()
  result.onboarding = 'COMPLETED (PUT /profile)'
} else {
  result.onboarding = 'NOT_SHOWN (profile exists)'
}

await waitFor('nav.navbar', 30000)
result.mode = (await page.$('[data-testid="demo-badge"]')) ? 'DEMO' : 'PRODUCTION'
result.defaultToday = await page.evaluate(() =>
  document.querySelector('[data-view="today"]')?.classList.contains('active'),
)

// B1 Today
await new Promise(r => setTimeout(r, 2000))
result.taskCards = await page.evaluate(() => document.querySelectorAll('.task-card').length)
result.todayStatus = await page.evaluate(() =>
  document.querySelector('[data-testid="today-production-status"]')?.textContent?.slice(0, 80) ?? null,
)

// B2 task action
if (result.taskCards > 0) {
  await click('.task-card [data-act="start"]')
  await new Promise(r => setTimeout(r, 1500))
  result.taskActionPosted = network.filter(n => n.includes('/events')).length
}

// B4 Profile memory
await click('nav .tab[data-view="profile"]')
await new Promise(r => setTimeout(r, 1500))
result.profileView = await page.evaluate(() => !!document.querySelector('[data-testid="profile-view"]'))
result.memorySection = await page.evaluate(() => {
  const m = document.querySelector('[data-profile-section="memory"]')
  return m ? m.textContent.replace(/\s+/g, ' ').slice(0, 120) : null
})

// B5 Weekly
await click('nav .tab[data-view="weekly"]')
await new Promise(r => setTimeout(r, 1500))
result.weeklyView = await page.evaluate(() => !!document.querySelector('[data-testid="weekly-view"]'))
result.weeklyUnavailable = await page.evaluate(() => !!document.querySelector('[data-testid="weekly-unavailable"]'))

// Assistant（真实 agentic）
await click('nav .tab[data-view="assistant"]')
await new Promise(r => setTimeout(r, 800))
await page.type('[data-testid="chat-input"]', '我写作业快一个小时了，现在有10分钟休息。')
await click('[data-testid="chat-submit"]')
await page.waitForFunction(
  () => document.querySelectorAll('.ask-message').length >= 2 || document.querySelector('[data-testid="agentic-error"]'),
  { timeout: 90000 },
).catch(() => {})
await new Promise(r => setTimeout(r, 1000))
result.assistantReply = await page.evaluate(() => {
  const error = document.querySelector('[data-testid="agentic-error"]')
  if (error) return `ERROR: ${error.textContent.slice(0, 120)}`
  return document.querySelector('.ask-wrap')?.innerText.slice(0, 200) ?? null
})

result.fatalErrors = consoleMessages.filter(
  m => m.startsWith('error') && !m.includes('ERR_CONNECTION_REFUSED') && !m.includes('Failed to load resource'),
)
result.network = network
console.log(JSON.stringify(result, null, 2))
await browser.close()
