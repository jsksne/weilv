import type {
  AssistantAnalysisStage,
  AssistantContract,
  AssistantKnowledgeChunk,
  AssistantPipeline,
  AssistantReply,
  AssistantRetrievalStage,
} from '@/contracts'

const pendingLabels = {
  pending: '等待开始',
}

function analysisStage(
  lead: string,
  items: AssistantAnalysisStage['items'],
  labels: AssistantAnalysisStage['statusLabels'],
): AssistantAnalysisStage {
  return {
    id: 'analysis',
    title: '问题拆解',
    status: 'pending',
    statusLabel: pendingLabels.pending,
    statusLabels: { ...pendingLabels, ...labels },
    visible: false,
    lead,
    items,
  }
}

function retrievalStage(
  chunks: readonly AssistantKnowledgeChunk[],
  labels: AssistantRetrievalStage['statusLabels'],
): AssistantRetrievalStage {
  return {
    id: 'retrieval',
    title: '知识检索',
    status: 'pending',
    statusLabel: pendingLabels.pending,
    statusLabels: { ...pendingLabels, ...labels },
    visible: false,
    chunks,
  }
}

function pipeline(
  analysis: AssistantAnalysisStage,
  retrieval: AssistantRetrievalStage,
): AssistantPipeline {
  return {
    analysis,
    retrieval,
    answer: {
      id: 'answer',
      title: '回答',
      status: 'pending',
      statusLabel: pendingLabels.pending,
      statusLabels: { pending: '等待检索', active: '生成中…', done: '已回答' },
      visible: false,
    },
  }
}

const examChunks: readonly AssistantKnowledgeChunk[] = [
  {
    id: 'exam-1',
    source: '健康教育指导纲要',
    text: '考试期间建议以低负担、可随时中断的微休息为主，优先缓解用眼与久坐疲劳。',
    relevance: 0.91,
  },
  {
    id: 'exam-2',
    source: 'WHO 身体活动指南',
    text: '青少年每次 1–3 分钟的间歇活动即可获益，无需连续长时间运动。',
    relevance: 0.87,
  },
]

const sleepChunks: readonly AssistantKnowledgeChunk[] = [
  {
    id: 'sleep-1',
    source: '青少年睡眠健康白皮书',
    text: '睡前进行 4-7-8 呼吸等慢呼吸练习，可降低唤醒水平，缩短入睡时间。',
    relevance: 0.93,
  },
  {
    id: 'sleep-2',
    source: '教育部睡眠管理通知',
    text: '睡前应减少学习与屏幕刺激，预留安静过渡时段。',
    relevance: 0.85,
  },
]

const neckChunks: readonly AssistantKnowledgeChunk[] = [
  {
    id: 'neck-1',
    source: '微律安全规则 v0.1',
    text: '身体部位疼痛类输入触发输入风险分流：暂停普通推荐，不做医疗判断，提示求助家长或老师。',
    relevance: 0.98,
  },
]

const fallbackChunks: readonly AssistantKnowledgeChunk[] = [
  {
    id: 'fallback-1',
    source: '微律审核知识库',
    text: '长时间学习后，起身到窗边远眺或轻度活动 1 分钟，对用眼、颈肩与情绪均有改善。',
    relevance: 0.82,
  },
]

const examReply: AssistantReply = {
  id: 'demo-exam',
  scenario: 'exam',
  pipeline: pipeline(
    analysisStage(
      '我先把这句话拆成两个小问题：',
      [
        { id: 'q1', title: '考试周适合的低负担小任务有哪些？', direction: '方向：可随时中断的微休息' },
        { id: 'q2', title: '只有 10 分钟时，优先做哪一件？', direction: '方向：结合你的任务偏好排序' },
      ],
      { active: '理解中…', done: '已拆解 2 个方向' },
    ),
    retrievalStage(examChunks, { active: '正在检索 health_knowledge_v1 …', done: '命中 2 个片段' }),
  ),
  answer: [
    { text: '10 分钟，两件小事就够了——' },
    { text: '窗边远眺 1 分钟', emphasis: true },
    { text: '照顾眼睛，' },
    { text: '颈肩伸展 3 分钟', emphasis: true },
    { text: '照顾脖子，剩下的时间安心复习。' },
  ],
  suggestedTask: { icon: '🌿', title: '颈肩小伸展', meta: '约 3 分钟 · 你接受率最高的类型', actionLabel: '去做' },
  safety: null,
  sources: [
    { label: '《中小学生健康教育指导纲要》' },
    { label: 'WHO《青少年身体活动指南》' },
  ],
  traceIsReal: false,
  timing: { analysisCard: 700, analysisFill: 750, retrievalCard: 850, retrievalFill: 850, answer: 900 },
}

