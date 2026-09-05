import { describe, expect, it } from 'vitest'

import { useAgenticRecommendation } from './composables/useAgenticRecommendation'
import { adaptRecommendationResponse, createProductionShellContract } from './data/adapters'
import { allowedRecommendation } from './test/recommendationFixtures'
import type { AssistantReply, UiDataSource } from './contracts'

function liveReply(): AssistantReply {
  return {
    id: 'fallback-reply',
    scenario: null,
    pipeline: null,
    answer: [{ text: '真实回答' }],
    suggestedTask: null,
    safety: null,
    sources: [],
    traceIsReal: true,
    timing: null,
  }
}

describe('stream fallback（PocketBay 网关对流式返回 403 时的产品级降级）', () => {
  it('falls back to askAssistant and flags the fallback when streaming fails', async () => {
    const reply = liveReply()
    const source = {
      async askAssistantStreaming(): Promise<AssistantReply> {
        throw new Error('http_403')
      },
      async askAssistant(): Promise<AssistantReply> {
        return reply
      },
    } as unknown as UiDataSource

    const flow = useAgenticRecommendation(source)
    const ok = await flow.submit('我最近睡不好')
    expect(ok).toBe(true)
    expect(flow.messages.value).toHaveLength(1)
    expect(flow.messages.value[0]!.status).toBe('complete')
    expect(flow.messages.value[0]!.reply).toStrictEqual(reply)
    expect(flow.messages.value[0]!.streamFallbackUsed).toBe(true)
  })

  it('keeps the original stream error when no non-streaming source exists', async () => {
    const source = {
      async askAssistantStreaming(): Promise<AssistantReply> {
        throw new Error('http_403')
      },
    } as unknown as UiDataSource

    const flow = useAgenticRecommendation(source)
    const ok = await flow.submit('我最近睡不好')
    expect(ok).toBe(false)
    expect(flow.messages.value).toHaveLength(1)
    expect(flow.messages.value[0]!.status).toBe('error')
    expect(flow.messages.value[0]!.errorMessage).toBe('http_403')
    expect(flow.messages.value[0]!.streamFallbackUsed).toBe(false)
  })

  it('does not use the fallback when streaming succeeds', async () => {
    const reply = liveReply()
    const source = {
      async askAssistantStreaming(): Promise<AssistantReply> {
        return reply
      },
      async askAssistant(): Promise<AssistantReply> {
        throw new Error('non-stream endpoint must not be called')
      },
    } as unknown as UiDataSource

    const flow = useAgenticRecommendation(source)
    const ok = await flow.submit('我最近睡不好')
    expect(ok).toBe(true)
    expect(flow.messages.value).toHaveLength(1)
    expect(flow.messages.value[0]!.reply).toStrictEqual(reply)
    expect(flow.messages.value[0]!.streamFallbackUsed).toBe(false)
  })
})

describe('production Today 契约对齐 02-sakura-spring 原型', () => {
  it('keeps mood/time prototype options and default selection', () => {
    const today = adaptRecommendationResponse(allowedRecommendation)
    expect(today.moods.map(mood => mood.label)).toEqual(['还不错', '平静', '有点累', '有点低落'])
    expect(today.timeOptions.map(option => option.label)).toEqual([
      '3 分钟',
      '5 分钟',
      '10 分钟',
      '25 分钟',
      '40 分钟以上',
    ])
    expect(today.defaultMood).toBe('calm')
    expect(today.defaultTimeMinutes).toBe(25)
    expect(today.tasksSectionNote).toBe('来自审核白名单 · 按你的画像生成')
  })

  it('maps whitelist domains to prototype domain labels and card tones', () => {
    const baseTask = allowedRecommendation.selected_task
    const dto = {
      ...allowedRecommendation,
      selected_task: {
        ...baseTask,
        covered_domains: ['sleep'],
      },
    }
    const today = adaptRecommendationResponse(dto)
    expect(today.tasks[0].domain).toBe('睡前准备')
    expect(today.tasks[0].tone).toBe('sleep')
  })

  it('uses the truthful whitelist explanation instead of an error note for tasks without LLM copy', () => {
    const today = adaptRecommendationResponse(allowedRecommendation)
    expect(today.tasks[0].why).not.toContain('暂不可用')
  })

  it('aligns shell navigation label with the prototype weekly tab', () => {
    expect(createProductionShellContract().navigation.map(item => item.label)).toEqual([
      '今日',
      '问问薇薇',
      '我的画像',
      '周度变化',
    ])
  })
})
