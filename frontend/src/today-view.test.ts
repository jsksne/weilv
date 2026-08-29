import { enableAutoUnmount, mount } from '@vue/test-utils'

import TodayView from './views/TodayView.vue'
import { todayFixture } from './data/fixtures/today.fixture'
import { createUnavailableTodayContract } from './data/adapters'
import { useDailyTasks } from './composables/useDailyTasks'
import { useToast } from './composables/useToast'

/* ------------------------------------------------------------------
   Sprint 4：TodayView 挂载与交互接线（结构 selector 来自冻结原型；
   交互结果与原型脚本行为一一对应）。冷却时钟注入，避免真实等待。
   ------------------------------------------------------------------ */

enableAutoUnmount(afterEach)

function makeClock() {
  let now = 1_000_000
  return { now: () => now, advance: (ms: number) => (now += ms) }
}

function mountToday() {
  const clock = makeClock()
  const daily = useDailyTasks(todayFixture, { now: clock.now })
  const wrapper = mount(TodayView, { props: { model: todayFixture, daily } })
  return { wrapper, daily, clock }
}

function toastMessages(): string[] {
  return useToast().toasts.value.map(toast => toast.message)
}

const TASK_COPY = {
  start: '开始',
  done: '✓ 完成啦',
  partial: '部分完成',
  replace: '换一朵',
  skip: '先跳过',
  restore: '恢复它',
}

describe('Sprint 4 TodayView: frozen structure', () => {
  it('renders the hero with greeting, summary, progress row and CTA', () => {
    const { wrapper } = mountToday()

    const hero = wrapper.get('.hero')
    expect(hero.find('.hero-arc').exists()).toBe(true)
    expect(hero.get('.hero-tag').text()).toBe('✦ 健康微行动 · 期中考试周 · 第 2 天')
    expect(hero.get('h1').text()).toBe('早上好，小满')
    expect(hero.get('h1 em').text()).toBe('小满')
    expect(hero.get('p b').text()).toBe('6 小时 50 分')
    expect(hero.get('[data-testid="hero-progress"]').text()).toContain('0')
    expect(hero.get('.progress-num small').text()).toContain('3')
    expect(hero.get('.progress-note').text()).toBe('完成一件，就算今天有交代')
    expect(hero.get('.progress-cta button').text()).toBe('✦ 开始今日检查')
    expect(hero.get('.hero-hint').text()).toBe('约 30 秒 · 从此刻的心情开始')
  })

  it('renders the observation card, mood card and three task cards', () => {
    const { wrapper } = mountToday()

    const observe = wrapper.get('.observe-card')
    expect(observe.get('.obs-main em').text()).toBe('轻松一点')
    expect(observe.findAll('.ob-stat')).toHaveLength(3)
    expect(observe.findAll('.sug-item')).toHaveLength(2)

    const moodCard = wrapper.get('.mood-card')
    const moods = moodCard.findAll('.mood')
    expect(moods).toHaveLength(4)
    expect(moods.map(mood => mood.findAll('span')[1]!.text())).toEqual(['还不错', '平静', '有点累', '有点低落'])
    expect(moods.map(mood => mood.get('.face').text())).toEqual(['◕‿◕', '˘‿˘', '>﹏<', '·︿·'])
    expect(moods[1]!.classes()).toContain('on')
    const chips = moodCard.findAll('.chip')
    expect(chips).toHaveLength(3)
    expect(chips[1]!.classes()).toContain('on')
    expect(chips[1]!.text()).toBe('25 分钟')

    const cards = wrapper.findAll('.task-card')
    expect(cards).toHaveLength(3)
    expect(cards[0]!.find('.task-domain').text()).toBe('用眼健康')
    expect(cards[1]!.find('.task-name').text()).toBe('颈肩小伸展')
    expect(cards[0]!.find('.task-why b').text()).toBe('为什么是它')
    expect(cards[0]!.find('.task-state svg').exists()).toBe(true)
    expect(cards[0]!.find('.task-badge').exists()).toBe(true)
  })

  it('renders the breath and rhythm cards in the aside', () => {
    const { wrapper } = mountToday()

    const breath = wrapper.get('.breath-card')
    expect(breath.get('h3').text()).toBe('此刻 · 跟随呼吸')
    expect(breath.find('.breath-core').exists()).toBe(true)
    expect(breath.findAll('.breath-halo')).toHaveLength(3)

    const rhythm = wrapper.get('.rhythm-card')
    expect(rhythm.findAll('.rhythm-item')).toHaveLength(3)
    expect(rhythm.find('.rhythm-item.now').exists()).toBe(true)
  })

  it('mounts the docked topbar progress bound to the same counter', () => {
    const { wrapper } = mountToday()

    const topbar = wrapper.get('[data-testid="docked-progress"]')
    expect(topbar.get('.tb-num').text()).toBe('0 / 3')
    expect(topbar.get('.tb-note').text()).toBe('捡起一片，就是今天的花瓣')
  })
})

