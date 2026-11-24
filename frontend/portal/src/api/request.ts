/**
 * axios 封装：统一响应解包 {code,message,data}（04 §1.2）、
 * 401 自动 refresh 续期（04 §1.5）、业务码错误抛出。
 */
import axios from 'axios'
import type { AxiosInstance, InternalAxiosRequestConfig } from 'axios'

import type { ApiError, ApiResponse } from '@shared/types/api'
import { useAuthStore } from '@/stores/auth'

const instance: AxiosInstance = axios.create({
  baseURL: '/api/portal/v1',
  timeout: 60_000, // AI 调用秒级延迟（02 §7），留足等待
})

// 请求拦截：携带 access token
instance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const auth = useAuthStore()
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

// 响应拦截：解包统一结构；失败按业务码抛出
instance.interceptors.response.use(
  (response) => {
    const body = response.data as ApiResponse | ApiError
    if (body.code === 0) {
      return (body as ApiResponse).data as never
    }
    return Promise.reject(body as ApiError)
  },
  async (error) => {
    // TODO(feature): 401 时用 refresh token 调 /auth/refresh 续期后重放原请求；
    // refresh 失效 → 清登录态跳登录页（04 §1.5 失效链路）
    const body: ApiError | null = error?.response?.data ?? null
    return Promise.reject(body ?? { code: 'SYS_INTERNAL', message: '网络异常，请稍后再试' })
  },
)

export default instance
