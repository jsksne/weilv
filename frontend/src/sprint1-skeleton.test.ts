import { mount } from '@vue/test-utils'

import AppShell from './layouts/AppShell.vue'
import * as uiContracts from './contracts/ui'
import type { UiMode, ViewId } from './contracts/ui'

describe('Sprint 1 UI skeleton', () => {
  it('can mount AppShell', () => {
    const wrapper = mount(AppShell)

    expect(wrapper.exists()).toBe(true)
    expect(wrapper.classes()).toContain('weilv-app-shell')
  })

  it('renders its default slot content', () => {
    const wrapper = mount(AppShell, {
      slots: {
        default: '<p data-testid="slot-content">slot content</p>',
      },
    })

    expect(wrapper.get('[data-testid="slot-content"]').text()).toBe('slot content')
  })

  it('contains no page controls or main landmark', () => {
    const wrapper = mount(AppShell, {
      slots: {
        default: '<p>slot content</p>',
      },
    })

    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.find('nav').exists()).toBe(false)
    expect(wrapper.find('main').exists()).toBe(false)
  })

  it('can import the UI contract boundary', () => {
    const viewId: ViewId = 'today'
    const uiMode: UiMode = 'production'

    expect(uiContracts).toBeDefined()
    expect(viewId).toBe('today')
    expect(uiMode).toBe('production')
  })
})
