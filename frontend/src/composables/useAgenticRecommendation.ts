import { ref } from 'vue'

import type { AssistantReply, UiDataSource } from '@/contracts'

export function useAgenticRecommendation(source: UiDataSource | null) {
  const question = ref('')
  const reply = ref<AssistantReply | null>(null)
  const busy = ref(false)
  const error = ref<Error | null>(null)
  const renderVersion = ref(0)

  async function submit(rawQuestion: string): Promise<boolean> {
    const nextQuestion = rawQuestion.trim()
    if (!nextQuestion || busy.value || !source) return false

    question.value = nextQuestion
    reply.value = null
    error.value = null
    busy.value = true
    renderVersion.value += 1
    try {
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

  return { question, reply, busy, error, renderVersion, submit }
}
