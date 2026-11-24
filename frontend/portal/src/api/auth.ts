/**
 * accounts 接口封装（04 §2.1 #1-#10）。
 * 基础工程阶段仅定义签名骨架，功能开发阶段按契约补齐实现。
 */
import request from './request'

import type { DateTimeString } from '@shared/types/api'

export interface LoginResult {
  accessToken: string
  refreshToken: string
  student: {
    id: number
    phone: string
    nickname: string
    avatarUrl?: string | null
    isAdmin?: boolean
  }
}

export function fetchSmsCode(phone: string): Promise<void> {
  return request.post('/auth/sms-code', { phone })
}

export function loginByPassword(payload: {
  phone: string
  password: string
  remember?: boolean
}): Promise<LoginResult> {
  return request.post('/auth/login/password', payload)
}

export function loginBySms(payload: {
  phone: string
  code: string
  remember?: boolean
}): Promise<LoginResult> {
  return request.post('/auth/login/sms', payload)
}

export function logout(): Promise<void> {
  return request.post('/auth/logout')
}

export function getProfile(): Promise<{
  id: number
  phone: string
  nickname: string
  avatarUrl?: string | null
  email?: string | null
  gender: 'male' | 'female' | 'secret'
  createdAt: DateTimeString
}> {
  return request.get('/profile')
}
