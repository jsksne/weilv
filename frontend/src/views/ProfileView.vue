<script setup lang="ts">
import { computed, ref } from 'vue'

import CompletionPatternCard from '@/components/profile/CompletionPatternCard.vue'
import MemoryCard from '@/components/profile/MemoryCard.vue'
import PreferenceCard from '@/components/profile/PreferenceCard.vue'
import ProfileHeader from '@/components/profile/ProfileHeader.vue'
import { useProfilePresentation } from '@/composables/useProfilePresentation'
import type { ProfileContract, UiDataSource } from '@/contracts'

const props = defineProps<{
  model: ProfileContract
  dataSource?: UiDataSource
  /** 删除成功后由 App 重新拉取真实 Profile/Memory list。 */
  onRefresh?: () => Promise<void>
}>()

const model = computed(() => props.model)
const presentation = useProfilePresentation(model.value)
const memoryModel = computed(() => ({
  ...model.value.memory,
  items: presentation.memoryItems.value,
}))

const removingIds = ref<ReadonlySet<string>>(new Set())
const deleteError = ref('')
const removingMemoryIds = computed(() =>
  model.value.state.mode === 'demo' ? presentation.removingMemoryIds.value : removingIds.value,
)

/**
 * Production：删除必须由后端 forget_memory 完成；成功（服务器确认）后才刷新
 * 真实列表。失败保留原条目并展示错误，绝不假装删除成功。
 */
async function onRemoveMemory(id: string): Promise<void> {
  if (model.value.state.mode === 'demo') {
    presentation.removeMemory(id)
    return
  }
  if (!props.dataSource?.deleteUserMemory || removingIds.value.has(id)) return
  removingIds.value = new Set([...removingIds.value, id])
  deleteError.value = ''
  try {
    await props.dataSource.deleteUserMemory(id)
    await props.onRefresh?.()
  } catch (cause) {
    deleteError.value = cause instanceof Error ? cause.message : '删除失败，请重试。'
  } finally {
    const next = new Set(removingIds.value)
    next.delete(id)
    removingIds.value = new Set(next)
  }
}
</script>

<template>
  <div class="profile-wrap" data-testid="profile-view">
    <ProfileHeader :model="model.header" />
    <div class="profile-grid stagger">
      <PreferenceCard :model="model.timePreference" />
      <PreferenceCard :model="model.taskPreference" />
      <CompletionPatternCard :model="model.completionPattern" />
      <MemoryCard
        :model="memoryModel"
        :mode="model.state.mode"
        :removing-ids="removingMemoryIds"
        @remove="onRemoveMemory"
      />
    </div>
    <p v-if="deleteError" class="consent" data-testid="memory-delete-error" role="alert">
      {{ deleteError }}
    </p>
  </div>
</template>
