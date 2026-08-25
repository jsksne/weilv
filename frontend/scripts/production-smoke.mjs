/**
 * Release Readiness — Production runtime smoke helper.
 *
 * 验证 Production 前端：boot 非 Demo、API-only、无 fixture fallback。
 * 用法（需要 backend/ES 环境与 VITE_UI_MODE=production 的 dev/build 服务）：
 *   node scripts/production-smoke.mjs <appUrl> [apiBaseUrl]
 * 输出：mode 判定、API 请求摘要、console 摘要、错误态文本。
 */
import puppeteer from 'puppeteer-core'
import { existsSync, readdirSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

function findExecutable() {
  if (process.env.PUPPETEER_EXECUTABLE_PATH) return process.env.PUPPETEER_EXECUTABLE_PATH
  const candidates = []
  const playwrightRoot = join(homedir(), 'AppData', 'Local', 'ms-playwright')
  if (existsSync(playwrightRoot)) {
    for (const entry of readdirSync(playwrightRoot)) {
      const exe = join(playwrightRoot, entry, 'chrome-win64', 'chrome.exe')
      if (existsSync(exe)) candidates.push(exe)
    }
  }
  candidates.push('C:/Program Files/Google/Chrome/Application/chrome.exe')
  for (const candidate of candidates) if (existsSync(candidate)) return candidate
  throw new Error('未找到 Chromium 可执行文件（可用 PUPPETEER_EXECUTABLE_PATH 指定）。')
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
const apiRequests = []
page.on('console', msg => consoleMessages.push(`${msg.type()}: ${msg.text()}`))
page.on('request', req => {
  if (req.url().includes(apiHost)) {
    apiRequests.push(`${req.method()} ${req.url().replace(`http://${apiHost}`, '')}`)
  }
})
await page.goto(appUrl, { waitUntil: 'networkidle0' })
await new Promise(resolve => setTimeout(resolve, 1500))

const state = await page.evaluate(() => {
  const error = document.querySelector('[data-testid="ui-data-error"]')
  return {
    title: document.title,
    hasShell: !!document.querySelector('nav.navbar'),
    hasHero: !!document.querySelector('.hero'),
    taskCards: document.querySelectorAll('.task-card').length,
    hasDemoBadge: !!document.querySelector('[data-testid="demo-badge"]'),
    errorText: error ? error.textContent.trim() : null,
  }
})

const fatalErrors = consoleMessages.filter(
  m => m.startsWith('error') && !m.includes('ERR_CONNECTION_REFUSED') && !m.includes('Failed to load resource'),
)
const summary = {
  mode: state.hasDemoBadge || state.hasHero || state.taskCards > 0 ? 'DEMO_OR_FIXTURE' : 'PRODUCTION',
  state,
  apiRequestCount: apiRequests.length,
  apiRequests: apiRequests.slice(0, 12),
  consoleCount: consoleMessages.length,
  fatalErrors,
}
console.log(JSON.stringify(summary, null, 2))
await browser.close()
