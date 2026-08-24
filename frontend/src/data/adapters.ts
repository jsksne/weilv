import type {
  AgenticRecommendationResponse,
  EvidenceSource,
  QuestionnaireSchema,
  QuestionnaireState,
  SelectedTask,
  UserProfile,
} from '@/api/types'
import type {
  AssistantAnalysisStage,
  AssistantAnswerStage,
  AssistantPipeline,
  AssistantReply,
  AssistantRetrievalStage,
  AssistantSafetyNotice,
  AssistantSource,
  OnboardingContract,
  OnboardingAnswerValue,
  ProfileContract,
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

/**
 * Sprint 6 的 Profile/Questionnaire 适配器只消费 DTO 已有字段。
 * 真实 DTO 没有偏好统计、完成率或 Memory list/delete，因此这些字段
 * 明确保持 unavailable；这里不导入任何 fixture，也不触发网络请求。
 */
export type MockProfileResponse = UserProfile | (Partial<UserProfile> & { user_id: string })
export type MockQuestionnaireResponse = QuestionnaireState
export type MockQuestionnaireSchemaResponse = QuestionnaireSchema

function unavailablePreference(
  id: 'time' | 'task',
  icon: 'clock' | 'leaf',
  title: string,
  message: string,
) {
  return { id, icon, title, status: 'unavailable' as const, items: [], unavailableMessage: message }
}

export function createUnavailableProfileContract(message = 'Production Profile 数据暂不可用。'): ProfileContract {
  return {
    state: { status: 'unavailable', mode: 'production', message },
    targetStage: 'unavailable',
    memoryEnabled: false,
    header: { title: '我的画像', description: message },
    timePreference: unavailablePreference('time', 'clock', '时间偏好', message),
    taskPreference: unavailablePreference('task', 'leaf', '任务偏好', message),
    completionPattern: {
      status: 'unavailable',
      icon: 'target',
      title: '历史规律',
      percentage: null,
      summaryLines: [],
      unavailableMessage: message,
    },
    memory: {
      status: 'unavailable',
      enabled: false,
      consent: 'missing',
      items: [],
      canDelete: false,
      notice: '没有明确 consent 时，Memory 保持关闭。',
      unavailableMessage: 'Production Memory list/delete API 暂不可用。',
    },
  }
}

export function adaptProfileResponse(dto: MockProfileResponse): ProfileContract {
  const memoryEnabled = dto.memory_enabled === true
  const consent = memoryEnabled ? 'granted' : dto.memory_enabled === false ? 'disabled' : 'missing'
  const unavailableMessage = 'Production 没有偏好统计、完成率和 Memory list/delete 接口。'

  return {
    state: { status: 'ready', mode: 'production' },
    targetStage: dto.target_stage ?? 'unavailable',
    memoryEnabled,
    header: {
      title: '我的画像',
      description: '当前只展示真实 Profile 状态；后端尚未提供的画像数据不会用演示数据填充。',
    },
    timePreference: unavailablePreference('time', 'clock', '时间偏好', unavailableMessage),
    taskPreference: unavailablePreference('task', 'leaf', '任务偏好', unavailableMessage),
    completionPattern: {
      status: 'unavailable',
      icon: 'target',
      title: '历史规律',
      percentage: null,
      summaryLines: [],
      unavailableMessage,
    },
    memory: {
      status: 'unavailable',
      enabled: memoryEnabled,
      consent,
      items: [],
      canDelete: false,
      notice: memoryEnabled
        ? 'Memory consent 已明确，但 Production Memory list/delete API 暂不可用。'
        : '没有明确 consent 时，Memory 保持关闭。',
      unavailableMessage: 'Production Memory list/delete API 暂不可用。',
    },
  }
}

function copyAnswers(
  answers: Record<string, string | string[]>,
): Readonly<Record<string, OnboardingAnswerValue>> {
  return Object.fromEntries(
    Object.entries(answers).map(([key, value]) => [key, Array.isArray(value) ? [...value] : value]),
  )
}

export function adaptQuestionnaireResponse(
  dto: MockQuestionnaireResponse | null,
  schema: MockQuestionnaireSchemaResponse | null = null,
) {
  return {
    status: dto && schema ? ('available' as const) : ('unavailable' as const),
    questionnaireId: dto?.questionnaire_id ?? schema?.questionnaire_id ?? null,
    completionState: dto?.completion_state ?? null,
    questionCount: schema?.questions.length ?? null,
    answers: copyAnswers(dto?.answers ?? {}),
  }
}

export function adaptQuestionnaireSchemaResponse(
  schema: MockQuestionnaireSchemaResponse | null,
) {
  if (!schema) {
    return {
      status: 'unavailable' as const,
      prototypeStepCount: 5,
      backendQuestionCount: null,
      message: '当前 Questionnaire schema 暂不可用，无法验证原型五步映射。',
    }
  }

  return {
    status: 'contractMismatch' as const,
    prototypeStepCount: 5,
    backendQuestionCount: schema.questions.length,
    message: `原型五步展示流程与当前 ${schema.questions.length} 题 Questionnaire 语义不一致，未提交演示答案。`,
  }
}

export function adaptOnboardingContract(
  schema: MockQuestionnaireSchemaResponse | null,
  response: MockQuestionnaireResponse | null,
): OnboardingContract {
  const questionnaire = adaptQuestionnaireResponse(response, schema)
  const questionnaireCompatibility = adaptQuestionnaireSchemaResponse(schema)
  const state = schema
    ? { status: 'ready' as const, mode: 'production' as const, message: questionnaireCompatibility.message }
    : { status: 'unavailable' as const, mode: 'production' as const, message: questionnaireCompatibility.message }

  return {
    state,
    steps: [],
    totalSteps: 0,
    initialAnswers: {},
    summary: { title: '画像生成不可用', lines: [] },
    questionnaire,
    questionnaireCompatibility,
    storageKey: '',
  }
}

export function adaptProfileAndQuestionnaire(
  profile: MockProfileResponse,
  schema: MockQuestionnaireSchemaResponse | null,
  response: MockQuestionnaireResponse | null,
): { profile: ProfileContract; onboarding: OnboardingContract } {
  return {
    profile: adaptProfileResponse(profile),
    onboarding: adaptOnboardingContract(schema, response),
  }
}
