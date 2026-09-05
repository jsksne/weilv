import { computed, ref, toValue, watch, type MaybeRefOrGetter, type Ref } from 'vue'

import type {
  TodayContract,
  TodaySavedInteraction,
  TodayTaskAction,
  TodayTaskView,
} from '@/contracts'

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
  | 'submission-failed'

export type TaskActionOutcome = TaskActionResult | Promise<TaskActionResult>

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
  adoptSuggested: (task: TodayTaskView) => 'added' | 'exists'
  start: (slotId: string) => TaskActionOutcome
  complete: (slotId: string) => TaskActionOutcome
  partial: (slotId: string) => TaskActionOutcome
  skip: (slotId: string) => TaskActionOutcome
  restore: (slotId: string) => TaskActionOutcome
  replace: (slotId: string) => TaskActionOutcome
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
  onAction?: (task: TodayTaskView, action: TodayTaskAction) => Promise<{ status: string }>
}

const ACTION_COOLDOWN_MS = 450

/** 卡片身份：优先真实执行记录（recommendationId），无记录时退回任务定义 id。 */
function taskSlotKey(task: TodayTaskView): string {
  return task.recommendationId ?? `t:${task.taskId}`
}

function stageForSaved(interaction: TodaySavedInteraction): TaskActionStage {
  if (interaction === 'started') return 'active'
  if (interaction === 'done' || interaction === 'partial') return 'completed'
  if (interaction === 'skipped') return 'restore'
  return 'initial'
}

/** F4：当天读回的已完成/部分完成任务，若反馈尚未保存则恢复待反馈提示。 */
function needsRestoredFeedback(entry: DailyTaskEntry): boolean {
  const saved = entry.task.savedInteraction
  return (saved === 'done' || saved === 'partial') && entry.task.feedbackSaved !== true
}

