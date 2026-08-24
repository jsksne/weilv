import type { AssistantContract } from './assistant'
import type { AssistantReply } from './assistant'
import type { OnboardingContract, OnboardingSubmitAnswers, OnboardingSubmitResult } from './onboarding'
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
  /** Production 提交首次引导：只写学段与 Memory 偏好；Demo 实现为本地 no-op。 */
  submitOnboarding?(answers: OnboardingSubmitAnswers): Promise<OnboardingSubmitResult>
}
