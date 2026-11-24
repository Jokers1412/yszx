/**
 * 用户管理接口封装（04 §4.9，user:*）。
 */
import request from './request'

import type { PageResult } from '@shared/types/api'

export interface UserItem {
  id: number
  username: string
  nickname: string
  avatarUrl?: string | null
  phone: string
  roleCode: string
  roleName: string
  status: 'enabled' | 'disabled'
  lastLoginAt?: string | null
}

export interface UserDetail extends UserItem {
  email?: string | null
  createdAt: string
  recentLogs: Array<{ action: string; at: string }>
}

export interface UserPayload {
  username: string
  phone: string
  email?: string | null
  roleCode: string
  password?: string
  status: 'enabled' | 'disabled'
}

export interface UserQuery {
  keyword?: string
  roleCode?: string
  status?: string
  pageNum?: number
  pageSize?: number
}

export function fetchUsers(params: UserQuery): Promise<PageResult<UserItem>> {
  return request.get('/users', { params })
}

export function fetchUser(id: number): Promise<UserDetail> {
  return request.get(`/users/${id}`)
}

export function createUser(payload: UserPayload & { password: string }): Promise<{ id: number }> {
  return request.post('/users', payload)
}

export function updateUser(id: number, payload: UserPayload): Promise<{ success: boolean }> {
  return request.put(`/users/${id}`, payload)
}

/** 删除（单个走 /users/{id}，多个走 batch-delete，均归并 user:edit） */
export function deleteUsers(ids: number[]): Promise<{ success: boolean }> {
  return ids.length === 1
    ? request.delete(`/users/${ids[0]}`)
    : request.post('/users/batch-delete', { ids })
}

export function patchUserStatus(id: number, status: 'enabled' | 'disabled'): Promise<{ success: boolean }> {
  return request.patch(`/users/${id}/status`, { status })
}

export function patchUsersStatus(
  ids: number[],
  status: 'enabled' | 'disabled',
): Promise<{ success: boolean }> {
  return request.post('/users/batch-status', { ids, status })
}

/** 重置为默认密码（应用层常量），该用户 refresh 全部失效 */
export function resetUserPassword(id: number): Promise<{ success: boolean }> {
  return request.post(`/users/${id}/password-reset`)
}
