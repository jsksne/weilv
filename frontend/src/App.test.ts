import { flushPromises, mount } from '@vue/test-utils'

import App from './App.vue'
import * as api from './api/client'

describe('App service status', () => {
  it('shows the connected state after a successful health check', async () => {
    vi.spyOn(api, 'healthCheck').mockResolvedValue({ status: 'ok' })

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('服务已连接')
  })

  it('shows a recoverable failure state instead of a blank screen', async () => {
    vi.spyOn(api, 'healthCheck').mockRejectedValue(new api.ApiError(0, '无法连接服务', 'network_error'))

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('微律')
    expect(wrapper.text()).toContain('暂时无法连接服务')
    expect(wrapper.get('button').text()).toBe('重新连接')
  })

  it('runs health check again after clicking reconnect', async () => {
    const health = vi
      .spyOn(api, 'healthCheck')
      .mockRejectedValueOnce(new api.ApiError(0, '无法连接服务', 'network_error'))
      .mockResolvedValueOnce({ status: 'ok' })

    const wrapper = mount(App)
    await flushPromises()
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(health).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('服务已连接')
  })
})
