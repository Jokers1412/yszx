/**
 * 学习路线接口封装（04 §3.3 #29-32，learning:*）。
 * 进度按 student_course 全局标记统计（Q1）；标记已学完幂等、仅标记不可取消。
 */
import request from './request'

export interface RouteSubjectCard {
  id: number
  name: string
  icon?: string | null
  routeCount: number
}

export interface RouteProgress {
  done: number
  total: number
  percent: number
}

export interface RouteListItem {
  id: number
  name: string
  icon?: string | null
  targetEducation?: string | null
  description?: string | null
  courseCount: number
  totalMinutes: number
  progress: RouteProgress
  lastStudiedAt?: string | null
}

export interface RouteCourseItem {
  id: number
  seq: number
  name: string
  coverUrl?: string | null
  bvid?: string | null
  durationMinutes: number
  playUrl?: string | null
  completed: boolean
}

export interface RouteDetail {
  id: number
  name: string
  subjectName: string
  targetEducation?: string | null
  description?: string | null
  courseCount: number
  totalMinutes: number
  progress: RouteProgress
  courses: RouteCourseItem[]
}

/** 学科卡片（含无路线学科，routeCount=启用路线数） */
export function fetchRouteSubjects(): Promise<RouteSubjectCard[]> {
  return request.get('/routes/subjects')
}

/** 路线列表（含进度/最近学习时间） */
export function fetchRoutes(subjectId: number): Promise<RouteListItem[]> {
  return request.get('/routes', { params: { subjectId } })
}

/** 路线详情（课程 + 已学标记） */
export function fetchRouteDetail(id: number): Promise<RouteDetail> {
  return request.get(`/routes/${id}`)
}

/** 标记已学完（幂等；仅标记不可取消） */
export function completeCourse(courseId: number): Promise<{ success: boolean }> {
  return request.post(`/courses/${courseId}/complete`)
}
