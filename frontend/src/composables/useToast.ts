import { ref, shallowReadonly, type Ref } from 'vue'

export interface ToastItem {
  id: string
  message: string
  leaving: boolean
}

export interface ToastController {
  toasts: Readonly<Ref<ToastItem[]>>
  push: (message: string) => string
  dismiss: (id: string) => void
  clear: () => void
}

type TimerHandle = ReturnType<typeof setTimeout>

/**
 * Sprint 4：toast 队列提升为模块级单例。
 *
 * 冻结原型只有唯一的 #toastBox：任意脚本调用 toast() 都进入同一宿主。
 * Sprint 2R 的 useToast 每次调用生成独立队列，ToastHost 与视图代码
 * 无法互通；现将状态收敛到模块级（API 不变），ToastHost 与
 * TodayView 等视图共享同一队列。任意消费作用域销毁时清空待处理计时器，
 * 避免 SPA 内跨页残留。
 */

const toasts = ref<ToastItem[]>([])
const timers = new Map<string, Set<TimerHandle>>()
let sequence = 0

function clearTimers(id: string): void {
  const pending = timers.get(id)
  if (!pending) return
  for (const timer of pending) clearTimeout(timer)
  timers.delete(id)
}

function remove(id: string): void {
  clearTimers(id)
  toasts.value = toasts.value.filter(toast => toast.id !== id)
}

function push(message: string): string {
  const id = `toast-${(sequence += 1)}`
  toasts.value.push({ id, message, leaving: false })
  const pending = new Set<TimerHandle>()
  timers.set(id, pending)

  /* 原型生命周期：2600ms 后加 .out，再 500ms 移除 */
  const exitTimer = setTimeout(() => {
    pending.delete(exitTimer)
    const toast = toasts.value.find(item => item.id === id)
    if (!toast) return
    toast.leaving = true
    const removeTimer = setTimeout(() => remove(id), 500)
    pending.add(removeTimer)
  }, 2600)
  pending.add(exitTimer)
  return id
}

function clear(): void {
  for (const id of [...timers.keys()]) clearTimers(id)
  toasts.value = []
}

export function useToast(): ToastController {
  return { toasts: shallowReadonly(toasts), push, dismiss: remove, clear }
}
