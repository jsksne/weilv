<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref } from 'vue'

import type { TodayContract, TodayMoodOption, TodayTimeOption } from '@/contracts'
import { useMotionPulse } from '@/composables/useMotionPulse'
import AvailableTimeSelector from './AvailableTimeSelector.vue'
import MoodSelector from './MoodSelector.vue'

/**
 * 冻结原型「现在的心情」区块（899-919 行）：section-title + .card.mood-card。
 * 组件化只改变代码组织：section 标题、心情选择、时间选择、已计入说明
 * 的 DOM 结构与类名逐字保留。
 *
 * defineExpose(focusCheck)：对应原型 btnCheck 的滚动聚焦——
 * scrollIntoView(center) + check-focus 1.6s 光晕（1700ms 后移除；
 * 先移除类再于 nextTick 加回，等价原型 remove→reflow→add 的动画重播）。
 */
const fallbackMoods: readonly TodayMoodOption[] = [
  { value: 'happy', face: '◕‿◕', label: '还不错' },
  { value: 'calm', face: '˘‿˘', label: '平静' },
  { value: 'tired', face: '>﹏<', label: '有点累' },
  { value: 'low', face: '·︿·', label: '有点低落' },
]
const fallbackTimeOptions: readonly TodayTimeOption[] = [
  { minutes: 10, label: '10 分钟' },
  { minutes: 25, label: '25 分钟' },
  { minutes: 40, label: '40 分钟' },
]

const props = defineProps<{
  model: TodayContract
  mood: string
  availableMinutes: number
}>()

const moods = computed(() => props.model.moods.length ? props.model.moods : fallbackMoods)
const timeOptions = computed(() => props.model.timeOptions.length ? props.model.timeOptions : fallbackTimeOptions)

const emit = defineEmits<{
  'select-mood': [value: string]
  'select-time': [minutes: number]
}>()

const card = ref<HTMLElement | null>(null)
const focusing = ref(false)
const { delay, dispose } = useMotionPulse()

function focusCheck(): void {
  card.value?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  focusing.value = false
  void nextTick(() => {
    focusing.value = true
    delay(1700, () => {
      focusing.value = false
    })
  })
}

onUnmounted(dispose)

defineExpose({ focusCheck })
</script>

<template>
  <div class="section-title">
    <h2>现在的心情</h2>
    <span>心情会轻轻影响推荐</span>
  </div>
  <div ref="card" class="card mood-card" :class="{ 'check-focus': focusing }">
    <MoodSelector
      v-if="moods.length"
      :moods="moods"
      :selected="mood"
      @select="emit('select-mood', $event)"
    />
    <div v-else class="mood-note" data-testid="mood-empty">
      暂时没有可用于推荐的心情信息；微律不会自行推断你的情绪。
    </div>
    <AvailableTimeSelector
      v-if="timeOptions.length"
      :options="timeOptions"
      :selected-minutes="availableMinutes"
      @select="emit('select-time', $event)"
    />
    <div v-else class="mood-note" data-testid="available-time-empty">
      可用时间尚未提供；只有你明确提供后才会用于推荐。
    </div>
    <div v-if="model.moodNoteLead || model.moodNoteLines.length" class="mood-note">
      <b>{{ model.moodNoteLead }}</b>{{ model.moodNoteLines[0] }}<br />{{ model.moodNoteLines[1] }}
    </div>
  </div>
</template>
