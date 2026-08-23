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

    const width = `${tab.offsetWidth}px`
    const transform = `translateX(${tab.offsetLeft - 4}px)`
    /* 值未变化时不赋新对象：函数 ref 每次 patch 都会重新调用 registerTab，
       若每次 recalc 都触发重渲染会形成「重渲染→ref→recalc→重渲染」的
       无限 nextTick 微任务链，饿死宏任务（setTimeout/rAF 永不执行） */
    if (gliderStyle.value.width === width && gliderStyle.value.transform === transform) return
    gliderStyle.value = { width, transform }
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
      /* Vue 对函数 ref 会在每次 patch 时重新调用；同一元素重复注册
         不再重新调度，避免与重渲染互相触发形成无限更新链 */
      const unchanged = tabs.get(view) === element
      tabs.set(view, element)
      if (view === activeView.value && !unchanged) scheduleRecalculation()
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
