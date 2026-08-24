import type { UiMode } from '@/contracts'
import { getConfiguredUiMode } from '@/config/uiMode'
import { ApiUiDataSource, type ApiUiDataSourceOptions } from './apiUiDataSource'
import { FixtureUiDataSource } from './fixtureUiDataSource'

export function createUiDataSource(
  mode: UiMode = getConfiguredUiMode(),
  options: ApiUiDataSourceOptions = {},
) {
  return mode === 'demo' ? new FixtureUiDataSource() : new ApiUiDataSource(options)
}
