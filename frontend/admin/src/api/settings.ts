/**
 * 系统设置接口封装（04 §4.12，system:settings）。
 */
import request from './request'

export interface SystemSettings {
  platformName: string
  platformDescription?: string | null
  logoUrl?: string | null
  defaultAvatarUrl?: string | null
}

export function fetchSettings(): Promise<SystemSettings> {
  return request.get('/settings')
}

export function saveSettings(payload: SystemSettings): Promise<{ success: boolean }> {
  return request.put('/settings', payload)
}

/** 上传图片（jpg/png ≤2MB）→ { url }（存 MinIO） */
export function uploadSettingImage(file: File, type: 'logo' | 'defaultAvatar'): Promise<{ url: string }> {
  const form = new FormData()
  form.append('file', file)
  form.append('type', type)
  return request.post('/settings/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
