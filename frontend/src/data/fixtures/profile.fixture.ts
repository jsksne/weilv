import type { ProfileContract } from '@/contracts'

/**
 * 冻结原型 Profile 演示数据。只由 Demo 运行态显式引用，Production Adapter
 * 不会从这里补齐偏好、完成率或 Memory。
 */
export const profileFixture = {
  state: { status: 'ready', mode: 'demo' },
  targetStage: 'senior_high',
  memoryEnabled: true,
  header: {
    title: '薇薇认识的你 🌷',
    description: '这不是成绩单，只是薇薇慢慢了解到的你。每一条都来自你的选择与反馈，随时可以修改或删除。',
  },
  timePreference: {
    id: 'time',
    icon: 'clock',
    title: '时间偏好',
    status: 'available',
    items: [
      { label: '最容易完成任务的时段', value: '17:30 – 18:10', tone: 'up' },
      { label: '次优时段', value: '21:30 – 21:50', tone: 'default' },
      { label: '几乎不碰任务的时段', value: '午休前 10 分钟', tone: 'down' },
    ],
  },
  taskPreference: {
    id: 'task',
    icon: 'leaf',
    title: '任务偏好',
    status: 'available',
    items: [
      { label: '伸展 / 拉伸类', value: '很喜欢 · 接受率 92%', tone: 'up' },
      { label: '呼吸 / 冥想类', value: '愿意尝试', tone: 'up' },
      { label: '跳跃 / 出汗类', value: '考试周会回避', tone: 'down' },
    ],
  },
  completionPattern: {
    status: 'available',
    icon: 'target',
    title: '历史规律',
    percentage: 92,
    summaryLines: [
      '3 分钟以内的小任务完成率最高。',
      '超过 10 分钟的，你 7 次里跳过了 5 次。',
      '所以薇薇越来越偏爱给你小小的事。',
    ],
  },
  memory: {
    status: 'available',
    /* Demo fixture 明确声明为已同意，仅用于演示本地撕除交互。 */
    enabled: true,
    consent: 'granted',
    canDelete: true,
    items: [
      { id: 'demo-memory-1', icon: 'flower', lead: '你说过', text: '课间走廊太挤，不想去操场活动' },
      { id: 'demo-memory-2', icon: 'moon', lead: '上周四', text: '你完成了睡前呼吸，并说「愿意继续」' },
      { id: 'demo-memory-3', icon: 'clock', lead: '薇薇发现', text: '你不太适应超过 10 分钟的任务' },
      { id: 'demo-memory-4', icon: 'book', lead: '考试周', text: '你更愿意接受坐着就能完成的任务' },
    ],
    notice: '这些记忆只属于你：薇薇不用它排名、不给任何人看，你撕掉后它就真的消失了。',
  },
} satisfies ProfileContract