const sleepReply: AssistantReply = {
  id: 'demo-sleep',
  scenario: 'sleep',
  pipeline: pipeline(
    analysisStage(
      '「睡不好」我拆成了两个方向：',
      [
        { id: 'q1', title: '入睡困难时的轻放松方法？', direction: '方向：慢呼吸类干预' },
        { id: 'q2', title: '考试周怎么安排睡前收尾？', direction: '方向：刺激控制与睡前过渡' },
      ],
      { active: '理解中…', done: '已拆解 2 个方向' },
    ),
    retrievalStage(sleepChunks, { active: '正在检索 health_knowledge_v1 …', done: '命中 2 个片段' }),
  ),
  answer: [
    { text: '今晚试试 ' },
    { text: '花瓣呼吸', emphasis: true },
    { text: '（吸 4 秒、停 7 秒、呼 8 秒，循环 4 次），已经放进你 ' },
    { text: '21:40 的节奏', emphasis: true },
    { text: '里啦。复习结束后留 10 分钟「不看书也不碰手机」的空白，会比直接躺下更容易睡着。' },
  ],
  suggestedTask: { icon: '🌙', title: '花瓣呼吸 4-7-8', meta: '约 2 分钟 · 已在今日清单', actionLabel: '去做' },
  safety: null,
  sources: [
    { label: '《中国青少年睡眠健康白皮书》' },
    { label: '教育部睡眠管理通知' },
  ],
  traceIsReal: false,
  timing: { analysisCard: 700, analysisFill: 750, retrievalCard: 850, retrievalFill: 850, answer: 900 },
}

const neckReply: AssistantReply = {
  id: 'demo-neck',
  scenario: 'neck',
  pipeline: pipeline(
    analysisStage(
      '我把「脖子疼」拆成一个需要谨慎处理的问题：',
      [{ id: 'q1', title: '身体疼痛类输入是否属于健康微干预的适用范围？', direction: '方向：安全边界判断' }],
      { active: '理解中…', done: '已拆解 1 个方向' },
    ),
    retrievalStage(neckChunks, { active: '正在检索安全规则库 …', done: '已命中安全规则 · 触发风险分流' }),
  ),
  answer: [{ text: '先暂停一下任务推荐。', emphasis: true }],
  suggestedTask: null,
  safety: {
    status: 'help_seeking',
    title: '⚠ 薇薇不看诊、不猜测',
    paragraphs: [
      '脖子疼可能只是久坐的僵硬，也可能需要专业的帮助。薇薇不能替代医生，所以不会推荐任何针对性的动作。',
      '如果疼得越来越厉害，或者伴随头晕、手发麻，请今天就把这件事告诉爸爸妈妈或老师，好吗？',
    ],
    rule: '已触发安全规则：输入风险分流 · 普通推荐已暂停 · 本次对话记入审计日志',
  },
  sources: [{ label: '微律安全规则 v0.1 · 输入风险分流' }],
  traceIsReal: false,
  timing: { analysisCard: 700, analysisFill: 650, retrievalCard: 850, retrievalFill: 850, answer: 800 },
}

const fallbackReply: AssistantReply = {
  id: 'demo-fallback',
  scenario: 'fallback',
  pipeline: pipeline(
    analysisStage(
      '围绕「{question}」，我先拆出一个最小的问题：',
      [{ id: 'q1', title: '现在能立刻做的、负担最小的一件事是什么？', direction: '方向：最小可行动' }],
      { active: '理解中…', done: '已拆解 1 个方向' },
    ),
    retrievalStage(fallbackChunks, { active: '正在检索 health_knowledge_v1 …', done: '命中 1 个片段' }),
  ),
  answer: [
    { text: '先给你一件最小的事：' },
    { text: '从椅子上起来，去窗边站 1 分钟', emphasis: true },
    { text: '——眼睛、脖子和心情都会谢谢你。' },
  ],
  suggestedTask: null,
  safety: null,
  sources: [{ label: '微律审核知识库 · health_knowledge_v1' }],
  traceIsReal: false,
  timing: { analysisCard: 700, analysisFill: 700, retrievalCard: 800, retrievalFill: 800, answer: 800 },
}

export const assistantFixture: AssistantContract = {
  state: { status: 'ready', mode: 'demo' },
  isDemo: true,
  traceIsReal: false,
  demoLabel: '演示模式 · 固定模板，不会请求真实 Agentic RAG',
  quickPrompts: [
    { id: 'exam', label: '考试周好累，只有 10 分钟', question: '考试周好累，只有 10 分钟' },
    { id: 'sleep', label: '最近睡不好', question: '最近睡不好' },
    { id: 'neck', label: '我脖子有点疼', question: '我脖子有点疼。' },
  ],
  greeting: {
    face: '薇薇',
    segments: [
      { text: '嗨，小满 🌸 我看过你今天的状态——连续学习 4 小时 20 分钟，明天还有数学考试，辛苦啦。' },
      {
        text: '随便和我说说现在的困扰。我会先把它拆成几个小问题，再去审核过的健康知识里检索依据，最后才给你小到能落地的行动。',
        breakBefore: true,
      },
    ],
  },
  replies: { exam: examReply, sleep: sleepReply, neck: neckReply, fallback: fallbackReply },
}
