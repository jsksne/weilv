<script setup lang="ts">
import { watch } from 'vue'

import type { ShellNavigationItem } from '@/contracts'
import BrandLogo from './BrandLogo.vue'
import { useAppNavigation } from '@/composables/useAppNavigation'

const props = withDefaults(defineProps<{
  items: readonly ShellNavigationItem[]
  displayName: string
  dateLabel: string
  activeView?: ShellNavigationItem['id']
}>(), {
  activeView: 'today',
})

const emit = defineEmits<{
  'update:activeView': [ShellNavigationItem['id']]
}>()

const { activeView, gliderStyle, setActiveView, registerTab, recalculateGlider } =
  useAppNavigation(props.activeView)

watch(
  () => props.activeView,
  view => {
    if (view !== activeView.value) setActiveView(view)
  },
)

function activate(view: ShellNavigationItem['id']): void {
  setActiveView(view)
  emit('update:activeView', view)
}

function activateToday(): void {
  activate('today')
}

defineExpose({ activeView, gliderStyle, recalculateGlider })
</script>

<template>
  <nav class="navbar" aria-label="主导航">
    <div class="nav-pill">
      <BrandLogo
        :display-name="displayName"
        tagline="健康微行动 · 个性化建议"
        @activate="activateToday"
      />
      <div class="tabs">
        <div
          id="glider"
          class="tab-glider"
          data-testid="nav-glider"
          :style="{ width: gliderStyle.width, transform: gliderStyle.transform }"
        ></div>
        <button
          v-for="item in items"
          :key="item.id"
          :ref="element => registerTab(item.id, element)"
          class="tab"
          :class="{ active: activeView === item.id }"
          :data-view="item.id"
          type="button"
          @click="activate(item.id)"
        >
          {{ item.label }}
        </button>
      </div>
      <div class="nav-right">
        <span id="navDate" class="nav-date">{{ dateLabel }}</span>
        <button
          class="avatar"
          type="button"
          data-action="open-profile"
          aria-label="打开我的画像"
          @click="activate('profile')"
        >
          {{ displayName.slice(0, 1) }}
        </button>
      </div>
    </div>
  </nav>
</template>
