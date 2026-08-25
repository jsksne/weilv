import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'

import { streamAgenticRecommendation } from './api/client'
import type {
  AgentTraceEventDto,
  RecommendationResponse,
} from './api/types'
import {
  adaptAgenticRecommendation,
  applyAgentTraceEvent,
  createLiveTracePipeline,
  createProductionAssistantContract,
} from './data/adapters'
import { ApiUiDataSource } from './data/apiUiDataSource'
import { assistantFixture } from './data/fixtures/assistant.fixture'
import AssistantView from './views/AssistantView.vue'
import type { AssistantReply, AssistantTraceEvent, UiDataSource } from './contracts'

enableAutoUnmount(afterEach)

afterEach(() => {
  vi.unstubAllGlobals()
})

function allowedDto(): RecommendationResponse {
  return {
    status: 'allowed',
    selected_task: {
      task_id: 'MT-EYE-001',
      title: '远眺 1 分钟',
      instruction: '起身到窗边远眺。',
      estimated_minutes: 1,
    },
    explanation: '真实最终回答：先休息一下，到窗边远眺 1 分钟。',
    sources: [
      {
        chunk_id: 'KC-1',
        source_locator: '健康知识库',
        source_url: 'https://example.org/knowledge',
      },
    ],
    context_sources: [],
    matched_rule_ids: [],
    reason_codes: [],
    explanation_guard: { passed: true, fallback_used: false, reason_codes: [] },
    personalization: null,
    recommendation_id: 'rec-b3-1',
    feedback_available: true,
  }
}

function ndjsonResponse(lines: unknown[]): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoder.encode(lines.map(line => JSON.stringify(line)).join('\n') + '\n'))
      controller.close()
    },
  })
  return new Response(stream, { status: 200, headers: { 'Content-Type': 'application/x-ndjson' } })
}

const completeStream: AgentTraceEventDto[] = [
  { stage: 'accepted', status: 'active', label: '正在理解你的需求', sequence: 1, timestamp_ms: 0 },
  { stage: 'safety', status: 'active', label: '正在进行安全检查', sequence: 2, timestamp_ms: 12 },
  { stage: 'analysis', status: 'active', label: '正在理解你的需求', sequence: 3, timestamp_ms: 40 },
  { stage: 'retrieval', status: 'active', label: '正在检索相关健康知识', sequence: 4, timestamp_ms: 120 },
  { stage: 'ranking', status: 'active', label: '正在匹配适合的信息', sequence: 5, timestamp_ms: 840 },
  { stage: 'personalization', status: 'active', label: '正在匹配适合的信息', sequence: 6, timestamp_ms: 950 },
  { stage: 'grounding', status: 'active', label: '正在核对信息', sequence: 7, timestamp_ms: 1300 },
  { stage: 'generation', status: 'active', label: '正在整理建议', sequence: 8, timestamp_ms: 1800 },
  { stage: 'completed', status: 'complete', label: '处理完成', sequence: 9, timestamp_ms: 2840, result: allowedDto() },
]

