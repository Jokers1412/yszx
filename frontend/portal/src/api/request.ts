/**
 * axios 封装：统一响应解包 {code,message,data}（04 §1.2）、
 * 401 自动 refresh 续期后重放（04 §1.5）、业务码错误抛出。
 * refresh 失效 → 清登录态跳登录页（带 redirect 回跳）。
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

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean }

/** 并发 401 共用同一次刷新 */
let refreshTask: Promise<boolean> | null = null

function doRefresh(): Promise<boolean> {
  if (!refreshTask) {
    refreshTask = (async () => {
      const auth = useAuthStore()
      if (!auth.refreshToken) return false
      try {
        const data = (await instance.post('/auth/refresh', {
          refreshToken: auth.refreshToken,
          clientType: 'portal',
        })) as unknown as { accessToken: string; refreshToken?: string }
        auth.setTokens(data.accessToken, data.refreshToken ?? auth.refreshToken)
        return true
      } catch {
        return false
      } finally {
        refreshTask = null
      }
    })()
  }
  return refreshTask
}

// 响应拦截：解包统一结构；失败按业务码抛出（token 失效先续期重放）
instance.interceptors.response.use(
  (response) => {
    const body = response.data as ApiResponse | ApiError
    if (body.code === 0) {
      return (body as ApiResponse).data as never
    }
    return Promise.reject(body as ApiError)
  },
  async (error) => {
    const body: ApiError | null = error?.response?.data ?? null
    const config = error?.config as RetriableConfig | undefined
    const code = body?.code
    const tokenInvalid = code === 'AUTH_TOKEN_INVALID' || code === 'AUTH_TOKEN_EXPIRED'
    const canRetry =
      !!config && !config._retried && !!config.url && !config.url.includes('/auth/refresh')

    if (tokenInvalid && canRetry) {
      const auth = useAuthStore()
      if (auth.refreshToken) {
        config._retried = true
        if (await doRefresh()) {
          config.headers.Authorization = `Bearer ${auth.accessToken}`
          return instance(config)
        }
        // refresh 失效 → 清登录态回登录页（04 §1.5 失效链路）
        auth.clear()
        if (!window.location.pathname.startsWith('/login')) {
          const redirect = encodeURIComponent(
            window.location.pathname + window.location.search,
          )
          window.location.assign(`/login?redirect=${redirect}`)
        }
      }
    }
    return Promise.reject(body ?? { code: 'SYS_INTERNAL', message: '网络异常，请稍后再试' })
  },
)

export default instance
