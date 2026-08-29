export const API_BASE_URL_ENV_KEY = 'VITE_API_BASE_URL'

export class ApiBaseUrlConfigurationError extends Error {
  constructor(value: string | undefined) {
    super(
      `${API_BASE_URL_ENV_KEY} must be configured for production; received ${value ?? 'missing'}.`,
    )
    this.name = 'ApiBaseUrlConfigurationError'
  }
}

export function resolveApiBaseUrl(value: string | undefined): string {
  const trimmed = value?.trim() ?? ''
  if (!trimmed) throw new ApiBaseUrlConfigurationError(value)
  const normalized = trimmed.replace(/\/+$/, '')
  return normalized || '/'
}

export function getConfiguredApiBaseUrl(): string {
  return resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL)
}
