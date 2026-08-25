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
  const renderVersion = ref(0)

  async function submit(rawQuestion: string): Promise<boolean> {
    const nextQuestion = rawQuestion.trim()
    if (!nextQuestion || busy.value || !source) return false

    question.value = nextQuestion
    reply.value = null
    pipeline.value = null
    error.value = null
    busy.value = true
    renderVersion.value += 1
    try {
      if (source.askAssistantStreaming) {
        reply.value = await source.askAssistantStreaming(nextQuestion, event => {
          // 只有真实 backend 事件才会推进 pipeline；没有事件就不会自行前进。
          pipeline.value = applyAgentTraceEvent(pipeline.value ?? createLiveTracePipeline(), event)
          renderVersion.value += 1
        })
        pipeline.value = null
      } else {
        reply.value = await source.askAssistant(nextQuestion)
      }
      return true
    } catch (cause) {
      error.value = cause instanceof Error ? cause : new Error('Agentic 推荐失败。')
      return false
    } finally {
      busy.value = false
      renderVersion.value += 1
    }
  }

  return { question, reply, pipeline, busy, error, renderVersion, submit }
}
