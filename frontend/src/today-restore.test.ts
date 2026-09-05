import { nextTick, ref } from 'vue'

import { adaptTodaySessions, mergeTodayContracts } from './data/adapters'
import { todayFixture } from './data/fixtures/today.fixture'
import { useDailyTasks } from './composables/useDailyTasks'
import type { TodaySessionsResponse } from './api/types'
import type { TodayContract } from './contracts'

/* ------------------------------------------------------------------
   F4：今日读回。当天已保存的任务/动作状态可恢复；模型刷新不再清空
   已开始/已完成/已放下的条目，只有未开始候选会被新推荐替换。
   ------------------------------------------------------------------ */

function sessionDto(overrides: Partial<TodaySessionsResponse['sessions'][number]> = {}) {
  return {
    recommendation_id: 'rec-1',
    task_id: 'MT-1',
    title: '窗边远眺 20 秒',
    instruction: '望向最远处，让眼睛放松。',
    estimated_minutes: 1,
    covered_domains: ['eye_health'],
    sources: [],
    agentic: false,
    created_at: '2026-09-05T01:00:00+00:00',
    actions: [],
    feedback: null,
    ...overrides,
  }
}

function restoredContract(
  sessions: TodaySessionsResponse['sessions'],
): TodayContract {
  return adaptTodaySessions({ user_id: 'user-1', date: '2026-09-05', sessions })
}

describe('F4 adaptTodaySessions: saved interaction derivation', () => {
  it('restores a completed task with its saved state and skips re-prompting feedback when saved', () => {
    const model = restoredContract([
      sessionDto({
        actions: [
          { action: 'started', recorded_at: '2026-09-05T01:01:00+00:00' },
          { action: 'completed', recorded_at: '2026-09-05T01:02:00+00:00' },
        ],
        feedback: { usefulness: 'helpful', difficulty: 'easy' },
      }),
    ])

    expect(model.tasks).toHaveLength(1)
    expect(model.tasks[0]!.savedInteraction).toBe('done')
    expect(model.tasks[0]!.feedbackSaved).toBe(true)
    expect(model.state.mode).toBe('production')
  })

  it('keeps skipped restorable and started in-progress semantics from the event trail', () => {
    const model = restoredContract([
      sessionDto({
        recommendation_id: 'rec-2',
        actions: [{ action: 'skipped', recorded_at: '2026-09-05T01:03:00+00:00' }],
      }),
      sessionDto({
        recommendation_id: 'rec-3',
        task_id: 'MT-2',
        actions: [
          { action: 'started', recorded_at: '2026-09-05T01:04:00+00:00' },
          { action: 'partially_completed', recorded_at: '2026-09-05T01:05:00+00:00' },
        ],
      }),
    ])

    expect(model.tasks[0]!.savedInteraction).toBe('skipped')
    expect(model.tasks[1]!.savedInteraction).toBe('partial')
  })

  it('restores a started-then-restored session as pending again', () => {
    const model = restoredContract([
      sessionDto({
        actions: [
          { action: 'started', recorded_at: '2026-09-05T01:01:00+00:00' },
          { action: 'restored', recorded_at: '2026-09-05T01:02:00+00:00' },
        ],
      }),
    ])

    expect(model.tasks[0]!.savedInteraction).toBe('pending')
  })
})

describe('F4 mergeTodayContracts: records survive, candidates refresh', () => {
  const active = sessionDto({
    actions: [
      { action: 'started', recorded_at: '2026-09-05T01:01:00+00:00' },
      { action: 'completed', recorded_at: '2026-09-05T01:02:00+00:00' },
    ],
  })

  it('keeps saved records and takes pending candidates from the freshest recommendation', () => {
    const restored = restoredContract([
      active,
      sessionDto({ recommendation_id: 'rec-old', task_id: 'MT-OLD', title: '早上的候选' }),
    ])
    const fresh: TodayContract = {
      ...todayFixture,
      tasks: [todayFixture.tasks[0]!],
    }

    const merged = mergeTodayContracts(restored, fresh)

    expect(merged.tasks.map(task => task.taskId)).toEqual(['MT-1', todayFixture.tasks[0]!.taskId])
    expect(merged.tasks[0]!.savedInteraction).toBe('done')
  })

  it('falls back to restored pending candidates when the fresh recommendation has none', () => {
    const restored = restoredContract([active, sessionDto({ recommendation_id: 'rec-old', task_id: 'MT-OLD' })])

    const merged = mergeTodayContracts(restored, { ...todayFixture, tasks: [] })

    expect(merged.tasks.map(task => task.taskId)).toEqual(['MT-1', 'MT-OLD'])
  })

  it('does not re-suggest a task definition the user already handled today', () => {
    const restored = restoredContract([active])
    const fresh: TodayContract = {
      ...todayFixture,
      tasks: [{ ...todayFixture.tasks[0]!, taskId: 'MT-1', recommendationId: 'rec-again' }],
    }

    const merged = mergeTodayContracts(restored, fresh)

    expect(merged.tasks.map(task => task.recommendationId)).toEqual(['rec-1'])
  })
})

