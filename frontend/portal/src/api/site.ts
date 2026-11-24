/**
 * 平台公开配置接口封装（04 §3.2 GET /settings/public，游客，两端共用）。
 * 管理端「系统设置」保存后由此同步到学员端页面（名称/描述/Logo/默认头像）。
 */
import request from './request'

export interface PublicSettings {
  platformName: string
  platformDescription?: string | null
  logoUrl?: string | null
  defaultAvatarUrl?: string | null
}

export function fetchPublicSettings(): Promise<PublicSettings> {
  return request.get('/settings/public')
}
