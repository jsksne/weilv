import { getCurrentScope, onScopeDispose, ref, type Ref } from 'vue'

/**
 * Sprint 4：右栏「此刻 · 跟随呼吸」的文字节奏（迁移自原型 breathLoop）。
 *
 * 原型语义（9s 循环，与 today.css 的 breathCycle 9s CSS 动画同频）：
 *   - 吸气段 1.8s：label「吸气 · 4 秒」，count 4→3→2→1（450ms 步进）；
 *   - 呼气段 7.2s：label「呼气 · 慢慢地」，count = max(1, ceil(6·(1-t)))；
 *   - 初始待机文案「准备… / —」，cycle 启动即覆盖；
 *   - setInterval(9000) 无限循环。
 *
 * 工程化差异（显示序列与时刻完全一致）：
 *   - 原型呼气计数用 RAF 逐帧采样 ceil(6·(1-t))；显示值只在
 *     t = k/6 边界（1800/3000/4200/5400/6600/7800ms）变化，
 *     此处在这些精确时刻调度 timeout，结果与 RAF 采样一致；
 *   - 全部 timer 登记在案，stop() / 作用域销毁即清理，
 *     杜绝原型 setInterval 永续运行的泄漏。
 */

export interface BreathCycleController {
  label: Readonly<Ref<string>>
  count: Readonly<Ref<string>>
  start: () => void
  stop: () => void
}

const CYCLE_MS = 9000
const INHALE_MS = CYCLE_MS * 0.2

/** 吸气倒计时：n 从 4 递减到 1，步进 INHALE_MS/4 = 450ms */
const INHALE_COUNTDOWN = [4, 3, 2, 1] as const
/** 呼气显示序列（k/6 边界时刻），相对循环起点 */
const EXHALE_SCHEDULE: ReadonlyArray<{ at: number; value: number }> = [
  { at: 1800, value: 6 },
  { at: 3000, value: 5 },
  { at: 4200, value: 4 },
  { at: 5400, value: 3 },
  { at: 6600, value: 2 },
  { at: 7800, value: 1 },
]

export function useBreathCycle(): BreathCycleController {
  const label = ref('准备…')
  const count = ref('—')

  const timerIds = new Set<ReturnType<typeof setTimeout>>()
  let cycleTimer: ReturnType<typeof setInterval> | null = null
  let stopped = false

  function scheduleTimeout(at: number, callback: () => void): void {
    const id = setTimeout(() => {
      timerIds.delete(id)
      if (!stopped) callback()
    }, at)
    timerIds.add(id)
  }

  function runCycle(): void {
    label.value = '吸气 · 4 秒'
    count.value = String(INHALE_COUNTDOWN[0])
    INHALE_COUNTDOWN.forEach((value, index) => {
      if (index > 0) scheduleTimeout((INHALE_MS / 4) * index, () => {
        count.value = String(value)
      })
    })

    scheduleTimeout(INHALE_MS, () => {
      label.value = '呼气 · 慢慢地'
    })
    for (const step of EXHALE_SCHEDULE) {
      scheduleTimeout(step.at, () => {
        count.value = String(step.value)
      })
    }
  }

  function start(): void {
    if (cycleTimer !== null) return
    stopped = false
    runCycle()
    cycleTimer = setInterval(() => {
      if (!stopped) runCycle()
    }, CYCLE_MS)
  }

  function stop(): void {
    stopped = true
    if (cycleTimer !== null) {
      clearInterval(cycleTimer)
      cycleTimer = null
    }
    for (const id of timerIds) clearTimeout(id)
    timerIds.clear()
  }

  if (getCurrentScope()) onScopeDispose(stop)

  return { label, count, start, stop }
}
