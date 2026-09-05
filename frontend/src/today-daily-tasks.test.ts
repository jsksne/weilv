import { todayFixture } from './data/fixtures/today.fixture'
import { useDailyTasks } from './composables/useDailyTasks'

/* ------------------------------------------------------------------
   Sprint 4：useDailyTasks —— Today 本地交互状态机
   （迁移自原型 taskStates / updateProgress / moodRow / timeChips /
   REPLACE_POOL 脚本，仅 local state，不依赖 API）
   时钟可注入：450ms 同位换钮冷却的确定性测试。
   ------------------------------------------------------------------ */

function makeClock() {
  let now = 1_000_000
  return {
    now: () => now,
    advance: (ms: number) => {
      now += ms
    },
  }
}

/* 交互按槽位寻址（原型 data-idx）；内容 id 会随 replace 变化 */
function slot(tasks: ReturnType<typeof useDailyTasks>, index: number): string {
  return tasks.entries.value[index]!.slotId
}

describe('Sprint 4 useDailyTasks: initial state', () => {
  it('boots every task as pending with the frozen hero/docked notes at step 0', () => {
    const tasks = useDailyTasks(todayFixture)

    expect(tasks.entries.value).toHaveLength(3)
    expect(tasks.entries.value.every(entry => entry.interaction === 'pending')).toBe(true)
    expect(tasks.entries.value.every(entry => entry.actions === 'initial')).toBe(true)
    expect(tasks.completed.value).toBe(0)
    expect(tasks.total.value).toBe(3)
    expect(tasks.heroProgressNote.value).toBe('完成一件，就算今天有交代')
    expect(tasks.dockedProgressNote.value).toBe('捡起一片，就是今天的花瓣')
    expect(tasks.mood.value).toBe('calm')
    expect(tasks.availableMinutes.value).toBe(25)
    expect(tasks.entries.value[0]!.task.name).toBe('窗边远眺 20 秒')
  })
})

