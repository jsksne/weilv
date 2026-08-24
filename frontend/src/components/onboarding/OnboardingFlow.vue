<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { useMotionPulse } from '@/composables/useMotionPulse'
import { useOnboarding } from '@/composables/useOnboarding'
import type { OnboardingContract } from '@/contracts'

import OnboardingProgress from './OnboardingProgress.vue'
import OnboardingStep from './OnboardingStep.vue'
import ProfileGenerationStage from './ProfileGenerationStage.vue'

const props = withDefaults(defineProps<{
  model: OnboardingContract
  open?: boolean
}>(), {
  open: true,
})

const emit = defineEmits<{
  complete: [status: 'completed' | 'skipped']
}>()

const flow = useOnboarding(props.model)
const open = ref(props.open)
const closing = ref(false)
const { delay } = useMotionPulse()

const currentNumber = computed(() => flow.index.value + 1)
const nextLabel = computed(() =>
  flow.isLast.value ? '进入微律' : flow.isFirst.value ? '开始认识你' : '下一步',
)
const mismatchMessage = computed(() => props.model.questionnaireCompatibility.message)

watch(() => props.open, value => {
  open.value = value
})

function finish(status: 'completed' | 'skipped'): void {
  if (closing.value) return
  closing.value = true
  if (status === 'completed') flow.complete()
  else flow.skip()
  emit('complete', status)
  delay(850, () => {
    open.value = false
  })
}

function next(): void {
  if (flow.isLast.value) finish('completed')
  else flow.next()
}

function skip(): void {
  finish('skipped')
}
</script>

<template>
  <div
    v-if="open && model.totalSteps > 0"
    class="onboard"
    :class="{ hide: closing }"
    data-testid="onboarding"
    role="dialog"
    aria-modal="true"
    aria-label="首次使用引导"
  >
    <div class="ob-card">
      <OnboardingProgress :current="currentNumber" :total="flow.total.value" />

      <OnboardingStep
        v-if="flow.currentStep.value?.kind !== 'generation' && flow.currentStep.value"
        :step="flow.currentStep.value"
        :answers="flow.answers"
        @update-answer="flow.setAnswer"
      />
      <ProfileGenerationStage
        v-else-if="flow.currentStep.value"
        :active="flow.currentStep.value.kind === 'generation'"
        :summary="model.summary"
      />

      <div class="ob-actions">
        <button
          v-if="!flow.isFirst.value"
          class="btn btn-ghost"
          type="button"
          data-action="onboarding-back"
          @click="flow.back"
        >
          上一步
        </button>
        <button class="btn btn-primary" type="button" data-action="onboarding-next" @click="next">
          {{ nextLabel }}
        </button>
      </div>
      <button class="ob-skip" type="button" data-action="onboarding-skip" @click="skip">
        跳过，先随便看看
      </button>
      <p class="ob-skip" data-testid="questionnaire-contract-status">{{ mismatchMessage }}</p>
    </div>
  </div>
</template>
