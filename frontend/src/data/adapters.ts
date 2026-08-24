import type {
  AgenticRecommendationResponse,
  EvidenceSource,
  QuestionnaireSchema,
  QuestionnaireState,
  RecommendationResponse,
  SelectedTask,
  UserProfile,
} from '@/api/types'
import type {
  AssistantAnalysisStage,
  AssistantAnswerStage,
  AssistantContract,
  AssistantPipeline,
  AssistantReply,
  AssistantRetrievalStage,
  AssistantSafetyNotice,
  AssistantSource,
  OnboardingContract,
  OnboardingAnswerValue,
  ProfileContract,
  ShellContract,
  TodayContract,
  TodayDataAvailability,
  TodayTaskView,
  WeeklyContract,
} from '@/contracts'

export function createProductionShellContract(): ShellContract {
  return {
    state: { status: 'ready', mode: 'production' },
    navigation: [
      { id: 'today', label: '今日' },
      { id: 'assistant', label: '问问薇薇' },
      { id: 'profile', label: '我的画像' },
      { id: 'weekly', label: '这一周' },
    ],
    displayName: '微律',
    dateLabel: '今日',
    progress: { completed: 0, total: 0, note: '今日进度不可用。' },
    toastExample: { id: 'production-shell', message: '' },
  }
}

const unavailableTodayAvailability: TodayDataAvailability = {
  selectedTask: 'unavailable',
  dailyTasks: 'unavailable',
  sleepStats: 'unavailable',
  visionStats: 'unavailable',
  moodStats: 'unavailable',
  rhythm: 'unavailable',
  progress: 'unavailable',
  replace: 'unavailable',
  restore: 'unavailable',
}

export function createUnavailableTodayContract(
  message = 'Production Today 仅显示后端已提供的数据。',
): TodayContract {
  return {
    state: { status: 'ready', mode: 'production', message },
    dataAvailability: 'unavailable',
    availability: unavailableTodayAvailability,
    unavailableFields: Object.keys(unavailableTodayAvailability),
    heroTag: 'Production · 今日任务',
    greetingLead: '你好，',
    greetingName: '微律用户',
    summaryLines: [],
    observation: {
      mainLead: '今日状态',
      mainEmphasis: 'unavailable',
      mainTail: '',
      summary: '',
      stats: [],
      suggestions: [],
    },
    moods: [],
    defaultMood: '',
    timeOptions: [],
    defaultTimeMinutes: 0,
    moodNoteLead: '',
    moodNoteLines: [],
    tasksSectionTitle: '今日可用任务',
    tasksSectionNote: '仅显示后端真实返回的任务',
    tasks: [],
    replacePool: [],
    lowMoodSwap: { taskId: '', name: '', description: '', why: '' },
    rhythm: { title: '今日节奏', sub: '', items: [] },
    breath: { title: '呼吸', sub: '', tip: '' },
    progressNotes: {
      hero: ['当前进度不可用', '当前进度不可用', '当前进度不可用', '当前进度不可用'],
      docked: ['当前进度不可用', '当前进度不可用', '当前进度不可用', '当前进度不可用'],
    },
    feedbackCopy: {
      start: '',
      done: '',
      partial: '',
      skip: '',
      restore: '',
      replace: '',
      lowMood: '',
      check: '',
    },
  }
}

/* B5 schema pending: Weekly has no approved Backend DTO or Production adapter. */
export function createUnavailableWeeklyContract(
  message = 'Production Weekly 数据暂不可用：B5 schema pending。',
): WeeklyContract {
  return {
    state: { status: 'unavailable', mode: 'production', message },
    dataAvailability: 'unavailable',
    header: {
      title: '这一周，薇薇的变化 🌱',
      description: '周度历史数据暂不可用。',
    },
    chart: {
      title: '每日完成任务的分钟数',
      note: '只统计白名单小任务',
    },
    days: [],
    minutes: [],
    timelineTitle: '推荐的调整轨迹',
    timeline: [],
    insight: { title: '本周洞察', segments: [], quote: '' },
  }
}

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

function unavailableAnswer(): AssistantAnswerStage {
  return {
    id: 'answer',
    title: '回答',
    status: 'unavailable',
    statusLabel: '等待真实回答',
    statusLabels: { unavailable: '等待真实回答' },
    visible: false,
  }
}

function toSource(source: EvidenceSource): AssistantSource {
  return {
    label: source.source_locator || source.source_url || '参考来源',
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
    id: 'production-agentic-reply',
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

export function createProductionAssistantContract(): AssistantContract {
  const reply: AssistantReply = {
    id: 'production-agentic-reply',
    scenario: null,
    pipeline: {
      analysis: unavailableAnalysis(),
      retrieval: unavailableRetrieval(),
      answer: unavailableAnswer(),
    },
    answer: [],
    suggestedTask: null,
    safety: null,
    sources: [],
    traceIsReal: false,
    timing: null,
  }

  return {
    state: { status: 'ready', mode: 'production' },
    isDemo: false,
    traceIsReal: false,
    demoLabel: '',
    quickPrompts: [
      { id: 'exam', label: '考试周好累，只有 10 分钟', question: '考试周好累，只有 10 分钟' },
      { id: 'sleep', label: '最近睡不好', question: '最近睡不好' },
      { id: 'neck', label: '我脖子有点疼', question: '我脖子有点疼' },
    ],
    greeting: {
      face: '薇薇',
      segments: [{ text: '告诉我你现在的困扰，我会请求一次真实的 Agentic 推荐。' }],
    },
    replies: { exam: reply, sleep: reply, neck: reply, fallback: reply },
  }
}

function toTodayTask(dto: SelectedTask, explanation: string | null): TodayTaskView {
  return {
    id: 'production-selected-task',
    tone: 'default',
    domain: dto.covered_domains[0] ?? '微任务',
    meta: `约 ${dto.estimated_minutes} 分钟`,
    name: dto.title,
    description: dto.instruction,
    why: explanation ?? '任务解释不可用。',
    whyIcon: 'flower',
  }
}

export function adaptRecommendationResponse(dto: RecommendationResponse): TodayContract {
  const selectedTask = dto.status === 'allowed' && dto.selected_task
    ? toTodayTask(dto.selected_task, dto.explanation)
    : null
  const availability: TodayDataAvailability = {
    ...unavailableTodayAvailability,
    selectedTask: selectedTask ? 'available' : 'unavailable',
  }
  const unavailableFields = Object.entries(availability)
    .filter(([, status]) => status === 'unavailable')
    .map(([field]) => field)
  const message =
    dto.explanation ??
    (selectedTask
      ? '当前仅有一条后端推荐可用，其余 Today 数据暂不可用。'
      : '当前没有后端返回的安全任务。')

  return {
    ...createUnavailableTodayContract(message),
    state: { status: 'ready', mode: 'production', message },
    dataAvailability: selectedTask ? 'partial' : 'unavailable',
    availability,
    unavailableFields,
    summaryLines: dto.explanation ? [[{ text: dto.explanation }]] : [],
    tasks: selectedTask ? [selectedTask] : [],
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
