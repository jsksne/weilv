import type {
  AgenticRecommendationResponse,
  EvidenceSource,
  SelectedTask,
} from '@/api/types'
import type {
  AssistantAnalysisStage,
  AssistantAnswerStage,
  AssistantPipeline,
  AssistantReply,
  AssistantRetrievalStage,
  AssistantSafetyNotice,
  AssistantSource,
} from '@/contracts'

const safetyCopy: Record<Exclude<AssistantSafetyNotice['status'], 'allowed'>, Omit<AssistantSafetyNotice, 'status'>> = {
  blocked: {
    title: '先暂停一下任务推荐',
    paragraphs: ['当前请求不适合继续普通任务推荐。'],
    rule: '已按后端结构化安全状态暂停普通推荐。',
  },
  help_seeking: {
    title: '先找一位大人聊聊',
    paragraphs: ['这次请求需要优先获得家长、老师或专业人员的帮助。'],
    rule: '已按后端结构化安全状态进入求助分流。',
  },
  no_safe_task: {
    title: '暂时没有合适的安全任务',
    paragraphs: ['当前没有可以放心推荐的任务。'],
    rule: '已按后端结构化安全状态停止任务推荐。',
  },
}

function unavailableAnalysis(): AssistantAnalysisStage {
  return {
    id: 'analysis',
    title: '问题拆解',
    status: 'unavailable',
    statusLabel: '实时轨迹不可用',
    statusLabels: { unavailable: '实时轨迹不可用' },
    visible: true,
    lead: null,
    items: [],
  }
}

function unavailableRetrieval(): AssistantRetrievalStage {
  return {
    id: 'retrieval',
    title: '知识检索',
    status: 'unavailable',
    statusLabel: '实时轨迹不可用',
    statusLabels: { unavailable: '实时轨迹不可用' },
    visible: true,
    chunks: [],
  }
}

function availableAnswer(): AssistantAnswerStage {
  return {
    id: 'answer',
    title: '回答',
    status: 'done',
    statusLabel: '已返回最终回答',
    statusLabels: { done: '已返回最终回答' },
    visible: true,
  }
}

function toSource(source: EvidenceSource): AssistantSource {
  return {
    label: source.source_locator || source.document_id || source.chunk_id,
    url: source.source_url || undefined,
  }
}

function toSuggestedTask(task: SelectedTask | null) {
  if (!task) return null

  return {
    icon: '🌿',
    title: task.title,
    meta: `约 ${task.estimated_minutes} 分钟`,
    actionLabel: '去做',
  }
}

function toSafety(dto: AgenticRecommendationResponse): AssistantSafetyNotice | null {
  if (dto.status === 'allowed') return null

  const copy = safetyCopy[dto.status]
  return {
    status: dto.status,
    title: copy.title,
    paragraphs: dto.explanation ? [dto.explanation] : copy.paragraphs,
    rule: copy.rule,
  }
}

export function adaptAgenticRecommendation(dto: AgenticRecommendationResponse): AssistantReply {
  const sources = [...dto.sources, ...(dto.context_sources ?? [])].map(toSource)
  const analysis = unavailableAnalysis()
  const retrieval = unavailableRetrieval()
  const answer = availableAnswer()
  const pipeline: AssistantPipeline = { analysis, retrieval, answer }
  const text = dto.explanation ? [{ text: dto.explanation }] : []

  return {
    id: dto.recommendation_id ?? 'production-agentic-reply',
    scenario: null,
    pipeline,
    answer: text,
    suggestedTask: dto.status === 'allowed' ? toSuggestedTask(dto.selected_task) : null,
    safety: toSafety(dto),
    sources,
    traceIsReal: false,
    timing: null,
  }
}
