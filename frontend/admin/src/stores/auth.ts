/**
 * 管理端登录态（Pinia）。
 * 独立 JWT（aud=admin，与学员端互不通用）；permissionCodes 驱动菜单/按钮（04 §1.6）；
 * super_admin 免检全部权限（前端侧等价于全量权限集）。
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import type { AdminUserBrief } from '@/api/auth'
import { storage } from '@/utils/storage'

const KEY_ACCESS = 'yszx_admin_access_token'
const KEY_REFRESH = 'yszx_admin_refresh_token'
const KEY_USER = 'yszx_admin_user'
const KEY_PERMS = 'yszx_admin_permissions'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string>(storage.get(KEY_ACCESS) ?? '')
  const refreshToken = ref<string>(storage.get(KEY_REFRESH) ?? '')
  const admin = ref<AdminUserBrief | null>(storage.get<AdminUserBrief>(KEY_USER))
  const permissionCodes = ref<string[]>(storage.get<string[]>(KEY_PERMS) ?? [])

  const isLoggedIn = computed(() => !!accessToken.value)

  function setTokens(access: string, refresh: string, remember: boolean) {
    accessToken.value = access
    refreshToken.value = refresh
    storage.set(KEY_ACCESS, access, { sessionOnly: !remember })
    storage.set(KEY_REFRESH, refresh, { sessionOnly: !remember })
  }

  function setAdmin(info: AdminUserBrief, perms: string[]) {
    admin.value = info
    permissionCodes.value = perms
    storage.set(KEY_USER, info)
    storage.set(KEY_PERMS, perms)
  }

  function hasPermission(code: string): boolean {
    if (!admin.value) return false
    return admin.value.isSuper || permissionCodes.value.includes(code)
  }

  function clear() {
    accessToken.value = ''
    refreshToken.value = ''
    admin.value = null
    permissionCodes.value = []
    storage.remove(KEY_ACCESS)
    storage.remove(KEY_REFRESH)
    storage.remove(KEY_USER)
    storage.remove(KEY_PERMS)
  }

  return {
    accessToken, refreshToken, admin, permissionCodes,
    isLoggedIn, setTokens, setAdmin, hasPermission, clear,
  }
})
