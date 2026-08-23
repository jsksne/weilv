import { reactive, ref } from 'vue'

import { ApiError, getUserProfile, upsertUserProfile } from '@/api/client'
import type { TargetStage, UserProfile } from '@/api/types'

export interface UserProfileDraft {
  user_id: string
  target_stage: TargetStage
  memory_enabled: boolean
}

export type UserProfileStatus = 'idle' | 'loading' | 'missing' | 'saved' | 'error'

export function useUserProfile() {
  const form = reactive<UserProfileDraft>({
    user_id: 'demo-user-001',
    target_stage: 'junior_high',
    memory_enabled: false,
  })
  const status = ref<UserProfileStatus>('idle')
  const error = ref<ApiError | null>(null)

  function applyProfile(profile: UserProfile): UserProfile {
    Object.assign(form, {
      user_id: profile.user_id,
      target_stage: profile.target_stage,
      memory_enabled: profile.memory_enabled,
    })
    status.value = 'saved'
    return profile
  }

  async function load(): Promise<UserProfile | null> {
    status.value = 'loading'
    error.value = null
    try {
      return applyProfile(await getUserProfile(form.user_id))
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 404) {
        form.memory_enabled = false
        status.value = 'missing'
        return null
      }
      error.value =
        cause instanceof ApiError ? cause : new ApiError(0, '无法连接服务', 'network_error')
      status.value = 'error'
      return null
    }
  }

  async function save(): Promise<UserProfile | null> {
    status.value = 'loading'
    error.value = null
    try {
      return applyProfile(
        await upsertUserProfile(form.user_id, {
          target_stage: form.target_stage,
          memory_enabled: form.memory_enabled,
        }),
      )
    } catch (cause) {
      error.value =
        cause instanceof ApiError ? cause : new ApiError(0, '无法连接服务', 'network_error')
      status.value = 'error'
      return null
    }
  }

  function updateField<K extends keyof UserProfileDraft>(
    field: K,
    value: UserProfileDraft[K],
  ): void {
    form[field] = value
  }

  return { form, status, error, load, save, updateField }
}
