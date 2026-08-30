import { computed, ref, toValue, watch, type MaybeRefOrGetter, type Ref } from 'vue'

import type { TodayContract, TodayTaskAction, TodayTaskView } from '@/contracts'

/**
 * Sprint 4：Today 本地交互状态机（迁移自冻结原型脚本）。
 *
 * 对应原型：
 *   - taskStates 数组（pending/started/done/partial/skipped）；
 *   - updateProgress()（done|partial 计数 + hero/顶栏双份 note）；
 *   - card._actAt 的 450ms 同位换钮冷却（clock 可注入便于确定性测试）；
 *   - REPLACE_POOL 模块级 replacePtr 循环指针；
 *   - moodRow / timeChips 单选与 low 心情换卡语义。
 *
 * 本 composable 只持有 local state，不请求 API、不写 Memory/Feedback。
 * 视觉副作用（toast / FX / 脉冲）由组件根据返回结果执行。
 */

export type TaskInteraction = 'pending' | 'started' | 'done' | 'partial' | 'skipped'

/** .task-actions 按钮组阶段（原型按 innerHTML 替换的四种形态） */
export type TaskActionStage = 'initial' | 'active' | 'completed' | 'restore'

export type TaskActionResult =
  | 'applied'
  | 'cooldown'
  | 'rejected-state'

export interface DailyTaskEntry {
  /** 卡片槽位（对应原型 data-idx）：内容可被 replace/low 换掉，槽位不变 */
  slotId: string
  task: TodayTaskView
  interaction: TaskInteraction
  actions: TaskActionStage
}

export type PendingFeedbackStatus = 'completed' | 'partially_completed' | 'skipped'

export interface PendingFeedback {
  slotId: string
  completionStatus: PendingFeedbackStatus
}

export interface DailyTasksController {
  entries: Readonly<Ref<readonly DailyTaskEntry[]>>
  completed: Readonly<Ref<number>>
  total: Readonly<Ref<number>>
  heroProgressNote: Readonly<Ref<string>>
  dockedProgressNote: Readonly<Ref<string>>
  mood: Readonly<Ref<string>>
  availableMinutes: Readonly<Ref<number>>
  pendingFeedback: Readonly<Ref<readonly PendingFeedback[]>>
  start: (slotId: string) => TaskActionResult
  complete: (slotId: string) => TaskActionResult
  partial: (slotId: string) => TaskActionResult
  skip: (slotId: string) => TaskActionResult
  restore: (slotId: string) => TaskActionResult
  replace: (slotId: string) => TaskActionResult
  applyMood: (value: string) => TaskActionResult
  selectTime: (minutes: number) => TaskActionResult
}

export interface UseDailyTasksOptions {
  /** 450ms 冷却判定用的时钟，默认 performance.now（测试可注入） */
  now?: () => number
  /**
   * Sprint 9：B2 任务动作事件回调（Production 由 App 接 DataSource）。
   * 只在任务带 recommendation_id 时调用，保证事件写对该任务。
   */
  onAction?: (task: TodayTaskView, action: TodayTaskAction) => void
}

const ACTION_COOLDOWN_MS = 450

