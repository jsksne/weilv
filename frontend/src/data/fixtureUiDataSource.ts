import type { UiDataBundle, UiDataSource } from '@/contracts'
import { assistantFixture } from '@/data/fixtures/assistant.fixture'
import { onboardingFixture } from '@/data/fixtures/onboarding.fixture'
import { profileFixture } from '@/data/fixtures/profile.fixture'
import { shellFixture } from '@/data/fixtures/shell.fixture'
import { todayFixture } from '@/data/fixtures/today.fixture'
import { weeklyFixture } from '@/data/fixtures/weekly.fixture'

function scenarioFor(question: string): keyof typeof assistantFixture.replies {
  const normalized = question.toLowerCase()
  if (normalized.includes('睡') || normalized.includes('sleep')) return 'sleep'
  if (normalized.includes('脖') || normalized.includes('颈') || normalized.includes('neck')) return 'neck'
  if (normalized.includes('考') || normalized.includes('exam')) return 'exam'
  return 'fallback'
}

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
    return Promise.resolve(assistantFixture.replies[scenarioFor(question)])
  }
}
