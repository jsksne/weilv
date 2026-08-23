import type { UiState, ViewId } from './common'

export interface ShellNavigationItem {
  id: ViewId
  label: string
}

export interface ShellTaskProgress {
  completed: number
  total: number
  note: string
}

export interface ShellToast {
  id: string
  message: string
}

export type ShellIconName = 'flower' | 'moon' | 'clock' | 'leaf' | 'target' | 'book'

export interface ShellContract {
  state: UiState
  navigation: readonly ShellNavigationItem[]
  displayName: string
  dateLabel: string
  progress: ShellTaskProgress
  toastExample: ShellToast
}