describe('Sprint 4 useDailyTasks: task state machine', () => {
  /* 原型 450ms 同位换钮冷却：start 后立刻 done 会被吞掉，测试注入时钟推进 */
  function setup() {
    const clock = makeClock()
    const tasks = useDailyTasks(todayFixture, { now: clock.now })
    return { clock, tasks }
  }

  it('keeps a production task pending when recording the action fails', async () => {
    const model = {
      ...todayFixture,
      tasks: [
        { ...todayFixture.tasks[0]!, recommendationId: 'rec-1' },
        ...todayFixture.tasks.slice(1),
      ],
    }
    const onAction = vi.fn().mockRejectedValue(new Error('offline'))
    const tasks = useDailyTasks(model, { onAction })
    const id = slot(tasks, 0)

    expect(await tasks.start(id)).toBe('submission-failed')
    expect(tasks.entries.value[0]!.interaction).toBe('pending')
    expect(tasks.entries.value[0]!.actions).toBe('initial')
  })

  it('start moves a pending task to started with the active button set', () => {
    const { tasks } = setup()
    const id = slot(tasks, 0)

    expect(tasks.start(id)).toBe('applied')
    expect(tasks.entries.value[0]!.interaction).toBe('started')
    expect(tasks.entries.value[0]!.actions).toBe('active')
    /* 原型 start 不改变进度 */
    expect(tasks.completed.value).toBe(0)
  })

  it('done marks the task terminal, counts progress and freezes the note copy', () => {
    const { clock, tasks } = setup()
    const id = slot(tasks, 0)

    tasks.start(id)
    clock.advance(450)
    expect(tasks.complete(id)).toBe('applied')
    expect(tasks.entries.value[0]!.interaction).toBe('done')
    expect(tasks.entries.value[0]!.actions).toBe('completed')
    expect(tasks.completed.value).toBe(1)
    expect(tasks.heroProgressNote.value).toBe('不错，慢慢来')
    expect(tasks.dockedProgressNote.value).toBe('很好呀，慢慢来')

    clock.advance(450)
    /* 终态幂等：原型 setTaskDone 对 done/partial 早退 */
    expect(tasks.complete(id)).toBe('rejected-state')
    expect(tasks.partial(id)).toBe('rejected-state')
    expect(tasks.completed.value).toBe(1)
  })

  it('partial also counts as progress with its own terminal state', () => {
    const { clock, tasks } = setup()
    const id = slot(tasks, 1)

    tasks.start(id)
    clock.advance(450)
    expect(tasks.partial(id)).toBe('applied')
    expect(tasks.entries.value[1]!.interaction).toBe('partial')
    expect(tasks.completed.value).toBe(1)
    clock.advance(450)
    expect(tasks.complete(id)).toBe('rejected-state')
  })

  it('skip parks the task without counting progress, restore returns it to pending', () => {
    const { clock, tasks } = setup()
    const id = slot(tasks, 2)

    expect(tasks.skip(id)).toBe('applied')
    expect(tasks.entries.value[2]!.interaction).toBe('skipped')
    expect(tasks.entries.value[2]!.actions).toBe('restore')
    expect(tasks.completed.value).toBe(0)

    clock.advance(450)
    expect(tasks.restore(id)).toBe('applied')
    expect(tasks.entries.value[2]!.interaction).toBe('pending')
    expect(tasks.entries.value[2]!.actions).toBe('initial')
  })

  it('progress notes walk the frozen four-step arrays and cap at total', () => {
    const { clock, tasks } = setup()

    tasks.complete(slot(tasks, 0))
    clock.advance(450)
    tasks.complete(slot(tasks, 1))
    clock.advance(450)
    expect(tasks.completed.value).toBe(2)
    expect(tasks.heroProgressNote.value).toBe('快收尾了，睡前那件最轻松')
    expect(tasks.dockedProgressNote.value).toBe('就剩一件啦')

    tasks.complete(slot(tasks, 2))
    expect(tasks.completed.value).toBe(3)
    expect(tasks.heroProgressNote.value).toBe('今天有交代了 ✦')
    expect(tasks.dockedProgressNote.value).toBe('今天的花瓣，凑齐啦 ✦')
  })

  it('hero progress and docked progress always derive from the same counter', () => {
    const { clock, tasks } = setup()

    for (const step of [0, 1, 2]) {
      expect(tasks.completed.value).toBe(step)
      tasks.complete(slot(tasks, step))
      clock.advance(450)
    }
    expect(tasks.completed.value).toBe(3)
    /* 单一状态源：两个 note 的索引一致（原型 updateProgress 同一 done 写两处） */
    expect(todayFixture.progressNotes.hero.indexOf(tasks.heroProgressNote.value))
      .toBe(todayFixture.progressNotes.docked.indexOf(tasks.dockedProgressNote.value))
  })
})

describe('Sprint 4 useDailyTasks: 450ms action cooldown', () => {
  it('swallows same-card actions within 450ms and does not extend the window', () => {
    const clock = makeClock()
    const tasks = useDailyTasks(todayFixture, { now: clock.now })
    const id = slot(tasks, 0)

    expect(tasks.start(id)).toBe('applied')
    /* 冷却内：吞掉，无状态变化 */
    clock.advance(400)
    expect(tasks.complete(id)).toBe('cooldown')
    expect(tasks.entries.value[0]!.interaction).toBe('started')

    /* 被吞掉的点击不刷新时间戳：t=500 距 start 500ms（若刷新过则只剩 100ms） */
    clock.advance(100)
    expect(tasks.complete(id)).toBe('applied')
    expect(tasks.entries.value[0]!.interaction).toBe('done')
  })

  it('keeps cooldown per card — other cards are unaffected', () => {
    const clock = makeClock()
    const tasks = useDailyTasks(todayFixture, { now: clock.now })

    tasks.start(slot(tasks, 0))
    expect(tasks.skip(slot(tasks, 1))).toBe('applied')
    expect(tasks.entries.value[1]!.interaction).toBe('skipped')
  })
})