describe('Sprint 4 TodayView: task interactions', () => {
  it('start swaps the button set, done marks terminal state with fx, toast and progress', async () => {
    vi.useFakeTimers()
    const { wrapper, clock } = mountToday()
    const card = wrapper.findAll('.task-card')[0]!

    await card.get('[data-act="start"]').trigger('click')
    expect(card.findAll('.task-actions button').map(btn => btn.text())).toEqual([
      TASK_COPY.done,
      TASK_COPY.partial,
      TASK_COPY.replace,
      TASK_COPY.skip,
    ])
    expect(toastMessages()).toContain('⏱ 开始啦 · 不着急')

    clock.advance(450)
    await card.get('[data-act="done"]').trigger('click')
    await vi.advanceTimersByTimeAsync(0)

    expect(card.classes()).toContain('done')
    expect(card.get('.badge-txt').text()).toBe('完成 · 今天的花瓣 +1')
    expect(card.get('.done-note').text()).toBe('🌸 已记下 · 今天的一片花瓣')
    expect(card.find('[data-act]').exists()).toBe(false)
    expect(toastMessages()).toContain('✦ 已记下这次完成 · 薇薇会记住的')
    expect(wrapper.get('.progress-num').text()).toContain('1')
    expect(wrapper.get('[data-testid="docked-progress"] .tb-num').text()).toBe('1 / 3')
    vi.useRealTimers()
  })

  it('skip parks the card and restore returns the initial buttons', async () => {
    const { wrapper, clock } = mountToday()
    const card = wrapper.findAll('.task-card')[2]!

    await card.get('[data-act="skip"]').trigger('click')
    expect(card.classes()).toContain('skippedcard')
    expect(card.get('.badge-txt').text()).toBe('跳过了 · 没关系呀')
    expect(card.get('[data-act="restore"]').text()).toBe(TASK_COPY.restore)
    expect(toastMessages()).toContain('🕊 跳过也没关系 · 薇薇会降低这类任务的频率')

    clock.advance(450)
    await card.get('[data-act="restore"]').trigger('click')
    expect(card.classes()).not.toContain('skippedcard')
    expect(
      card.findAll('.task-actions button').map(btn => btn.text()),
    ).toEqual([TASK_COPY.start, TASK_COPY.replace, TASK_COPY.skip])
  })

  it('replace swaps the card content from the frozen pool', async () => {
    vi.useFakeTimers()
    const { wrapper } = mountToday()
    const card = wrapper.findAll('.task-card')[0]!

    await card.get('[data-act="replace"]').trigger('click')
    await vi.advanceTimersByTimeAsync(470)

    expect(card.get('.task-name').text()).toBe('走廊慢走 · 5 分钟')
    expect(card.get('.task-domain').text()).toBe('轻活动')
    expect(toastMessages()).toContain('🌸 换好了 · 新任务同样来自审核白名单')
    vi.useRealTimers()
  })

  it('partial keeps its own badge and done-note copy', async () => {
    const { wrapper, clock } = mountToday()
    const card = wrapper.findAll('.task-card')[1]!

    await card.get('[data-act="start"]').trigger('click')
    clock.advance(450)
    await card.get('[data-act="partial"]').trigger('click')

    expect(card.classes()).toContain('partial')
    expect(card.get('.badge-txt').text()).toBe('部分完成 · 也算数哦')
    expect(card.get('.done-note').text()).toBe('🌱 部分完成 · 已记下')
    expect(toastMessages()).toContain('🌱 部分完成也很棒 · 已记录')
  })

  it('plays the completion fx at the task-state center on done', async () => {
    vi.useFakeTimers()
    const plays: Array<[number, number]> = []
    const stub = {
      name: 'TaskCompletionFx',
      props: {},
      setup() {
        return { play: (cx: number, cy: number) => plays.push([cx, cy]), reset: () => {} }
      },
      render: () => null,
    }
    const clock = makeClock()
    const daily = useDailyTasks(todayFixture, { now: clock.now })
    const wrapper = mount(TodayView, {
      props: { model: todayFixture, daily },
      global: { stubs: { TaskCompletionFx: stub } },
    })

    const card = wrapper.findAll('.task-card')[0]!
    await card.get('[data-act="start"]').trigger('click')
    clock.advance(450)
    await card.get('[data-act="done"]').trigger('click')

    expect(plays).toHaveLength(1)
    vi.useRealTimers()
  })
})

