<script setup lang="ts">
import { shallowRef, type CSSProperties } from 'vue'

/**
 * 光尘系统 — 迁移自 ui-prototypes/02-sakura-spring.html 的 makeDust() IIFE。
 *
 * 原型规律（逐项保留）：
 *   - 54 粒光尘，随机生成：位置(0~100%)、尺寸(0.8~3px)、
 *     五种暖色、闪烁周期 --d(2.8~6.8s)、延迟 --delay(0~4s)、峰值透明度 --o(0.35~0.85)；
 *   - 发光：box-shadow 0 0 (size·2)px 同色；
 *   - 闪烁动画由 CSS dustTwinkle 关键帧驱动（非对称脉冲：0→20% rise / 20%→100% decay）。
 *
 * 生命周期：纯 CSS 动画、无 JS 计时器；prefers-reduced-motion 由
 * accessibility.css 全局冻结，组件侧无泄漏来源。
 */

/* 原型常量；移动端降低密度，保留闪烁层和色彩。 */
const DUST_COUNT = typeof window !== 'undefined' && window.innerWidth <= 768 ? 32 : 54
const DUST_COLORS = ['#ffd9e2', '#e6d5f9', '#cdeee6', '#ffe9db', '#ffffff'] as const

interface DustSpec {
  leftPercent: number
  topPercent: number
  size: number
  color: string
  durationSeconds: number
  delaySeconds: number
  peakOpacity: number
}

function createDust(): DustSpec {
  const size = Math.random() * 2.2 + 0.8
  return {
    leftPercent: Math.random() * 100,
    topPercent: Math.random() * 100,
    size,
    color: DUST_COLORS[Math.floor(Math.random() * DUST_COLORS.length)]!,
    durationSeconds: Math.random() * 4 + 2.8,
    delaySeconds: Math.random() * 4,
    peakOpacity: Math.random() * 0.5 + 0.35,
  }
}

const dust = shallowRef<DustSpec[]>(Array.from({ length: DUST_COUNT }, createDust))

function dustStyle(spec: DustSpec): CSSProperties {
  return {
    left: `${spec.leftPercent}%`,
    top: `${spec.topPercent}%`,
    width: `${spec.size}px`,
    height: `${spec.size}px`,
    background: spec.color,
    boxShadow: `0 0 ${spec.size * 2}px ${spec.color}`,
    '--d': `${spec.durationSeconds.toFixed(1)}s`,
    '--delay': `${spec.delaySeconds.toFixed(1)}s`,
    '--o': spec.peakOpacity.toFixed(2),
  }
}
</script>

<template>
  <div id="dust">
    <i v-for="(spec, index) in dust" :key="index" class="dust" :style="dustStyle(spec)" />
  </div>
</template>
