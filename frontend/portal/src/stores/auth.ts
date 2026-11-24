/**
 * 学员端登录态（Pinia）。
 * 双 token（04 §1.5）：access 2h + refresh 7d/30d（记住我）；
 * 存储经 utils/storage（localStorage，键 yszx_* 前缀约定）。
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { storage } from '@/utils/storage'

const KEY_ACCESS = 'yszx_portal_access_token'
const KEY_REFRESH = 'yszx_portal_refresh_token'

export interface StudentInfo {
  id: number
  phone: string
  nickname: string
  avatarUrl?: string | null
  isAdmin?: boolean // 后台账号登录学员端标记（04 §1.5 Q4）
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string>(storage.get(KEY_ACCESS) ?? '')
  const refreshToken = ref<string>(storage.get(KEY_REFRESH) ?? '')
  const student = ref<StudentInfo | null>(null)

  const isLoggedIn = computed(() => !!accessToken.value)

  function setTokens(access: string, refresh: string, remember: boolean) {
    accessToken.value = access
    refreshToken.value = refresh
    storage.set(KEY_ACCESS, access)
    storage.set(KEY_REFRESH, refresh, { sessionOnly: !remember })
  }

  function setStudent(info: StudentInfo | null) {
    student.value = info
  }

  function clear() {
    accessToken.value = ''
    refreshToken.value = ''
    student.value = null
    storage.remove(KEY_ACCESS)
    storage.remove(KEY_REFRESH)
  }

  return { accessToken, refreshToken, student, isLoggedIn, setTokens, setStudent, clear }
})
