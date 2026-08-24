/**
 * Sprint 9：Production 用户身份 integration seam。
 *
 * 当前架构没有认证系统；为不引入假用户，这里沿用 uiMode 的显式 env 配置
 * 模式：Production 必须提供 VITE_USER_ID，缺失即配置错误（进入 error 状态，
 * 绝不落入 demo/fixture 用户）。未来接入真实身份提供方时替换本模块即可。
 */
export const USER_ID_ENV_KEY = 'VITE_USER_ID'

export class UserContextConfigurationError extends Error {
  constructor(value: string | undefined) {
    super(
      `${USER_ID_ENV_KEY} must be configured for production; received ${value ?? 'missing'}.`,
    )
    this.name = 'UserContextConfigurationError'
  }
}

export function resolveUserId(value: string | undefined): string {
  const trimmed = value?.trim() ?? ''
  if (!trimmed) throw new UserContextConfigurationError(value)
  return trimmed
}

export function getConfiguredUserId(): string {
  return resolveUserId(import.meta.env.VITE_USER_ID)
}
