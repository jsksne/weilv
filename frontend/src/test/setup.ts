import { afterEach, beforeEach, vi } from 'vitest'

Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
  configurable: true,
  writable: true,
  value: vi.fn(),
})

beforeEach(() => {
  vi.stubEnv('VITE_UI_MODE', 'demo')
  vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000')
  vi.stubGlobal('scrollTo', vi.fn())
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})
