/**
 * 学习路线管理接口封装（04 §4.7，route:*）。
 */
import request from './request'

export interface RouteCoursePreview {
  name: string
  coverUrl?: string | null
}

export interface RouteCard {
  id: number
  name: string
  status: 'enabled' | 'disabled'
  subjectName: string
  targetEducation?: string | null
  description?: string | null
  courseCount: number
  totalMinutes: number
  coursePreview: RouteCoursePreview[]
  createdAt: string
}

export interface RouteCourseItem {
  id: number
  bvid?: string | null
  name: string
  durationMinutes: number
  sortOrder: number
}

export interface RouteDetail {
  id: number
  name: string
  status: 'enabled' | 'disabled'
  subjectId: number
  subjectName: string
  icon?: string | null
  targetEducation?: string | null
  description?: string | null
  courseCount: number
  totalMinutes: number
  courses: RouteCourseItem[]
  createdAt: string
}

export interface RouteQuery {
  subjectId?: number
  status?: string // all | enabled | disabled
  keyword?: string
  pageNum?: number
  pageSize?: number
}

export interface RouteListResult {
  list: RouteCard[]
  total: number
  pageNum: number
  pageSize: number
}

export interface RouteBasicPayload {
  name: string
  subjectId: number
  status: 'enabled' | 'disabled'
  icon?: string | null
  targetEducation?: string | null
  description?: string | null
}

export interface RouteCreatePayload extends RouteBasicPayload {
  courseIds?: number[] // 有序
}

export function fetchRoutes(params: RouteQuery): Promise<RouteListResult> {
  return request.get('/routes', { params })
}

export function fetchRoute(id: number): Promise<RouteDetail> {
  return request.get(`/routes/${id}`)
}

export function createRoute(payload: RouteCreatePayload): Promise<{ id: number }> {
  return request.post('/routes', payload)
}

/** 编辑路线（基本信息全量更新，不含课程） */
export function updateRoute(id: number, payload: RouteBasicPayload): Promise<{ success: boolean }> {
  return request.put(`/routes/${id}`, payload)
}

export function deleteRoute(id: number): Promise<{ success: boolean }> {
  return request.delete(`/routes/${id}`)
}

/** 从课程库添加课程（已添加的自动忽略） */
export function addRouteItems(id: number, courseIds: number[]): Promise<{ affected: number }> {
  return request.post(`/routes/${id}/items`, { courseIds })
}

/** 课程排序/移除（有序全量，未含即移除） */
export function updateRouteItems(id: number, courseIds: number[]): Promise<{ success: boolean }> {
  return request.put(`/routes/${id}/items`, { courseIds })
}
