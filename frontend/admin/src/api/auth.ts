/**
 * 管理端认证接口封装（04 §4.1）：登录 / 登出 / 当前管理员+权限码。
 * 其余系统接口（/users* /roles* /logs* /settings*）待功能开发按契约补齐。
 */
import request from './request'

export interface AdminUserBrief {
  id: number
  username: string
  nickname: string // 派生值（=username，04 §4.1）
  avatarUrl?: string | null
  roleName: string
  isSuper: boolean
}

export interface LoginResult {
  accessToken: string
  refreshToken: string
  expiresIn: number // access 有效期（秒）
  user: AdminUserBrief
}

export interface ProfileResult {
  user: AdminUserBrief
  permissionCodes: string[]
}

/** POST /auth/login 后台登录（游客｜频控） */
export function login(payload: {
  username: string
  password: string
  rememberMe?: boolean
}): Promise<LoginResult> {
  return request.post('/auth/login', payload)
}

/** POST /auth/logout 登出（refresh 立即失效） */
export function logout(refreshToken?: string): Promise<{ success: boolean }> {
  return request.post('/auth/logout', { refreshToken: refreshToken ?? null })
}

/** GET /auth/profile 当前管理员 + 权限码集合（超管全量 33 码） */
export function fetchProfile(): Promise<ProfileResult> {
  return request.get('/auth/profile')
}
