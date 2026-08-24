import { onScopeDispose, ref, type Ref } from 'vue'

import type { MemoryItemContract, ProfileContract } from '@/contracts'

export interface ProfilePresentationController {
  memoryItems: Ref<MemoryItemContract[]>
  removingMemoryIds: Ref<ReadonlySet<string>>
  removeMemory: (id: string) => void
}

/**
 * Profile 的唯一本地交互：Demo Memory 撕除。
 * 不调用 API、不写 localStorage，也不把 Production unavailable 变成可编辑状态。
 */
export function useProfilePresentation(model: ProfileContract): ProfilePresentationController {
  const memoryItems = ref<MemoryItemContract[]>([...model.memory.items])
  const removingMemoryIds = ref<ReadonlySet<string>>(new Set())
  const timers = new Map<string, ReturnType<typeof setTimeout>>()

  function removeMemory(id: string): void {
    if (
      model.state.mode !== 'demo' ||
      model.memory.status !== 'available' ||
      !model.memory.enabled ||
      !model.memory.canDelete ||
      !memoryItems.value.some(item => item.id === id)
    ) {
      return
    }

    if (timers.has(id)) return
    removingMemoryIds.value = new Set([...removingMemoryIds.value, id])
    const timer = setTimeout(() => {
      memoryItems.value = memoryItems.value.filter(item => item.id !== id)
      const next = new Set(removingMemoryIds.value)
      next.delete(id)
      removingMemoryIds.value = next
      timers.delete(id)
    }, 520)
    timers.set(id, timer)
  }

  onScopeDispose(() => {
    for (const timer of timers.values()) clearTimeout(timer)
    timers.clear()
  })

  return { memoryItems, removingMemoryIds, removeMemory }
}
