import { flushPromises, mount } from '@vue/test-utils'
import { enableAutoUnmount } from '@vue/test-utils'
import { afterEach, vi } from 'vitest'

import { todayFixture } from './data/fixtures/today.fixture'
import { useDailyTasks } from './composables/useDailyTasks'
import TodayView from './views/TodayView.vue'
import type { TodayContract } from './contracts'

enableAutoUnmount(afterEach)

/* ------------------------------------------------------------------
   F6：完成后一次轻反馈——与完成状态独立保存，不答可离开，
   失败可重试且不影响完成记录。
   ------------------------------------------------------------------ */

function mountToday(submit: ReturnType<typeof vi.fn>) {
  let now = 1_000_000
  const daily = useDailyTasks(todayFixture, { now: () => now })
  const advance = (ms: number) => {
    now += ms
  }
  const wrapper = mount(TodayView, {
    props: { model: todayFixture as TodayContract, daily, submitLightFeedback: submit },
  })
  return { wrapper, daily, advance }
}

describe('F6 完成后一次轻反馈', () => {
  it('完成后显示一次性反馈行；评价保存成功后不再追问', async () => {
    const submit = vi.fn().mockResolvedValue({ status: 'recorded' })
    const { wrapper, daily, advance } = mountToday(submit)

    const card = wrapper.findAll('.task-card')[0]!
    await card.get('[data-act="start"]').trigger('click')
    advance(450)
    await card.get('[data-act="done"]').trigger('click')

    const prompt = wrapper.get('[data-testid="light-feedback"]')
    expect(prompt.text()).toContain('这次感觉怎么样？')

    await prompt.get('[data-feedback="helpful"]').trigger('click')
    await flushPromises()

    expect(submit).toHaveBeenCalledWith(
      expect.objectContaining({ taskId: 'today-task-eye-look-far' }),
      'completed',
      'helpful',
    )
    expect(wrapper.find('[data-testid="light-feedback"]').exists()).toBe(false)
    /* 完成记录不受反馈影响。 */
    expect(daily.completed.value).toBe(1)
  })

  it('反馈保存失败时保留重试入口，完成状态不变', async () => {
    const submit = vi.fn().mockRejectedValue(new Error('offline'))
    const { wrapper, daily, advance } = mountToday(submit)

    const card = wrapper.findAll('.task-card')[0]!
    await card.get('[data-act="start"]').trigger('click')
    advance(450)
    await card.get('[data-act="done"]').trigger('click')
    await wrapper.get('[data-feedback="unhelpful"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="light-feedback"]').text()).toContain('没有记上')
    expect(daily.completed.value).toBe(1)
  })
})