describe('B3 client — stream API transport', () => {
  const request = {
    user_id: 'b3-user',
    query: '最近睡不好',
    target_stage: 'junior_high' as const,
    current_context: 'home' as const,
    activity_context: 'reading' as const,
    available_minutes: 10,
    vision_abnormal: false,
    physical_discomfort: false,
    medical_request: false,
    cannot_move: false,
    unstable_environment: false,
    sleep_being_crowded: false,
  }

  it('posts to the stream endpoint and surfaces sanitized events in order', async () => {
    const fetchMock = vi.fn().mockResolvedValue(ndjsonResponse(completeStream))
    vi.stubGlobal('fetch', fetchMock)
    const events: AgentTraceEventDto[] = []

    const final = await streamAgenticRecommendation(request, event => events.push(event))

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/recommend/agentic/stream',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(events.map(event => event.stage)).toEqual([
      'accepted', 'safety', 'analysis', 'retrieval', 'ranking',
      'personalization', 'grounding', 'generation', 'completed',
    ])
    expect(events.map(event => event.label)).not.toContain('正在结合你的历史情况')
    expect(final.explanation).toBe('真实最终回答：先休息一下，到窗边远眺 1 分钟。')
  })

  it('never calls the old non-stream agentic endpoint from the stream client', async () => {
    const fetchMock = vi.fn().mockResolvedValue(ndjsonResponse(completeStream))
    vi.stubGlobal('fetch', fetchMock)

    await streamAgenticRecommendation(request, () => {})

    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('/agentic/stream')
    expect(url).not.toMatch(/\/agentic$/)
  })

  it('throws a safe error when the stream is interrupted without a completed event', async () => {
    const truncated = completeStream.slice(0, 5) // 没有 completed
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ndjsonResponse(truncated)))

    await expect(streamAgenticRecommendation(request, () => {})).rejects.toMatchObject({
      code: 'stream_interrupted',
    })
  })

  it('throws ApiError on non-2xx stream response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'dependency_service_unavailable' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )

    await expect(streamAgenticRecommendation(request, () => {})).rejects.toMatchObject({
      status: 503,
      code: 'service_unavailable',
    })
  })
})

describe('B3 adapter — real trace pipeline', () => {
  it('does not advance without any event', () => {
    const pipeline = createLiveTracePipeline()
    expect(pipeline.analysis.status).toBe('pending')
    expect(pipeline.retrieval.status).toBe('pending')
    expect(pipeline.answer.status).toBe('pending')
  })

  it('drives the three frozen rows from real coarse stages', () => {
    let pipeline = createLiveTracePipeline()
    pipeline = applyAgentTraceEvent(pipeline, { stage: 'accepted', status: 'active', label: '正在理解你的需求' })
    pipeline = applyAgentTraceEvent(pipeline, { stage: 'safety', status: 'active', label: '正在进行安全检查' })
    expect(pipeline.analysis.status).toBe('active')
    expect(pipeline.retrieval.status).toBe('pending')

    pipeline = applyAgentTraceEvent(pipeline, { stage: 'ranking', status: 'active', label: '正在匹配适合的信息' })
    expect(pipeline.analysis.status).toBe('done')
    expect(pipeline.retrieval.status).toBe('active')

    pipeline = applyAgentTraceEvent(pipeline, { stage: 'generation', status: 'active', label: '正在整理建议' })
    expect(pipeline.retrieval.status).toBe('done')
    expect(pipeline.answer.status).toBe('active')

    pipeline = applyAgentTraceEvent(pipeline, { stage: 'completed', status: 'complete', label: '处理完成' })
    expect(pipeline.analysis.status).toBe('done')
    expect(pipeline.retrieval.status).toBe('done')
    // answer 的 done 由最终 reply 呈现，live 期间保持 active
    expect(pipeline.answer.status).toBe('active')
  })

  it('never fabricates generation when the trace stopped early', () => {
    let pipeline = createLiveTracePipeline()
    pipeline = applyAgentTraceEvent(pipeline, { stage: 'safety', status: 'active', label: '正在进行安全检查' })
    pipeline = applyAgentTraceEvent(pipeline, { stage: 'completed', status: 'complete', label: '处理完成' })
    expect(pipeline.answer.status).toBe('pending') // 未出现 generation，绝不伪造
    expect(pipeline.retrieval.status).toBe('pending')
  })
})

