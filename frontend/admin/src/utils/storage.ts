/**
 * localStorage 封装（与 portal 同构，键前缀 yszx_）。
 */

export interface StorageOptions {
  sessionOnly?: boolean
}

function bucket(options?: StorageOptions): Storage {
  return options?.sessionOnly ? window.sessionStorage : window.localStorage
}

export const storage = {
  get<T = string>(key: string): T | null {
    try {
      const raw = window.localStorage.getItem(key) ?? window.sessionStorage.getItem(key)
      return raw === null ? null : (JSON.parse(raw) as T)
    } catch {
      return null
    }
  },

  set(key: string, value: unknown, options?: StorageOptions): void {
    bucket(options).setItem(key, JSON.stringify(value))
  },

  remove(key: string): void {
    window.localStorage.removeItem(key)
    window.sessionStorage.removeItem(key)
  },
}