describe('Sprint 4 useDailyTasks: replace pool', () => {
  it('cycles the frozen REPLACE_POOL with a shared pointer', () => {
    const clock = makeClock()
    const tasks = useDailyTasks(todayFixture, { now: clock.now })
    const id = slot(tasks, 0)

    tasks.replace(id)
    expect(tasks.entries.value[0]!.task.name).toBe('走廊慢走 · 5 分钟')
    expect(tasks.entries.value[0]!.task.tone).toBe('move')
    expect(tasks.entries.value[0]!.actions).toBe('initial')

    clock.advance(450)
    tasks.replace(id)
    expect(tasks.entries.value[0]!.task.name).toBe('掌心热敷闭眼')

    clock.advance(450)
    tasks.replace(slot(tasks, 2))
    /* 指针跨卡共享：第三张卡取到第 3 项 */
    expect(tasks.entries.value[2]!.task.name).toBe('窗边晒太阳 · 3 分钟')

    clock.advance(450)
    tasks.replace(id)
    expect(tasks.entries.value[0]!.task.name).toBe('走廊慢走 · 5 分钟')
  })

  it('resets the button set but keeps the interaction state (started stays started)', () => {
    const clock = makeClock()
    const tasks = useDailyTasks(todayFixture, { now: clock.now })
    const id = slot(tasks, 1)

    tasks.start(id)
    clock.advance(450)
    tasks.replace(id)
    expect(tasks.entries.value[1]!.interaction).toBe('started')
    expect(tasks.entries.value[1]!.actions).toBe('initial')

    /* 原型语义推论：start→replace 后该卡已非 pending，low 心情不再改写它 */
    tasks.applyMood('low')
    expect(tasks.entries.value[1]!.task.name).toBe('走廊慢走 · 5 分钟')
  })
})

describe('Sprint 4 useDailyTasks: mood and available time', () => {
  it('selects moods as single choice starting from the frozen default', () => {
    const tasks = useDailyTasks(todayFixture)

    expect(tasks.mood.value).toBe('calm')
    tasks.applyMood('tired')
    expect(tasks.mood.value).toBe('tired')
    tasks.applyMood('happy')
    expect(tasks.mood.value).toBe('happy')
    /* 非 low 心情不改写任务 */
    expect(tasks.entries.value[1]!.task.name).toBe('颈肩小伸展')
  })

  it('low mood rewrites only the second task copy while it is pending', () => {
    const tasks = useDailyTasks(todayFixture)

    tasks.applyMood('low')
    const swapped = tasks.entries.value[1]!.task
    expect(swapped.name).toBe('闭眼听声音 · 1 分钟')
    expect(swapped.description).toContain('闭上眼睛，数一数能听到几种声音')
    expect(swapped.why).toContain('有点低落')
    /* domain/meta/色调不变（原型只改 name/desc/why 三个文本节点） */
    expect(swapped.domain).toBe('颈肩放松')
    expect(swapped.meta).toBe('约 3 分钟 · 低强度')
    expect(swapped.tone).toBe('move')
    /* 其他卡不受影响 */
    expect(tasks.entries.value[0]!.task.name).toBe('窗边远眺 20 秒')

    /* 选回其他心情不回写（原型无回退逻辑） */
    tasks.applyMood('calm')
    expect(tasks.entries.value[1]!.task.name).toBe('闭眼听声音 · 1 分钟')
  })

  it('low mood does not touch a started second task', () => {
    const clock = makeClock()
    const tasks = useDailyTasks(todayFixture, { now: clock.now })

    tasks.start(slot(tasks, 1))
    tasks.applyMood('low')
    expect(tasks.entries.value[1]!.task.name).toBe('颈肩小伸展')
    expect(tasks.mood.value).toBe('low')
  })

  it('selects available time as single choice from the frozen default', () => {
    const tasks = useDailyTasks(todayFixture)

    expect(tasks.availableMinutes.value).toBe(25)
    tasks.selectTime(10)
    expect(tasks.availableMinutes.value).toBe(10)
    tasks.selectTime(40)
    expect(tasks.availableMinutes.value).toBe(40)
  })
})