describe('B3 DataSource — Production uses the stream API', () => {
  it('submits via /agentic/stream and maps sanitized events to UI contract', async () => {
    const fetchMock = vi.fn().mockResolvedValue(ndjsonResponse(completeStream))
    vi.stubGlobal('fetch', fetchMock)

    const source = new ApiUiDataSource({
      userId: 'b3-user',
      recommendationRequest: {
        user_id: 'b3-user',
        query: '最近睡不好',
        target_stage: 'junior_high',
        current_context: 'home',
        activity_context: 'reading',
        available_minutes: 10,
        vision_abnormal: false,
        physical_discomfort: false,
        medical_request: false,
        cannot_move: false,
        unstable_environment: false,
        sleep_being_crowded: false,
      },
    })
    const uiEvents: AssistantTraceEvent[] = []
    const reply = await source.askAssistantStreaming('最近睡不好', event => uiEvents.push(event))

    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('/agentic/stream')
    expect(uiEvents).toHaveLength(9)
    expect(uiEvents[0]).toEqual({ stage: 'accepted', status: 'active', label: '正在理解你的需求' })
    expect(reply.traceIsReal).toBe(true)
    expect(reply.answer[0].text).toContain('真实最终回答')
    expect(reply.pipeline.analysis.status).toBe('done')
    expect(reply.pipeline.retrieval.status).toBe('done')
    expect(reply.sources[0].label).toBe('健康知识库')
  })
})

