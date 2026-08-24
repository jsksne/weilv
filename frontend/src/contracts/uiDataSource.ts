import type { AssistantContract } from './assistant'
import type { OnboardingContract } from './onboarding'
import type { ProfileContract } from './profile'
import type { ShellContract } from './shell'
import type { WeeklyContract } from './weekly'

export interface UiDataSource {
  getShell(): Promise<ShellContract>
  getAssistant(): Promise<AssistantContract>
  getProfile(): Promise<ProfileContract>
  getWeekly(): Promise<WeeklyContract>
  getOnboarding(): Promise<OnboardingContract>
}