describe('Sprint 4 TodayView: mood, time and check CTA', () => {
  it('low mood rewrites the second task copy and toasts', async () => {
    const { wrapper } = mountToday()
    const card = wrapper.findAll('.task-card')[1]!

    await wrapper.findAll('.mood')[3]!.trigger('click')

    expect(wrapper.findAll('.mood')[3]!.classes()).toContain('on')
    expect(card.get('.task-name').text()).toBe('闭眼听声音 · 1 分钟')
    expect(card.get('.task-domain').text()).toBe('颈肩放松')
    expect(toastMessages()).toContain('🌷 收到 · 薇薇把任务都换成了最轻的')
  })

  it('switches the selected available time chip', async () => {
    const { wrapper } = mountToday()
    const chips = wrapper.findAll('.chip')

    await chips[0]!.trigger('click')

    expect(chips[0]!.classes()).toContain('on')
    expect(chips[1]!.classes()).not.toContain('on')
  })

  it('keeps mood and time choices available when Production Today context is missing', async () => {
    const model = createUnavailableTodayContract('missing current context')
    const daily = useDailyTasks(model)
    const wrapper = mount(TodayView, { props: { model, daily } })

    expect(wrapper.findAll('.mood')).toHaveLength(4)
    expect(wrapper.findAll('.chip')).toHaveLength(3)

    await wrapper.findAll('.mood')[2]!.trigger('click')
    await wrapper.findAll('.chip')[0]!.trigger('click')

    expect(daily.mood.value).toBe('tired')
    expect(daily.availableMinutes.value).toBe(10)
    expect(wrapper.emitted('context-change')?.at(-1)?.[0]).toEqual({
      mood: 'tired',
      availableMinutes: 10,
    })
  })

  it('check CTA focuses the mood card and toasts the frozen copy', async () => {
    vi.useFakeTimers()
    const { wrapper } = mountToday()

    await wrapper.get('.progress-cta button').trigger('click')

    const moodCard = wrapper.get('.mood-card')
    expect(moodCard.classes()).toContain('check-focus')
    expect(toastMessages()).toContain('✦ 从此刻的心情开始 · 30 秒完成今日检查')

    vi.advanceTimersByTime(1700)
    await vi.advanceTimersByTimeAsync(0)
    expect(moodCard.classes()).not.toContain('check-focus')
    vi.useRealTimers()
  })
})
