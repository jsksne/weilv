import { nextTick, onMounted, onUnmounted, ref, type Ref } from 'vue'

import type { ViewId } from '@/contracts'

export interface GliderStyle {
  width: string
  transform: string
}

export interface AppNavigationController {
  activeView: Ref<ViewId>
  gliderStyle: Ref<GliderStyle>
  setActiveView: (view: ViewId) => void
  registerTab: (view: ViewId, element: unknown) => void
  recalculateGlider: (view?: ViewId) => void
}

export function useAppNavigation(initialView: ViewId = 'today'): AppNavigationController {
  const activeView = ref<ViewId>(initialView)
  const gliderStyle = ref<GliderStyle>({ width: '0px', transform: 'translateX(0px)' })
  const tabs = new Map<ViewId, HTMLElement>()
  let disposed = false
  let fonts: FontFaceSet | null = null

  function recalculateGlider(view: ViewId = activeView.value): void {
    const tab = tabs.get(view)
    if (!tab) return

    gliderStyle.value = {
      width: `${tab.offsetWidth}px`,
      transform: `translateX(${tab.offsetLeft - 4}px)`,
    }
  }

  function scheduleRecalculation(): void {
    void nextTick().then(() => {
      if (!disposed) recalculateGlider()
    })
  }

  function setActiveView(view: ViewId): void {
    activeView.value = view
    scheduleRecalculation()
  }

  function registerTab(view: ViewId, element: unknown): void {
    if (element instanceof HTMLElement) {
      tabs.set(view, element)
      if (view === activeView.value) scheduleRecalculation()
    } else {
      tabs.delete(view)
    }
  }

  function handleResize(): void {
    recalculateGlider()
  }

  onMounted(() => {
    window.addEventListener('resize', handleResize)

    if (typeof document !== 'undefined' && document.fonts) {
      fonts = document.fonts
      fonts.addEventListener('loadingdone', handleResize)
      void fonts.ready.then(() => {
        if (!disposed) handleResize()
      })
    }

    scheduleRecalculation()
  })

  onUnmounted(() => {
    disposed = true
    window.removeEventListener('resize', handleResize)
    fonts?.removeEventListener('loadingdone', handleResize)
    fonts = null
    tabs.clear()
  })

  return { activeView, gliderStyle, setActiveView, registerTab, recalculateGlider }
}
