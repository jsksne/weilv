import { nextTick } from 'vue'
import { enableAutoUnmount, mount } from '@vue/test-utils'

import AppShell from './layouts/AppShell.vue'
import AppNavigation from './components/shell/AppNavigation.vue'
import BrandLogo from './components/shell/BrandLogo.vue'
import DockedTaskProgress from './components/shell/DockedTaskProgress.vue'
import IconSprite from './components/shell/IconSprite.vue'
import PrototypeReplayControl from './components/shell/PrototypeReplayControl.vue'
import ToastHost from './components/shell/ToastHost.vue'
import { shellFixture } from './data/fixtures/shell.fixture'

enableAutoUnmount(afterEach)

describe('Sprint 2R navigation', () => {
  it('defaults to today and changes active state on tab click', async () => {
    const wrapper = mount(AppNavigation, {
      props: {
        items: shellFixture.navigation,
        displayName: shellFixture.displayName,
        dateLabel: shellFixture.dateLabel,
      },
    })

    expect(wrapper.get('[data-view="today"]').classes()).toContain('active')
    await wrapper.get('[data-view="assistant"]').trigger('click')

    expect(wrapper.get('[data-view="today"]').classes()).not.toContain('active')
    expect(wrapper.get('[data-view="assistant"]').classes()).toContain('active')
    expect(wrapper.emitted('update:activeView')?.at(-1)).toEqual(['assistant'])
  })

  it('calculates the glider from tab width and offset after resize', async () => {
    const wrapper = mount(AppNavigation, {
      props: {
        items: shellFixture.navigation,
        displayName: shellFixture.displayName,
        dateLabel: shellFixture.dateLabel,
      },
    })
    const todayTab = wrapper.get('[data-view="today"]').element
    Object.defineProperty(todayTab, 'offsetWidth', { configurable: true, value: 92 })
    Object.defineProperty(todayTab, 'offsetLeft', { configurable: true, value: 12 })

    window.dispatchEvent(new Event('resize'))
    await nextTick()

    const gliderStyle = wrapper.get('[data-testid="nav-glider"]').attributes('style') ?? ''
    expect(gliderStyle).toContain('width: 92px')
    expect(gliderStyle).toContain('translateX(8px)')
  })

  it('cleans resize listeners when navigation unmounts', () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    const wrapper = mount(AppNavigation, {
      props: {
        items: shellFixture.navigation,
        displayName: shellFixture.displayName,
        dateLabel: shellFixture.dateLabel,
      },
    })

    wrapper.unmount()

    expect(removeSpy.mock.calls.some(([event]) => event === 'resize')).toBe(true)
  })
})

describe('Sprint 2R brand and icon shell', () => {
  it('keeps the frozen BrandLogo SVG structure and emits its activate event', async () => {
    const wrapper = mount(BrandLogo, {
      props: {
        displayName: shellFixture.displayName,
        tagline: '春日极光 · 健康同伴',
      },
    })

    expect(wrapper.find('.logo-flower').exists()).toBe(true)
    expect(wrapper.findAll('.logo-flower path')).toHaveLength(5)
    expect(wrapper.text()).toContain('微律')
    expect(wrapper.text()).toContain('春日极光 · 健康同伴')

    await wrapper.get('.logo').trigger('click')
    expect(wrapper.emitted('activate')).toHaveLength(1)
  })

  it('renders the six frozen prototype SVG symbols without an icon library', () => {
    const wrapper = mount(IconSprite)
    const ids = wrapper.findAll('symbol').map(symbol => symbol.attributes('id'))

    expect(wrapper.find('svg[aria-hidden="true"]').exists()).toBe(true)
    expect(ids).toEqual(['i-flower', 'i-moon', 'i-clock', 'i-leaf', 'i-target', 'i-book'])
  })

  it('keeps PrototypeReplayControl as a minimal shell replay event', async () => {
    const wrapper = mount(PrototypeReplayControl)

    await wrapper.get('.proto-tag').trigger('click')

    expect(wrapper.emitted('replay')).toHaveLength(1)
  })
})

