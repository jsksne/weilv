import { frozenOnboardingSteps } from '@/data/onboardingSteps'
import type {
  EvidenceSource,
  MemoryListResponse,
  QuestionnaireSchema,
  QuestionnaireState,
  PublicRagTrace,
  RecommendationResponse,
  SelectedTask,
  SurfacedTask,
  TodaySessionItem,
  TodaySessionsResponse,
  UserProfile,
  WeeklyEvent,
  WeeklyResponse,
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
  AssistantTraceEvent,
  MemoryItemContract,
  MemoryConsentState,
  OnboardingContract,
  OnboardingAnswerValue,
  ProfileContract,
  ProfileMemoryListContract,
  ShellContract,
  TodayContract,
  TodayDataAvailability,
  TodayRecommendationStatus,
  TodaySavedInteraction,
  TodayTaskTone,
  TodayTaskView,
  WeeklyContract,
  WeeklyTextSegment,
  WeeklyTimelineItem,
  WeeklyTimelineStatus,
} from '@/contracts'

export function createProductionShellContract(): ShellContract {
  return {
    state: { status: 'ready', mode: 'production' },
    navigation: [
      { id: 'today', label: '今日' },
      { id: 'assistant', label: '问问薇薇' },
      { id: 'profile', label: '我的画像' },
      { id: 'weekly', label: '周度变化' },
    ],
    displayName: '微律',
    dateLabel: '今日',
    progress: { completed: 0, total: 0, note: '完成一件，就算今天有交代。' },
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
  message = '当前还没有可展示的真实今日数据。',
): TodayContract {
  return {
    state: { status: 'ready', mode: 'production', message },
    dataAvailability: 'unavailable',
    recommendationStatus: 'unavailable',
    availability: unavailableTodayAvailability,
    unavailableFields: Object.keys(unavailableTodayAvailability),
    heroTag: '✦ 今日 · 真实推荐',
    greetingLead: '你好，',
    greetingName: '微律用户',
    summaryLines: [],
    observation: {
      mainLead: '今天还没有足够的',
      mainEmphasis: '状态数据',
      mainTail: '。',
      summary: '有真实记录后，微律会在这里整理观察；没有数据时不会推断睡眠、用眼或情绪。',
      stats: [],
      suggestions: [],
    },
    moods: [
      { value: 'happy', face: '◕‿◕', label: '还不错' },
      { value: 'calm', face: '˘‿˘', label: '平静' },
      { value: 'tired', face: '>﹏<', label: '有点累' },
      { value: 'low', face: '·︿·', label: '有点低落' },
    ],
    defaultMood: 'calm',
    timeOptions: [
      { minutes: 10, label: '10 分钟' },
      { minutes: 25, label: '25 分钟' },
      { minutes: 40, label: '40 分钟以上' },
    ],
    defaultTimeMinutes: 25,
    moodNoteLead: '',
    moodNoteLines: ['怎么选都可以，微律只负责读懂你。', ''],
    tasksSectionTitle: '今日微任务',
    tasksSectionNote: '来自审核白名单 · 按你的画像生成',
    tasks: [],
    replacePool: [],
    lowMoodSwap: { taskId: '', name: '', description: '', why: '' },
    rhythm: { title: '今天的节奏', sub: '有真实节奏数据后会显示在这里', items: [] },
    breath: {
      title: '此刻 · 跟随呼吸',
      sub: '微律 AI 节律 · 9 秒一循环',
      tip: '这是微律的呼吸节律：吸气 20% · 呼气 80%。',
    },
    progressNotes: {
      hero: ['完成一件，就算今天有交代', '已经完成一件 ✦', '慢慢来，快收尾了', '今天有交代了 ✦'],
      docked: ['完成一件，就算今天有交代', '已经完成一件', '快收尾了', '今天完成啦 ✦'],
    },
    feedbackCopy: {
      start: '⏱ 开始啦 · 不着急',
      done: '✦ 当前进度 +1',
      partial: '🌱 部分完成也算数 · 当前进度已更新',
      skip: '🕊 跳过也没关系',
      restore: '',
      replace: '',
      lowMood: '🌷 收到 · 微律会轻轻调整推荐',
      check: '✦ 从此刻的心情开始 · 30 秒完成今日检查',
    },
  }
}

export function createUnavailableWeeklyContract(
  message = '周度数据暂时无法加载。',
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

const WEEKLY_ACTION_LABELS: Record<string, string> = {
  started: '开始',
  completed: '完成',
  partially_completed: '部分完成',
  skipped: '跳过',
  replaced: '替换',
  restored: '恢复',
}

function toWeeklyTimelineItem(event: WeeklyEvent, index: number): WeeklyTimelineItem {
  const status: WeeklyTimelineStatus =
    event.action === 'replaced' || event.action === 'restored'
      ? 'adjusted'
      : event.action === 'skipped'
        ? 'skipped'
        : 'completed'
  const actionLabel = WEEKLY_ACTION_LABELS[event.action] ?? event.action
  return {
    id: `${event.recommendation_id}-${index}`,
    /* B5 事件时间为 UTC ISO；只取时间部分展示，日期语义不重新解释。 */
    time: event.recorded_at.slice(11, 16),
    action: event.action,
    tag: actionLabel,
    description: event.title ? `${event.title} · ${actionLabel}` : actionLabel,
    status,
  }
}

/** B5：只读统计映射；insight 只包含确定性统计事实，不生成 AI 结论。 */
export function adaptWeeklyResponse(
  dto: WeeklyResponse,
  message = 'Production Weekly 统计（UTC 日期边界）。',
): WeeklyContract {
  const counts = dto.totals?.action_counts ?? {}
  const segments: WeeklyTextSegment[] = [
    { text: `完成 ${counts.completed ?? 0} 项 · 累计 ${dto.totals?.completed_minutes ?? 0} 分钟` },
  ]
  if ((counts.skipped ?? 0) > 0) segments.push({ text: `跳过 ${counts.skipped} 项` })
  if ((counts.replaced ?? 0) > 0) segments.push({ text: `替换 ${counts.replaced} 项` })

  return {
    state: { status: 'ready', mode: 'production', message },
    dataAvailability: dto.days?.length ? 'available' : 'unavailable',
    header: {
      title: '这一周，薇薇的变化 🌱',
      description: `统计区间 ${dto.start_date} ～ ${dto.end_date}（UTC 日期边界）`,
    },
    chart: {
      title: '每日完成任务的分钟数',
      note: '只统计白名单小任务',
    },
    days: (dto.days ?? []).map(day => day.date.slice(5)),
    minutes: (dto.days ?? []).map(day => day.completed_minutes),
    timelineTitle: '推荐的调整轨迹',
    timeline: (dto.events ?? []).map(toWeeklyTimelineItem),
    insight: {
      title: '本周统计',
      segments,
      quote: '',
    },
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

function toSuggestedTask(task: SelectedTask | null, recommendationId?: string | null) {
  if (!task) return null

  return {
    taskId: task.task_id,
    icon: '🌿',
    title: task.title,
    meta: `约 ${task.estimated_minutes} 分钟`,
    actionLabel: '去做',
    recommendationId: recommendationId ?? undefined,
    instruction: task.instruction,
    domains: 'covered_domains' in task ? task.covered_domains : [],
  }
}

function toSafety(dto: RecommendationResponse): AssistantSafetyNotice | null {
  if (dto.status === 'allowed') return null

  const copy = safetyCopy[dto.status]
  return {
    status: dto.status,
    title: copy.title,
    paragraphs: dto.explanation ? [dto.explanation] : copy.paragraphs,
    rule: copy.rule,
  }
}

function tracedAnalysis(publicRag: PublicRagTrace | null | undefined): AssistantAnalysisStage {
  const factors = publicRag?.factors ?? []
  return {
    id: 'analysis',
    title: '问题拆解',
    status: 'done',
    statusLabel: '已完成分析',
    statusLabels: { done: '已完成分析' },
    visible: true,
    lead: publicRag?.analysis_fallback
      ? '本次未返回结构化问题拆解；已使用原问题继续真实检索。'
      : factors.length
        ? `已将问题整理为 ${factors.length} 个可公开、可核验的方向。`
        : '已完成需求理解；本次执行没有返回可公开的结构化拆解。',
    items: publicRag?.analysis_fallback
      ? []
      : factors.map(factor => ({
          id: factor.factor_id,
          title: factor.subquery,
          direction: factor.evidence_need || (factor.domain_hint ? `关注领域：${factor.domain_hint}` : '检索相关审核知识'),
      })),
  }
}

function toEvidenceOnlyChunk(source: EvidenceSource) {
  return {
    id: source.chunk_id,
    source: source.source_locator || source.source_url || '参考来源',
    text: null,
    relevance: null,
  }
}

function tracedRetrieval(
  allowed: boolean,
  publicRag: PublicRagTrace | null | undefined,
  evidence: readonly EvidenceSource[],
): AssistantRetrievalStage {
  const publicChunks = publicRag?.knowledge_chunks ?? []
  const chunks = publicChunks.length
    ? publicChunks.map(chunk => ({
        id: `${chunk.factor_id}-${chunk.chunk_id}`,
        source: chunk.source_locator || chunk.source_url || '审核知识库',
        text: chunk.excerpt,
        relevance: null,
      }))
    : evidence.map(toEvidenceOnlyChunk)
  return allowed
    ? {
        id: 'retrieval',
        title: '知识检索',
        status: 'done',
        statusLabel: publicChunks.length ? `命中 ${publicChunks.length} 个公开片段` : '已完成检索',
        statusLabels: { done: '已完成检索' },
        visible: true,
        chunks,
      }
    : {
        id: 'retrieval',
        title: '知识检索',
        status: 'pending',
        statusLabel: '未开始',
        statusLabels: { pending: '未开始' },
        visible: true,
        chunks: [],
      }
}

export function adaptAgenticRecommendation(
  dto: RecommendationResponse,
  options: { traceIsReal?: boolean } = {},
): AssistantReply {
  const traced = options.traceIsReal === true
  const allowed = dto.status === 'allowed'
  const evidence = [...dto.sources, ...(dto.context_sources ?? [])]
  const sources = evidence.map(toSource)
  const analysis = traced && allowed ? tracedAnalysis(dto.public_rag) : unavailableAnalysis()
  const retrieval = traced && allowed
    ? tracedRetrieval(allowed, dto.public_rag, evidence)
    : unavailableRetrieval()
  const answer = availableAnswer()
  const pipeline: AssistantPipeline = { analysis, retrieval, answer }
  const text = dto.explanation ? [{ text: dto.explanation }] : []

  return {
    id: 'production-agentic-reply',
    scenario: null,
    pipeline,
    answer: text,
    suggestedTask: dto.status === 'allowed'
      ? toSuggestedTask(dto.selected_task, dto.recommendation_id)
      : null,
    safety: toSafety(dto),
    sources,
    guardNotice: dto.explanation_guard?.fallback_used
      ? '本次生成回答未通过输出校验，已切换为安全兜底说明；检索与来源仍来自本次真实执行。'
      : null,
    traceIsReal: traced,
    timing: null,
  }
}

/* B3：一次 Agentic 执行期间的实时 pipeline 初始状态（不自行推进）。 */
export function createLiveTracePipeline(): AssistantPipeline {
  return {
    analysis: {
      id: 'analysis',
      title: '问题拆解',
      status: 'pending',
      statusLabel: '等待开始',
      statusLabels: { active: '正在理解你的需求' },
      visible: true,
      lead: null,
      items: [],
    },
    retrieval: {
      id: 'retrieval',
      title: '知识检索',
      status: 'pending',
      statusLabel: '等待开始',
      statusLabels: { active: '正在检索相关健康知识' },
      visible: true,
      chunks: [],
    },
    answer: {
      id: 'answer',
      title: '回答',
      status: 'pending',
      statusLabel: '等待开始',
      statusLabels: { active: '正在整理建议' },
      visible: false,
    },
  }
}

const ANALYSIS_TRACE_STAGES = new Set(['accepted', 'safety', 'analysis'])
const RETRIEVAL_TRACE_STAGES = new Set([
  'retrieval',
  'ranking',
  'memory',
  'personalization',
  'grounding',
])

/**
 * B3：用真实 backend trace 事件更新 pipeline。
 * 仅在收到事件时推进；后一阶段真实事件到达 = 前一阶段已真实完成。
 */
export function applyAgentTraceEvent(
  pipeline: AssistantPipeline,
  event: AssistantTraceEvent,
): AssistantPipeline {
  const next: AssistantPipeline = {
    analysis: { ...pipeline.analysis },
    retrieval: { ...pipeline.retrieval },
    answer: { ...pipeline.answer },
  }
  if (event.status === 'error') return next
  if (ANALYSIS_TRACE_STAGES.has(event.stage)) {
    if (event.status === 'complete') {
      next.analysis.status = 'done'
      next.analysis.statusLabel = event.label
      next.analysis.statusLabels = { ...next.analysis.statusLabels, done: event.label }
      next.analysis.visible = true
      if (event.stageResult?.analysis) {
        next.analysis.lead = event.stageResult.analysis.lead
        next.analysis.items = [...event.stageResult.analysis.items]
      }
    } else {
      next.analysis.status = 'active'
      next.analysis.statusLabel = event.label
      next.analysis.statusLabels = { ...next.analysis.statusLabels, active: event.label }
    }
  } else if (RETRIEVAL_TRACE_STAGES.has(event.stage)) {
    if (event.status === 'complete') {
      if (next.analysis.status === 'active') next.analysis.status = 'done'
      next.retrieval.status = 'done'
      next.retrieval.statusLabel = event.label
      next.retrieval.statusLabels = { ...next.retrieval.statusLabels, done: event.label }
      next.retrieval.visible = true
      if (event.stageResult?.retrieval) {
        next.retrieval.chunks = [...event.stageResult.retrieval.chunks]
      }
    } else {
      if (next.analysis.status === 'active') next.analysis.status = 'done'
      next.retrieval.status = 'active'
      next.retrieval.statusLabel = event.label
      next.retrieval.statusLabels = { ...next.retrieval.statusLabels, active: event.label }
    }
  } else if (event.stage === 'generation') {
    if (next.analysis.status === 'active') next.analysis.status = 'done'
    if (next.retrieval.status === 'active') next.retrieval.status = 'done'
    next.answer.status = 'active'
    next.answer.statusLabel = event.label
    next.answer.statusLabels = { ...next.answer.statusLabels, active: event.label }
    next.answer.visible = true
  } else if (event.stage === 'completed') {
    if (next.analysis.status === 'active') next.analysis.status = 'done'
    if (next.retrieval.status === 'active') next.retrieval.status = 'done'
    // answer 的 done 由最终 reply 呈现（同一执行），live 期间保持 active/pending，
    // 避免在真实 reply 尚未落地时渲染空 AnswerCard。
  }
  return next
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
      { id: 'neck', label: '我脖子有点疼', question: '我脖子有点疼。' },
    ],
    greeting: {
      face: '薇薇',
      segments: [{ text: '告诉我你现在的困扰，我会结合审核知识库和你的状态，给出适合你的小建议。' }],
    },
    replies: { exam: reply, sleep: reply, neck: reply, fallback: reply },
  }
}

/** 白名单领域 → 原型中文标签 / 卡片色调。 */
const TASK_DOMAIN_LABELS: Record<string, string> = {
  eye_health: '用眼健康',
  light_recovery: '用眼健康',
  sleep: '睡前准备',
  sleep_hygiene: '睡前准备',
  physical_activity: '身体活动',
  sedentary: '身体活动',
  study_break: '学习休息',
  neck_shoulder: '颈肩放松',
  emotion: '情绪照顾',
  mood: '情绪照顾',
  stress: '情绪照顾',
}

const TASK_DOMAIN_TONES: Record<string, 'eye' | 'move' | 'sleep'> = {
  eye_health: 'eye',
  light_recovery: 'eye',
  sleep: 'sleep',
  sleep_hygiene: 'sleep',
  physical_activity: 'move',
  sedentary: 'move',
  neck_shoulder: 'move',
}

function taskToneFromDomains(domains: readonly string[]): TodayTaskTone {
  for (const domain of domains) {
    const tone = TASK_DOMAIN_TONES[domain]
    if (tone) return tone
  }
  return 'default'
}

function toTodayTask(
  task: SurfacedTask | SelectedTask,
  recommendationId: string | null,
  explanation: string | null,
): TodayTaskView {
  const id = task.task_id
  const domains = 'covered_domains' in task ? task.covered_domains : []
  return {
    id,
    taskId: id,
    recommendationId: recommendationId ?? undefined,
    tone: taskToneFromDomains(domains),
    domain: domains.map(domain => TASK_DOMAIN_LABELS[domain]).find(Boolean) ?? '微任务',
    meta: `约 ${task.estimated_minutes} 分钟`,
    name: task.title,
    description: task.instruction,
    /* B1：只有 rank1 有 LLM explanation；task2/task3 诚实省略。 */
    why: explanation ?? '该任务来自审核白名单，并结合你此刻的状态与可用时间选出。',
    whyIcon: 'flower',
  }
}

export function adaptRecommendationResponse(dto: RecommendationResponse): TodayContract {
  const recommendationStatus: TodayRecommendationStatus = dto.status
  const raw = (dto.tasks ?? []).filter(task => task.task_id)
  let tasks: TodayTaskView[] = []
  if (dto.status === 'allowed') {
    if (raw.length > 0) {
      tasks = raw.map((task, index) =>
        toTodayTask(
          task,
          task.recommendation_id ?? (index === 0 ? dto.recommendation_id : null),
          index === 0 ? dto.explanation : null,
        ),
      )
    } else if (dto.selected_task) {
      /* 兼容旧单任务 backend 响应（无 B1 tasks 字段）。 */
      tasks = [toTodayTask(dto.selected_task, dto.recommendation_id, dto.explanation)]
    }
  }
  const availability: TodayDataAvailability = {
    ...unavailableTodayAvailability,
    selectedTask: tasks.length > 0 ? 'available' : 'unavailable',
    dailyTasks: tasks.length > 0 ? 'available' : 'unavailable',
    progress: tasks.length > 0 ? 'available' : 'unavailable',
    restore: tasks.length > 0 ? 'available' : 'unavailable',
  }
  const unavailableFields = Object.entries(availability)
    .filter(([, status]) => status === 'unavailable')
    .map(([field]) => field)
  const message =
    dto.explanation ??
    (tasks.length > 0
      ? `当前有 ${tasks.length} 条后端推荐任务。`
      : '当前没有后端返回的安全任务。')

  return {
    ...createUnavailableTodayContract(message),
    state: { status: 'ready', mode: 'production', message },
    dataAvailability: tasks.length > 0 ? (tasks.length < 3 ? 'partial' : 'available') : 'unavailable',
    recommendationStatus,
    availability,
    unavailableFields,
    summaryLines: dto.explanation ? [[{ text: dto.explanation }]] : [],
    tasksSectionTitle: '今日微任务',
    tasksSectionNote: '来自审核白名单 · 按你的画像生成',
    tasks,
  }
}

/** 由 B2 任务动作事件按时间顺序推导当天已保存的交互状态。 */
function deriveSavedInteraction(actions: readonly { action: string }[]): TodaySavedInteraction {
  let state: TodaySavedInteraction = 'pending'
  for (const event of actions) {
    if (event.action === 'started') state = 'started'
    else if (event.action === 'completed') state = 'done'
    else if (event.action === 'partially_completed') state = 'partial'
    else if (event.action === 'skipped') state = 'skipped'
    else if (event.action === 'restored') state = 'pending'
  }
  return state
}

function toTodayTaskFromSession(session: TodaySessionItem): TodayTaskView {
  return {
    id: session.task_id,
    taskId: session.task_id,
    recommendationId: session.recommendation_id,
    tone: taskToneFromDomains(session.covered_domains),
    domain: session.covered_domains.map(domain => TASK_DOMAIN_LABELS[domain]).find(Boolean) ?? '微任务',
    meta: `约 ${session.estimated_minutes} 分钟`,
    name: session.title,
    description: session.instruction,
    why: '这项任务今天已加入你的清单，直接继续就好。',
    whyIcon: 'flower',
    savedInteraction: deriveSavedInteraction(session.actions),
    feedbackSaved: session.feedback !== null && session.feedback !== undefined,
  }
}

/**
 * F4：把当天已保存的推荐会话还原为 Today 契约。
 * 任务内容来自创建时保存的正式任务快照，不是重新生成。
 */
export function adaptTodaySessions(dto: TodaySessionsResponse): TodayContract {
  const tasks = dto.sessions.filter(session => session.recommendation_id).map(toTodayTaskFromSession)
  const message =
    tasks.length > 0
      ? `已恢复今天保存的 ${tasks.length} 项任务记录。`
      : '今天还没有已保存的任务。'
  return {
    ...createUnavailableTodayContract(message),
    state: { status: 'ready', mode: 'production', message },
    dataAvailability: tasks.length > 0 ? 'available' : 'unavailable',
    recommendationStatus: 'allowed',
    availability: {
      ...unavailableTodayAvailability,
      selectedTask: tasks.length > 0 ? 'available' : 'unavailable',
      dailyTasks: tasks.length > 0 ? 'available' : 'unavailable',
      progress: tasks.length > 0 ? 'available' : 'unavailable',
      restore: tasks.length > 0 ? 'available' : 'unavailable',
    },
    unavailableFields: [],
    tasksSectionTitle: '今日微任务',
    tasksSectionNote: '来自审核白名单 · 按你的画像生成',
    tasks,
  }
}

/**
 * F4：读回记录 + 新推荐合并。
 * 已开始/已完成/已放下的读回条目是今天的记录，始终保留；
 * 未开始候选一律来自最新一次推荐（反映当前心情/时间），避免用旧上下文
 * 的候选冒充已适配；新推荐不可用时才回退展示读回的未开始候选。
 * 按任务定义 id 去重，不把已处理过的任务再排进候选。
 */
export function mergeTodayContracts(restored: TodayContract, fresh: TodayContract): TodayContract {
  const isPending = (task: TodayTaskView): boolean =>
    !task.savedInteraction || task.savedInteraction === 'pending'
  const active = restored.tasks.filter(task => !isPending(task))
  const restoredPending = restored.tasks.filter(isPending)
  const handled = new Set(active.map(task => task.taskId))
  const target = Math.max(3, active.length)
  const extra: TodayTaskView[] = []
  for (const task of fresh.tasks) {
    if (extra.length + active.length >= target) break
    if (handled.has(task.taskId)) continue
    handled.add(task.taskId)
    extra.push(task)
  }
  const candidates =
    extra.length > 0 ? extra : restoredPending.slice(0, Math.max(0, target - active.length))
  const tasks = [...active, ...candidates]
  const count = tasks.length
  return {
    ...restored,
    dataAvailability: count > 0 ? (count < 3 ? 'partial' : 'available') : 'unavailable',
    tasks,
  }
}

/**
 * Profile/Questionnaire 适配器只消费真实 DTO。
 * 偏好统计没有正式数据源时保留真实空态；Memory 与近 7 天完成情况
 * 分别由 B4/B5 DTO 接线，不导入 fixture，也不触发第二套 LLM。
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
      unavailableMessage: '记忆暂时无法加载，请稍后重试。',
    },
  }
}

/** B4：Memory list → Profile Memory 展示切片（只展示真实数据）。 */
export function adaptMemoryListResponse(dto: MemoryListResponse): ProfileMemoryListContract {
  const enabled = dto.memory_enabled === true
  const items: MemoryItemContract[] = (dto.memories ?? []).map(memory => ({
    id: memory.memory_id,
    icon: 'leaf',
    lead: memory.memory_type,
    text: memory.summary,
  }))
  return {
    enabled,
    consent: enabled ? 'granted' : 'disabled',
    items,
    canDelete: enabled && items.length > 0,
    notice: enabled
      ? items.length > 0
        ? '这些是当前已形成的记忆；你可以随时删除。'
        : '记忆已开启；尚未形成可展示的记忆。'
      : 'Memory 保持关闭。',
  }
}

function completionPatternFromWeekly(dto: WeeklyResponse | null): ProfileContract['completionPattern'] {
  if (!dto) {
    return {
      status: 'unavailable',
      icon: 'target',
      title: '近 7 天完成情况',
      percentage: null,
      summaryLines: [],
      unavailableMessage: '近 7 天任务记录暂时无法加载。',
    }
  }
  const counts = dto.totals?.action_counts ?? {}
  const completed = counts.completed ?? 0
  const partial = counts.partially_completed ?? 0
  const skipped = counts.skipped ?? 0
  const outcomes = completed + partial + skipped
  if (outcomes === 0) {
    return {
      status: 'available',
      icon: 'target',
      title: '近 7 天完成情况',
      percentage: null,
      summaryLines: [],
      unavailableMessage: '近 7 天还没有足够的任务结果；有记录后会在这里形成统计。',
    }
  }
  return {
    status: 'available',
    icon: 'target',
    title: '近 7 天完成情况',
    percentage: Math.round(((completed + partial) / outcomes) * 100),
    summaryLines: [
      `完成 ${completed} 项 · 部分完成 ${partial} 项 · 跳过 ${skipped} 项。`,
      '比例只根据已有任务结果计算，不推断未记录的行为。',
    ],
  }
}

export function adaptProfileResponse(
  dto: MockProfileResponse,
  memories: ProfileMemoryListContract | null = null,
  weekly: WeeklyResponse | null = null,
): ProfileContract {
  const memoryEnabled = dto.memory_enabled === true
  const consent: MemoryConsentState = memoryEnabled
    ? 'granted'
    : dto.memory_enabled === false
      ? 'disabled'
      : 'missing'
  const preferenceEmptyMessage = '还没有形成可展示的偏好统计。'
  const memory = memories
    ? { status: 'available' as const, ...memories }
    : {
        status: 'unavailable' as const,
        enabled: memoryEnabled,
        consent,
        items: [],
        canDelete: false,
        notice: memoryEnabled
          ? '记忆已开启，但暂时无法加载。'
          : '没有明确 consent 时，Memory 保持关闭。',
        unavailableMessage: '记忆暂时无法加载，请稍后重试。',
      }

  return {
    state: { status: 'ready', mode: 'production' },
    targetStage: dto.target_stage ?? 'unavailable',
    memoryEnabled,
    header: {
      title: '我的画像',
      description: '这里只展示你的个人设置、任务记录和已授权记忆；没有数据时不会用示例内容填充。',
    },
    timePreference: unavailablePreference('time', 'clock', '时间偏好', preferenceEmptyMessage),
    taskPreference: unavailablePreference('task', 'leaf', '任务偏好', preferenceEmptyMessage),
    completionPattern: completionPatternFromWeekly(weekly),
    memory,
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
    phase: 'unavailable',
    steps: [],
    totalSteps: 0,
    initialAnswers: {},
    summary: { title: '画像生成不可用', lines: [] },
    questionnaire,
    questionnaireCompatibility,
    persistence: [],
    consent: { prompt: '', note: '' },
    storageKey: '',
  }
}

/** 后端合法学段（TargetStage）。 */
export const PRODUCTION_TARGET_STAGES: readonly string[] = [
  'primary_upper',
  'junior_high',
  'senior_high',
]

/**
 * B6：Production 5 步引导。只有学段与 Memory 偏好会持久化，
 * 其余字段仅为本次会话展示。
 */
export function createProductionOnboardingContract(
  message = '完成引导后，只保存你的学段与 Memory 偏好；其余回答仅用于本次会话。',
): OnboardingContract {
  const steps = frozenOnboardingSteps

  return {
    state: { status: 'ready', mode: 'production', message },
    phase: 'ready',
    steps,
    totalSteps: frozenOnboardingSteps.length,
    initialAnswers: {},
    summary: {
      title: '✦ 画像已生成',
      lines: ['已保存你的学段与 Memory 偏好。', '睡眠、近期问题、时长与时段偏好仅本次展示，未写入长期数据。'],
    },
    questionnaire: {
      status: 'unavailable',
      questionnaireId: null,
      completionState: null,
      questionCount: null,
      answers: {},
    },
    questionnaireCompatibility: {
      status: 'unavailable',
      prototypeStepCount: 5,
      backendQuestionCount: null,
      message: '新引导不使用旧 7 题问卷；只保存学段与 Memory 偏好。',
    },
    persistence: [
      { fieldId: 'grade', status: 'persisted', reason: '写入 profile.target_stage' },
      { fieldId: 'sleep', status: 'unavailable', reason: '仅本次引导展示，不保存长期数据' },
      { fieldId: 'issues', status: 'unavailable', reason: '仅本次引导展示，不保存长期数据' },
      { fieldId: 'duration', status: 'unavailable', reason: '后端暂无正式时长偏好字段' },
      { fieldId: 'slot', status: 'unavailable', reason: '后端暂无正式时段偏好字段' },
      { fieldId: 'memory_enabled', status: 'persisted', reason: '写入 profile.memory_enabled' },
    ],
    consent: {
      prompt: '允许微律使用记忆来调整后续建议（默认关闭）',
      note: '只有你明确开启后才会启用；可随时在设置中关闭。',
    },
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
