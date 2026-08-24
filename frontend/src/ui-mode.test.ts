import { ApiUiDataSource } from './data/apiUiDataSource'
import { createUiDataSource } from './data/createUiDataSource'
import { FixtureUiDataSource } from './data/fixtureUiDataSource'
import { UiModeConfigurationError, resolveUiMode } from './config/uiMode'

describe('Sprint 8 UI mode boundary', () => {
  it.each([
    [undefined, 'missing'],
    ['', 'empty'],
    ['staging', 'invalid'],
    ['DEMO', 'invalid'],
  ])('%s is a configuration error', (value) => {
    expect(() => resolveUiMode(value)).toThrow(UiModeConfigurationError)
  })

  it('accepts only demo and production', () => {
    expect(resolveUiMode('demo')).toBe('demo')
    expect(resolveUiMode('production')).toBe('production')
  })

  it('creates exactly one source for the resolved mode', () => {
    expect(createUiDataSource('demo')).toBeInstanceOf(FixtureUiDataSource)
    expect(createUiDataSource('production')).toBeInstanceOf(ApiUiDataSource)
  })
})
