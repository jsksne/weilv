<script setup lang="ts">
import { computed, ref } from 'vue'

import type { QuestionnaireAnswerValue, QuestionnaireOption } from '@/api/types'
import type { useQuestionnaire } from '@/composables/useQuestionnaire'

const props = defineProps<{
  flow: ReturnType<typeof useQuestionnaire>
  userId: string
}>()

const confirming = ref(false)

const questions = computed(() => props.flow.questions.value)
const current = computed(() => props.flow.question.value)
const currentAnswered = computed(() =>
  current.value ? isSelected(current.value.question_id) : false,
)

function isSelected(questionId: string, value?: string): boolean {
  const answer = props.flow.answers[questionId]
  if (value === undefined) {
    if (Array.isArray(answer)) return answer.length > 0
    return answer !== undefined && answer !== ''
  }
  if (Array.isArray(answer)) return answer.includes(value)
  return answer === value
}

function toggleOption(questionId: string, option: QuestionnaireOption): void {
  const definition = questions.value.find((item) => item.question_id === questionId)
  if (!definition) return
  if (definition.option_type === 'single') {
    props.flow.setAnswer(questionId, option.value)
    return
  }
  const currentValues = (props.flow.answers[questionId] as string[] | undefined) ?? []
  let nextValues: string[]
  if (option.value === 'none') {
    nextValues = currentValues.includes('none') ? [] : ['none']
  } else if (currentValues.includes(option.value)) {
    nextValues = currentValues.filter((value) => value !== option.value && value !== 'none')
  } else {
    nextValues = [...currentValues.filter((value) => value !== 'none'), option.value]
  }
  props.flow.setAnswer(questionId, nextValues)
}

function labelFor(questionId: string, value: string): string {
  const definition = questions.value.find((item) => item.question_id === questionId)
  return definition?.options.find((option) => option.value === value)?.label ?? value
}

function summaryItems(): Array<{ questionId: string; label: string }> {
  return questions.value
    .filter((item) => isSelected(item.question_id))
    .map((item) => {
      const answer = props.flow.answers[item.question_id] as QuestionnaireAnswerValue
      const label = Array.isArray(answer)
        ? answer.map((value) => labelFor(item.question_id, value)).join('、')
        : labelFor(item.question_id, answer)
      return { questionId: item.question_id, label }
    })
}

function onNext(): void {
  if (props.flow.isLast.value) {
    confirming.value = true
    return
  }
  props.flow.next()
}
</script>

<template>
  <section data-testid="questionnaire" class="questionnaire">
    <template v-if="flow.status.value === 'loading'">
      <p aria-live="polite">正在准备几个小问题……</p>
    </template>

    <template v-else-if="flow.status.value === 'error'">
      <p role="alert">暂时无法读取问卷，可以稍后再来，不影响使用推荐功能。</p>
      <div class="actions">
        <button data-action="questionnaire-retry" type="button" @click="flow.load(userId)">
          重试
        </button>
        <button data-action="questionnaire-skip" type="button" @click="flow.skip(userId)">
          跳过问卷
        </button>
      </div>
    </template>

    <template v-else-if="flow.status.value === 'active'">
      <div class="questionnaire-head">
        <p class="questionnaire-hint">先认识一下你的日常习惯，推荐会更合拍～</p>
        <button data-action="questionnaire-skip" type="button" @click="flow.skip(userId)">
          跳过问卷
        </button>
      </div>

      <div
        class="questionnaire-progress"
        role="progressbar"
        :aria-valuenow="flow.progress.value"
        aria-valuemin="0"
        aria-valuemax="100"
      >
        <div class="questionnaire-progress-fill" :style="{ width: `${flow.progress.value}%` }" />
      </div>

      <template v-if="confirming">
        <h2>先确认一下，再开始为你推荐～</h2>
        <ul class="questionnaire-summary">
          <li v-for="item in summaryItems()" :key="item.questionId">
            <span class="questionnaire-summary-question">
              {{ questions.find((q) => q.question_id === item.questionId)?.title }}
            </span>
            <span class="questionnaire-summary-answer">{{ item.label }}</span>
          </li>
        </ul>
        <div class="actions">
          <button data-action="questionnaire-revise" type="button" @click="confirming = false">
            返回修改
          </button>
          <button
            data-action="questionnaire-finish"
            type="button"
            :disabled="flow.saving.value"
            @click="flow.finish(userId)"
          >
            {{ flow.saving.value ? '正在保存……' : '保存并开始使用' }}
          </button>
        </div>
      </template>

      <template v-else-if="current">
        <p class="questionnaire-count">第 {{ flow.index.value + 1 }} / {{ flow.total.value }} 题</p>
        <h2>{{ current.title }}</h2>
        <p v-if="current.description" class="questionnaire-description">{{ current.description }}</p>

        <fieldset class="questionnaire-options">
          <label
            v-for="option in current.options"
            :key="option.value"
            class="questionnaire-option"
            :class="{ selected: isSelected(current.question_id, option.value) }"
          >
            <input
              :name="current.question_id"
              :type="current.option_type === 'multi' ? 'checkbox' : 'radio'"
              :value="option.value"
              :checked="isSelected(current.question_id, option.value)"
              @change="toggleOption(current.question_id, option)"
            />
            <span>{{ option.label }}</span>
          </label>
        </fieldset>

        <div class="actions">
          <button
            v-if="flow.index.value > 0"
            data-action="questionnaire-back"
            type="button"
            @click="flow.back()"
          >
            上一步
          </button>
          <button
            data-action="questionnaire-next"
            type="button"
            :disabled="current.required && !currentAnswered"
            @click="onNext"
          >
            {{ flow.isLast.value ? '完成' : '下一步' }}
          </button>
        </div>
      </template>
    </template>
  </section>
</template>
