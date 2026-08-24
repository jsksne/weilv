import type { ShellIconName } from './shell'
import type { UiState } from './common'

export type ProfileValueTone = 'default' | 'up' | 'down'
export type ProfileSectionStatus = 'available' | 'unavailable'
export type MemoryConsentState = 'granted' | 'missing' | 'disabled'
export type ProfileTargetStage = 'primary_upper' | 'junior_high' | 'senior_high' | 'unavailable'

export interface ProfileHeaderContract {
  title: string
  description: string
}

export interface ProfilePreferenceItem {
  label: string
  value: string
  tone?: ProfileValueTone
}

export interface PreferenceCardContract {
  id: 'time' | 'task'
  icon: ShellIconName
  title: string
  status: ProfileSectionStatus
  items: readonly ProfilePreferenceItem[]
  unavailableMessage?: string
}

export interface CompletionPatternContract {
  status: ProfileSectionStatus
  icon: ShellIconName
  title: string
  percentage: number | null
  summaryLines: readonly string[]
  unavailableMessage?: string
}

export interface MemoryItemContract {
  id: string
  icon: ShellIconName
  lead: string
  text: string
}

export interface MemorySectionContract {
  status: ProfileSectionStatus
  enabled: boolean
  consent: MemoryConsentState
  items: readonly MemoryItemContract[]
  canDelete: boolean
  notice: string
  unavailableMessage?: string
}

/** B4：从 Memory list API 映射出的 Profile Memory 展示切片。 */
export interface ProfileMemoryListContract {
  enabled: boolean
  consent: MemoryConsentState
  items: readonly MemoryItemContract[]
  canDelete: boolean
  notice: string
}

export interface ProfileContract {
  state: UiState
  targetStage: ProfileTargetStage
  memoryEnabled: boolean
  header: ProfileHeaderContract
  timePreference: PreferenceCardContract
  taskPreference: PreferenceCardContract
  completionPattern: CompletionPatternContract
  memory: MemorySectionContract
}
