import { getCurrentScope, onScopeDispose, ref, type Ref } from 'vue'

/**
 * 非对称脉冲运动系统（WL）的 Vue 工程化迁移。
 *
 * 原型来源：ui-prototypes/02-sakura-spring.html 交互脚本头部：
 *   WL.rise(t)  = t^3                     （上升段：easeInCubic 先慢后快）
 *   WL.decay(t) = exp(-4.5 * t)           （衰减段：RC 放电式指数长尾）
 *   WL.pulse(t) = 0..0.2 rise / 0.2..1 decay
 *   WL.play(duration, onUpdate, onDone)   （RAF 逐帧驱动）
 *
 * 工程化增强（不改变运动曲线本身）：
 *   - play 返回 cancel 句柄，可中途取消；
 *   - 所有 RAF / timeout 由 composable 统一登记，组件卸载（scope dispose）
 *     时自动清理，杜绝生命周期泄漏；
 *   - prefers-reduced-motion 生效时 play 主动降级：跳过逐帧动画，
 *     直接以终值回调一次并同步完成（Sprint 2 无障碍要求）。
 */

export type MotionPulseUpdate = (value: number, progress: number) => void

export interface MotionPulse {
  /** 缓动数学（与原型逐字等价），导出便于单测 */
  rise: (t: number) => number
  decay: (t: number) => number
  pulse: (t: number) => number
  /** 当前环境是否偏好减少动效（响应式，随系统设置变化） */
  reducedMotion: Ref<boolean>
  /** 逐帧播放一次脉冲；返回取消函数 */
  play: (durationMs: number, onUpdate: MotionPulseUpdate, onDone?: () => void) => () => void
  /** 登记式 requestAnimationFrame（卸载时自动取消），返回取消函数 */
  nextFrame: (callback: (timestamp: number) => void) => () => void
  /** 登记式 setTimeout（卸载时自动清除），返回取消函数 */
  delay: (ms: number, callback: () => void) => () => void
  /** 立即取消本实例登记的全部动画 / 帧回调 / 定时器（幂等） */
  dispose: () => void
}

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)'

function queryReducedMotion(): MediaQueryList | null {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return null
  return window.matchMedia(REDUCED_MOTION_QUERY)
}

export function useMotionPulse(): MotionPulse {
  const media = queryReducedMotion()
  const reducedMotion = ref(media?.matches ?? false)

  const rise = (t: number): number => t * t * t
  const decay = (t: number): number => Math.exp(-4.5 * t)
  function pulse(t: number): number {
    if (t <= 0) return 0
    if (t < 0.2) return rise(t / 0.2)
    return decay((t - 0.2) / 0.8)
  }

  const cancels = new Set<() => void>()

  function play(
    durationMs: number,
    onUpdate: MotionPulseUpdate,
    onDone?: () => void,
  ): () => void {
    if (reducedMotion.value) {
      onUpdate(pulse(1), 1)
      onDone?.()
      return () => {}
    }
    let rafId = 0
    let cancelled = false
    const cancel = () => {
      if (cancelled) return
      cancelled = true
      cancels.delete(cancel)
      if (rafId !== 0 && typeof window !== 'undefined') window.cancelAnimationFrame(rafId)
    }
    cancels.add(cancel)
    const frame = (timestamp: number) => {
      if (cancelled) return
      const t = Math.min((timestamp - startedAt) / durationMs, 1)
      onUpdate(pulse(t), t)
      if (t < 1) rafId = window.requestAnimationFrame(frame)
      else {
        cancel()
        onDone?.()
      }
    }
    const startedAt = performance.now()
    frame(startedAt)
    return cancel
  }

  function nextFrame(callback: (timestamp: number) => void): () => void {
    let rafId = 0
    let cancelled = false
    const cancel = () => {
      if (cancelled) return
      cancelled = true
      cancels.delete(cancel)
      if (rafId !== 0 && typeof window !== 'undefined') window.cancelAnimationFrame(rafId)
    }
    cancels.add(cancel)
    rafId = window.requestAnimationFrame((timestamp) => {
      if (cancelled) return
      cancels.delete(cancel)
      callback(timestamp)
    })
    return cancel
  }

  function delay(ms: number, callback: () => void): () => void {
    let cancelled = false
    const cancel = () => {
      if (cancelled) return
      cancelled = true
      cancels.delete(cancel)
      clearTimeout(timerId)
    }
    cancels.add(cancel)
    const timerId = setTimeout(() => {
      if (cancelled) return
      cancels.delete(cancel)
      callback()
    }, ms)
    return cancel
  }

  function dispose(): void {
    for (const cancel of [...cancels]) cancel()
    cancels.clear()
  }

  const onMediaChange = (event: MediaQueryListEvent): void => {
    reducedMotion.value = event.matches
    if (event.matches) dispose()
  }
  media?.addEventListener('change', onMediaChange)

  if (getCurrentScope()) {
    onScopeDispose(() => {
      dispose()
      media?.removeEventListener('change', onMediaChange)
    })
  }

  return { rise, decay, pulse, reducedMotion, play, nextFrame, delay, dispose }
}
