import type { ShellIconName, ShellTaskProgress } from './shell'
import type { UiDataAvailability, UiFieldAvailability, UiState } from './common'

/**
 * Today UI Contract（Sprint 4）。
 *
 * 全部字段为展示模型：内容逐字来自冻结原型
 * `ui-prototypes/02-sakura-spring.html` 的 #view-today 区块，
 * 不包含任何后端 RecommendationResponse / api DTO 结构。
 * Demo（fixture）与未来的 API DataSource 都映射到同一 Contract。
 */

export type TodayTaskTone = 'default' | 'eye' | 'move' | 'sleep'

/** B2 任务动作事件（与 backend TaskAction 一致的六个动作）。 */
export type TodayTaskAction =
  | 'started'
  | 'completed'
  | 'partially_completed'
  | 'skipped'
  | 'replaced'
  | 'restored'

export type TodayRecommendationStatus =
  | 'allowed'
  | 'blocked'
  | 'help_seeking'
  | 'no_safe_task'
  | 'unavailable'

/**
 * 读回当天已保存交互状态（由 B2 任务动作事件推导）；
 * 缺省 = 全新待开始。与 useDailyTasks 的 TaskInteraction 语义一致。
 */
export type TodaySavedInteraction = 'pending' | 'started' | 'done' | 'partial' | 'skipped'

export interface TodayTaskView {
  id: string
  /** B1：后端正式任务 id（用于展示与追溯）。 */
  taskId: string
  /** B1/B2：该任务自己的 recommendation_id（B2 事件必须用它）。 */
  recommendationId?: string
  /** 原型 t-eye / t-move / t-sleep 色调类（default 即粉色无后缀） */
  tone: TodayTaskTone
  domain: string
  /** 「约 1 分钟 · 极低强度」 */
  meta: string
  name: string
  description: string
  why: string
  whyIcon: ShellIconName
  /** F4：当天读回时已保存的交互状态；新推荐不携带。 */
  savedInteraction?: TodaySavedInteraction
  /** F4：该任务当天的主观反馈已保存（避免读回后重复追问）。 */
  feedbackSaved?: boolean
}

export interface TodayObservationStat {
  key: string
  value: string
  delta: string
  deltaTone: 'up' | 'warn'
}

export interface TodaySuggestion {
  icon: ShellIconName
  /** 原型 sg-ic night 类：图标换紫色调 */
  night?: boolean
  /** <b>加粗引导段</b> */
  lead: string
  /** 引导段后的普通文本（含起始破折号） */
  rest: string
}

export interface TodayObservationView {
  /** obs-main 渐变强调 em 之前的文本 */
  mainLead: string
  /** obs-main 内 <em> 文本 */
  mainEmphasis: string
  /** obs-main em 之后的文本 */
  mainTail: string
  summary: string
  stats: readonly TodayObservationStat[]
  suggestions: readonly TodaySuggestion[]
}

export interface TodayMoodOption {
  value: string
  face: string
  label: string
}

export interface TodayTimeOption {
  minutes: number
  label: string
}

export interface TodayContextSelection {
  mood: string
  availableMinutes: number
  /** F5：“现在不适合——场合不方便（不方便起身等）”→ 正式 cannot_move 约束；仅当次有效。 */
  cannotMove?: boolean
}

/** 选择「有点低落」时对第二张任务卡的内容替换（仅 pending 可用） */
export interface TodayLowMoodSwap {
  taskId: string
  name: string
  description: string
  why: string
}

export interface TodayRichTextSegment {
  text: string
  emphasis?: boolean
}

export interface TodayRhythmItem {
  time: string
  title: string
  note: string
  now?: boolean
}

/** 原型 updateProgress 的两组四段文案（hero 行 / 吸附顶栏） */
export interface TodayProgressNotes {
  hero: readonly [string, string, string, string]
  docked: readonly [string, string, string, string]
}

export interface TodayDataAvailability {
  selectedTask: UiFieldAvailability
  dailyTasks: UiFieldAvailability
  sleepStats: UiFieldAvailability
  visionStats: UiFieldAvailability
  moodStats: UiFieldAvailability
  rhythm: UiFieldAvailability
  progress: UiFieldAvailability
  replace: UiFieldAvailability
  restore: UiFieldAvailability
}

/** 任务与检查交互的冻结 toast 文案（restore 无 toast，为空串） */
export interface TodayFeedbackCopy {
  start: string
  done: string
  partial: string
  skip: string
  restore: string
  replace: string
  lowMood: string
  check: string
}

export interface TodayContract {
  state: UiState
  dataAvailability: UiDataAvailability
  recommendationStatus: TodayRecommendationStatus
  availability: TodayDataAvailability
  unavailableFields: readonly string[]
  heroTag: string
  greetingLead: string
  greetingName: string
  /** hero 状态说明 p：两行，每行是带 emphasis 段的富文本 */
  summaryLines: readonly (readonly TodayRichTextSegment[])[]
  observation: TodayObservationView
  moods: readonly TodayMoodOption[]
  defaultMood: string
  timeOptions: readonly TodayTimeOption[]
  defaultTimeMinutes: number
  moodNoteLead: string
  moodNoteLines: readonly string[]
  tasksSectionTitle: string
  tasksSectionNote: string
  tasks: readonly TodayTaskView[]
  replacePool: readonly TodayTaskView[]
  lowMoodSwap: TodayLowMoodSwap
  rhythm: {
    title: string
    sub: string
    items: readonly TodayRhythmItem[]
  }
  breath: {
    title: string
    sub: string
    tip: string
  }
  progressNotes: TodayProgressNotes
  feedbackCopy: TodayFeedbackCopy
}

/** 吸附顶栏进度（与 hero 进度行同源的展示切片） */
export type TodayDockedProgress = ShellTaskProgress
