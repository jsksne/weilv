import type { OnboardingContract } from '@/contracts'
import { frozenOnboardingSteps } from '@/data/onboardingSteps'

/** 冻结原型五步 Demo flow；答案只存在于组件内存，不提交 Questionnaire。 */
export const onboardingFixture = {
  state: { status: 'ready', mode: 'demo' },
  phase: 'ready',
  totalSteps: 5,
  steps: frozenOnboardingSteps,
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
  persistence: [
    { fieldId: 'grade', status: 'unavailable', reason: 'Demo 模式不写入后端' },
    { fieldId: 'sleep', status: 'unavailable', reason: 'Demo 模式不写入后端' },
    { fieldId: 'issues', status: 'unavailable', reason: 'Demo 模式不写入后端' },
    { fieldId: 'duration', status: 'unavailable', reason: 'Demo 模式不写入后端' },
    { fieldId: 'slot', status: 'unavailable', reason: 'Demo 模式不写入后端' },
    { fieldId: 'memory_enabled', status: 'unavailable', reason: 'Demo 模式不写入后端' },
  ],
  consent: {
    prompt: '允许微律使用记忆来调整后续建议（Demo 不保存）',
    note: 'Demo 模式不会写入任何数据；只有明确开启后真实服务才会使用记忆。',
  },
  storageKey: 'wl_aurora_onboarded',
} satisfies OnboardingContract
