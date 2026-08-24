<script setup lang="ts">
import type { PreferenceCardContract } from '@/contracts'

defineProps<{
  model: PreferenceCardContract
}>()
</script>

<template>
  <div class="card p-card" :data-profile-section="model.id">
    <h3>
      <svg class="ic" aria-hidden="true"><use :href="`#i-${model.icon}`" /></svg>
      {{ model.title }}
    </h3>
    <template v-if="model.status === 'available'">
      <div v-for="item in model.items" :key="item.label" class="pref-line">
        <span class="k">{{ item.label }}</span>
        <span class="v" :class="item.tone">{{ item.value }}</span>
      </div>
    </template>
    <p v-else class="consent" data-testid="profile-section-unavailable">
      {{ model.unavailableMessage }}
    </p>
  </div>
</template>
