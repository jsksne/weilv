import type { WeeklyContract } from '@/contracts'

/**
 * 冻结原型 #view-weekly Demo 数据；Production 没有对应 Backend DTO，
 * 因此不会从此 fixture 补齐历史、调整轨迹或洞察。
 */
export const weeklyFixture = {
  state: { status: 'ready', mode: 'demo' },
  dataAvailability: 'available',
  header: {
    title: '这一周，薇薇的变化 🌱',
    description: '重要的不是你完成了多少，而是薇薇怎样一步步学会「什么对你更容易」。',
  },
  chart: {
    title: '每日完成任务的分钟数',
    note: '只统计白名单小任务',
  },
  days: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
  minutes: [0, 1, 4, 3, 6, 9, 8],
  timelineTitle: '推荐的调整轨迹',
  timeline: [
    {
      id: 'weekly-mon-outdoor-walk',
      time: '周一',
      action: '推荐「户外快走 10 分钟」 → 你跳过了',
      tag: '没时间',
      description: '薇薇记下：周一课后比预想的紧张',
      status: 'skipped',
    },
    {
      id: 'weekly-tue-window-look',
      time: '周二',
      action: '换成「窗边远眺 1 分钟」',
      tag: '薇薇调整',
      description: '负担降到你愿意的程度 → 完成',
      status: 'adjusted',
    },
    {
      id: 'weekly-wed-neck-stretch',
      time: '周三',
      action: '保留远眺 + 新增「颈肩伸展」',
      tag: '均完成',
      description: '都放在你偏好的 17:30 后提醒',
      status: 'completed',
    },
    {
      id: 'weekly-thu-breath',
      time: '周四',
      action: '用「花瓣呼吸」替换跳跃类',
      tag: '薇薇调整',
      description: '因为你考试周回避出汗类活动',
      status: 'adjusted',
    },
    {
      id: 'weekly-fri-small-tasks',
      time: '周五',
      action: '全部任务收进 3 分钟内',
      tag: '全部完成',
      description: '今天只剩一件：睡前呼吸',
      status: 'completed',
    },
  ],
  insight: {
    title: '本周洞察',
    segments: [
      { text: '你更容易接受 ' },
      { text: '3 分钟以内', emphasis: true },
      { text: '、' },
      { text: '坐着就能完成', emphasis: true },
      { text: '的小事。下周薇薇会优先给你这类任务，再看看周三晚上适不适合加一件户外的。' },
    ],
    quote: '薇薇想学会的从来不是「你够不够好」，而是「怎样让你更容易」。',
  },
} satisfies WeeklyContract
