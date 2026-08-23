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
</script>

<template>
  <div class="section-title" style="margin-top: 26px">
    <h2>{{ model.tasksSectionTitle }}</h2>
    <span>{{ model.tasksSectionNote }}</span>
  </div>
  <div class="task-list">
    <TaskCard
      v-for="entry in controller.entries.value"
      :key="entry.slotId"
      :entry="entry"
      :controller="controller"
      :copy="model.feedbackCopy"
    />
  </div>
</template>
