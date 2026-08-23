import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

import { enableAutoUnmount, mount } from '@vue/test-utils'

import AppShell from './layouts/AppShell.vue'
import { shellFixture } from './data/fixtures/shell.fixture'

const appShellPath = join(process.cwd(), 'src', 'layouts', 'AppShell.vue')
const shellComponentDir = join(process.cwd(), 'src', 'components', 'shell')
const shellComponentFiles = readdirSync(shellComponentDir)
  .filter(file => file.endsWith('.vue'))
  .map(file => join(shellComponentDir, file))

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
      props: { shell: shellFixture },
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

  it('keeps shell runtime files independent from fixture data', () => {
    const fixtureImports = [appShellPath, ...shellComponentFiles].flatMap(file => {
      const source = readFileSync(file, 'utf8')
      return source.match(/from\s+['"][^'"]*data\/fixtures[^'"]*['"]/g) ?? []
    })

    expect(fixtureImports).toEqual([])
  })

  it('uses active view classes instead of v-show inline-style selectors', () => {
    const source = readFileSync(appShellPath, 'utf8')

    expect(source).toMatch(/\.view\.active\s*\{\s*display:\s*block/)
    expect(source).not.toMatch(/\.view\[style\*/)
  })

  it('renders an unavailable structural shell when named slots have no data', () => {
    const wrapper = mount(AppShell, {
      slots: { today: '<p data-testid="today-view">Today shell slot</p>' },
    })

    expect(wrapper.find('nav').exists()).toBe(true)
    expect(wrapper.get('[data-view="today"]').exists()).toBe(true)
  })
})
