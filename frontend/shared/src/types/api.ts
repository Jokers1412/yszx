/**
 * 统一响应与分页契约类型（04 §1.2/§1.3 定稿）。
 * 成功：{ code: 0, message: "success", data }；失败：code 为稳定字符串业务码。
 */

/** 成功响应（code 恒为 0） */
export interface ApiResponse<T = unknown> {
  code: 0
  message: string
  data: T
}

/** 失败响应（code 为 04 附录 B 稳定业务码） */
export interface ApiError {
  code: string
  message: string
  data?: {
    fieldErrors?: Array<{ field: string; reason: string }>
    [key: string]: unknown
  } | null
}

/** 分页入参 */
export interface PageQuery {
  pageNum?: number // 从 1 起，默认 1
  pageSize?: number // 默认 10，上限 100
}

/** 分页出参（data 内） */
export interface PageResult<T> {
  list: T[]
  total: number
  pageNum: number
  pageSize: number
}

/** 时间字符串：Asia/Shanghai `YYYY-MM-DD HH:mm:ss` */
export type DateTimeString = string

/** 04 附录 C：API 字符串枚举 */
export type Difficulty = 'easy' | 'medium' | 'hard'
export type QuestionType = 'single' | 'multiple' | 'judge' | 'short'
export type QuestionStatus = 'onShelf' | 'offShelf' | 'pending' | 'draft' | 'rejected'
export type EnableStatus = 'enabled' | 'disabled'
export type Gender = 'male' | 'female' | 'secret'
