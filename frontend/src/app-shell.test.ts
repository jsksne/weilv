import { enableAutoUnmount, mount } from '@vue/test-utils'

import AppShell from './layouts/AppShell.vue'

enableAutoUnmount(afterEach)

describe('Sprint 2R AppShell contract', () => {
  it('renders the default legacy slot without forcing new shell pages', () => {
    const wrapper = mount(AppShell, {
      slots: {
        default: '<form data-testid="legacy-form"><button type="submit">旧业务</button></form>',
      },
    })

    expect(wrapper.get('[data-testid="legacy-form"]').exists()).toBe(true)
    expect(wrapper.find('[data-view]').exists()).toBe(false)
    expect(wrapper.find('nav').exists()).toBe(false)
  })

  it('renders each named view slot in shell test mode', () => {
    const wrapper = mount(AppShell, {
      slots: {
        today: '<p data-testid="today-view">Today shell slot</p>',
        assistant: '<p data-testid="assistant-view">Assistant shell slot</p>',
        profile: '<p data-testid="profile-view">Profile shell slot</p>',
        weekly: '<p data-testid="weekly-view">Weekly shell slot</p>',
      },
    })

    expect(wrapper.get('[data-testid="today-view"]').text()).toBe('Today shell slot')
    expect(wrapper.get('[data-testid="assistant-view"]').text()).toBe('Assistant shell slot')
    expect(wrapper.get('[data-testid="profile-view"]').text()).toBe('Profile shell slot')
    expect(wrapper.get('[data-testid="weekly-view"]').text()).toBe('Weekly shell slot')
  })
})
