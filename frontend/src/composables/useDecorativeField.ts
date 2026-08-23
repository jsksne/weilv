import { getCurrentScope, onScopeDispose, ref, type Ref } from 'vue'

/**
 * 装饰粒子场（花瓣 / 光尘等）的生命周期基础设施。
 *
 * 原型来源：ui-prototypes/02-sakura-spring.html 的 petals() RAF 循环：
 *   dt = Math.min((now - last) / 1000, 0.05)  —— 帧间隔上限 50ms
 *   t  = now / 1000                            —— 用于 S 曲线横漂 / 呼吸缩放
 *
 * 工程化增强（不改变运动规律）：
 *   - startLoop 返回停止函数；组件卸载（scope dispose）自动停止全部循环；
 *   - prefers-reduced-motion 生效时不启动循环，运行途中系统切换到
 *     reduce 也会立即停止（Sprint 2 要求 JS 侧主动降级，而非仅 CSS 冻结）。
 */

export type DecorativeLoopCallback = (deltaSeconds: number, elapsedSeconds: number) => void

export interface DecorativeField {
  /** 当前环境是否偏好减少动效（响应式，随系统设置变化） */
  reducedMotion: Ref<boolean>
  /**
   * 启动逐帧循环（deltaSeconds 已按原型钳制到 ≤ 0.05s）。
   * reduce 环境下不启动，直接返回空操作句柄。
   */
  startLoop: (callback: DecorativeLoopCallback) => () => void
}

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)'

function queryReducedMotion(): MediaQueryList | null {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return null
  return window.matchMedia(REDUCED_MOTION_QUERY)
}

export function useDecorativeField(): DecorativeField {
  const media = queryReducedMotion()
  const reducedMotion = ref(media?.matches ?? false)

  const stops = new Set<() => void>()

  function startLoop(callback: DecorativeLoopCallback): () => void {
    if (reducedMotion.value) return () => {}
    let rafId = 0
    let stopped = false
    let last = performance.now()
    const stop = () => {
      if (stopped) return
      stopped = true
      stops.delete(stop)
      if (rafId !== 0 && typeof window !== 'undefined') window.cancelAnimationFrame(rafId)
    }
    stops.add(stop)
    const tick = (now: number): void => {
      if (stopped) return
      const deltaSeconds = Math.min((now - last) / 1000, 0.05)
      last = now
      callback(deltaSeconds, now / 1000)
      if (!stopped) rafId = window.requestAnimationFrame(tick)
    }
    rafId = window.requestAnimationFrame(tick)
    return stop
  }

  function stopAll(): void {
    for (const stop of [...stops]) stop()
    stops.clear()
  }

  const onMediaChange = (event: MediaQueryListEvent): void => {
    reducedMotion.value = event.matches
    if (event.matches) stopAll()
  }
  media?.addEventListener('change', onMediaChange)

  if (getCurrentScope()) {
    onScopeDispose(() => {
      stopAll()
      media?.removeEventListener('change', onMediaChange)
    })
  }

  return { reducedMotion, startLoop }
}
