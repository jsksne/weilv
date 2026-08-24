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

  getWeekly() {
    return Promise.resolve(weeklyFixture)
  }

  askAssistant(question: string) {
    void question
    return Promise.resolve(assistantFixture.replies.fallback)
  }
}
