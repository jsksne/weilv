import { ref } from 'vue'

import type { AssistantPipeline, AssistantReply, UiDataSource } from '@/contracts'
import { applyAgentTraceEvent, createLiveTracePipeline } from '@/data/adapters'

export function useAgenticRecommendation(source: UiDataSource | null) {
  const question = ref('')
  const reply = ref<AssistantReply | null>(null)
  /** B3：流式期间的实时 pipeline（仅由真实 trace 事件推进）。 */
  const pipeline = ref<AssistantPipeline | null>(null)
  const busy = ref(false)
  const error = ref<Error | null>(null)
  /** 流式通道失败后由非流式端点完成同一流程时置位（如实提示，不冒充流式）。 */
  const streamFallbackUsed = ref(false)
  const renderVersion = ref(0)

  async function submit(rawQuestion: string): Promise<boolean> {
    const nextQuestion = rawQuestion.trim()
    if (!nextQuestion || busy.value || !source) return false

    question.value = nextQuestion
    reply.value = null
    pipeline.value = null
    error.value = null
    streamFallbackUsed.value = false
    busy.value = true
    renderVersion.value += 1
    try {
      if (source.askAssistantStreaming) {
        try {
          reply.value = await source.askAssistantStreaming(nextQuestion, event => {
            // 只有真实 backend 事件才会推进 pipeline；没有事件就不会自行前进。
            pipeline.value = applyAgentTraceEvent(pipeline.value ?? createLiveTracePipeline(), event)
            renderVersion.value += 1
          })
          pipeline.value = null
          return true
        } catch (streamCause) {
          /* 网关可能不支持流式响应（如 PocketBay 返回 403/204）：
             回退到非流式端点完成同一条 Agentic 管线，而不是让用户卡在报错。 */
          if (typeof source.askAssistant !== 'function') throw streamCause
          streamFallbackUsed.value = true
          pipeline.value = null
          reply.value = await source.askAssistant(nextQuestion)
          return true
        }
      }
      reply.value = await source.askAssistant(nextQuestion)
      return true
    } catch (cause) {
      error.value = cause instanceof Error ? cause : new Error('Agentic 推荐失败。')
      return false
    } finally {
      busy.value = false
      renderVersion.value += 1
    }
  }

  return { question, reply, pipeline, busy, error, streamFallbackUsed, renderVersion, submit }
}
