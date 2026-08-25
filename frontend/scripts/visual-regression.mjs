/**
 * 微律 UI Migration · Sprint 10 Visual Regression Gate
 *
 * 可重复执行的视觉对比机制。参数固定（见 release-checklist）：
 *   - Browser: Chromium headless（自动探测 ms-playwright chromium 或 Edge/Chrome）
 *   - Viewports: 1080/960/720/560 × 固定高 900
 *   - deviceScaleFactor: 1, zoom: 1
 *   - fonts: await document.fonts.ready + networkidle
 *   - animation determinism: 注入 `animation:none;transition:none` +
 *     prefers-reduced-motion: reduce（CDP Emulation.setEmulatedMedia）
 *   - 无随机种子需求：动画被冻结后画面确定
 *
 * 用法：
 *   node scripts/visual-regression.mjs capture --url <app|prototype> --out <dir> [--prototype]
 *   node scripts/visual-regression.mjs diff --baseline <dir> --candidate <dir> --out <dir>
 */
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { PNG } from 'pngjs'
import pixelmatch from 'pixelmatch'
import puppeteer from 'puppeteer-core'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const VIEWPORTS = [
  { width: 1080, height: 900, label: '1080' },
  { width: 960, height: 900, label: '960' },
  { width: 720, height: 900, label: '720' },
  { width: 560, height: 900, label: '560' },
]
const PAGES = ['today', 'assistant', 'profile', 'weekly']
const FROZEN_CSS = `
  *, *::before, *::after {
    animation: none !important;
    transition: none !important;
    scroll-behavior: auto !important;
  }
`

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
  candidates.push(
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  )
  for (const candidate of candidates) if (existsSync(candidate)) return candidate
  throw new Error('未找到可用的 Chromium/Chrome 可执行文件（可用 PUPPETEER_EXECUTABLE_PATH 指定）。')
}

async function launch() {
  const browser = await puppeteer.launch({
    executablePath: findExecutable(),
    headless: true,
    args: ['--disable-gpu', '--no-sandbox', '--force-color-profile=srgb'],
  })
  return browser
}

async function newDeterministicPage(browser) {
  const page = await browser.newPage()
  await page.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: 'reduce' }])
  await page.setViewport({ width: 1080, height: 900, deviceScaleFactor: 1 })
  await page.evaluateOnNewDocument((css) => {
    const style = document.createElement('style')
    style.textContent = css
    document.documentElement.appendChild(style)
  }, FROZEN_CSS)
  return page
}

async function waitReady(page) {
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
  })
  await new Promise(resolve => setTimeout(resolve, 300))
}

async function captureApp(page, outDir) {
  // 每个 viewport 独立：清 demo 完成标记 → reload → Onboarding Step 1 → skip → 四页面
  for (const { width, height, label } of VIEWPORTS) {
    await page.setViewport({ width, height, deviceScaleFactor: 1 })
    await page.evaluate(() => {
      try { localStorage.removeItem('wl_aurora_onboarded') } catch { /* noop */ }
    })
    await page.reload({ waitUntil: 'networkidle0' })
    await waitReady(page)

    if (await page.$('[data-testid="onboarding"]')) {
      const file = join(outDir, `onboarding-step1-${label}.png`)
      await page.screenshot({ path: file })
      console.log('captured', file)
    }
    const skip = await page.$('[data-action="onboarding-skip"]')
    if (skip) await skip.click()
    // 等待 onboarding 关闭计时器（850ms）完成，避免 overlay 关闭竞态导致画面不确定
    await new Promise(resolve => setTimeout(resolve, 950))
    await waitReady(page)

    for (const pageName of PAGES) {
      const active = await page.$(`nav .tab[data-view="${pageName}"]`)
      if (active) await active.click()
      await waitReady(page)
      const file = join(outDir, `${pageName}-${label}.png`)
      await page.screenshot({ path: file })
      console.log('captured', file)
    }
  }
}

async function capturePrototype(page, outDir) {
  await waitReady(page)
  for (const { width, height, label } of VIEWPORTS) {
    await page.setViewport({ width, height, deviceScaleFactor: 1 })
    await waitReady(page)
    const file = join(outDir, `prototype-${label}.png`)
    await page.screenshot({ path: file, fullPage: true })
    console.log('captured', file)
  }
}

function diffImages(baselineFile, candidateFile, outFile) {
  const a = PNG.sync.read(readFileSync(baselineFile))
  const b = PNG.sync.read(readFileSync(candidateFile))
  const { width, height } = a
  if (b.width !== width || b.height !== height) {
    throw new Error(`尺寸不一致 ${baselineFile}: ${width}x${height} vs ${b.width}x${b.height}`)
  }
  const diff = new PNG({ width, height })
  const pixels = pixelmatch(a.data, b.data, diff.data, width, height, { threshold: 0.1 })
  writeFileSync(outFile, PNG.sync.write(diff))
  return { pixels, total: width * height, ratio: pixels / (width * height) }
}

async function runDiff(baselineDir, candidateDir, outDir) {
  mkdirSync(outDir, { recursive: true })
  const baselineFiles = readdirSync(baselineDir).filter(f => f.endsWith('.png')).sort()
  const manifest = []
  let failed = 0
  for (const file of baselineFiles) {
    const candidateFile = join(candidateDir, file)
    if (!existsSync(candidateFile)) {
      manifest.push({ name: file, status: 'missing-candidate' })
      failed += 1
      continue
    }
    const result = diffImages(join(baselineDir, file), candidateFile, join(outDir, file))
    const pass = result.ratio <= 0.002
    if (!pass) failed += 1
    manifest.push({ name: file, status: pass ? 'pass' : 'FAIL', ...result })
    console.log(pass ? 'PASS' : 'FAIL', file, `diff=${result.pixels}px (${(result.ratio * 100).toFixed(4)}%)`)
  }
  writeFileSync(join(outDir, 'manifest.json'), JSON.stringify({ generatedAt: new Date().toISOString(), failed, entries: manifest }, null, 2))
  console.log(`\n视觉差异: ${failed}/${manifest.length} FAIL`)
  process.exitCode = failed === 0 ? 0 : 1
}

const [mode, ...rest] = process.argv.slice(2)
if (mode === 'capture') {
  const urlArg = rest[rest.indexOf('--url') + 1]
  const out = rest[rest.indexOf('--out') + 1]
  const isPrototype = rest.includes('--prototype')
  if (!urlArg || !out) throw new Error('capture 需要 --url 与 --out')
  const outDir = resolve(ROOT, out)
  mkdirSync(outDir, { recursive: true })
  const browser = await launch()
  const page = await newDeterministicPage(browser)
  await page.goto(urlArg, { waitUntil: 'networkidle0' })
  if (isPrototype) await capturePrototype(page, outDir)
  else await captureApp(page, outDir)
  await browser.close()
} else if (mode === 'diff') {
  const baseline = resolve(ROOT, rest[rest.indexOf('--baseline') + 1])
  const candidate = resolve(ROOT, rest[rest.indexOf('--candidate') + 1])
  const out = resolve(ROOT, rest[rest.indexOf('--out') + 1])
  await runDiff(baseline, candidate, out)
} else {
  throw new Error('用法: capture --url <u> --out <dir> [--prototype] | diff --baseline <dir> --candidate <dir> --out <dir>')
}
