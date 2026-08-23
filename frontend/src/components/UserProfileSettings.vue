<script setup lang="ts">
import type { UserProfileDraft, UserProfileStatus } from '@/composables/useUserProfile'

const props = defineProps<{
  form: UserProfileDraft
  status: UserProfileStatus
}>()

defineEmits<{
  change: [field: keyof UserProfileDraft, value: UserProfileDraft[keyof UserProfileDraft]]
  save: []
}>()

function textValue(event: Event): string {
  return (event.target as HTMLInputElement).value
}

function checkedValue(event: Event): boolean {
  return (event.target as HTMLInputElement).checked
}
</script>

<template>
  <section data-testid="profile-settings">
    <h2>演示用户设置</h2>
    <label>
      用户 ID
      <input
        :value="props.form.user_id"
        name="profile_user_id"
        required
        @input="$emit('change', 'user_id', textValue($event).trim())"
      />
    </label>
    <label>
      学段
      <select
        :value="props.form.target_stage"
        name="profile_target_stage"
        @change="$emit('change', 'target_stage', textValue($event))"
      >
        <option value="primary_upper">小学高年级</option>
        <option value="junior_high">初中</option>
        <option value="senior_high">高中</option>
      </select>
    </label>
    <label>
      <input
        :checked="props.form.memory_enabled"
        name="memory_enabled"
        type="checkbox"
        @change="$emit('change', 'memory_enabled', checkedValue($event))"
      />
      启用个性化记忆
    </label>
    <p v-if="status === 'loading'" aria-live="polite">正在读取用户设置……</p>
    <p v-else-if="status === 'missing'">尚未保存用户设置</p>
    <p v-else-if="status === 'saved'">用户设置已保存</p>
    <p v-else-if="status === 'error'" role="alert">用户设置暂时无法读取或保存</p>
    <button
      data-action="save-profile"
      type="button"
      :disabled="status === 'loading'"
      @click="$emit('save')"
    >
      保存设置
    </button>
  </section>
</template>
