import { onUnmounted, ref } from 'vue'

import type {
  AssistantContract,
  AssistantPipeline,
  AssistantReply,
  AssistantScenario,
  AssistantStageId,
  AssistantStageStatus,
} from '@/contracts'

type TimerHandle = ReturnType<typeof setTimeout>

const defaultStatusLabels: Record<AssistantStageStatus, string> = {
  pending: '等待开始',
  active: '进行中…',
  done: '已完成',
  unavailable: '实时轨迹不可用',
}

function cloneReply(source: AssistantReply, question: string): AssistantReply {
  const reply: AssistantReply = {
    ...source,
    pipeline: {
      analysis: {
        ...source.pipeline.analysis,
        statusLabels: { ...source.pipeline.analysis.statusLabels },
        items: [...source.pipeline.analysis.items],
      },
      retrieval: {
        ...source.pipeline.retrieval,
        statusLabels: { ...source.pipeline.retrieval.statusLabels },
        chunks: [...source.pipeline.retrieval.chunks],
      },
      answer: {
        ...source.pipeline.answer,
        statusLabels: { ...source.pipeline.answer.statusLabels },
      },
    },
    answer: [...source.answer],
    sources: [...source.sources],
  }

  if (reply.scenario === 'fallback') {
    const shortQuestion = question.length > 16 ? `${question.slice(0, 16)}…` : question
    reply.pipeline.analysis.lead = reply.pipeline.analysis.lead?.replace('{question}', shortQuestion) ?? null
  }

  return reply
}

export function useAssistantFlow(model: AssistantContract) {
  const question = ref('')
  const reply = ref<AssistantReply | null>(null)
  const pipeline = ref<AssistantPipeline | null>(null)
  const busy = ref(false)
  const renderVersion = ref(0)
  const timers = new Set<TimerHandle>()
  let runId = 0

  function touch(): void {
    renderVersion.value += 1
  }

  function clearTimers(): void {
    for (const timer of timers) clearTimeout(timer)
    timers.clear()
    runId += 1
  }

  function schedule(delay: number, token: number, callback: () => void): void {
    const timer = setTimeout(() => {
      timers.delete(timer)
      if (token !== runId) return
      callback()
    }, delay)
    timers.add(timer)
  }

  function setStage(stageId: AssistantStageId, status: AssistantStageStatus, visible?: boolean): void {
    const current = pipeline.value?.[stageId]
    if (!current) return

    current.status = status
    current.statusLabel = current.statusLabels[status] ?? defaultStatusLabels[status]
    if (visible !== undefined) current.visible = visible
  }

  function submit(rawQuestion: string, scenario: AssistantScenario = 'fallback'): boolean {
    const nextQuestion = rawQuestion.trim()
    if (!nextQuestion || busy.value) return false

    const baseReply = model.replies[scenario] ?? model.replies.fallback
    const nextReply = cloneReply(baseReply, nextQuestion)
    const timing = nextReply.timing
    const token = ++runId

    clearTimers()
    runId = token
    question.value = nextQuestion
    reply.value = nextReply
    pipeline.value = nextReply.pipeline
    busy.value = true
    touch()

    if (!timing) {
      setStage('analysis', 'unavailable', true)
      setStage('retrieval', 'unavailable', true)
      setStage('answer', 'done', true)
      busy.value = false
      touch()
      return true
    }

    const analysisCardAt = timing.analysisCard
    const analysisDoneAt = analysisCardAt + timing.analysisFill
    const retrievalCardAt = analysisDoneAt + timing.retrievalCard
    const retrievalDoneAt = retrievalCardAt + timing.retrievalFill
    const answerDoneAt = retrievalDoneAt + timing.answer

    schedule(analysisCardAt, token, () => {
      setStage('analysis', 'active', true)
      touch()
    })
    schedule(analysisDoneAt, token, () => {
      setStage('analysis', 'done')
      setStage('retrieval', 'active')
      touch()
    })
    schedule(retrievalCardAt, token, () => {
      setStage('retrieval', 'active', true)
      touch()
    })
    schedule(retrievalDoneAt, token, () => {
      setStage('retrieval', 'done')
      setStage('answer', 'active')
      touch()
    })
    schedule(answerDoneAt, token, () => {
      setStage('answer', 'done', true)
      busy.value = false
      touch()
    })

    return true
  }

  onUnmounted(clearTimers)

  return {
    question,
    reply,
    pipeline,
    busy,
    renderVersion,
    submit,
    clearTimers,
    timerCount: () => timers.size,
  }
}
