/**
 * B站课程库接口封装（04 §4.4，course:*）。
 */
import request from './request'

export interface CourseSubjectRef {
  id: number
  name: string
  isPrimary: boolean
}

export interface CourseItem {
  id: number
  name: string
  bvid?: string | null
  coverUrl?: string | null
  durationMinutes: number
  source: 'bili' | 'other'
  playUrl?: string | null
  subjects: CourseSubjectRef[]
  createdAt: string
  routeRefCount: number // 删除确认提示所需（04 §4.4）
}

export interface CourseCards {
  total: number
  totalHours: number
  linkedSubjectCount: number
}

export interface CourseListResult {
  cards: CourseCards
  list: CourseItem[]
  total: number
  pageNum: number
  pageSize: number
}

export interface CourseQuery {
  keyword?: string
  subjectId?: number
  source?: string // all | bili | other
  pageNum?: number
  pageSize?: number
}

export interface CoursePayload {
  name: string
  bvid?: string | null
  coverUrl?: string | null
  durationMinutes: number
  source: 'bili' | 'other'
  playUrl?: string | null
  subjectIds: number[] // 第一个=主学科；含「其他学科」时仅可单选
}

export interface ImportSummary {
  totalRows: number
  newCount: number
  updateCount: number
  warningCount: number
  errorCount: number
}

export interface ImportIssue {
  rowNo: number // 0 = 文件级
  reason: string
}

export interface ImportPreviewRow {
  rowNo: number
  name: string
  durationMinutes: number
  subjectNames: string
  source: 'bili' | 'other'
  result: 'new' | 'update' | 'warning'
}

export interface ImportPreviewResult {
  importToken: string
  summary: ImportSummary
  errors: ImportIssue[]
  warnings: ImportIssue[]
  affectedRoutes: { courses: number; routes: number }
  rows: ImportPreviewRow[]
}

export function fetchCourses(params: CourseQuery): Promise<CourseListResult> {
  return request.get('/courses', { params })
}

export function createCourse(payload: CoursePayload): Promise<{ id: number }> {
  return request.post('/courses', payload)
}

export function updateCourse(id: number, payload: CoursePayload): Promise<{ success: boolean }> {
  return request.put(`/courses/${id}`, payload)
}

export function deleteCourse(id: number): Promise<{ success: boolean }> {
  return request.delete(`/courses/${id}`)
}

/** 导入预览（两段式第一步：解析 + 校验，返回 importToken） */
export function previewCourseImport(file: File): Promise<ImportPreviewResult> {
  const form = new FormData()
  form.append('file', file)
  return request.post('/courses/import/preview', form)
}

/** 确认导入（两段式第二步：按 importToken 全量落库） */
export function confirmCourseImport(importToken: string): Promise<{ created: number; updated: number }> {
  return request.post('/courses/import', { importToken })
}

/** 下载导入模板（.xlsx） */
export async function downloadCourseTemplate(): Promise<void> {
  const blob = (await request.get('/courses/import/template', { responseType: 'blob' })) as Blob
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'B站课程库-导入模板.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}

/** 导出课程 Excel（按当前筛选，服务端导出 + 落操作审计，04 §4.4） */
export async function exportCourses(params: CourseQuery): Promise<void> {
  const blob = (await request.get('/courses/export', { params, responseType: 'blob' })) as Blob
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'B站课程库.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}
