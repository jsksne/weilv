<script setup lang="ts">
import type {
  CompletionStatus,
  Difficulty,
  Usefulness,
} from '@/api/types'
import type { FeedbackDraft } from '@/composables/useFeedbackFlow'

const props = defineProps<{
  input: FeedbackDraft
  loading: boolean
}>()

defineEmits<{
  change: [field: keyof FeedbackDraft, value: FeedbackDraft[keyof FeedbackDraft]]
  submit: []
}>()

function completionValue(event: Event): CompletionStatus {
  return (event.target as HTMLSelectElement).value as CompletionStatus
}

function usefulnessValue(event: Event): Usefulness {
  return (event.target as HTMLInputElement).value as Usefulness
}

function difficultyValue(event: Event): Difficulty {
  return (event.target as HTMLSelectElement).value as Difficulty
}

function reasonValue(event: Event): string {
  return (event.target as HTMLInputElement).value
}
</script>

<template>
  <form data-testid="feedback-form" @submit.prevent="$emit('submit')">
    <h3>这个建议有帮助吗？</h3>

    <label>
      完成情况
      <select
        :value="props.input.completion_status"
        name="completion_status"
        @change="$emit('change', 'completion_status', completionValue($event))"
      >
        <option value="completed">完成了</option>
        <option value="partially_completed">部分完成</option>
        <option value="skipped">没做</option>
      </select>
    </label>

    <fieldset class="usefulness-options">
      <legend>对你的帮助</legend>
      <label>
        <input
          :checked="props.input.usefulness === 'helpful'"
          name="usefulness"
          type="radio"
          value="helpful"
          @change="$emit('change', 'usefulness', usefulnessValue($event))"
        />
        👍 有帮助
      </label>
      <label>
        <input
          :checked="props.input.usefulness === 'neutral'"
          name="usefulness"
          type="radio"
          value="neutral"
          @change="$emit('change', 'usefulness', usefulnessValue($event))"
        />
        😐 一般
      </label>
      <label>
        <input
          :checked="props.input.usefulness === 'not_helpful'"
          name="usefulness"
          type="radio"
          value="not_helpful"
          @change="$emit('change', 'usefulness', usefulnessValue($event))"
        />
        👎 不适合
      </label>
    </fieldset>

    <label>
      难度如何
      <select
        :value="props.input.difficulty"
        name="difficulty"
        @change="$emit('change', 'difficulty', difficultyValue($event))"
      >
        <option value="easy">很轻松</option>
        <option value="suitable">刚刚好</option>
        <option value="difficult">有点难</option>
      </select>
    </label>

    <label>
      想说的话（可选）
      <input
        :value="props.input.reason"
        name="reason"
        maxlength="100"
        type="text"
        placeholder="简单说说原因，比如：当时不太方便……"
        @input="$emit('change', 'reason', reasonValue($event))"
      />
    </label>

    <p v-if="loading" aria-live="polite">正在记录……</p>
    <button data-action="feedback-submit" type="submit" :disabled="loading">
      提交反馈
    </button>
  </form>
</template>
