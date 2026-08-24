import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'

import App from './App.vue'
import WeeklyView from './views/WeeklyView.vue'
import { createUnavailableWeeklyContract } from './data/adapters'
import { weeklyFixture } from './data/fixtures/weekly.fixture'

enableAutoUnmount(afterEach)

describe('Sprint 7 WeeklyView', () => {
  beforeEach(() => {
    window.localStorage.setItem('wl_aurora_onboarded', '1')
  })

  afterEach(() => {
    window.localStorage.clear()
  })

  it('renders the frozen seven-day chart, timeline and insight in Demo', () => {
    const wrapper = mount(WeeklyView, { props: { model: weeklyFixture } })

    expect(wrapper.get('[data-testid="weekly-header"]').text()).toContain('这一周，薇薇的变化')
    expect(wrapper.findAll('.chart-line')).toHaveLength(1)
    expect(wrapper.findAll('.chart-area')).toHaveLength(1)
    expect(wrapper.findAll('.chart-point')).toHaveLength(7)
    expect(wrapper.findAll('.chart-value')).toHaveLength(7)
    expect(wrapper.findAll('.chart-day')).toHaveLength(7)
    expect(wrapper.findAll('[data-testid="weekly-timeline"] .tl-item')).toHaveLength(5)
    expect(wrapper.get('[data-testid="weekly-insight"]').text()).toContain('3 分钟以内')
    expect(wrapper.get('[data-status="skipped"] .tl-tag').text()).toBe('没时间')
  })

  it('shows an empty state without manufacturing history', () => {
    const empty = {
      ...weeklyFixture,
      days: [],
      minutes: [],
      timeline: [],
      insight: { ...weeklyFixture.insight, segments: [], quote: '' },
    }
    const wrapper = mount(WeeklyView, { props: { model: empty } })

    expect(wrapper.get('[data-testid="weekly-chart-empty"]').exists()).toBe(true)
    expect(wrapper.findAll('.chart-point')).toHaveLength(0)
    expect(wrapper.findAll('.chart-line')).toHaveLength(0)
    expect(wrapper.findAll('.chart-area')).toHaveLength(0)
    expect(wrapper.findAll('[data-testid="weekly-timeline"] .tl-item')).toHaveLength(0)
  })

  it('keeps Production unavailable and does not import or display the fixture', () => {
    const production = createUnavailableWeeklyContract()
    const wrapper = mount(WeeklyView, { props: { model: production } })
    const viewSource = readFileSync(join(process.cwd(), 'src', 'views', 'WeeklyView.vue'), 'utf8')

    expect(production.state.mode).toBe('production')
    expect(production.dataAvailability).toBe('unavailable')
    expect(production.state.message).toContain('B5')
    expect(wrapper.get('[data-testid="weekly-unavailable"]').text()).toContain('B5 schema pending')
    expect(wrapper.find('[data-testid="weekly-chart"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('3 分钟以内')
    expect(viewSource).not.toMatch(/data\/fixtures/)
  })

  it('does not duplicate SVG nodes after leaving and re-entering Weekly', async () => {
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
    const wrapper = mount(App)
    await flushPromises()

    await wrapper.get('nav .tab[data-view="weekly"]').trigger('click')
    await wrapper.get('nav .tab[data-view="today"]').trigger('click')
    await wrapper.get('nav .tab[data-view="weekly"]').trigger('click')

    expect(wrapper.findAll('[data-view="weekly"] .chart-point')).toHaveLength(7)
    expect(wrapper.findAll('[data-view="weekly"] .chart-value')).toHaveLength(7)
    expect(wrapper.findAll('[data-view="weekly"] .chart-day')).toHaveLength(7)
  })
})
