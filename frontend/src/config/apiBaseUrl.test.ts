import { ApiBaseUrlConfigurationError, resolveApiBaseUrl } from './apiBaseUrl'

describe('API base URL configuration', () => {
  it('rejects a missing value instead of selecting a local fallback', () => {
    expect(() => resolveApiBaseUrl(undefined)).toThrow(ApiBaseUrlConfigurationError)
    expect(() => resolveApiBaseUrl('   ')).toThrow(ApiBaseUrlConfigurationError)
  })

  it('keeps the same-origin root usable for the production container', () => {
    expect(resolveApiBaseUrl('/')).toBe('/')
    expect(resolveApiBaseUrl('https://api.example.test/')).toBe('https://api.example.test')
  })
})
