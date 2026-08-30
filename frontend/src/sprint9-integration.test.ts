import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'

import App from './App.vue'
import type {
  MemoryListResponse,
  RecommendationResponse,
  UserProfile,
  WeeklyResponse,
} from './api/types'
import {
  adaptMemoryListResponse,
  adaptRecommendationResponse,
  adaptWeeklyResponse,
} from './data/adapters'
import { ApiUiDataSource } from './data/apiUiDataSource'

enableAutoUnmount(afterEach)

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
  window.localStorage.clear()
})

/* ------------------------------------------------------------------ */

function profileObject(over: Partial<UserProfile> = {}): UserProfile {
  return {
    user_id: 'u-9',
    target_stage: 'senior_high',
    memory_enabled: false,
    created_at: '2026-08-20T00:00:00+00:00',
    updated_at: '2026-08-20T00:00:00+00:00',
    ...over,
  }
}

function memoryObject(over: Partial<MemoryListResponse> = {}): MemoryListResponse {
  return { user_id: 'u-9', memory_enabled: false, memories: [], ...over }
}

function threeTaskRecommendation(): RecommendationResponse {
  return {
    status: 'allowed',
    selected_task: {
      task_id: 'MT-A',
      title: '任务A',
      instruction: '指令A',
      evidence_chunk_ids: ['KC-A'],
      covered_domains: ['sedentary'],
      estimated_minutes: 5,
    },
    explanation: 'rank1 解释',
    sources: [],
    context_sources: [],
    matched_rule_ids: [],
    reason_codes: [],
    explanation_guard: { passed: true, fallback_used: false, reason_codes: [] },
    personalization: null,
    recommendation_id: 'rec-A',
    feedback_available: true,
    tasks: [
      { recommendation_id: 'rec-A', task_id: 'MT-A', title: '任务A', instruction: '指令A', estimated_minutes: 5, sources: [] },
      { recommendation_id: 'rec-B', task_id: 'MT-B', title: '任务B', instruction: '指令B', estimated_minutes: 10, sources: [] },
      { recommendation_id: 'rec-C', task_id: 'MT-C', title: '任务C', instruction: '指令C', estimated_minutes: 15, sources: [] },
    ],
  }
}

function weeklyResponse(): WeeklyResponse {
  return {
    user_id: 'u-9',
    start_date: '2026-08-18',
    end_date: '2026-08-24',
    minutes_policy: 'official_estimated_minutes_only',
    days: [
      { date: '2026-08-20', completed_minutes: 10, action_counts: { completed: 1 } },
      { date: '2026-08-21', completed_minutes: 0, action_counts: { skipped: 1 } },
    ],
    totals: { completed_minutes: 10, action_counts: { completed: 1, skipped: 1 } },
    events: [
      { recommendation_id: 'rec-A', task_id: 'MT-A', title: '任务A', action: 'completed', recorded_at: '2026-08-20T09:00:00+00:00' },
      { recommendation_id: 'rec-B', task_id: 'MT-B', title: '任务B', action: 'skipped', recorded_at: '2026-08-21T09:00:00+00:00' },
    ],
    adjustments: [],
  }
}

