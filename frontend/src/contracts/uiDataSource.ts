import type { AssistantContract } from './assistant'
import type { OnboardingContract } from './onboarding'
import type { ProfileContract } from './profile'
import type { ShellContract } from './shell'

export interface UiDataSource {
  getShell(): Promise<ShellContract>
  getAssistant(): Promise<AssistantContract>
  getProfile(): Promise<ProfileContract>
  getOnboarding(): Promise<OnboardingContract>
}
