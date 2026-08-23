import { flushPromises, mount } from '@vue/test-utils'

import App from './App.vue'
import { ApiError } from './api/client'
import * as api from './api/client'
import { useUserProfile } from './composables/useUserProfile'

const savedProfile = {
  user_id: 'demo-user-001',
  target_stage: 'senior_high' as const,
  memory_enabled: true,
  created_at: '2026-08-15T10:00:00+08:00',
  updated_at: '2026-08-15T10:00:00+08:00',
}

describe('useUserProfile', () => {
  it('keeps memory disabled and reports a missing clean-demo profile', async () => {
    vi.spyOn(api, 'getUserProfile').mockRejectedValue(
      new ApiError(404, '请求未能完成', 'profile_not_found'),
    )
    const profile = useUserProfile()

    await profile.load()

    expect(profile.status.value).toBe('missing')
    expect(profile.form.memory_enabled).toBe(false)
  })

  it('saves only the explicit profile choices through the existing API', async () => {
    const upsert = vi.spyOn(api, 'upsertUserProfile').mockResolvedValue(savedProfile)
    const profile = useUserProfile()
    profile.updateField('target_stage', 'senior_high')
    profile.updateField('memory_enabled', true)

    await profile.save()

    expect(upsert).toHaveBeenCalledWith('demo-user-001', {
      target_stage: 'senior_high',
      memory_enabled: true,
    })
    expect(profile.status.value).toBe('saved')
  })
})

describe('Profile consent web flow', () => {
  it('shows missing state, saves explicit consent, and syncs recommendation identity', async () => {
    vi.spyOn(api, 'healthCheck').mockResolvedValue({ status: 'ok' })
    vi.spyOn(api, 'getUserProfile').mockRejectedValue(
      new ApiError(404, '请求未能完成', 'profile_not_found'),
    )
    const upsert = vi.spyOn(api, 'upsertUserProfile').mockResolvedValue(savedProfile)
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('尚未保存用户设置')
    expect(wrapper.get('input[name="memory_enabled"]').element.checked).toBe(false)

    await wrapper.get('select[name="profile_target_stage"]').setValue('senior_high')
    await wrapper.get('input[name="memory_enabled"]').setValue(true)
    await wrapper.get('[data-action="save-profile"]').trigger('click')
    await flushPromises()

    expect(upsert).toHaveBeenCalledWith('demo-user-001', {
      target_stage: 'senior_high',
      memory_enabled: true,
    })
    expect(wrapper.get('select[name="target_stage"]').element.value).toBe('senior_high')
    expect(wrapper.text()).toContain('用户设置已保存')
  })
})
