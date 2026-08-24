<script setup lang="ts">
import type {
  OnboardingAnswerValue,
  OnboardingChoiceGroup,
  OnboardingStepContract,
} from '@/contracts'

const props = defineProps<{
  step: OnboardingStepContract
  answers: Readonly<Record<string, OnboardingAnswerValue>>
}>()

const emit = defineEmits<{
  'update-answer': [id: string, value: OnboardingAnswerValue]
}>()

const flowerPetals = [
  { fill: '#ffb7c5', rotate: 0 },
  { fill: '#ffd9e2', rotate: 72 },
  { fill: '#ffb7c5', rotate: 144 },
  { fill: '#e6c9f7', rotate: 216 },
  { fill: '#ffd9e2', rotate: 288 },
]

function selected(group: OnboardingChoiceGroup, value: string): boolean {
  const answer = props.answers[group.id]
  return group.multiple ? Array.isArray(answer) && answer.includes(value) : answer === value
}

function toggle(group: OnboardingChoiceGroup, value: string): void {
  const answer = props.answers[group.id]
  if (group.multiple) {
    const values = Array.isArray(answer) ? [...answer] : []
    const index = values.indexOf(value)
    if (index >= 0) values.splice(index, 1)
    else values.push(value)
    emit('update-answer', group.id, values)
  } else {
    emit('update-answer', group.id, value)
  }
}
</script>

<template>
  <div v-if="step.kind === 'welcome'" class="ob-step s1 active" data-onboarding-step="welcome">
    <svg class="ob-logo" viewBox="0 0 32 32" aria-hidden="true">
      <g fill="none">
        <path
          v-for="petal in flowerPetals"
          :key="petal.rotate"
          d="M16 4 C19 8 19 12 16 15 C13 12 13 8 16 4 Z"
          :fill="petal.fill"
          :transform="`rotate(${petal.rotate} 16 16)`"
        />
        <circle cx="16" cy="16" r="3" fill="#f78fb0" />
      </g>
    </svg>
    <h2>你好，我是<em>微律</em></h2>
    <p class="ob-intro">
      <template v-for="(line, index) in step.intro ?? []" :key="line">
        {{ line }}<br v-if="index < (step.intro?.length ?? 0) - 1" />
      </template>
    </p>
  </div>

  <div v-else-if="step.kind === 'choices'" class="ob-step active" :data-onboarding-step="step.id">
    <h2>{{ step.title }}</h2>
    <div v-for="group in step.groups ?? []" :key="group.id">
      <div class="ob-q">{{ group.prompt }}</div>
      <div class="ob-chips" :data-ob="group.id" :data-multi="group.multiple ? '1' : undefined">
        <button
          v-for="option in group.options"
          :key="option.value"
          class="chip"
          :class="{ on: selected(group, option.value), disabled: option.supported === false }"
          type="button"
          :data-option="option.value"
          :disabled="option.supported === false"
          :title="option.supported === false ? '当前后端不支持该选项' : undefined"
          @click="toggle(group, option.value)"
        >
          {{ option.label }}
        </button>
      </div>
    </div>
  </div>
</template>
