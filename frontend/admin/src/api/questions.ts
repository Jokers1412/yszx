/**
 * 题库管理接口封装（04 §4.5，question:*）。
 */
import request from './request'

export type QuestionType = 'single' | 'multiple' | 'judge' | 'short'
export type QuestionDifficulty = 'easy' | 'medium' | 'hard'
export type QuestionStatus = 'onShelf' | 'offShelf' | 'pending' | 'draft' | 'rejected'

export interface QuestionListItem {
  id: number
  content: string // 题干截断
  subjectName: string
  stageName: string
  type: QuestionType
  difficulty: QuestionDifficulty
  status: QuestionStatus
  createdAt: string
}

export interface QuestionListResult {
  list: QuestionListItem[]
  total: number
  pageNum: number
  pageSize: number
}

export interface QuestionSummary {
  total: number
  onShelf: number
  pending: number
  single: number
  multiple: number
  judge: number
  short: number
}

export interface QuestionQuery {
  keyword?: string
  subjectId?: number
  stageId?: number
  type?: string // all | single | multiple | judge | short
  difficulty?: string // all | easy | medium | hard
  status?: string // all | onShelf | offShelf | pending | draft | rejected
  pageNum?: number
  pageSize?: number
}

export interface QuestionOption {
  key: string
  content: string
  isCorrect: boolean
}

export interface QuestionPayload {
  stageId: number
  type: QuestionType
  difficulty: QuestionDifficulty
  content: string
  tags?: string[]
  analysis?: string | null
  options?: QuestionOption[] | null // 单选/多选：2~6 项
  judgeAnswer?: boolean | null // 判断
  referenceAnswer?: string | null // 简答（可空）
}

export interface QuestionDetail {
  id: number
  stageId: number
  subjectName: string
  stageName: string
  type: QuestionType
  difficulty: QuestionDifficulty
  content: string
  tags: string[]
  analysis?: string | null
  options: QuestionOption[]
  judgeAnswer?: boolean | null
  referenceAnswer?: string | null
  status: QuestionStatus
  createdAt: string
  createdBy?: string | null
  stats: { answerCount: number; correctCount: number; accuracy: number }
}

export interface QuestionImportPreviewRow {
  rowNo: number
  content: string
  subjectName: string
  stageName: string
  type: QuestionType
  difficulty: QuestionDifficulty
}

export interface QuestionImportPreviewResult {
  importToken: string
  summary: {
    totalRows: number
    newCount: number
    updateCount: number
    warningCount: number
    errorCount: number
  }
  errors: Array<{ rowNo: number; reason: string }>
  warnings: Array<{ rowNo: number; reason: string }>
  rows: QuestionImportPreviewRow[]
}

export function fetchQuestions(params: QuestionQuery): Promise<QuestionListResult> {
  return request.get('/questions', { params })
}

export function fetchQuestionSummary(): Promise<QuestionSummary> {
  return request.get('/questions/summary')
}

export function fetchQuestion(id: number): Promise<QuestionDetail> {
  return request.get(`/questions/${id}`)
}

export function createQuestion(payload: QuestionPayload): Promise<{ id: number }> {
  return request.post('/questions', payload)
}

export function updateQuestion(id: number, payload: QuestionPayload): Promise<{ success: boolean }> {
  return request.put(`/questions/${id}`, payload)
}

export function deleteQuestion(id: number): Promise<{ success: boolean }> {
  return request.delete(`/questions/${id}`)
}

/** 审核（仅待审核可审） */
export function reviewQuestion(id: number, result: 'pass' | 'reject'): Promise<{ status: QuestionStatus }> {
  return request.post(`/questions/${id}/review`, { result })
}

/** 重新提交/上架（已驳回/已下架 → 待审核） */
export function submitQuestion(id: number): Promise<{ status: QuestionStatus }> {
  return request.post(`/questions/${id}/submit`)
}

/** 下架（仅已上架可下架） */
export function unpublishQuestion(id: number): Promise<{ status: QuestionStatus }> {
  return request.post(`/questions/${id}/unpublish`)
}

/** 批量审核（仅待审核可审；不合法条目跳过并回传 skipped） */
export function batchReviewQuestions(
  result: 'pass' | 'reject',
  ids: number[],
): Promise<{ affected: number; skipped: number[] }> {
  return request.post('/questions/batch-review', { result, ids })
}

/** 批量上架/下架（不合法条目跳过并回传 skipped） */
export function batchStatusQuestions(
  action: 'submit' | 'unpublish',
  ids: number[],
): Promise<{ affected: number; skipped: number[] }> {
  return request.post('/questions/batch-status', { action, ids })
}

export function batchDeleteQuestions(ids: number[]): Promise<{ affected: number }> {
  return request.post('/questions/batch-delete', { ids })
}

/** 导入预览（两段式第一步） */
export function previewQuestionImport(file: File): Promise<QuestionImportPreviewResult> {
  const form = new FormData()
  form.append('file', file)
  return request.post('/questions/import/preview', form)
}

/** 确认导入（两段式第二步） */
export function confirmQuestionImport(importToken: string): Promise<{ created: number; updated: number }> {
  return request.post('/questions/import', { importToken })
}

/** 下载导入模板（.xlsx，四种题型各 1 行示例） */
export async function downloadQuestionTemplate(): Promise<void> {
  const blob = (await request.get('/questions/import/template', { responseType: 'blob' })) as Blob
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = '题库-导入模板.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}

/** 导出题目（服务端 .xlsx，14 列可回灌；返回是否截断） */
export async function exportQuestions(params: QuestionQuery): Promise<boolean> {
  const blob = (await request.get('/questions/export', {
    params,
    responseType: 'blob',
  })) as unknown as Blob & { __headers?: Record<string, string> }
  const truncated = blob.__headers?.['x-truncated'] === 'true'
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = '题库.xlsx'
  a.click()
  URL.revokeObjectURL(url)
  return truncated
}
