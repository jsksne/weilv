import type { OnboardingContract } from '@/contracts'

/** 冻结原型五步 Demo flow；答案只存在于组件内存，不提交 Questionnaire。 */
export const onboardingFixture = {
  state: { status: 'ready', mode: 'demo' },
  totalSteps: 5,
  steps: [
    {
      id: 'welcome',
      kind: 'welcome',
      title: '你好，我是微律',
      intro: [
        '你的专属健康 AI。我会留意你的睡眠、用眼和情绪，',
        '每天只给你三件小到不会拒绝的事。',
        '先花 60 秒，让我认识你。',
      ],
    },
    {
      id: 'basics',
      kind: 'choices',
      title: '基础画像',
      groups: [
        {
          id: 'grade',
          prompt: '你现在在读…',
          options: [
            { value: 'junior_high', label: '初中' },
            { value: 'senior_high', label: '高中' },
            { value: 'university', label: '大学' },
          ],
          defaultValue: 'senior_high',
        },
        {
          id: 'sleep',
          prompt: '昨晚睡了多久？',
          options: [
            { value: 'under_6', label: '不到 6 小时' },
            { value: '6_to_7', label: '6 – 7 小时' },
            { value: '7_to_8', label: '7 – 8 小时' },
            { value: 'over_8', label: '8 小时以上' },
          ],
          defaultValue: '6_to_7',
        },
      ],
    },
    {
      id: 'issues',
      kind: 'choices',
      title: '最近主要问题',
      groups: [
        {
          id: 'issues',
          prompt: '可多选 · 微律会优先照顾这些',
          multiple: true,
          options: [
            { value: 'tired_eyes', label: '眼睛容易累' },
            { value: 'tight_shoulders', label: '肩颈发紧' },
            { value: 'racing_thoughts', label: '睡前想太多' },
            { value: 'mood_swings', label: '情绪起伏' },
            { value: 'no_time', label: '没时间运动' },
          ],
          defaultValues: ['tired_eyes', 'tight_shoulders'],
        },
      ],
    },
    {
      id: 'behavior',
      kind: 'choices',
      title: '行为偏好',
      groups: [
        {
          id: 'duration',
          prompt: '能接受的任务时长',
          options: [
            { value: 'under_3', label: '3 分钟以内' },
            { value: '3_to_5', label: '3 – 5 分钟' },
            { value: '5_to_10', label: '5 – 10 分钟' },
          ],
          defaultValue: 'under_3',
        },
        {
          id: 'slot',
          prompt: '偏好任务时段',
          options: [
            { value: 'after_school', label: '放学后' },
            { value: 'after_dinner', label: '晚饭后' },
            { value: 'before_bed', label: '睡前' },
          ],
          defaultValue: 'after_school',
        },
      ],
    },
    {
      id: 'generation',
      kind: 'generation',
      title: '生成初始画像',
    },
  ],
  initialAnswers: {
    grade: 'senior_high',
    sleep: '6_to_7',
    issues: ['tired_eyes', 'tight_shoulders'],
    duration: 'under_3',
    slot: 'after_school',
  },
  summary: {
    title: '✦ 画像已生成',
    lines: ['高中生 · 睡眠偏短 · 用眼负担大 · 偏好 3 分钟内的小任务', '今晚 21:40，微律为你准备了第一件小事。'],
  },
  questionnaire: {
    status: 'unavailable',
    questionnaireId: null,
    completionState: null,
    questionCount: null,
    answers: {},
  },
  questionnaireCompatibility: {
    status: 'contractMismatch',
    prototypeStepCount: 5,
    backendQuestionCount: 7,
    message: '演示流程不会提交当前 Questionnaire：原型五步与现有七题问卷语义不一致。',
  },
  storageKey: 'wl_aurora_onboarded',
} satisfies OnboardingContract