export function useDailyTasks(
  input: MaybeRefOrGetter<TodayContract>,
  options: UseDailyTasksOptions = {},
): DailyTasksController {
  const now = options.now ?? (() => performance.now())
  const model = computed(() => toValue(input))

  const entries = ref<readonly DailyTaskEntry[]>([])
  const mood = ref('')
  const availableMinutes = ref(0)
  const pendingFeedback = ref<readonly PendingFeedback[]>([])
  let replacePointer = 0
  const lastActionAt = new Map<string, number>()

  /**
   * F4：模型变化不再整体重置交互状态。
   * 按稳定记录身份（recommendationId / taskId）合并：已有条目保留本地
   * 交互状态（可能比读回更新）；新条目从 savedInteraction 恢复；
   * 已开始/已完成/已放下的条目即使不在新模型里也保留——今日记录不消失，
   * 只有未开始的候选任务会被新推荐替换。
   */
  function syncModel(next: TodayContract): void {
    const previous = entries.value
    const byKey = new Map(previous.map(entry => [taskSlotKey(entry.task), entry]))
    const merged: DailyTaskEntry[] = []
    const consumed = new Set<string>()
    next.tasks.forEach((task, index) => {
      const key = taskSlotKey(task)
      consumed.add(key)
      const kept = byKey.get(key)
      merged.push(kept ? { ...kept, task } : entryFromTask(task, index))
    })
    for (const entry of previous) {
      if (!consumed.has(taskSlotKey(entry.task)) && entry.interaction !== 'pending') {
        merged.push(entry)
      }
    }
    /* 已开始/已完成/已放下的记录排在候选前面（首页优先动作语义）。 */
    entries.value = [
      ...merged.filter(entry => entry.interaction !== 'pending'),
      ...merged.filter(entry => entry.interaction === 'pending'),
    ]

    const knownFeedback = new Set(pendingFeedback.value.map(item => item.slotId))
    pendingFeedback.value = [
      ...pendingFeedback.value,
      ...merged
        .filter(entry => !knownFeedback.has(entry.slotId) && needsRestoredFeedback(entry))
        .map(entry => ({
          slotId: entry.slotId,
          completionStatus:
            entry.task.savedInteraction === 'done'
              ? ('completed' as const)
              : ('partially_completed' as const),
        })),
    ]

    /* 用户尚未主动选择时落回契约默认；已选择则原样保留。 */
    if (!mood.value) mood.value = next.defaultMood
    if (availableMinutes.value <= 0) availableMinutes.value = next.defaultTimeMinutes
  }

  function entryFromTask(task: TodayTaskView, index: number): DailyTaskEntry {
    const interaction = task.savedInteraction ?? 'pending'
    return {
      slotId: `slot-${index}-${taskSlotKey(task)}`,
      task,
      interaction,
      actions: stageForSaved(interaction),
    }
  }

  syncModel(model.value)
  /* 模型刷新保留用户已选的心情与时间；未选择时落回契约默认。 */
  watch(model, syncModel)

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

  function applyAfterSubmission(
    entry: DailyTaskEntry,
    action: TodayTaskAction,
    apply: () => void,
  ): TaskActionOutcome {
    if (!entry.task.recommendationId || !options.onAction) {
      apply()
      return 'applied'
    }

    return options.onAction(entry.task, action).then(
      result => {
        if (result.status !== 'recorded' && result.status !== 'demo_local') {
          lastActionAt.delete(entry.slotId)
          return 'submission-failed'
        }
        apply()
        return 'applied'
      },
      () => {
        lastActionAt.delete(entry.slotId)
        return 'submission-failed'
      },
    )
  }

  function start(slotId: string): TaskActionOutcome {
    const entry = findEntry(slotId)
    if (!entry) return 'rejected-state'
    if (!passesCooldown(slotId)) return 'cooldown'
    return applyAfterSubmission(entry, 'started', () => {
      updateEntry(slotId, { interaction: 'started', actions: 'active' })
    })
  }

  function finish(slotId: string, interaction: 'done' | 'partial'): TaskActionOutcome {
    const entry = findEntry(slotId)
    if (!entry) return 'rejected-state'
    if (entry.interaction === 'done' || entry.interaction === 'partial') return 'rejected-state'
    if (!passesCooldown(slotId)) return 'cooldown'
    const action = interaction === 'done' ? 'completed' : 'partially_completed'
    return applyAfterSubmission(entry, action, () => {
      updateEntry(slotId, { interaction, actions: 'completed' })
      pendingFeedback.value = [
        ...pendingFeedback.value.filter(item => item.slotId !== slotId),
        {
          slotId,
          completionStatus: action,
        },
      ]
    })
  }

  function complete(slotId: string): TaskActionOutcome {
    return finish(slotId, 'done')
  }

  function partial(slotId: string): TaskActionOutcome {
    return finish(slotId, 'partial')
  }

  function skip(slotId: string): TaskActionOutcome {
    const entry = findEntry(slotId)
    if (!entry) return 'rejected-state'
    if (!passesCooldown(slotId)) return 'cooldown'
    return applyAfterSubmission(entry, 'skipped', () => {
      updateEntry(slotId, { interaction: 'skipped', actions: 'restore' })
      pendingFeedback.value = [
        ...pendingFeedback.value.filter(item => item.slotId !== slotId),
        { slotId, completionStatus: 'skipped' },
      ]
    })
  }

  function restore(slotId: string): TaskActionOutcome {
    const entry = findEntry(slotId)
    if (!entry) return 'rejected-state'
    if (!passesCooldown(slotId)) return 'cooldown'
    return applyAfterSubmission(entry, 'restored', () => {
      updateEntry(slotId, { interaction: 'pending', actions: 'initial' })
      pendingFeedback.value = pendingFeedback.value.filter(item => item.slotId !== slotId)
    })
  }

  /**
   * 原型 replace 分支：内容换为 REPLACE_POOL[replacePtr++ % 3]，按钮组重置为
   * 初始三钮，但 taskStates[idx] 不回退（started 仍为 started，随后 low
   * 心情因此不再改写该卡——保持该语义）。
   */
  function replace(slotId: string): TaskActionOutcome {
    const entry = findEntry(slotId)
    if (!entry) return 'rejected-state'
    if (model.value.replacePool.length === 0) return 'rejected-state'
    if (!passesCooldown(slotId)) return 'cooldown'
    return applyAfterSubmission(entry, 'replaced', () => {
      const next = model.value.replacePool[replacePointer % model.value.replacePool.length]!
      replacePointer += 1
      updateEntry(slotId, { task: next, actions: 'initial' })
    })
  }

  /**
   * 原型 moodRow low 分支：每次点 low 都提示；仅当换卡目标仍为 pending
   * 时改写其 name/description/why（domain/meta/色调不变，选回其他心情不回写）。
   */
  function applyMood(value: string): TaskActionResult {
    mood.value = value
    if (value !== 'low') return 'applied'
    const swap = model.value.lowMoodSwap
    /* 槽位按模型位置定位，条目按记录身份查找（记录可能排在候选前面）。 */
    const targetTask = model.value.tasks[lowMoodSlotIndex.value]
    const target = targetTask
      ? entries.value.find(entry => taskSlotKey(entry.task) === taskSlotKey(targetTask))
      : undefined
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

  /**
   * F2：把 AI 建议加入今日。绑定真实 recommendationId（该会话已在后端建立），
   * 动作事件照常落到该记录；按任务定义 id 去重，不重复添加。
   */
  function adoptSuggested(task: TodayTaskView): 'added' | 'exists' {
    if (entries.value.some(entry => entry.task.taskId === task.taskId)) return 'exists'
    entries.value = [
      ...entries.value,
      {
        slotId: `slot-adopt-${taskSlotKey(task)}`,
        task,
        interaction: 'pending',
        actions: 'initial',
      },
    ]
    return 'added'
  }

  return {
    entries,
    completed,
    total,
    adoptSuggested,
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
