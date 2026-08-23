<script setup lang="ts">
/**
 * AI 存在感：呼吸极光球 + 环绕花瓣 — 结构与描参数值逐字对应
 * ui-prototypes/02-sakura-spring.html「问问薇薇」ask-hero 内的 .orb 节点。
 *
 * 动画（纯 CSS，见 styles/assistant.css + animations.css）：
 *   - orb-core：orbBreath 6s 非对称脉冲（scale 1 → 1.2）
 *   - orb-ring：orbSpin 14s / 22s 反向虚线旋转，花瓣点缀于轨道顶点
 */
</script>

<template>
  <div class="orb">
    <div class="orb-ring">
      <span class="op">
        <svg width="14" height="14" viewBox="0 0 40 40">
          <path d="M20 2 C31 8 33 20 20 38 C7 20 9 8 20 2 Z" fill="#ffb7c5" opacity="0.9" />
        </svg>
      </span>
    </div>
    <div class="orb-ring r2">
      <span class="op">
        <svg width="12" height="12" viewBox="0 0 40 40">
          <path d="M20 2 C31 8 33 20 20 38 C7 20 9 8 20 2 Z" fill="#bfe8dd" opacity="0.9" />
        </svg>
      </span>
    </div>
    <div class="orb-core"></div>
  </div>
</template>
