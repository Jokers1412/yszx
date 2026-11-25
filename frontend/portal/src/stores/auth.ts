/**
 * 学员端登录态（Pinia）。
 * 双 token（04 §1.5）：access 2h + refresh 7d/30d（记住我）；
 * 存储经 utils/storage（localStorage，键 yszx_* 前缀约定）。
 * 记住我 → refresh 存 localStorage，否则 sessionStorage。
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import type { AuthResult, AuthUser } from '@/api/auth'
import { storage } from '@/utils/storage'

const KEY_ACCESS = 'yszx_portal_access_token'
const KEY_REFRESH = 'yszx_portal_refresh_token'
const KEY_STUDENT = 'yszx_portal_student' // 用户快照（昵称/头像等，刷新后顶栏即显）

export interface StudentInfo extends AuthUser {
  phone?: string
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string>(storage.get(KEY_ACCESS) ?? '')
  const refreshToken = ref<string>(storage.get(KEY_REFRESH) ?? '')
  const student = ref<StudentInfo | null>(storage.get<StudentInfo>(KEY_STUDENT))
  const rememberMe = ref(true) // 会话内记住选择（决定 refresh/快照存储桶）

  const isLoggedIn = computed(() => !!accessToken.value)

  function setTokens(access: string, refresh: string) {
    accessToken.value = access
    refreshToken.value = refresh
    storage.set(KEY_ACCESS, access)
    storage.set(KEY_REFRESH, refresh, { sessionOnly: !rememberMe.value })
  }

  /** 登录/注册成功落地（S3 注册即登录；remember 决定 refresh 有效期档位） */
  function applyAuth(result: AuthResult, remember: boolean) {
    rememberMe.value = remember
    setTokens(result.accessToken, result.refreshToken)
    student.value = { ...result.user }
    storage.set(KEY_STUDENT, student.value, { sessionOnly: !remember })
  }

  /** 个人中心保存后同步顶栏昵称/头像 */
  function patchStudent(patch: Partial<StudentInfo>) {
    if (student.value) {
      student.value = { ...student.value, ...patch }
      storage.set(KEY_STUDENT, student.value, { sessionOnly: !rememberMe.value })
    }
  }

  /** 启动/回跳时以服务端资料回填快照（覆盖刷新丢失或旧会话缺快照的场景） */
  function hydrateStudent(info: StudentInfo) {
    student.value = info
    storage.set(KEY_STUDENT, info, { sessionOnly: !rememberMe.value })
  }

  function clear() {
    accessToken.value = ''
    refreshToken.value = ''
    student.value = null
    rememberMe.value = true
    storage.remove(KEY_ACCESS)
    storage.remove(KEY_REFRESH)
    storage.remove(KEY_STUDENT)
  }

  return {
    accessToken,
    refreshToken,
    student,
    rememberMe,
    isLoggedIn,
    setTokens,
    applyAuth,
    patchStudent,
    hydrateStudent,
    clear,
  }
})
