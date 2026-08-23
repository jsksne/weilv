import { effectScope } from 'vue'

import { useBreathCycle } from './composables/useBreathCycle'

/* ------------------------------------------------------------------
   Sprint 4：useBreathCycle —— 右栏「此刻 · 跟随呼吸」文字节奏
   （迁移自原型 breathLoop：9s 循环 = 吸气 1.8s（4→1）+ 呼气 7.2s（6→1））
   ------------------------------------------------------------------ */

function withCycle(test: (cycle: ReturnType<typeof useBreathCycle>) => void) {
  const cycle = useBreathCycle()
  try {
    test(cycle)
  } finally {
    cycle.stop()
  }
}

describe('Sprint 4 useBreathCycle', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows the frozen idle copy before the first cycle starts', () => {
    withCycle(cycle => {
      expect(cycle.label.value).toBe('准备…')
      expect(cycle.count.value).toBe('—')
    })
  })

  it('begins the inhale phase immediately with the 4-second countdown', () => {
    withCycle(cycle => {
      cycle.start()
      expect(cycle.label.value).toBe('吸气 · 4 秒')
      expect(cycle.count.value).toBe('4')

      vi.advanceTimersByTime(450)
      expect(cycle.count.value).toBe('3')
      vi.advanceTimersByTime(450)
      expect(cycle.count.value).toBe('2')
      vi.advanceTimersByTime(450)
      expect(cycle.count.value).toBe('1')
      /* 吸气段 1.8s 结束前保持 1 */
      vi.advanceTimersByTime(449)
      expect(cycle.label.value).toBe('吸气 · 4 秒')
      expect(cycle.count.value).toBe('1')
    })
  })

  it('switches to the exhale phase with the 6→1 decay at exact boundaries', () => {
    withCycle(cycle => {
      cycle.start()
      /* 原型呼气计数 max(1, ceil(6*(1-t)))，t 为 7.2s 内的进度；
         值变化时刻：1800ms→6，3000→5，4200→4，5400→3，6600→2，7800→1 */
      vi.advanceTimersByTime(1800)
      expect(cycle.label.value).toBe('呼气 · 慢慢地')
      expect(cycle.count.value).toBe('6')

      vi.advanceTimersByTime(1200)
      expect(cycle.count.value).toBe('5')
      vi.advanceTimersByTime(1200)
      expect(cycle.count.value).toBe('4')
      vi.advanceTimersByTime(1200)
      expect(cycle.count.value).toBe('3')
      vi.advanceTimersByTime(1200)
      expect(cycle.count.value).toBe('2')
      vi.advanceTimersByTime(1200)
      expect(cycle.count.value).toBe('1')
      /* 循环尾段保持 1 */
      vi.advanceTimersByTime(1199)
      expect(cycle.count.value).toBe('1')
    })
  })

  it('repeats the 9-second cycle', () => {
    withCycle(cycle => {
      cycle.start()
      vi.advanceTimersByTime(9000)
      expect(cycle.label.value).toBe('吸气 · 4 秒')
      expect(cycle.count.value).toBe('4')
      /* 第二轮吸气段：+900ms → 2 */
      vi.advanceTimersByTime(900)
      expect(cycle.count.value).toBe('2')
    })
  })

  it('stops all timers on stop() so nothing changes afterwards', () => {
    withCycle(cycle => {
      cycle.start()
      vi.advanceTimersByTime(1000)
      cycle.stop()
      const labelAtStop = cycle.label.value
      const countAtStop = cycle.count.value

      vi.advanceTimersByTime(60000)
      expect(cycle.label.value).toBe(labelAtStop)
      expect(cycle.count.value).toBe(countAtStop)
    })
  })

  it('cleans up automatically when the owning scope disposes', () => {
    const scope = effectScope()
    const cycle = scope.run(() => useBreathCycle())!
    cycle.start()
    vi.advanceTimersByTime(1000)
    scope.stop()

    const labelAtStop = cycle.label.value
    vi.advanceTimersByTime(60000)
    expect(cycle.label.value).toBe(labelAtStop)
  })
})