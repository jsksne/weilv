# Sprint 6 Migration Record

## Profile Header

Prototype: `ui-prototypes/02-sakura-spring.html`
HTML selector: `#view-profile .profile-head`
Original behavior: 展示“薇薇认识的你”标题和说明文字；进入 Profile 时以页面头部的 stagger 视觉出现，不提供成绩排名语义。
Vue component: `frontend/src/components/profile/ProfileHeader.vue`
Contract dependency: `ProfileContract.header`
Test coverage: `profile-view.test.ts` 验证标题和说明可见。

## Preference cards

Prototype: `ui-prototypes/02-sakura-spring.html`
HTML selector: `#view-profile .profile-grid .p-card:nth-child(1-2)`
Original behavior: 两张卡片分别展示时间偏好和任务偏好，每行有 label/value，并通过 up/down 色调区分偏好趋势；Production 没有统计字段时显示 unavailable。
Vue component: `PreferenceCard.vue`
Contract dependency: `ProfileContract.timePreference` / `ProfileContract.taskPreference`
Test coverage: `profile-view.test.ts` 验证四个 Profile 区域挂载；`profile-contract-validation.test.ts` 验证 Production 偏好 unavailable。

## Completion Ring

Prototype: `ui-prototypes/02-sakura-spring.html`
HTML selector: `#view-profile .stat-ring .ring-box`
Original behavior: 92% 圆环从 0 逐步绘制，中心数字同步增长；动画使用 RAF，页面卸载时不得留下 RAF。
Vue component: `CompletionPatternCard.vue` + `CompletionRing.vue`
Contract dependency: `ProfileContract.completionPattern`
Test coverage: `profile-view.test.ts` 验证 Demo 圆环；既有 `visual-system.test.ts` 验证 `useMotionPulse` 生命周期清理；Production 无完成率时不渲染圆环。

## Memory cards

Prototype: `ui-prototypes/02-sakura-spring.html`
HTML selector: `#view-profile .mem-list .mem-item`
Original behavior: Demo 展示四条记忆；点击 × 后卡片向右撕除、淡出并收起。该演示动作只修改本地 fixture state，不调用 Memory API；无 consent 或 Production 缺少接口时不展示模拟 Memory。
Vue component: `MemoryCard.vue` + `MemoryList.vue` + `MemoryItem.vue`
Contract dependency: `ProfileContract.memory`
Test coverage: `profile-view.test.ts` 验证本地撕除、零 fetch、Production 无 fixture Memory 和 missing consent；`profile-contract-validation.test.ts` 验证 `memory_enabled=false` 不产生列表/删除能力。

## Onboarding five-step flow

Prototype: `ui-prototypes/02-sakura-spring.html`
HTML selector: `#onboard`, `#obDots`, `.ob-step`, `#obNext`, `#obPrev`, `#obSkip`
Original behavior: 五步 Demo flow 展示欢迎、基础画像、主要问题、行为偏好和生成画像；支持单选/多选、Next、Back、Skip、生成动画和完成后的摘要；原型完成状态只写 `wl_aurora_onboarded`。
Vue component: `OnboardingFlow.vue` + `OnboardingProgress.vue` + `OnboardingStep.vue` + `ProfileGenerationStage.vue`
Contract dependency: `OnboardingContract.steps`, `initialAnswers`, `summary`, `questionnaireCompatibility`
Test coverage: `onboarding-flow.test.ts` 验证五步进退、Skip、Replay-ready completion、生成摘要、localStorage 边界、zero fetch；`profile-contract-validation.test.ts` 验证当前 Questionnaire mismatch/unavailable。
