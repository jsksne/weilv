import { enableAutoUnmount, mount } from '@vue/test-utils'

import ProfileView from './views/ProfileView.vue'
import { adaptProfileResponse } from './data/adapters'
import { profileFixture } from './data/fixtures/profile.fixture'

enableAutoUnmount(afterEach)

describe('Sprint 6 ProfileView', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('renders the four frozen Profile areas and the completion ring', () => {
    const wrapper = mount(ProfileView, { props: { model: profileFixture } })

    expect(wrapper.get('[data-testid="profile-header"]').text()).toContain('薇薇认识的你')
    expect(wrapper.findAll('[data-profile-section]')).toHaveLength(4)
    expect(wrapper.find('[data-testid="completion-ring"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-memory-id]')).toHaveLength(4)
  })

  it('tears a Demo Memory item from local fixture state only', async () => {
    vi.useFakeTimers()
    try {
      const fetchSpy = vi.spyOn(globalThis, 'fetch')
      const wrapper = mount(ProfileView, { props: { model: profileFixture } })
      const item = wrapper.get('[data-memory-id="demo-memory-1"]')

      await item.get('.mem-del').trigger('click')
      expect(item.classes()).toContain('removing')
      expect(window.localStorage.length).toBe(0)
      expect(fetchSpy).not.toHaveBeenCalled()

      await vi.advanceTimersByTimeAsync(520)
      expect(wrapper.find('[data-memory-id="demo-memory-1"]').exists()).toBe(false)
      expect(wrapper.findAll('[data-memory-id]')).toHaveLength(3)
    } finally {
      vi.useRealTimers()
    }
  })

  it('does not render fixture Memory or deletion controls for Production', () => {
    const production = adaptProfileResponse({ user_id: 'production-user', memory_enabled: false })
    const wrapper = mount(ProfileView, { props: { model: production } })

    expect(production.state.mode).toBe('production')
    expect(production.memory.enabled).toBe(false)
    expect(wrapper.findAll('[data-memory-id]')).toHaveLength(0)
    expect(wrapper.get('[data-testid="memory-unavailable"]').text()).toContain('还没有开启记忆功能')
    expect(wrapper.get('[data-testid="profile-header"]').text()).not.toMatch(/Profile|Memory|consent/i)
    expect(wrapper.find('[data-testid="completion-ring"]').exists()).toBe(false)
  })

  it('renders refreshed production memories instead of keeping the first response', async () => {
    const first = adaptProfileResponse(
      { user_id: 'production-user', memory_enabled: true },
      {
        enabled: true,
        consent: 'granted',
        items: [{ id: 'old', icon: 'leaf', lead: '旧记录', text: '旧内容' }],
        canDelete: true,
        notice: '只保留你允许记住的内容。',
      },
    )
    const refreshed = adaptProfileResponse(
      { user_id: 'production-user', memory_enabled: true },
      {
        enabled: true,
        consent: 'granted',
        items: [{ id: 'new', icon: 'leaf', lead: '新记录', text: '新内容' }],
        canDelete: true,
        notice: '只保留你允许记住的内容。',
      },
    )
    const wrapper = mount(ProfileView, { props: { model: first } })

    await wrapper.setProps({ model: refreshed })

    expect(wrapper.find('[data-memory-id="old"]').exists()).toBe(false)
    expect(wrapper.get('[data-memory-id="new"]').text()).toContain('新内容')
  })

  it('defaults missing consent to memory disabled', () => {
    const production = adaptProfileResponse({ user_id: 'missing-consent-user' })

    expect(production.memory.enabled).toBe(false)
    expect(production.memory.consent).toBe('missing')
    expect(production.memory.items).toEqual([])
    expect(production.memory.canDelete).toBe(false)
  })
})
