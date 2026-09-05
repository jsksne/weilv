import type { ConversationTurn, ScheduleEventContract, ScheduleEventUpsertContract } from './common'
import type { AssistantContract } from './assistant'
import type { AssistantReply } from './assistant'
import type { AssistantTraceEvent } from './assistant'
import type { OnboardingContract, OnboardingSubmitAnswers, OnboardingSubmitResult } from './onboarding'
import type { ProfileContract, ProfileMemoryListContract } from './profile'
import type { ShellContract } from './shell'
import type { TodayContextSelection, TodayContract, TodayTaskAction } from './today'
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
  /** Today 的用户选择作为下一次真实 RecommendationRequest 的上下文。 */
  setTodayContext?(context: TodayContextSelection): void
  askAssistant(
    question: string,
    history?: ConversationTurn[],
    easyStart?: boolean,
  ): Promise<AssistantReply>
  /**
   * B3：流式 Agentic 提交。每次调用 = 一次真实 backend Agentic 执行；
   * onEvent 仅在收到真实 sanitized trace 事件时触发。最终回答来自同一执行。
   * history 为最近会话轮次（F1），进入理解环节但不写 Memory。
   * 未实现时（如 Demo/fixture）回退到 askAssistant。
   */
  askAssistantStreaming?(
    question: string,
    onEvent: (event: AssistantTraceEvent) => void,
    history?: ConversationTurn[],
    easyStart?: boolean,
  ): Promise<AssistantReply>
  /** Production 提交首次引导：只写学段与 Memory 偏好；Demo 实现为本地 no-op。 */
  submitOnboarding?(answers: OnboardingSubmitAnswers): Promise<OnboardingSubmitResult>
  /** B2：记录任务动作事件（不是 Feedback）。Demo 实现为本地 no-op。 */
  submitTaskAction?(recommendationId: string, action: TodayTaskAction): Promise<{ status: string }>
  /** B4：读取 Memory list。 */
  getUserMemories?(): Promise<ProfileMemoryListContract>
  /** B4：删除一条 Memory（后端 forget_memory）。 */
  deleteUserMemory?(memoryId: string): Promise<{ status: string }>
  /** 日程最小实现：列出/新增/修改/删除当天可见事件（名称只存不传模型）。 */
  getSchedule?(fromDate?: string, toDate?: string): Promise<ScheduleEventContract[]>
  saveScheduleEvent?(body: ScheduleEventUpsertContract, eventId?: string): Promise<{ status: string }>
  deleteScheduleEvent?(eventId: string): Promise<{ status: string }>
}
