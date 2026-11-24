/**
 * 面试题库管理接口封装（04 §4.6，interviewbank:*）。
 */
import request from './request'

export type InterviewDifficulty = 'easy' | 'medium' | 'hard'

export interface InterviewQuestionListItem {
  id: number
  content: string // 题干截断
  subjectName: string
  difficulty: InterviewDifficulty
  topic?: string | null // 空=未分类
  tags: string[]
  sourceType: 'manual' | 'excel'
  sourceFile?: string | null
  sourceRow?: number | null
}

export interface InterviewQuestionListResult {
  list: InterviewQuestionListItem[]
  total: number
  pageNum: number
  pageSize: number
}

export interface InterviewQuestionDetail extends InterviewQuestionListItem {
  subjectId: number
  referenceAnswer?: string | null
  createdAt: string
}

export interface InterviewQuestionQuery {
  keyword?: string
  subjectId?: number
  topic?: string
  difficulty?: string // all | easy | medium | hard
  unclassifiedOnly?: boolean
  pageNum?: number
  pageSize?: number
}

export interface InterviewQuestionCreatePayload {
  subjectId: number
  content: string
  referenceAnswer?: string | null
  topic?: string | null
  difficulty: InterviewDifficulty
  tags?: string[]
}

export interface InterviewQuestionUpdatePayload {
  topic?: string | null // 清空=未分类
  difficulty: InterviewDifficulty
}

export interface InterviewImportPreviewRow {
  rowNo: number
  content: string
  subjectName: string
  difficulty: InterviewDifficulty
  topic?: string | null
}

export interface InterviewImportPreviewResult {
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
  subjects: Array<{ subjectName: string; count: number }>
  rows: InterviewImportPreviewRow[]
}

export function fetchInterviewQuestions(params: InterviewQuestionQuery): Promise<InterviewQuestionListResult> {
  return request.get('/interview-questions', { params })
}

export function fetchInterviewQuestion(id: number): Promise<InterviewQuestionDetail> {
  return request.get(`/interview-questions/${id}`)
}

export function createInterviewQuestion(payload: InterviewQuestionCreatePayload): Promise<{ id: number }> {
  return request.post('/interview-questions', payload)
}

/** 编辑（仅主题与难度） */
export function updateInterviewQuestion(
  id: number,
  payload: InterviewQuestionUpdatePayload,
): Promise<{ success: boolean }> {
  return request.put(`/interview-questions/${id}`, payload)
}

export function deleteInterviewQuestion(id: number): Promise<{ success: boolean }> {
  return request.delete(`/interview-questions/${id}`)
}

/** 导入预览（两段式第一步） */
export function previewInterviewImport(file: File): Promise<InterviewImportPreviewResult> {
  const form = new FormData()
  form.append('file', file)
  return request.post('/interview-questions/import/preview', form)
}

/** 确认导入（两段式第二步） */
export function confirmInterviewImport(importToken: string): Promise<{ created: number; updated: number }> {
  return request.post('/interview-questions/import', { importToken })
}

/** 下载导入模板（.xlsx，6 列） */
export async function downloadInterviewTemplate(): Promise<void> {
  const blob = (await request.get('/interview-questions/import/template', { responseType: 'blob' })) as Blob
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = '面试题库-导入模板.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}
