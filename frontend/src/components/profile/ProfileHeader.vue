<script setup lang="ts">
import type { ProfileHeaderContract } from '@/contracts'

defineProps<{
  model: ProfileHeaderContract
}>()
</script>

<template>
  <div class="profile-head" data-testid="profile-header">
    <h2>{{ model.title }}</h2>
    <p>{{ model.description }}</p>
  </div>
</template>
