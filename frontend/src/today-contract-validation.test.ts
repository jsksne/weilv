import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { todayFixture } from './data/fixtures/today.fixture'
import type { TodayContract, TodayTaskView } from './contracts/today'

/* ------------------------------------------------------------------
   Sprint 4：Today fixture 必须满足 Today Contract（同一套类型，
   不创建第二套），内容来自冻结原型而非新造数据。
   ------------------------------------------------------------------ */

const srcDir = dirname(fileURLToPath(import.meta.url))

const todayRuntimeFiles = [
  'views/TodayView.vue',
  'components/today/TodayHero.vue',
  'components/today/ObservationCard.vue',
  'components/today/DailyCheckCard.vue',
  'components/today/MoodSelector.vue',
  'components/today/AvailableTimeSelector.vue',
  'components/today/TaskList.vue',
  'components/today/TaskCard.vue',
  'components/today/BreathCard.vue',
  'components/today/RhythmTimeline.vue',
  'composables/useDailyTasks.ts',
  'composables/useBreathCycle.ts',
  'data/fixtures/today.fixture.ts',
]

function readTodayRuntimeFile(file: string): string {
  return readFileSync(join(srcDir, file), 'utf8')
}

describe('Sprint 4 today contract validation', () => {
  it('satisfies the TodayContract type with frozen prototype content', () => {
    const fixture: TodayContract = todayFixture

    expect(fixture.state.status).toBe('ready')
    expect(fixture.state.mode).toBe('demo')
  })

  it('freezes the hero copy from the prototype', () => {
    expect(todayFixture.heroTag).toBe('✦ 健康微行动 · 期中考试周 · 第 2 天')
    expect(todayFixture.greetingLead).toBe('早上好，')
    expect(todayFixture.greetingName).toBe('小满')
    /* 昨晚睡了 6 小时 50 分，比前天多 40 分钟——……<br>微律准备了 3 件微任务…… */
    expect(todayFixture.summaryLines).toHaveLength(2)
    expect(todayFixture.summaryLines[0]).toEqual([
      { text: '昨晚睡了 ' },
      { text: '6 小时 50 分', emphasis: true },
      { text: '，比前天多 40 分钟——今天的状态，比昨天轻松一点。' },
    ])
    expect(todayFixture.summaryLines[1]).toEqual([
      { text: '微律准备了 ' },
      { text: '3 件微任务', emphasis: true },
      { text: '，都很小，小到像捡起一片花瓣。' },
    ])
  })

  it('freezes the three prototype task cards with unique ids', () => {
    const tasks = todayFixture.tasks

    expect(tasks).toHaveLength(3)
    expect(new Set(tasks.map(task => task.id)).size).toBe(3)

    expect(tasks[0]).toMatchObject({
      tone: 'eye',
      domain: '用眼健康',
      meta: '约 1 分钟 · 极低强度',
      name: '窗边远眺 20 秒',
      whyIcon: 'flower',
    })
    expect(tasks[1]).toMatchObject({ tone: 'move', domain: '颈肩放松', name: '颈肩小伸展' })
    expect(tasks[2]).toMatchObject({ tone: 'sleep', domain: '睡前准备', name: '花瓣呼吸 4-7-8' })
    expect(tasks[2]!.description).toContain('吸气 4 秒')
    expect(tasks.every(task => task.why.length > 0)).toBe(true)
  })

  it('freezes the replace pool from the prototype REPLACE_POOL', () => {
    const pool = todayFixture.replacePool

    expect(pool).toHaveLength(3)
    expect(pool.map(item => item.name)).toEqual([
      '走廊慢走 · 5 分钟',
      '掌心热敷闭眼',
      '窗边晒太阳 · 3 分钟',
    ])
    expect(pool.every(item => item.tone && item.domain && item.meta && item.description && item.why)).toBe(true)
  })

  it('freezes mood / time defaults from the prototype (calm / 25)', () => {
    expect(todayFixture.moods.map(mood => mood.value)).toEqual(['happy', 'calm', 'tired', 'low'])
    expect(todayFixture.moods.map(mood => mood.label)).toEqual(['还不错', '平静', '有点累', '有点低落'])
    expect(todayFixture.defaultMood).toBe('calm')
    expect(todayFixture.timeOptions.map(option => option.minutes)).toEqual([10, 25, 40])
    expect(todayFixture.defaultTimeMinutes).toBe(25)
  })

  it('freezes the low-mood swap copy applied to the second task only', () => {
    expect(todayFixture.lowMoodSwap.taskId).toBe(todayFixture.tasks[1]!.id)
    expect(todayFixture.lowMoodSwap.name).toBe('闭眼听声音 · 1 分钟')
    expect(todayFixture.lowMoodSwap.description).toContain('闭上眼睛，数一数能听到几种声音')
    expect(todayFixture.lowMoodSwap.why).toContain('有点低落')
  })

  it('freezes hero and docked progress notes as four-step arrays', () => {
    expect(todayFixture.progressNotes.hero).toEqual([
      '完成一件，就算今天有交代',
      '不错，慢慢来',
      '快收尾了，睡前那件最轻松',
      '今天有交代了 ✦',
    ])
    expect(todayFixture.progressNotes.docked).toEqual([
      '捡起一片，就是今天的花瓣',
      '很好呀，慢慢来',
      '就剩一件啦',
      '今天的花瓣，凑齐啦 ✦',
    ])
  })

  it('freezes interaction feedback copy from the prototype', () => {
    expect(todayFixture.feedbackCopy.start).toBe('⏱ 开始啦 · 不着急')
    expect(todayFixture.feedbackCopy.done).toBe('✦ 已记下这次完成 · 薇薇会记住的')
    expect(todayFixture.feedbackCopy.partial).toBe('🌱 部分完成也很棒 · 已记录')
    expect(todayFixture.feedbackCopy.skip).toBe('🕊 跳过也没关系 · 薇薇会降低这类任务的频率')
    expect(todayFixture.feedbackCopy.restore).toBe('')
    expect(todayFixture.feedbackCopy.replace).toBe('🌸 换好了 · 新任务同样来自审核白名单')
    expect(todayFixture.feedbackCopy.lowMood).toBe('🌷 收到 · 薇薇把任务都换成了最轻的')
    expect(todayFixture.feedbackCopy.check).toBe('✦ 从此刻的心情开始 · 30 秒完成今日检查')
  })

  it('freezes the rhythm timeline with the now marker on the first item', () => {
    const items = todayFixture.rhythm.items

    expect(items).toHaveLength(3)
    expect(items[0]).toMatchObject({ time: '17:30', title: '窗边远眺', now: true })
    expect(items[1]).toMatchObject({ time: '18:10', title: '颈肩小伸展' })
    expect(items[2]).toMatchObject({ time: '21:40', title: '花瓣呼吸' })
  })

  it('replaces pool entries are valid TodayTaskView without api DTO leakage', () => {
    const sample: TodayTaskView = todayFixture.replacePool[0]!

    expect(sample.id).toContain('pool')
  })

  it('keeps today runtime files free of api/types and fetch usage', () => {
    for (const file of todayRuntimeFiles) {
      const source = readTodayRuntimeFile(file)
      expect(source, file).not.toMatch(/api\/types/)
      expect(source, file).not.toMatch(/\bfetch\s*\(/)
    }
  })
})