interface RouterState {
  profileStatus: number
  profile: UserProfile | null
  memory: MemoryListResponse
  recommendation: RecommendationResponse | null
  weekly: WeeklyResponse | null
  recommendationResponse?: Promise<Response>
  calls: Array<{ url: string; init: RequestInit }>
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function createProductionFetchRouter(state: RouterState) {
  const mock = vi.fn((input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = String(input)
    const record = { url, init: init ?? {} }
    state.calls.push(record)
    const method = init?.method ?? 'GET'

    if (url.includes('/profile')) {
      if (method === 'PUT') return Promise.resolve(json(profileObject()))
      if (state.profileStatus === 404) {
        return Promise.resolve(json({ detail: 'profile_not_found' }, 404))
      }
      if (state.profileStatus !== 200) {
        return Promise.resolve(json({ detail: 'dependency_service_unavailable' }, state.profileStatus))
      }
      return Promise.resolve(json(profileObject(state.profile ?? {})))
    }
    if (url.includes('/memories')) {
      if (url.includes('/delete')) return Promise.resolve(json({ status: 'forgotten', memory_id: 'x' }))
      return Promise.resolve(json(memoryObject(state.memory)))
    }
    if (url.includes('/weekly')) {
      return Promise.resolve(json(state.weekly))
    }
    if (url.includes('/events')) {
      return Promise.resolve(json({ status: 'recorded' }))
    }
    if (url.includes('/recommend')) {
      if (state.recommendationResponse) return state.recommendationResponse
      return Promise.resolve(json(state.recommendation))
    }
    if (url.includes('/recommendations')) {
      return Promise.resolve(json(state.recommendation))
    }
    return Promise.reject(new Error(`unmocked url: ${url}`))
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

function defaultRouterState(): RouterState {
  return {
    profileStatus: 200,
    profile: { user_id: 'u-9', target_stage: 'senior_high', memory_enabled: false, created_at: 't', updated_at: 't' },
    memory: { user_id: 'u-9', memory_enabled: false, memories: [] },
    recommendation: threeTaskRecommendation(),
    weekly: weeklyResponse(),
    calls: [],
  }
}

function requestBody(call: { url: string; init: RequestInit }): unknown {
  return JSON.parse(String(call.init.body))
}

/* ------------------------------------------------------------------ */

describe('Sprint 9 production mode boundary', () => {
  it('configures App as production with a real user identity (no demo user)', async () => {
    vi.stubEnv('VITE_UI_MODE', 'production')
    vi.stubEnv('VITE_USER_ID', 'u-9')
    const state = defaultRouterState()
    createProductionFetchRouter(state)
    /* 生产引导改为浏览器本地首次标记：已见过的浏览器不再弹。 */
    window.localStorage.setItem('weilv-prod-onboarding-seen', '1')
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.get('[data-testid="hero-progress"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('demo-user-001')
    expect(wrapper.find('[data-testid="onboarding"]').exists()).toBe(false)
    expect(state.calls.filter(call => call.url.includes('/profile')).length).toBe(1)
  })

  it('fails closed when VITE_USER_ID is missing in production', async () => {
    vi.stubEnv('VITE_UI_MODE', 'production')
    vi.stubEnv('VITE_USER_ID', undefined)
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.get('[data-testid="ui-data-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('VITE_USER_ID')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('fails closed when VITE_API_BASE_URL is missing in production', async () => {
    vi.stubEnv('VITE_UI_MODE', 'production')
    vi.stubEnv('VITE_USER_ID', 'u-9')
    vi.stubEnv('VITE_API_BASE_URL', undefined)
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.get('[data-testid="ui-data-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('VITE_API_BASE_URL')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('Sprint 9 new user → Onboarding', () => {
  it('shows first-visit onboarding while the Today recommendation is still loading', async () => {
    vi.stubEnv('VITE_UI_MODE', 'production')
    vi.stubEnv('VITE_USER_ID', 'u-9')
    let resolveRecommendation!: (response: Response) => void
    const state = defaultRouterState()
    state.recommendationResponse = new Promise(resolve => {
      resolveRecommendation = resolve
    })
    createProductionFetchRouter(state)

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.get('[data-testid="ui-data-loading"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="onboarding"]').exists()).toBe(true)

    resolveRecommendation(json(state.recommendation))
    await flushPromises()
    expect(wrapper.get('[data-testid="hero-progress"]').exists()).toBe(true)
  })

  it('shows onboarding on first visit; hides it after the local seen mark', async () => {
    vi.stubEnv('VITE_UI_MODE', 'production')
    vi.stubEnv('VITE_USER_ID', 'u-9')

    const newUser = defaultRouterState()
    newUser.profileStatus = 404
    newUser.weekly = null
    createProductionFetchRouter(newUser)
    const wrapper = mount(App)
    await flushPromises()
    expect(wrapper.get('[data-testid="onboarding"]').exists()).toBe(true)
    /* New user：production 仍渲染真实 Hero + Observation，不暴露「未提供」调试文案。 */
    expect(wrapper.get('[data-testid="hero-progress"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('未提供：')
    expect(wrapper.text()).not.toContain('今日数据不可用')
    wrapper.unmount()

    /* 已有 Profile 的浏览器同样按"本地首次"展示引导；写入 seen 标记后不再弹出。 */
    const existing = defaultRouterState()
    createProductionFetchRouter(existing)
    const existingWrapper = mount(App)
    await flushPromises()
    expect(existingWrapper.find('[data-testid="onboarding"]').exists()).toBe(true)
    existingWrapper.unmount()

    window.localStorage.setItem('weilv-prod-onboarding-seen', '1')
    const seenWrapper = mount(App)
    await flushPromises()
    expect(seenWrapper.find('[data-testid="onboarding"]').exists()).toBe(false)
    expect(seenWrapper.findAll('.task-card')).toHaveLength(3)
  })

  it('treats a server 500 as an error, never as a new user', async () => {
    vi.stubEnv('VITE_UI_MODE', 'production')
    vi.stubEnv('VITE_USER_ID', 'u-9')
    const state = defaultRouterState()
    state.profileStatus = 500
    createProductionFetchRouter(state)
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.get('[data-testid="ui-data-error"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="onboarding"]').exists()).toBe(false)
  })
})

describe('Sprint 9 B1 Top3 + B2 events through the App', () => {
  it('renders three real tasks and routes actions to each own recommendation_id', async () => {
    vi.stubEnv('VITE_UI_MODE', 'production')
    vi.stubEnv('VITE_USER_ID', 'u-9')
    const state = defaultRouterState()
    createProductionFetchRouter(state)
    const wrapper = mount(App)
    await flushPromises()

    const cards = wrapper.findAll('.task-card')
    expect(cards).toHaveLength(3)
    expect(cards.map(card => card.get('.task-name').text())).toEqual(['任务A', '任务B', '任务C'])

    await cards[1]!.get('[data-act="start"]').trigger('click')

    const eventCall = state.calls.find(call => call.url.includes('/events'))
    expect(eventCall).toBeDefined()
    expect(String(eventCall!.url)).toContain('rec-B')
    /* B2 事件只有 action，绝不携带 Feedback 字段。 */
    expect(requestBody(eventCall!)).toEqual({ action: 'started' })
  })

  it('uses the loaded profile.target_stage in the recommendation request (no hardcode)', async () => {
    vi.stubEnv('VITE_UI_MODE', 'production')
    vi.stubEnv('VITE_USER_ID', 'u-9')
    const state = defaultRouterState()
    state.profile = { user_id: 'u-9', target_stage: 'junior_high', memory_enabled: false, created_at: 't', updated_at: 't' }
    createProductionFetchRouter(state)
    const wrapper = mount(App)
    await flushPromises()

    const recommendationCall = state.calls.find(call => call.url.includes('/recommendations') && !call.url.includes('/recommend/'))
    expect(recommendationCall).toBeDefined()
    const body = requestBody(recommendationCall!) as { target_stage: string }
    expect(body.target_stage).toBe('junior_high')
    expect(wrapper.get('[data-testid="hero-progress"]').exists()).toBe(true)
  })
})

describe('Sprint 9 B4 / B5 DataSource integration', () => {
  it('deletes a Memory through the real endpoint and does not fake success on failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(json(memoryObject({ memory_enabled: true, memories: [{ memory_id: 'UM-1', memory_type: 'task_feedback', summary: '已完成', created_at: 't', updated_at: 't' }] }))),
    )
    const source = new ApiUiDataSource({ userId: 'u-9' })

    const memories = await source.getUserMemories()
    expect(memories.items).toHaveLength(1)
    expect(memories.canDelete).toBe(true)
    expect(memories.items[0]!.id).toBe('UM-1')

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ detail: 'down' }, 503)))
    await expect(source.deleteUserMemory('UM-1')).rejects.toMatchObject({ status: 503 })
  })

  it('maps B5 weekly deterministically without AI insight', () => {
    const model = adaptWeeklyResponse(weeklyResponse())

    expect(model.dataAvailability).toBe('available')
    expect(model.days).toEqual(['08-20', '08-21'])
    expect(model.minutes).toEqual([10, 0])
    expect(model.timeline.map(item => item.status)).toEqual(['completed', 'skipped'])
    expect(JSON.stringify(model)).not.toContain('越来越')
    expect(model.insight.title).toBe('本周统计')
    expect(model.insight.segments[0]!.text).toContain('完成 1 项')
  })

  it('maps B4 memory list without leaking internal fields', () => {
    const contract = adaptMemoryListResponse({
      user_id: 'u-9',
      memory_enabled: true,
      memories: [
        { memory_id: 'UM-1', memory_type: 'task_feedback', summary: '已完成 · 帮助度 5/5', created_at: 't', updated_at: 't' },
      ],
    })

    expect(contract.items[0]).toEqual({ id: 'UM-1', icon: 'leaf', lead: 'task_feedback', text: '已完成 · 帮助度 5/5' })
    expect(JSON.stringify(contract)).not.toContain('retrieval_text')
    expect(JSON.stringify(contract)).not.toContain('embedding')
  })

  it('does not fall back to fixture on API failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'x' }), { status: 503 })),
    )
    const source = new ApiUiDataSource({ userId: 'u-9', recommendationRequest: { user_id: 'u-9', query: 'q', target_stage: 'senior_high', current_context: 'home', activity_context: 'writing', available_minutes: 10, vision_abnormal: false, physical_discomfort: false, medical_request: false, cannot_move: false, unstable_environment: false, sleep_being_crowded: false } })

    await expect(source.getToday()).rejects.toMatchObject({ status: 503 })
  })
})

describe('Sprint 9 Today adapter B1 semantics', () => {
  it('renders 2 tasks without fabricating a third', () => {
    const dto = threeTaskRecommendation()
    dto.tasks = dto.tasks!.slice(0, 2)
    const model = adaptRecommendationResponse(dto)

    expect(model.tasks).toHaveLength(2)
    expect(model.dataAvailability).toBe('partial')
  })

  it('keeps independent recommendation ids on every surfaced task', () => {
    const model = adaptRecommendationResponse(threeTaskRecommendation())

    expect(model.tasks.map(task => task.recommendationId)).toEqual(['rec-A', 'rec-B', 'rec-C'])
    expect(model.tasks[0]!.taskId).toBe('MT-A')
  })

  it('returns no tasks for safety statuses', () => {
    for (const status of ['blocked', 'help_seeking', 'no_safe_task'] as const) {
      const model = adaptRecommendationResponse({
        ...threeTaskRecommendation(),
        status,
        selected_task: null,
        explanation: null,
        recommendation_id: null,
        tasks: null,
      })
      expect(model.tasks).toHaveLength(0)
      expect(model.recommendationStatus).toBe(status)
    }
  })

  it('keeps rank1 explanation and omits it for ranks 2+', () => {
    const model = adaptRecommendationResponse(threeTaskRecommendation())

    expect(model.tasks[0]!.why).toBe('rank1 解释')
    expect(model.tasks[1]!.why).not.toBe('rank1 解释')
  })
})
