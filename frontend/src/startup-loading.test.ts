import { flushPromises, mount } from '@vue/test-utils'

import StartupLoading from './components/StartupLoading.vue'
import { useUiDataSource } from './composables/useUiDataSource'
import type { UiDataSource } from './contracts'
import { FixtureUiDataSource } from './data/fixtureUiDataSource'

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function sourceWithToday(getToday: UiDataSource['getToday']): UiDataSource {
  const fixture = new FixtureUiDataSource()
  return {
    getShell: () => fixture.getShell(),
    getToday,
    getAssistant: () => fixture.getAssistant(),
    getProfile: () => fixture.getProfile(),
    getOnboarding: () => fixture.getOnboarding(),
    getWeekly: () => fixture.getWeekly(),
    askAssistant: question => fixture.askAssistant(question),
  }
}

describe('startup data progress', () => {
  it('reports resolved requests and exposes onboarding before the slow Today request', async () => {
    const fixture = new FixtureUiDataSource()
    const today = deferred<Awaited<ReturnType<UiDataSource['getToday']>>>()
    const ui = useUiDataSource(sourceWithToday(() => today.promise), { autoLoad: false })

    const first = ui.load()
    const duplicate = ui.load()
    expect(duplicate).toBe(first)
    await flushPromises()

    expect(ui.status.value).toBe('loading')
    expect(ui.progress.value).toMatchObject({ completed: 5, total: 6, percent: 83 })
    expect(ui.onboarding.value).toEqual(await fixture.getOnboarding())

    today.resolve(await fixture.getToday())
    await first

    expect(ui.status.value).toBe('ready')
    expect(ui.progress.value).toEqual({
      completed: 6,
      total: 6,
      percent: 100,
      stage: '准备好了',
    })
  })

  it('keeps resolved progress on failure and resets it before retrying', async () => {
    const fixture = new FixtureUiDataSource()
    const retryToday = deferred<Awaited<ReturnType<UiDataSource['getToday']>>>()
    const getToday = vi
      .fn<UiDataSource['getToday']>()
      .mockRejectedValueOnce(new Error('today down'))
      .mockImplementationOnce(() => retryToday.promise)
    const ui = useUiDataSource(sourceWithToday(getToday), { autoLoad: false })

    await ui.load()
    expect(ui.status.value).toBe('error')
    expect(ui.progress.value.percent).toBeLessThan(100)

    const retry = ui.retry()
    expect(ui.progress.value).toMatchObject({ completed: 0, percent: 0 })
    retryToday.resolve(await fixture.getToday())
    await retry

    expect(ui.status.value).toBe('ready')
    expect(ui.progress.value.percent).toBe(100)
  })

  it('waits for an active load before starting an explicit reload', async () => {
    const fixture = new FixtureUiDataSource()
    const firstToday = deferred<Awaited<ReturnType<UiDataSource['getToday']>>>()
    const getToday = vi
      .fn<UiDataSource['getToday']>()
      .mockImplementationOnce(() => firstToday.promise)
      .mockImplementation(() => fixture.getToday())
    const source = sourceWithToday(getToday)
    const shellSpy = vi.spyOn(source, 'getShell')
    const ui = useUiDataSource(source, { autoLoad: false })

    const initial = ui.load()
    const reload = ui.reload()
    expect(shellSpy).toHaveBeenCalledTimes(1)

    firstToday.resolve(await fixture.getToday())
    await initial
    await reload

    expect(shellSpy).toHaveBeenCalledTimes(2)
    expect(ui.status.value).toBe('ready')
  })
})

describe('StartupLoading', () => {
  it('announces the real stage and progress values', () => {
    const wrapper = mount(StartupLoading, {
      props: {
        progress: { completed: 3, total: 6, percent: 50, stage: '读取你的状态' },
      },
    })

    expect(wrapper.get('[role="progressbar"]').attributes()).toMatchObject({
      'aria-valuemin': '0',
      'aria-valuemax': '100',
      'aria-valuenow': '50',
    })
    expect(wrapper.text()).toContain('读取你的状态')
    expect(wrapper.text()).toContain('3 / 6')
    expect(wrapper.text()).toContain('50%')
  })
})
