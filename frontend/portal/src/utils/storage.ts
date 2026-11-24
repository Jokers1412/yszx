/**
 * localStorage 封装（02 D7 / 需求 3.5、3.8.2）。
 * 练习进度、面试会话（消息流/当前题号/用时）、新手引导等本地持久化；
 * 统一键前缀 yszx_（原型约定）。
 */

export interface StorageOptions {
  /** 仅存 sessionStorage（如未勾选记住我的 refresh token） */
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

/** 本地会话键名常量（练习进度 / 面试会话 / 新手引导，功能开发阶段细化） */
export const SESSION_KEYS = {
  practiceProgress: 'yszx_practice_progress',   // 刷题练习进度（继续上次）
  interviewSession: 'yszx_interview_session',   // 面试会话（退出=保存可续，口径 S22）
  beginnerGuide: 'yszx_beginner_guide',         // 新手引导完成标记
} as const
