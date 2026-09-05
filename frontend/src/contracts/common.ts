export type ViewId = 'today' | 'assistant' | 'profile' | 'weekly'

export type UiMode = 'demo' | 'production'

export type UiLoadState = 'loading' | 'ready' | 'error' | 'unavailable'

export type UiDataAvailability = 'available' | 'partial' | 'unavailable'
export type UiFieldAvailability = 'available' | 'unavailable'

export interface UiState {
  status: UiLoadState
  mode: UiMode
  message?: string
}

/** F1：一次会话历史轮次；随推荐请求进入理解环节，不写 Memory。 */
export interface ConversationTurn {
  role: 'user' | 'assistant'
  content: string
}

/** 日程最小实现（契约层）。kind/busy_level 为结构化事实；name 只用于展示。 */
export type ScheduleKind = 'exam' | 'holiday' | 'plan'
export type ScheduleBusyLevel = 'busy' | 'some' | 'free'

export interface ScheduleEventContract {
  event_id: string
  name: string
  start_date: string
  end_date: string
  kind: ScheduleKind
  busy_level: ScheduleBusyLevel | null
}

export interface ScheduleEventUpsertContract {
  name: string
  start_date: string
  end_date: string
  kind: ScheduleKind
  busy_level: ScheduleBusyLevel | null
}