describe('F4 useDailyTasks: model refresh keeps local state', () => {
  function taskWithRec(index: number, rec: string) {
    return { ...todayFixture.tasks[index]!, recommendationId: rec }
  }

  it('keeps an in-progress task and its button set when a context refresh swaps candidates', async () => {
    const model = ref<TodayContract>({
      ...todayFixture,
      tasks: [taskWithRec(0, 'rec-1'), taskWithRec(1, 'rec-2'), taskWithRec(2, 'rec-3')],
    })
    const tasks = useDailyTasks(() => model.value)
    await tasks.start(tasks.entries.value[0]!.slotId)
    expect(tasks.entries.value[0]!.interaction).toBe('started')

    /* 心情/时间变化 → 新推荐换掉候选；进行中的 rec-1 必须保留。 */
    model.value = {
      ...todayFixture,
      tasks: [taskWithRec(0, 'rec-1'), taskWithRec(2, 'rec-9')],
    }
    await nextTick()

    expect(tasks.entries.value.map(entry => entry.task.recommendationId)).toEqual([
      'rec-1',
      'rec-9',
    ])
    expect(tasks.entries.value[0]!.interaction).toBe('started')
    expect(tasks.entries.value[0]!.actions).toBe('active')
  })

  it('retains a completed record even when the new recommendation no longer contains it', async () => {
    const model = ref<TodayContract>({
      ...todayFixture,
      tasks: [taskWithRec(0, 'rec-1')],
    })
    const tasks = useDailyTasks(() => model.value)
    await tasks.complete(tasks.entries.value[0]!.slotId)

    model.value = { ...todayFixture, tasks: [taskWithRec(1, 'rec-2')] }
    await nextTick()

    expect(tasks.completed.value).toBe(1)
    expect(tasks.entries.value.map(entry => entry.task.recommendationId)).toEqual([
      'rec-1',
      'rec-2',
    ])
  })

  it('replaces untouched pending candidates without carrying old state onto new tasks', async () => {
    const model = ref<TodayContract>({
      ...todayFixture,
      tasks: [taskWithRec(0, 'rec-1'), taskWithRec(1, 'rec-2')],
    })
    const tasks = useDailyTasks(() => model.value)
    await tasks.start(tasks.entries.value[1]!.slotId)

    model.value = {
      ...todayFixture,
      tasks: [taskWithRec(0, 'rec-9'), taskWithRec(1, 'rec-8')],
    }
    await nextTick()

    /* rec-2 已开始 → 保留；两个全新候选以初始状态进入，不套用旧状态。 */
    const byRec = new Map(tasks.entries.value.map(entry => [entry.task.recommendationId, entry]))
    expect(byRec.get('rec-2')!.interaction).toBe('started')
    expect(byRec.get('rec-9')!.interaction).toBe('pending')
    expect(byRec.get('rec-8')!.interaction).toBe('pending')
    expect(byRec.get('rec-9')!.actions).toBe('initial')
  })
})

describe('F4 useDailyTasks: restored entries boot into saved states', () => {
  it('boots a read-back completed task as completed with no re-ask when feedback saved', () => {
    const model = restoredContract([
      sessionDto({
        actions: [
          { action: 'started', recorded_at: '2026-09-05T01:01:00+00:00' },
          { action: 'completed', recorded_at: '2026-09-05T01:02:00+00:00' },
        ],
        feedback: { usefulness: 'helpful' },
      }),
    ])

    const tasks = useDailyTasks(model)

    expect(tasks.entries.value[0]!.interaction).toBe('done')
    expect(tasks.entries.value[0]!.actions).toBe('completed')
    expect(tasks.completed.value).toBe(1)
    expect(tasks.pendingFeedback.value).toHaveLength(0)
  })

  it('queues a restored feedback prompt for completed tasks without saved feedback', () => {
    const model = restoredContract([
      sessionDto({
        actions: [{ action: 'completed', recorded_at: '2026-09-05T01:02:00+00:00' }],
      }),
    ])

    const tasks = useDailyTasks(model)

    expect(tasks.pendingFeedback.value).toEqual([
      { slotId: tasks.entries.value[0]!.slotId, completionStatus: 'completed' },
    ])
  })
})
