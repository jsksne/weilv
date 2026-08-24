import type { UiDataBundle, UiDataSource } from '@/contracts'
import { assistantFixture } from '@/data/fixtures/assistant.fixture'
import { onboardingFixture } from '@/data/fixtures/onboarding.fixture'
import { profileFixture } from '@/data/fixtures/profile.fixture'
import { shellFixture } from '@/data/fixtures/shell.fixture'
import { todayFixture } from '@/data/fixtures/today.fixture'
import { weeklyFixture } from '@/data/fixtures/weekly.fixture'

export class FixtureUiDataSource implements UiDataSource {
  getInitialData(): UiDataBundle {
    return {
      shell: shellFixture,
      today: todayFixture,
      assistant: assistantFixture,
      profile: profileFixture,
      onboarding: onboardingFixture,
      weekly: weeklyFixture,
    }
  }

  getShell() {
    return Promise.resolve(shellFixture)
  }

  getToday() {
    return Promise.resolve(todayFixture)
  }

  getAssistant() {
    return Promise.resolve(assistantFixture)
  }

  getProfile() {
    return Promise.resolve(profileFixture)
  }

  getOnboarding() {
    return Promise.resolve(onboardingFixture)
  }

  /** Demo 引导只存在本地；提交是本地 no-op，绝不调用真实 API。 */
  submitOnboarding() {
    return Promise.resolve({
      status: 'completed' as const,
      persistence: [],
    })
  }

  /** Demo 任务动作是本地状态，不写 B2 事件。 */
  submitTaskAction() {
    return Promise.resolve({ status: 'demo_local' })
  }

  /** Demo 使用 fixture Memory，不读 B4 API。 */
  getUserMemories() {
    return Promise.resolve({
      enabled: profileFixture.memory.enabled,
      consent: profileFixture.memory.consent,
      items: profileFixture.memory.items,
      canDelete: profileFixture.memory.canDelete,
      notice: profileFixture.memory.notice,
    })
  }

  /** Demo 撕除只影响本地 fixture 状态，不调 B4 delete。 */
  deleteUserMemory() {
    return Promise.resolve({ status: 'demo_local' })
  }

  getWeekly() {
    return Promise.resolve(weeklyFixture)
  }

  askAssistant(question: string) {
    void question
    return Promise.resolve(assistantFixture.replies.fallback)
  }
}
