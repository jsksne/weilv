import { afterEach, beforeEach, vi } from 'vitest'

beforeEach(() => {
  vi.stubEnv('VITE_UI_MODE', 'demo')
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})
