import { flushPromises, mount } from '@vue/test-utils'
import { enableAutoUnmount } from '@vue/test-utils'
import { afterEach } from 'vitest'

import { useAgenticRecommendation } from './composables/useAgenticRecommendation'
import { createProductionAssistantContract } from './data/adapters'
import AssistantView from './views/AssistantView.vue'
import type { AssistantReply, ConversationTurn, UiDataSource } from './contracts'

enableAutoUnmount(afterEach)

function replyFor(id: string): AssistantReply {
  return {
    id,
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
    answer: [{ text: `回答 ${id}` }],
    suggestedTask: null,
    safety: null,
    sources: [],
    traceIsReal: true,
    timing: null,
  }
}

interface StreamCall {
  question: string
  history: ConversationTurn[]
}

function streamingSource(calls: StreamCall[], failFirst = false): UiDataSource {
  let count = 0
  return {
    async askAssistantStreaming(question, _onEvent, history = []) {
      calls.push({ question, history })
      count += 1
      if (failFirst && count === 1) throw new Error('backend down')
      return replyFor(`reply-${count}`)
    },
  } as unknown as UiDataSource
}

describe('F1 连续对话：历史真实进入请求', () => {
  it('第二问携带第一轮问答作为 conversation_history', async () => {
    const calls: StreamCall[] = []
    const flow = useAgenticRecommendation(streamingSource(calls))

    await flow.submit('推荐一个课间能做的小事')
    await flow.submit('再简单一点')

    expect(calls).toHaveLength(2)
    expect(calls[1]!.history).toEqual([
      { role: 'user', content: '推荐一个课间能做的小事' },
      { role: 'assistant', content: '回答 reply-1' },
    ])
    /* 第一轮仍可见：消息按顺序保留。 */
    expect(flow.messages.value.map(message => message.question)).toEqual([
      '推荐一个课间能做的小事',
      '再简单一点',
    ])
    expect(flow.messages.value[0]!.reply?.id).toBe('reply-1')
  })

  it('历史有轮次上限，只携带最近 6 轮', async () => {
    const calls: StreamCall[] = []
    const flow = useAgenticRecommendation(streamingSource(calls))

    for (let round = 1; round <= 8; round += 1) {
      await flow.submit(`第 ${round} 问`)
    }

    const lastCall = calls[calls.length - 1]!
    expect(lastCall.history.length).toBeLessThanOrEqual(12)
    expect(lastCall.question).toBe('第 8 问')
    /* 超出上限的最早轮次被丢弃；最近的完整轮次保留。 */
    expect(lastCall.history.some(turn => turn.content.includes('第 1 问'))).toBe(false)
    expect(lastCall.history.some(turn => turn.content.includes('第 7 问'))).toBe(true)
  })

  it('新对话清空上下文：下一问不携带历史，也不删除已完成消息之外的数据', async () => {
    const calls: StreamCall[] = []
    const flow = useAgenticRecommendation(streamingSource(calls))

    await flow.submit('第一问')
    expect(flow.startNewConversation()).toBe(true)
    expect(flow.messages.value).toHaveLength(0)
    await flow.submit('新会话第一问')

    expect(calls[1]!.history).toEqual([])
  })

  it('同一会话等待期间拒绝并发提交', async () => {
    let release!: (reply: AssistantReply) => void
    const source = {
      askAssistantStreaming: () =>
        new Promise<AssistantReply>(resolve => {
          release = resolve
        }),
    } as unknown as UiDataSource
    const flow = useAgenticRecommendation(source)

    const first = flow.submit('第一问')
    expect(await flow.submit('第二问')).toBe(false)
    release(replyFor('late'))
    await first
    expect(flow.messages.value).toHaveLength(1)
  })

  it('失败轮次不进入历史；原位重试不重复追加用户消息', async () => {
    const calls: StreamCall[] = []
    const flow = useAgenticRecommendation(streamingSource(calls, true))

    const ok = await flow.submit('第一问')
    expect(ok).toBe(false)
    expect(flow.messages.value).toHaveLength(1)
    expect(flow.messages.value[0]!.status).toBe('error')

    await flow.retry(flow.messages.value[0]!.id)

    expect(flow.messages.value).toHaveLength(1)
    expect(flow.messages.value[0]!.status).toBe('complete')
    expect(calls).toHaveLength(2)
    expect(calls[1]!.history).toEqual([])
  })
})

describe('F1 AssistantView：会话按顺序渲染', () => {
  it('连续两问后两轮问答都保留在会话日志中', async () => {
    const calls: StreamCall[] = []
    const source = streamingSource(calls)
    const wrapper = mount(AssistantView, {
      props: { model: createProductionAssistantContract(), dataSource: source },
      global: { config: { warnHandler: () => {} } },
    })

    const composer = wrapper.find('[data-testid="chat-composer"]')
    await composer.find('input').setValue('第一问')
    await composer.trigger('submit')
    await flushPromises()
    await composer.find('input').setValue('第二问')
    await composer.trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('第一问')
    expect(wrapper.text()).toContain('第二问')
    expect(wrapper.text()).toContain('回答 reply-1')
    expect(wrapper.text()).toContain('回答 reply-2')
  })
})
