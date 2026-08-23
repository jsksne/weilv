<script setup lang="ts">
import DustField from './DustField.vue'
import PetalField from './PetalField.vue'

/**
 * 统一背景层 — 结构逐字对应 ui-prototypes/02-sakura-spring.html：
 *   <div class="bg" aria-hidden="true">
 *     blobs(b1~b4) + bg-grid + petalField + dust + bg-noise
 *   </div>
 *
 * 样式见 styles/aurora.css（blobs / 网格 / 噪点为纯 CSS 动画，
 * 花瓣与光尘分别由 PetalField / DustField 组件生成）。
 * 整层 pointer-events: none，不参与交互。
 */
</script>

<template>
  <div class="bg" aria-hidden="true">
    <div class="blob b1"></div>
    <div class="blob b2"></div>
    <div class="blob b3"></div>
    <div class="blob b4"></div>
    <div class="bg-grid"></div>
    <PetalField />
    <DustField />
    <div class="bg-noise"></div>
  </div>
</template>
