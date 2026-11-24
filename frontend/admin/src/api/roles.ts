/**
 * 角色管理接口封装（04 §4.10，仅超管）。
 */
import request from './request'

export interface RoleItem {
  id: number
  code: string
  name: string
  description?: string | null
  isPreset: boolean
  userCount: number
  permissionTags: string[]
}

export interface PermissionGroup {
  group: string
  items: Array<{ code: string; name: string }>
}

export function fetchRoles(): Promise<{ list: RoleItem[] }> {
  return request.get('/roles')
}

export function createRole(payload: {
  name: string
  code: string
  description?: string
}): Promise<{ id: number }> {
  return request.post('/roles', payload)
}

export function updateRole(
  id: number,
  payload: { name: string; description?: string },
): Promise<{ success: boolean }> {
  return request.put(`/roles/${id}`, payload)
}

/** 授权（全量覆盖） */
export function updateRolePermissions(
  id: number,
  permissionCodes: string[],
): Promise<{ success: boolean }> {
  return request.put(`/roles/${id}/permissions`, { permissionCodes })
}

export function deleteRole(id: number): Promise<{ success: boolean }> {
  return request.delete(`/roles/${id}`)
}

/** 权限树（9 组 33 项） */
export function fetchPermissionTree(): Promise<PermissionGroup[]> {
  return request.get('/permissions')
}
