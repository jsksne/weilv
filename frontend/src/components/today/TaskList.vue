<script setup lang="ts">
import type { TodayContract } from '@/contracts'
import type { DailyTasksController } from '@/composables/useDailyTasks'
import TaskCard from './TaskCard.vue'

/**
 * 冻结原型（921-922 行）：section-title「今日微任务」+ .task-list 三卡列表。
 */
defineProps<{
  model: TodayContract
  controller: DailyTasksController
}>()

const emit = defineEmits<{
  'open-panel': [entry: import('@/composables/useDailyTasks').DailyTaskEntry]
  unsuitable: [entry: import('@/composables/useDailyTasks').DailyTaskEntry]
}>()
</script>

<template>
  <div class="section-title" style="margin-top: 26px">
    <h2>{{ model.tasksSectionTitle }}</h2>
    <span>{{ model.tasksSectionNote }}</span>
  </div>
  <div class="task-list">
    <div v-if="!controller.entries.value.length" class="card task-card" data-testid="today-task-empty">
      <h3 class="task-name">今天暂时没有可展示的安全任务</h3>
      <p class="task-desc">{{ model.state.message || '稍后可以重试；这里不会用演示任务填充。' }}</p>
    </div>
    <TaskCard
      v-for="entry in controller.entries.value"
      :key="entry.slotId"
      :entry="entry"
      :controller="controller"
      :copy="model.feedbackCopy"
      :can-replace="model.availability.replace === 'available' && model.replacePool.length > 0"
      @open-panel="emit('open-panel', $event)"
      @unsuitable="emit('unsuitable', $event)"
    />
  </div>
</template>
