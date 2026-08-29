import { afterEach, beforeEach, vi } from 'vitest'

beforeEach(() => {
  vi.stubEnv('VITE_UI_MODE', 'demo')
  vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000')
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})
