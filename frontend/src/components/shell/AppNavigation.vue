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
        tagline="春日极光 · 健康同伴"
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
        <div class="avatar" aria-hidden="true">{{ displayName.slice(0, 1) }}</div>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.navbar {
  position: sticky;
  top: 14px;
  z-index: 50;
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 20px;
  transition: top 0.55s cubic-bezier(0.16, 1, 0.3, 1);
}

:global(body.tb-dock) .navbar {
  top: 54px;
}

.nav-pill {
  display: flex;
  align-items: center;
  gap: 18px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.85);
  outline: 1px solid rgba(255, 183, 197, 0.35);
  border-radius: 999px;
  padding: 9px 12px 9px 20px;
  box-shadow: 0 10px 34px rgba(247, 143, 176, 0.18);
}

.tabs {
  position: relative;
  display: flex;
  gap: 4px;
  margin-left: 6px;
  background: rgba(255, 219, 228, 0.4);
  padding: 4px;
  border-radius: 999px;
}

.tab-glider {
  position: absolute;
  z-index: 0;
  top: 4px;
  left: 0;
  height: calc(100% - 8px);
  border-radius: 999px;
  background: linear-gradient(100deg, #ffa8bd 0%, #f78fb0 42%, #b9a7ea 100%);
  box-shadow: 0 4px 18px rgba(169, 156, 224, 0.4);
  transition: transform 0.55s cubic-bezier(0.16, 1, 0.3, 1),
    width 0.55s cubic-bezier(0.16, 1, 0.3, 1);
}

.tab {
  border: none;
  background: none;
  cursor: pointer;
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 13.5px;
  color: #765f70;
  padding: 7px 16px;
  border-radius: 999px;
  transition: color 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
  z-index: 1;
}

.tab:hover {
  color: #f27ba4;
}

.tab.active {
  color: #fff;
  font-weight: 500;
  text-shadow: 0 1px 6px rgba(180, 90, 130, 0.25);
}

.nav-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-date {
  font-size: 11.5px;
  color: #9b8495;
  letter-spacing: 1px;
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, #ffd9e2, #c9a7eb);
  display: grid;
  place-items: center;
  font-size: 13px;
  cursor: pointer;
  border: 2px solid #fff;
  box-shadow: 0 4px 12px rgba(247, 143, 176, 0.3);
  transition: transform 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}

.avatar:hover {
  transform: scale(1.1) rotate(-6deg);
}

@media (max-width: 960px) {
  .nav-pill {
    flex-wrap: wrap;
    border-radius: 26px;
  }

  .tabs {
    order: 3;
    width: 100%;
    justify-content: space-between;
  }
}
</style>
