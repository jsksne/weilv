import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'

import App from './App.vue'
import * as api from './api/client'
import { createUnavailableTodayContract } from './data/adapters'
import { useDailyTasks } from './composables/useDailyTasks'
import OnboardingFlow from './components/onboarding/OnboardingFlow.vue'
import TodayView from './views/TodayView.vue'
import type { TodayContract, TodayTaskView } from './contracts'

enableAutoUnmount(afterEach)

afterEach(() => {
  vi.unstubAllGlobals()
})

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const task: TodayTaskView = {
  id: 'MT-A',
  taskId: 'MT-A',
  recommendationId: 'rec-A',
  tone: 'default',
  domain: '微任务',
  meta: '约 5 分钟',
  name: '任务A',
  description: '指令A',
  why: '原因A',
  whyIcon: 'flower',
}

function todayModel(dataAvailability: 'available' | 'partial' | 'unavailable'): TodayContract {
  return {
    ...createUnavailableTodayContract(),
    state: { status: 'ready', mode: 'production' },
    dataAvailability,
    recommendationStatus: 'allowed',
    tasks: dataAvailability === 'unavailable' ? [] : [task],
  }
}

describe('Preflight — App onboarding submit binding', () => {
  it('calls the DataSource method bound to its instance (this.userId accessible)', async () => {
    vi.stubEnv('VITE_UI_MODE', 'production')
    vi.stubEnv('VITE_USER_ID', 'u-bind')
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/profile')) return Promise.resolve(json({ detail: 'profile_not_found' }, 404))
        if (url.includes('/weekly')) {
          return Promise.resolve(json({ user_id: 'u-bind', start_date: 'a', end_date: 'b', minutes_policy: 'x', days: [], totals: { completed_minutes: 0, action_counts: {} }, events: [], adjustments: [] }))
        }
        return Promise.reject(new Error(`unmocked ${url}`))
      }),
    )
    const upsert = vi.spyOn(api, 'upsertUserProfile').mockResolvedValue({
      user_id: 'u-bind', target_stage: 'junior_high', memory_enabled: false,
      created_at: 't', updated_at: 't',
    })

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.getComponent(OnboardingFlow).exists()).toBe(true)
    await wrapper.getComponent(OnboardingFlow).props('submit')({ grade: 'junior_high', memoryEnabled: false })
    await flushPromises()

    // 旧写法 :submit="dataSource?.submitOnboarding" 会因 this 丢失抛错，不会走到这里
    expect(upsert).toHaveBeenCalledWith('u-bind', { target_stage: 'junior_high', memory_enabled: false })
  })
})

describe('Preflight — TodayView production rendering', () => {
  function mountToday(dataAvailability: 'available' | 'partial' | 'unavailable') {
    const model = todayModel(dataAvailability)
    const daily = useDailyTasks(model)
    return mount(TodayView, { props: { model, daily } })
  }

  it('renders the production Hero card when dataAvailability is available', () => {
    const wrapper = mountToday('available')
    expect(wrapper.find('[data-testid="hero-progress"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('未提供：')
  })

  it('renders the production Hero card when dataAvailability is partial', () => {
    const wrapper = mountToday('partial')
    expect(wrapper.find('[data-testid="hero-progress"]').exists()).toBe(true)
  })

  it('still renders the production layout without internal "未提供" debug copy when dataAvailability is unavailable', () => {
    const wrapper = mountToday('unavailable')
    expect(wrapper.find('[data-testid="hero-progress"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('未提供：')
    expect(wrapper.text()).not.toContain('今日数据不可用')
  })
})
