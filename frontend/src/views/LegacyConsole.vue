<script setup lang="ts">
import { computed, onMounted } from 'vue'

import FeedbackForm from '@/components/FeedbackForm.vue'
import FeedbackResult from '@/components/FeedbackResult.vue'
import ColdStartQuestionnaire from '@/components/ColdStartQuestionnaire.vue'
import RecommendationForm from '@/components/RecommendationForm.vue'
import RecommendationResult from '@/components/RecommendationResult.vue'
import SafetyResult from '@/components/SafetyResult.vue'
import ServiceStatus from '@/components/ServiceStatus.vue'
import UserProfileSettings from '@/components/UserProfileSettings.vue'
import { useFeedbackFlow } from '@/composables/useFeedbackFlow'
import { useQuestionnaire } from '@/composables/useQuestionnaire'
import { useRecommendationFlow } from '@/composables/useRecommendationFlow'
import { useServiceHealth } from '@/composables/useServiceHealth'
import { useUserProfile } from '@/composables/useUserProfile'
import type { UserProfile } from '@/api/types'

/**
 * Sprint 4：App.vue 切换为 Shell 运行态后，legacy 表单流
 * （Sprint 0 的 API 驱动界面）原样保留在本组件，经 ?legacy=1 访问，
 * 作为可回滚 backup 与既有 flow 测试的挂载点（Sprint 9 移除）。
 */

const { loading: serviceLoading, connected, refresh } = useServiceHealth()
const profile = useUserProfile()
const questionnaire = useQuestionnaire()
const {
  form,
  loading: recommendationLoading,
  result,
  error,
  submittedRequest,
  updateField,
  submit: submitRecommendation,
  reset: resetRecommendation,
} = useRecommendationFlow()

const {
  input: feedbackInput,
  loading: feedbackLoading,
  result: feedbackResult,
  error: feedbackError,
  updateField: updateFeedbackField,
  submit: submitFeedback,
  reset: resetFeedback,
} = useFeedbackFlow()

const showQuestionnaire = computed(() => {
  if (profile.status.value !== 'saved') return false
  return ['active', 'loading', 'error'].includes(questionnaire.status.value)
})

function syncRecommendationIdentity(saved: UserProfile | null): void {
  if (!saved) return
  updateField('user_id', saved.user_id)
  updateField('target_stage', saved.target_stage)
}

onMounted(async () => {
  const saved = await profile.load()
  if (saved) await questionnaire.load(saved.user_id)
})

const feedbackEligible = computed(
  () =>
    result.value?.status === 'allowed' &&
    result.value.feedback_available &&
    result.value.recommendation_id !== null &&
    submittedRequest.value !== null,
)

async function requestRecommendation(): Promise<void> {
  resetFeedback()
  await submitRecommendation()
}

function resetAll(): void {
  resetRecommendation()
  resetFeedback()
}

async function recordFeedback(): Promise<void> {
  if (!feedbackEligible.value || !result.value?.recommendation_id || !submittedRequest.value) {
    return
  }
  await submitFeedback(submittedRequest.value.user_id, result.value.recommendation_id)
}

async function saveProfile(): Promise<void> {
  syncRecommendationIdentity(await profile.save())
  await questionnaire.load(profile.form.user_id)
}
</script>

<template>
  <main>
    <h1>微律</h1>
    <p>以微小行动，找到每个人更适合自己的健康节律。</p>
    <ServiceStatus :loading="serviceLoading" :connected="connected" @refresh="refresh" />

    <UserProfileSettings
      :form="profile.form"
      :status="profile.status.value"
      @change="profile.updateField"
      @save="saveProfile"
    />

    <ColdStartQuestionnaire
      v-if="showQuestionnaire"
      :flow="questionnaire"
      :user-id="profile.form.user_id"
    />

    <RecommendationForm
      :form="form"
      :loading="recommendationLoading"
      @change="updateField"
      @submit="requestRecommendation"
      @reset="resetAll"
    />

    <section v-if="error" role="alert">
      <p>暂时无法获取微任务，请稍后重试。</p>
      <button data-action="retry" type="button" @click="requestRecommendation">重试</button>
    </section>

    <template v-else-if="result?.status === 'allowed' && result.selected_task">
      <RecommendationResult :result="result" />

      <section v-if="feedbackEligible">
        <FeedbackResult v-if="feedbackResult" :result="feedbackResult" />
        <template v-else>
          <FeedbackForm
            :input="feedbackInput"
            :loading="feedbackLoading"
            @change="updateFeedbackField"
            @submit="recordFeedback"
          />
          <div v-if="feedbackError" role="alert">
            <p>反馈暂时没有提交成功，请重试。</p>
            <button
              data-action="feedback-retry"
              type="button"
              :disabled="feedbackLoading"
              @click="recordFeedback"
            >
              重试
            </button>
          </div>
        </template>
      </section>
    </template>

    <SafetyResult
      v-else-if="result && result.status !== 'allowed'"
      :result="result"
      @reset="resetAll"
    />
  </main>
</template>