describe('Sprint 2R docked progress', () => {
  it('observes the progress row, docks when hidden, and disconnects on unmount', async () => {
    let observeTarget: Element | null = null
    type FakeIntersectionEntry = Pick<IntersectionObserverEntry, 'isIntersecting' | 'boundingClientRect'>
    let intersectionCallback: ((entries: FakeIntersectionEntry[]) => void) | null = null
    const disconnect = vi.fn()

    class FakeIntersectionObserver {
      constructor(callback: (entries: FakeIntersectionEntry[]) => void) {
        intersectionCallback = callback
      }

      observe(target: Element): void {
        observeTarget = target
      }

      disconnect(): void {
        disconnect()
      }
    }

    vi.stubGlobal('IntersectionObserver', FakeIntersectionObserver)
    const wrapper = mount(DockedTaskProgress, {
      props: { progress: shellFixture.progress },
    })

    expect(observeTarget).toBe(wrapper.get('[data-testid="progress-row"]').element)
    intersectionCallback?.([
      { isIntersecting: true, boundingClientRect: { bottom: 600 } as DOMRect },
    ])
    await nextTick()
    expect(document.body.classList.contains('tb-dock')).toBe(false)

    intersectionCallback?.([
      { isIntersecting: false, boundingClientRect: { bottom: 600 } as DOMRect },
    ])
    await nextTick()
    expect(document.body.classList.contains('tb-dock')).toBe(false)

    intersectionCallback?.([
      { isIntersecting: false, boundingClientRect: { bottom: -1 } as DOMRect },
    ])
    await nextTick()
    expect(document.body.classList.contains('tb-dock')).toBe(true)
    expect(wrapper.get('[data-testid="docked-progress"]').attributes('aria-hidden')).toBe('false')

    wrapper.unmount()
    expect(disconnect).toHaveBeenCalledOnce()
    expect(document.body.classList.contains('tb-dock')).toBe(false)
  })

  it('uses a scroll-position fallback when IntersectionObserver is unavailable', async () => {
    vi.stubGlobal('IntersectionObserver', undefined)
    const getBoundingClientRect = vi
      .spyOn(HTMLElement.prototype, 'getBoundingClientRect')
      .mockReturnValue({ bottom: 1 } as DOMRect)

    const wrapper = mount(DockedTaskProgress, {
      props: { progress: shellFixture.progress },
    })
    await nextTick()

    expect(document.body.classList.contains('tb-dock')).toBe(false)
    getBoundingClientRect.mockReturnValue({ bottom: -1 } as DOMRect)
    window.dispatchEvent(new Event('scroll'))
    await nextTick()
    expect(document.body.classList.contains('tb-dock')).toBe(true)
    wrapper.unmount()
  })
})

describe('Sprint 2R toast lifecycle', () => {
  it('queues a toast and removes it after the prototype in/out lifecycle', async () => {
    vi.useFakeTimers()
    const wrapper = mount(ToastHost)

    wrapper.vm.push(shellFixture.toastExample.message)
    await nextTick()
    expect(wrapper.findAll('.toast')).toHaveLength(1)
    expect(wrapper.find('.toast').text()).toBe(shellFixture.toastExample.message)

    vi.advanceTimersByTime(2600)
    await nextTick()
    expect(wrapper.find('.toast').classes()).toContain('out')
    vi.advanceTimersByTime(500)
    await nextTick()
    expect(wrapper.find('.toast').exists()).toBe(false)

    wrapper.unmount()
    vi.useRealTimers()
  })

  it('cleans pending toast timers when the host unmounts', () => {
    vi.useFakeTimers()
    const clearTimeoutSpy = vi.spyOn(globalThis, 'clearTimeout')
    const wrapper = mount(ToastHost)

    wrapper.vm.push('待清理')
    wrapper.unmount()

    expect(clearTimeoutSpy).toHaveBeenCalled()
    vi.useRealTimers()
  })
})

describe('Sprint 2R AppShell view switching', () => {
  it('switches between the four named slots without affecting legacy mode', async () => {
    const scrollSpy = vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
    const wrapper = mount(AppShell, {
      props: { shell: shellFixture },
      slots: {
        today: '<p data-testid="today-view">Today shell slot</p>',
        assistant: '<p data-testid="assistant-view">Assistant shell slot</p>',
        profile: '<p data-testid="profile-view">Profile shell slot</p>',
        weekly: '<p data-testid="weekly-view">Weekly shell slot</p>',
      },
    })

    await wrapper.get('[data-view="assistant"]').trigger('click')

    expect(wrapper.get('[data-testid="assistant-view"]').isVisible()).toBe(true)
    expect(wrapper.get('[data-testid="today-view"]').isVisible()).toBe(false)
    expect(wrapper.get('#view-assistant').classes()).toContain('active')
    expect(wrapper.get('#view-today').classes()).not.toContain('active')
    expect(scrollSpy).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' })
  })
})
