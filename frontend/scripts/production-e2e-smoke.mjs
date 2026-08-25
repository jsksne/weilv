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
let agenticStreamBody = null
let agenticStreamResolve = null
const agenticStreamReady = new Promise(resolve => {
  agenticStreamResolve = resolve
})
page.on('console', msg => consoleMessages.push(`${msg.type()}: ${msg.text()}`))
page.on('response', res => {
  const url = res.url()
  if (url.includes(apiHost)) {
    network.push(`${res.request().method()} ${url.replace(`http://${apiHost}`, '').split('?')[0]} -> ${res.status()}`)
  }
  // B3：捕获真实 stream 响应体作为时间顺序 trace evidence（stage/label/相对时间）。
  if (url.includes('/api/v1/recommend/agentic/stream')) {
    res
      .text()
      .then(text => {
        agenticStreamBody = text
      })
      .catch(() => {})
      .finally(() => agenticStreamResolve?.())
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

// Assistant（真实 agentic，等待真实新响应完成或真实 error）
await click('nav .tab[data-view="assistant"]')
await new Promise(r => setTimeout(r, 800))
await page.type('[data-testid="chat-input"]', '我写作业快一个小时了，现在有10分钟休息。')
await click('[data-testid="chat-submit"]')
let assistantDone = false
try {
  await page.waitForFunction(
    () => document.querySelector('[data-testid="answer-card"]') || document.querySelector('[data-testid="agentic-error"]'),
    { timeout: 90000 },
  )
  assistantDone = true
} catch {
  assistantDone = false
}
await new Promise(r => setTimeout(r, 500))
result.assistantReply = await page.evaluate(() => {
  const error = document.querySelector('[data-testid="agentic-error"]')
  if (error) return `ERROR: ${error.textContent.slice(0, 120)}`
  return document.querySelector('.ask-wrap')?.innerText.slice(0, 200) ?? null
})
result.assistantDone = assistantDone

/* ---------- B3：真实 trace evidence（只保留 stage / label / 相对时间） ---------- */
await Promise.race([agenticStreamReady, new Promise(r => setTimeout(r, 15000))])
if (agenticStreamBody) {
  result.agenticTrace = agenticStreamBody
    .trim()
    .split('\n')
    .map(line => JSON.parse(line))
    .map(event => ({
      stage: event.stage,
      label: event.label,
      timestamp_ms: event.timestamp_ms,
    }))
  const completed = result.agenticTrace.find(event => event.stage === 'completed')
  result.agenticDurationMs = completed?.timestamp_ms ?? null
}
const agenticStreamCalls = network.filter(
  line => line.startsWith('POST ') && line.includes('/agentic/stream') && line.includes('-> 200'),
).length
const oldAgenticCalls = network.filter(line => line.startsWith('POST ') && line.includes('/recommend/agentic ->')).length

result.fatalErrors = consoleMessages.filter(
  m => m.startsWith('error') && !m.includes('ERR_CONNECTION_REFUSED') && !m.includes('Failed to load resource'),
)
result.network = network

/* ---------- hard gate assertions ---------- */
const failures = []
const code = (path, status) => network.find(line => line.includes(path) && line.includes(`-> ${status}`))
if (result.mode !== 'PRODUCTION') failures.push('mode !== PRODUCTION')
if (result.taskCards < 1) failures.push('taskCards < 1 (B1)')
if (!code('/api/v1/recommendations', 200) && !code('/api/v1/recommend/agentic', 200)) failures.push('no recommendation 200')
if (!network.some(line => line.includes('/events') && line.includes('-> 200'))) failures.push('task event not 200 (B2)')
if (!code('/memories', 200)) failures.push('memories not 200 (B4)')
if (!code('/weekly', 200)) failures.push('weekly not 200 (B5)')
if (!network.some(line => line.includes('/recommend/agentic') && line.includes('-> 200'))) failures.push('agentic not 200')
if (!result.assistantDone) failures.push('assistant final answer not rendered (or error state)')
if (result.fatalErrors.length > 0) failures.push(`fatal console errors: ${result.fatalErrors.join(' | ')}`)
if (result.assistantReply && result.assistantReply.startsWith('ERROR:')) failures.push(`assistant error: ${result.assistantReply}`)
/* B3 单次执行 gate：一次 submit = 一次 stream Agentic 执行，无第二次旧 endpoint 调用 */
if (agenticStreamCalls !== 1) failures.push(`agentic stream calls != 1: ${agenticStreamCalls}`)
if (oldAgenticCalls !== 0) failures.push(`old /recommend/agentic called ${oldAgenticCalls} times (double-run)`)
if (!result.agenticTrace?.some(event => event.stage === 'completed')) failures.push('stream missing completed event')
if (result.agenticTrace?.some(event => event.stage === 'error')) failures.push('stream contained sanitized error event')
const traceTimes = (result.agenticTrace ?? []).map(event => event.timestamp_ms ?? 0)
for (let index = 1; index < traceTimes.length; index += 1) {
  if (traceTimes[index] < traceTimes[index - 1]) failures.push(`trace timestamps not monotonic at ${index}`)
}

console.log(JSON.stringify(result, null, 2))
await browser.close()
if (failures.length > 0) {
  console.error('PRODUCTION E2E GATE FAILED:')
  for (const failure of failures) console.error(`  - ${failure}`)
  process.exitCode = 1
} else {
  console.log('PRODUCTION E2E GATE: PASS')
}
