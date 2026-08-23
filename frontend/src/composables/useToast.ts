import { onScopeDispose, ref, shallowReadonly, type Ref } from 'vue'

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

export function useToast(): ToastController {
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
    const id = `toast-${sequence += 1}`
    toasts.value.push({ id, message, leaving: false })
    const pending = new Set<TimerHandle>()
    timers.set(id, pending)

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

  onScopeDispose(clear)

  return { toasts: shallowReadonly(toasts), push, dismiss: remove, clear }
}
