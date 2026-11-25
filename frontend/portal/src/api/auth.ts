/**
 * accounts 接口封装（04 §3.1 #1-#10 + /profile/stats）。
 * 注册即登录（S3）；登录响应 user.isAdmin 为后台账号标识（Q4）。
 */
import request from './request'

import type { DateTimeString } from '@shared/types/api'

export interface AuthUser {
  id: number
  nickname: string
  avatarUrl?: string | null
  isAdmin?: boolean
}

export interface AuthResult {
  accessToken: string
  refreshToken: string
  expiresIn: number
  user: AuthUser
}

export interface ProfileResult {
  id: number
  nickname: string
  phone: string // 完整值，前端脱敏展示（需求 3.3 / 口径 S6）
  email?: string | null
  gender?: 'male' | 'female' | 'secret' | null // admin 身份为 null
  avatarUrl?: string | null
  isAdmin?: boolean
  createdAt?: DateTimeString | null
  lastLoginAt?: DateTimeString | null
}

export interface ProfileStats {
  practiceCount: number
  wrongCount: number
  interviewCount: number
  doneQuestions: number
  accuracy: number
}

export type SmsScene = 'register' | 'login' | 'reset'

/** 获取短信验证码（不回传验证码本体；开发期在后端控制台查看 Mock 短信） */
export function fetchSmsCode(scene: SmsScene, phone: string): Promise<{ sentAt: string }> {
  return request.post('/auth/sms-code', { scene, phone })
}

/** 注册（成功即登录） */
export function register(payload: {
  phone: string
  code: string
  password: string
}): Promise<AuthResult> {
  return request.post('/auth/register', payload)
}

/** 账号密码登录（手机号或邮箱；兼容后台账号 Q4） */
export function loginByPassword(payload: {
  account: string
  password: string
  rememberMe: boolean
}): Promise<AuthResult> {
  return request.post('/auth/login/password', payload)
}

/** 手机验证码登录（仅已注册学员） */
export function loginBySms(payload: {
  phone: string
  code: string
  rememberMe: boolean
}): Promise<AuthResult> {
  return request.post('/auth/login/sms', payload)
}

/** 找回密码（重置后全部登录态失效） */
export function resetPassword(payload: {
  phone: string
  code: string
  newPassword: string
}): Promise<{ success: boolean }> {
  return request.post('/auth/password/reset', payload)
}

/** 刷新 access token（refresh 滚动续期） */
export function refreshTokens(payload: {
  refreshToken: string
  clientType: 'portal' | 'admin'
}): Promise<{ accessToken: string; expiresIn: number; refreshToken?: string }> {
  return request.post('/auth/refresh', payload)
}

/** 退出登录（refresh 立即失效） */
export function logout(payload?: { refreshToken?: string }): Promise<{ success: boolean }> {
  return request.post('/auth/logout', payload ?? {})
}

export function getProfile(): Promise<ProfileResult> {
  return request.get('/profile')
}

/** 修改基本信息（手机号只读；admin 身份仅昵称/头像 S4） */
export function updateProfile(payload: {
  nickname: string
  email?: string | null
  gender: 'male' | 'female' | 'secret'
  avatarUrl?: string | null
}): Promise<ProfileResult> {
  return request.put('/profile', payload)
}

/** 上传头像（jpg/png ≤2MB → MinIO） */
export async function uploadAvatar(file: File): Promise<{ url: string }> {
  const form = new FormData()
  form.append('file', file)
  return request.post('/profile/avatar', form)
}

/** 个人学习数据（03 §5.2 口径） */
export function fetchProfileStats(): Promise<ProfileStats> {
  return request.get('/profile/stats')
}
