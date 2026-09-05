import { flushPromises, mount } from '@vue/test-utils'
import { enableAutoUnmount } from '@vue/test-utils'
import { afterEach, vi } from 'vitest'

import { createProductionAssistantContract } from './data/adapters'
import AssistantView from './views/AssistantView.vue'
import TodayView from './views/TodayView.vue'
import { todayFixture } from './data/fixtures/today.fixture'
import type { AssistantReply, UiDataSource } from './contracts'
import type { ConversationTurn } from './contracts/common'
import type { TodayContract } from './contracts'
import { useDailyTasks } from './composables/useDailyTasks'

enableAutoUnmount(afterEach)

afterEach(() => {
  vi.unstubAllGlobals()
})

/* ------------------------------------------------------------------
   日程与易启动推荐 spec：前端行为
   - 日程卡读回与新增（通过 DataSource）
   - 易启动开关随请求携带 prefer_easy_start
   - “本次考虑”摘要来自真实请求字段
   ------------------------------------------------------------------ */

interface AskCall {
  question: string
  history: ConversationTurn[]
  easyStart?: boolean
}

function replyWith(): AssistantReply {
  return {
    id: 'reply-easy',
    scenario: null,
    pipeline: {
      analysis: {
        id: 'analysis', title: '问题拆解', status: 'done', statusLabel: '已完成',
        statusLabels: {}, visible: true, lead: null, items: [],
      },
      retrieval: {
        id: 'retrieval', title: '知识检索', status: 'done', statusLabel: '已完成',
        statusLabels: {}, visible: true, chunks: [],
      },
      answer: { id: 'answer', title: '回答', status: 'done', statusLabel: '已完成', statusLabels: {}, visible: true },
    },
    answer: [{ text: '推荐：窗边远眺 20 秒。' }],
    suggestedTask: null,
    safety: null,
    sources: [],
    traceIsReal: true,
    timing: null,
    considered: ['可用 2 分钟', '今天有考试安排'],
  }
}

function sourceRecording(calls: AskCall[]): UiDataSource {
  return {
    async askAssistantStreaming(question, _onEvent, history = [], easyStart) {
      calls.push({ question, history, easyStart })
      return replyWith()
    },
  } as unknown as UiDataSource
}

describe('易启动开关进入真实请求', () => {
  it('开启「轻一点」后下一次提问携带 easyStart，关闭后恢复', async () => {
    const calls: AskCall[] = []
    const wrapper = mount(AssistantView, {
      props: { model: createProductionAssistantContract(), dataSource: sourceRecording(calls) },
    })

    const toggle = wrapper.get('[data-testid="easy-start-toggle"]')
    await toggle.trigger('click')
    expect(toggle.attributes('aria-pressed')).toBe('true')

    const composer = wrapper.get('[data-testid="chat-composer"]')
    await composer.find('input').setValue('推荐一件事')
    await composer.trigger('submit')
    await flushPromises()

    expect(calls).toHaveLength(1)
    expect(calls[0]!.easyStart).toBe(true)

    await toggle.trigger('click')
    await composer.find('input').setValue('再来一件事')
    await composer.trigger('submit')
    await flushPromises()

    expect(calls[1]!.easyStart).toBe(false)
  })
})

describe('「本次考虑」摘要展示', () => {
  it('在回答附近显示来自请求真实字段的条件摘要', async () => {
    const calls: AskCall[] = []
    const wrapper = mount(AssistantView, {
      props: { model: createProductionAssistantContract(), dataSource: sourceRecording(calls) },
    })

    const composer = wrapper.get('[data-testid="chat-composer"]')
    await composer.find('input').setValue('现在只有两分钟')
    await composer.trigger('submit')
    await flushPromises()

    const note = wrapper.get('[data-testid="considered-note"]')
    expect(note.text()).toContain('本次考虑')
    expect(note.text()).toContain('可用 2 分钟')
    expect(note.text()).toContain('今天有考试安排')
  })
})

describe('日程卡读回与新增', () => {
  function scheduleSource(events: unknown[], saved: unknown[] = []): { source: UiDataSource; calls: unknown[] } {
    const calls: unknown[] = []
    const source = {
      async getSchedule() {
        calls.push('list')
        return events
      },
      async saveScheduleEvent(body) {
        calls.push(['save', body])
        saved.push(body)
        return { status: 'saved' }
      },
      async deleteScheduleEvent(eventId: string) {
        calls.push(['delete', eventId])
        return { status: 'deleted' }
      },
    } as unknown as UiDataSource
    return { source, calls }
  }

  function todayModel(): TodayContract {
    return { ...todayFixture, state: { ...todayFixture.state, mode: 'production' } }
  }

  function mountToday(source: UiDataSource, model: TodayContract) {
    const daily = useDailyTasks(model)
    return mount(TodayView, { props: { model, daily, dataSource: source } })
  }

  it('首页简短呈现当天安排，并可新增后读回', async () => {
    const { source, calls } = scheduleSource([
      {
        event_id: 'e1',
        name: '数学期中考试',
        start_date: '2026-09-05',
        end_date: '2026-09-06',
        kind: 'exam',
        busy_level: 'busy',
        created_at: '',
        updated_at: '',
      },
    ])
    const wrapper = mountToday(source, todayModel())

    await flushPromises()
    const summary = wrapper.get('[data-testid="schedule-card"]').text()
    expect(summary).toContain('今天：数学期中考试（考试）')

    await wrapper.get('[data-testid="schedule-toggle"]').trigger('click')
    await wrapper.get('[data-testid="schedule-name"]').setValue('周末放假')
    await wrapper.get('[data-testid="schedule-save"]').trigger('submit')
    await flushPromises()

    const saveCall = calls.find(item => Array.isArray(item) && item[0] === 'save') as unknown[]
    expect(saveCall).toBeDefined()
    expect((saveCall[1] as { name: string }).name).toBe('周末放假')
  })

  it('demo 模式不挂日程卡', () => {
    const { source } = scheduleSource([])
    const wrapper = mountToday(source, todayFixture)
    expect(wrapper.find('[data-testid="schedule-card"]').exists()).toBe(false)
  })
})
