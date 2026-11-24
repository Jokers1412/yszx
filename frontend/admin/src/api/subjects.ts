/**
 * 学科管理接口封装（04 §4.3，subject:*）。
 */
import request from './request'

export interface StageItem {
  id: number
  name: string
  icon?: string | null
  sortOrder: number
  status: 'enabled' | 'disabled'
  questionCount: number
}

export interface SubjectItem {
  id: number
  name: string
  icon: string
  description: string
  sortOrder: number
  themeColor: string
  courseCount: number
  routeCount: number
  questionCount: number
  stages: StageItem[]
}

export interface SubjectCards {
  total: number
  withStages: number
  stageTotal: number
  questionTotal: number
}

export interface SubjectListResult {
  cards: SubjectCards
  list: SubjectItem[]
}

export interface SubjectPayload {
  name: string
  icon: string
  description: string
  sortOrder?: number
  themeColor: string
}

export interface StagePayload {
  subjectId: number
  name: string
  icon?: string | null
  sortOrder?: number
}

/** 学科+阶段列表（含统计卡与删除三态提示计数） */
export function fetchSubjects(): Promise<SubjectListResult> {
  return request.get('/subjects')
}

export function createSubject(payload: SubjectPayload): Promise<{ id: number }> {
  return request.post('/subjects', payload)
}

export function updateSubject(id: number, payload: SubjectPayload): Promise<{ success: boolean }> {
  return request.put(`/subjects/${id}`, payload)
}

export function deleteSubject(id: number): Promise<{ success: boolean }> {
  return request.delete(`/subjects/${id}`)
}

/** 学科排序（全量 id，按新顺序） */
export function sortSubjects(orderedIds: number[]): Promise<{ success: boolean }> {
  return request.put('/subjects/sort', { orderedIds })
}

export function createStage(payload: StagePayload): Promise<{ id: number }> {
  return request.post('/stages', payload)
}

export function updateStage(id: number, payload: StagePayload): Promise<{ success: boolean }> {
  return request.put(`/stages/${id}`, payload)
}

/** 阶段启用/禁用 */
export function patchStageStatus(id: number, status: 'enabled' | 'disabled'): Promise<{ success: boolean }> {
  return request.patch(`/stages/${id}/status`, { status })
}

export function deleteStage(id: number): Promise<{ success: boolean }> {
  return request.delete(`/stages/${id}`)
}

/** 阶段排序（同学科全量 id，按新顺序） */
export function sortStages(subjectId: number, orderedIds: number[]): Promise<{ success: boolean }> {
  return request.put('/stages/sort', { subjectId, orderedIds })
}
