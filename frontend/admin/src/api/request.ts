/**
 * axios 封装（管理端）：统一响应解包 {code,message,data}（04 §1.2）、
 * 401 跳登录、403 PERM_DENIED 提示、业务码错误抛出。
 */
import axios from 'axios'
import type { AxiosInstance, InternalAxiosRequestConfig } from 'axios'

import type { ApiError, ApiResponse } from '@shared/types/api'
import { useAuthStore } from '@/stores/auth'

const instance: AxiosInstance = axios.create({
  baseURL: '/api/admin/v1',
  timeout: 60_000,
})

instance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const auth = useAuthStore()
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

instance.interceptors.response.use(
  (response) => {
    // 文件流（导出 CSV/xlsx）直接透传；附加响应头（如 X-Truncated）供导出提示
    if (response.config.responseType === 'blob') {
      Object.defineProperty(response.data, '__headers', {
        value: response.headers,
        enumerable: false,
      })
      return response.data as never
    }
    const body = response.data as ApiResponse | ApiError
    if (body.code === 0) {
      return (body as ApiResponse).data as never
    }
    return Promise.reject(body as ApiError)
  },
  async (error) => {
    const body: ApiError | null = error?.response?.data ?? null
    if (body?.code === 'AUTH_TOKEN_INVALID' || body?.code === 'AUTH_TOKEN_EXPIRED') {
      // 登录态失效 → 跳登录页（04 §1.5）
      const auth = useAuthStore()
      auth.clear()
      window.location.href = '/login'
    }
    return Promise.reject(body ?? { code: 'SYS_INTERNAL', message: '网络异常，请稍后再试' })
  },
)

export default instance
