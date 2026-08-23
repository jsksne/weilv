import { onMounted, onUnmounted, ref, watch, type Ref } from 'vue'

export interface DockedProgressController {
  isDocked: Ref<boolean>
}

/**
 * Sprint 4：哨兵元素可响应式替换。
 *
 * 原型 onScroll 每次查询 `.view.active .progress-row` 的位置；
 * Vue 版本通过 sentinel ref 观察 hero 进度行元素，元素替换
 * （视图重挂）时自动重绑观察。
 */
/** prop 可选时 toRef 产生 undefined；sentinel 缺位等同未观察（null） */
export function useDockedProgress(
  sentinel: Ref<HTMLElement | null | undefined>,
): DockedProgressController {
  const isDocked = ref(false)
  let observer: IntersectionObserver | null = null
  let listeningToScroll = false

  function detach(): void {
    observer?.disconnect()
    observer = null
    if (listeningToScroll) window.removeEventListener('scroll', updateFromScroll)
    listeningToScroll = false
  }

  function updateFromScroll(): void {
    const row = sentinel.value
    isDocked.value = row ? row.getBoundingClientRect().bottom < 0 : false
  }

  function attach(): void {
    const row = sentinel.value
    if (!row) return

    if (typeof IntersectionObserver !== 'undefined') {
      observer = new IntersectionObserver(entries => {
        const entry = entries[0]
        if (entry) {
          isDocked.value = !entry.isIntersecting && entry.boundingClientRect.bottom < 0
        }
      })
      observer.observe(row)
      return
    }

    listeningToScroll = true
    window.addEventListener('scroll', updateFromScroll, { passive: true })
    updateFromScroll()
  }

  watch(sentinel, (next, previous) => {
    if (next === previous) return
    detach()
    isDocked.value = false
    attach()
  })

  onMounted(attach)

  onUnmounted(() => {
    detach()
    isDocked.value = false
  })

  return { isDocked }
}
