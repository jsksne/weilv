import { onMounted, onUnmounted, ref, type Ref } from 'vue'

export interface DockedProgressController {
  isDocked: Ref<boolean>
}

export function useDockedProgress(progressRow: Ref<HTMLElement | null>): DockedProgressController {
  const isDocked = ref(false)
  let observer: IntersectionObserver | null = null
  let listeningToScroll = false

  function updateFromScroll(): void {
    const row = progressRow.value
    isDocked.value = row ? row.getBoundingClientRect().bottom < 0 : false
  }

  onMounted(() => {
    const row = progressRow.value
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
  })

  onUnmounted(() => {
    observer?.disconnect()
    observer = null
    if (listeningToScroll) window.removeEventListener('scroll', updateFromScroll)
    listeningToScroll = false
  })

  return { isDocked }
}
