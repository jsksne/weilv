<script setup lang="ts">
import { computed } from 'vue'

import CompletionPatternCard from '@/components/profile/CompletionPatternCard.vue'
import MemoryCard from '@/components/profile/MemoryCard.vue'
import PreferenceCard from '@/components/profile/PreferenceCard.vue'
import ProfileHeader from '@/components/profile/ProfileHeader.vue'
import { useProfilePresentation } from '@/composables/useProfilePresentation'
import type { ProfileContract } from '@/contracts'

const props = defineProps<{
  model: ProfileContract
}>()

const model = computed(() => props.model)
const presentation = useProfilePresentation(model.value)
const memoryModel = computed(() => ({
  ...model.value.memory,
  items: presentation.memoryItems.value,
}))
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
        :removing-ids="presentation.removingMemoryIds.value"
        @remove="presentation.removeMemory"
      />
    </div>
  </div>
</template>