export function useDailyTasks(
  input: MaybeRefOrGetter<TodayContract>,
  options: UseDailyTasksOptions = {},
): DailyTasksController {
  const now = options.now ?? (() => performance.now())
  const model = computed(() => toValue(input))

  function emitAction(entry: DailyTaskEntry, action: TodayTaskAction): void {
    if (entry.task.recommendationId) options.onAction?.(entry.task, action)
  }

  const entries = ref<readonly DailyTaskEntry[]>([])
  const mood = ref('')
  const availableMinutes = ref(0)
  const pendingFeedback = ref<readonly PendingFeedback[]>([])
  let replacePointer = 0
  const lastActionAt = new Map<string, number>()

  function reset(next: TodayContract): void {
    entries.value = next.tasks.map((task, index) => ({
      slotId: `today-slot-${index}`,
      task,
      interaction: 'pending',
      actions: 'initial',
    }))
    mood.value = next.defaultMood
    availableMinutes.value = next.defaultTimeMinutes
    pendingFeedback.value = []
    replacePointer = 0
    lastActionAt.clear()
  }

  reset(model.value)
  /* 上下文刷新（心情/时间变化 → 换一推荐）时保留用户已选的心情与时间；
     首次加载两者为空值，仍落回契约默认。 */
  watch(model, next => {
    const keepMood = mood.value
    const keepMinutes = availableMinutes.value
    reset(next)
    if (keepMood) mood.value = keepMood
    if (keepMinutes > 0) availableMinutes.value = keepMinutes
  })

  const completed = computed(
    () => entries.value.filter(entry => entry.interaction === 'done' || entry.interaction === 'partial').length,
  )
  const total = computed(() => entries.value.length)
  /* 契约为固定 4 元组（TodayProgressNotes），Math.min 保证索引 ∈ [0,3]，
     访问必为 string；noUncheckedIndexedAccess 下需显式断言收窄 */
  const heroProgressNote = computed(
    () => model.value.progressNotes.hero[Math.min(completed.value, model.value.progressNotes.hero.length - 1)] ?? '当前进度不可用',
  )
  const dockedProgressNote = computed(
    () => model.value.progressNotes.docked[Math.min(completed.value, model.value.progressNotes.docked.length - 1)] ?? '当前进度不可用',
  )

  /* low 心情换卡按初始槽位定位（原型 data-idx="1" 是位置语义） */
  const lowMoodSlotIndex = computed(
    () => model.value.tasks.findIndex(task => task.id === model.value.lowMoodSwap.taskId),
  )

  function findEntry(slotId: string): DailyTaskEntry | undefined {
    return entries.value.find(entry => entry.slotId === slotId)
  }

  /** 原型 card._actAt：冷却内的点击直接忽略，且不刷新时间戳 */
  function passesCooldown(slotId: string): boolean {
    const last = lastActionAt.get(slotId)
    const current = now()
    if (last !== undefined && current - last < ACTION_COOLDOWN_MS) return false
    lastActionAt.set(slotId, current)
    return true
  }

  function updateEntry(slotId: string, patch: Partial<DailyTaskEntry>): void {
    entries.value = entries.value.map(entry =>
      entry.slotId === slotId ? { ...entry, ...patch } : entry,
    )
  }

  function start(slotId: string): TaskActionResult {
    const entry = findEntry(slotId)
    if (!entry) return 'rejected-state'
    if (!passesCooldown(slotId)) return 'cooldown'
    updateEntry(slotId, { interaction: 'started', actions: 'active' })
    emitAction(entry, 'started')
    return 'applied'
  }

  function finish(slotId: string, interaction: 'done' | 'partial'): TaskActionResult {
    const entry = findEntry(slotId)
    if (!entry) return 'rejected-state'
    if (entry.interaction === 'done' || entry.interaction === 'partial') return 'rejected-state'
    if (!passesCooldown(slotId)) return 'cooldown'
    updateEntry(slotId, { interaction, actions: 'completed' })
    pendingFeedback.value = [
      ...pendingFeedback.value.filter(item => item.slotId !== slotId),
      {
        slotId,
        completionStatus: interaction === 'done' ? 'completed' : 'partially_completed',
      },
    ]
    emitAction(entry, interaction === 'done' ? 'completed' : 'partially_completed')
    return 'applied'
  }

  function complete(slotId: string): TaskActionResult {
    return finish(slotId, 'done')
  }

  function partial(slotId: string): TaskActionResult {
    return finish(slotId, 'partial')
  }

  function skip(slotId: string): TaskActionResult {
    const entry = findEntry(slotId)
    if (!entry) return 'rejected-state'
    if (!passesCooldown(slotId)) return 'cooldown'
    updateEntry(slotId, { interaction: 'skipped', actions: 'restore' })
    pendingFeedback.value = [
      ...pendingFeedback.value.filter(item => item.slotId !== slotId),
      { slotId, completionStatus: 'skipped' },
    ]
    emitAction(entry, 'skipped')
    return 'applied'
  }

  function restore(slotId: string): TaskActionResult {
    const entry = findEntry(slotId)
    if (!entry) return 'rejected-state'
    if (!passesCooldown(slotId)) return 'cooldown'
    updateEntry(slotId, { interaction: 'pending', actions: 'initial' })
    pendingFeedback.value = pendingFeedback.value.filter(item => item.slotId !== slotId)
    emitAction(entry, 'restored')
    return 'applied'
  }

  /**
   * 原型 replace 分支：内容换为 REPLACE_POOL[replacePtr++ % 3]，按钮组重置为
   * 初始三钮，但 taskStates[idx] 不回退（started 仍为 started，随后 low
   * 心情因此不再改写该卡——保持该语义）。
   */
  function replace(slotId: string): TaskActionResult {
    const entry = findEntry(slotId)
    if (!entry) return 'rejected-state'
    if (model.value.replacePool.length === 0) return 'rejected-state'
    if (!passesCooldown(slotId)) return 'cooldown'
    const next = model.value.replacePool[replacePointer % model.value.replacePool.length]!
    replacePointer += 1
    updateEntry(slotId, { task: next, actions: 'initial' })
    emitAction(entry, 'replaced')
    return 'applied'
  }

  /**
   * 原型 moodRow low 分支：每次点 low 都提示；仅当换卡目标仍为 pending
   * 时改写其 name/description/why（domain/meta/色调不变，选回其他心情不回写）。
   */
  function applyMood(value: string): TaskActionResult {
    mood.value = value
    if (value !== 'low') return 'applied'
    const swap = model.value.lowMoodSwap
    const target = entries.value[lowMoodSlotIndex.value]
    if (target && target.interaction === 'pending') {
      updateEntry(target.slotId, {
        task: {
          ...target.task,
          name: swap.name,
          description: swap.description,
          why: swap.why,
        },
      })
    }
    return 'applied'
  }

  function selectTime(minutes: number): TaskActionResult {
    availableMinutes.value = minutes
    return 'applied'
  }

  return {
    entries,
    completed,
    total,
    heroProgressNote,
    dockedProgressNote,
    mood,
    availableMinutes,
    pendingFeedback,
    start,
    complete,
    partial,
    skip,
    restore,
    replace,
    applyMood,
    selectTime,
  }
}