describe('B3 AssistantView — real trace rendering', () => {
  function productionModel() {
    return createProductionAssistantContract()
  }

  function mockSource(impl: (question: string, onEvent: (event: AssistantTraceEvent) => void) => Promise<AssistantReply>): UiDataSource {
    return { askAssistantStreaming: impl } as unknown as UiDataSource
  }

  it('updates pipeline only when real events arrive, then shows the final answer', async () => {
    let emitEvent: ((event: AssistantTraceEvent) => void) | null = null
    let resolveReply: ((reply: AssistantReply) => void) | null = null
    const source = mockSource((_question, onEvent) => {
      emitEvent = onEvent
      onEvent({ stage: 'accepted', status: 'active', label: '正在理解你的需求' })
      onEvent({ stage: 'safety', status: 'active', label: '正在进行安全检查' })
      return new Promise<AssistantReply>(resolve => {
        resolveReply = resolve
      })
    })
    const wrapper = mount(AssistantView, { props: { model: productionModel(), dataSource: source } })

    await wrapper.get('[data-prompt="sleep"]').trigger('click')
    await nextTick()

    // 真实事件已到达：analysis 行 active，retrieval 尚未推进
    expect(wrapper.get('[data-stage="analysis"]').classes()).toContain('active')
    expect(wrapper.get('[data-stage="retrieval"]').classes()).toContain('pending')
    expect(wrapper.find('[data-testid="answer-card"]').exists()).toBe(false)

    // 补发后续真实事件
    emitEvent?.({ stage: 'retrieval', status: 'active', label: '正在检索相关健康知识' })
    emitEvent?.({ stage: 'generation', status: 'active', label: '正在整理建议' })
    await nextTick()
    expect(wrapper.get('[data-stage="retrieval"]').classes()).toContain('done')
    expect(wrapper.get('[data-stage="answer"]').classes()).toContain('active')

    // completed：live 阶段保持 active，最终 reply 落地后变为 done
    emitEvent?.({ stage: 'completed', status: 'complete', label: '处理完成' })
    await nextTick()
    expect(wrapper.get('[data-stage="answer"]').classes()).toContain('active')
    expect(wrapper.find('[data-testid="answer-card"]').exists()).toBe(false)

    resolveReply?.(adaptAgenticRecommendation(allowedDto(), { traceIsReal: true }))
    await flushPromises()
    await nextTick()

    expect(wrapper.get('[data-testid="answer-card"]').text()).toContain('真实最终回答')
    expect(wrapper.get('[data-testid="evidence-list"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="evidence-list"]').text()).toContain('健康知识库')
  })

  it('does not advance the pipeline when no trace event has arrived', async () => {
    let resolveReply: ((reply: AssistantReply) => void) | null = null
    const source = mockSource(
      () =>
        new Promise<AssistantReply>(resolve => {
          resolveReply = resolve
        }),
    )
    const wrapper = mount(AssistantView, { props: { model: productionModel(), dataSource: source } })

    await wrapper.get('[data-prompt="sleep"]').trigger('click')
    await nextTick()

    // 一个事件都没有：不自行推进，也不出现 fake 回答
    expect(wrapper.find('[data-testid="agent-pipeline"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="answer-card"]').exists()).toBe(false)

    // 只有同一执行 resolve 后才有最终回答
    resolveReply?.(adaptAgenticRecommendation(allowedDto(), { traceIsReal: true }))
    await flushPromises()
    await nextTick()
    expect(wrapper.get('[data-testid="answer-card"]').text()).toContain('真实最终回答')
  })

  it('shows a safe error (role=alert) on backend failure without a fake answer', async () => {
    const source = mockSource(() => Promise.reject(new Error('暂时无法完成，请稍后重试')))
    const wrapper = mount(AssistantView, { props: { model: productionModel(), dataSource: source } })

    await wrapper.get('[data-prompt="sleep"]').trigger('click')
    await flushPromises()

    const error = wrapper.get('[data-testid="agentic-error"]')
    expect(error.attributes('role')).toBe('alert')
    expect(error.text()).toContain('暂时无法完成，请稍后重试')
    expect(wrapper.find('[data-testid="answer-card"]').exists()).toBe(false)
  })

  it('renders the Safety notice for a blocked execution without any generation stage', async () => {
    const blockedDto: RecommendationResponse = {
      status: 'blocked',
      selected_task: null,
      explanation: '当前请求需要先获得家长或老师的帮助。',
      sources: [],
      context_sources: [],
      matched_rule_ids: ['SR-001'],
      reason_codes: ['medical_emergency'],
      explanation_guard: null,
      personalization: null,
      recommendation_id: null,
      feedback_available: false,
    }
    const source = mockSource((_question, onEvent) => {
      onEvent({ stage: 'accepted', status: 'active', label: '正在理解你的需求' })
      onEvent({ stage: 'safety', status: 'active', label: '正在进行安全检查' })
      onEvent({ stage: 'completed', status: 'complete', label: '处理完成' })
      return Promise.resolve(adaptAgenticRecommendation(blockedDto, { traceIsReal: true }))
    })
    const wrapper = mount(AssistantView, { props: { model: productionModel(), dataSource: source } })

    await wrapper.get('[data-prompt="neck"]').trigger('click')
    await flushPromises()
    await nextTick()

    const notice = wrapper.get('[data-testid="safety-notice"]')
    expect(notice.text()).toContain('家长')
    // 阻断路径没有 generation：回答区不出现正常答案文本
    expect(wrapper.find('[data-testid="answer-card"]').text()).not.toContain('真实最终回答')
  })

  it('shows the real answer text, never a fixture fallback reply', async () => {
    const source = mockSource((_question, onEvent) => {
      onEvent({ stage: 'accepted', status: 'active', label: '正在理解你的需求' })
      onEvent({ stage: 'completed', status: 'complete', label: '处理完成' })
      return Promise.resolve(adaptAgenticRecommendation(allowedDto(), { traceIsReal: true }))
    })
    const wrapper = mount(AssistantView, { props: { model: productionModel(), dataSource: source } })

    await wrapper.get('[data-prompt="sleep"]').trigger('click')
    await flushPromises()
    await nextTick()

    const card = wrapper.get('[data-testid="answer-card"]')
    expect(card.text()).toContain('真实最终回答')
    expect(card.text()).not.toContain('最小的事') // fixture 文案不得出现
  })

  it('demo mode never calls the stream backend', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(AssistantView, { props: { model: assistantFixture } })

    await wrapper.get('[data-prompt="exam"]').trigger('click')

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('uses consent-neutral footer copy', () => {
    const wrapper = mount(AssistantView, { props: { model: productionModel() } })
    const footer = wrapper.get('p.ask-foot')

    expect(footer.text()).toContain('回答基于审核知识库和你提供的信息')
    expect(footer.text()).not.toContain('历史记忆')
    expect(wrapper.text()).not.toContain('你的记忆')
  })
})
