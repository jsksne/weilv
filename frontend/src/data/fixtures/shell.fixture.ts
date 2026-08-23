import type { ShellContract } from '@/contracts'

export const shellFixture = {
  state: {
    status: 'ready',
    mode: 'demo',
  },
  navigation: [
    { id: 'today', label: '今日' },
    { id: 'assistant', label: '问问薇薇' },
    { id: 'profile', label: '我的画像' },
    { id: 'weekly', label: '周度变化' },
  ],
  displayName: '小满',
  dateLabel: '4 月 22 日 · 星期一',
  progress: {
    completed: 0,
    total: 3,
    note: '捡起一片，就是今天的花瓣',
  },
  toastExample: {
    id: 'shell-example',
    message: '✦ 已记下这次完成',
  },
} satisfies ShellContract
