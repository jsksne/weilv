import type { UiMode } from '@/contracts'

export const UI_MODE_ENV_KEY = 'VITE_UI_MODE'

export class UiModeConfigurationError extends Error {
  constructor(value: string | undefined) {
    super(
      `${UI_MODE_ENV_KEY} must be exactly "demo" or "production"; received ${value ?? 'missing'}.`,
    )
    this.name = 'UiModeConfigurationError'
  }
}

export function resolveUiMode(value: string | undefined): UiMode {
  if (value === 'demo' || value === 'production') return value
  throw new UiModeConfigurationError(value)
}

export function getConfiguredUiMode(): UiMode {
  return resolveUiMode(import.meta.env.VITE_UI_MODE)
}
