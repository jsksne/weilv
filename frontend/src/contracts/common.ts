export type ViewId = 'today' | 'assistant' | 'profile' | 'weekly'

export type UiMode = 'demo' | 'production'

export type UiLoadState = 'loading' | 'ready' | 'error' | 'unavailable'

export interface UiState {
  status: UiLoadState
  mode: UiMode
  message?: string
}
