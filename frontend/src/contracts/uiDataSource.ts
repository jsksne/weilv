import type { AssistantContract } from './assistant'
import type { AssistantReply } from './assistant'
import type { OnboardingContract } from './onboarding'
import type { ProfileContract } from './profile'
import type { ShellContract } from './shell'
import type { TodayContract } from './today'
import type { WeeklyContract } from './weekly'

export interface UiDataBundle {
  today: TodayContract
  assistant: AssistantContract
  profile: ProfileContract
  onboarding: OnboardingContract
  weekly: WeeklyContract
  shell: ShellContract
}

export interface UiDataSource {
  getInitialData?(): UiDataBundle
  getShell(): Promise<ShellContract>
  getAssistant(): Promise<AssistantContract>
  getProfile(): Promise<ProfileContract>
  getWeekly(): Promise<WeeklyContract>
  getOnboarding(): Promise<OnboardingContract>
  getToday(): Promise<TodayContract>
  askAssistant(question: string): Promise<AssistantReply>
}
