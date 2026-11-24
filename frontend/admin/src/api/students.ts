/**
 * 学员管理接口封装（04 §4.8，student:*）。
 */
import request from './request'

export interface StudentListItem {
  id: number
  nickname: string
  avatarUrl?: string | null
  phone: string // 完整手机号（不脱敏）
  registeredAt: string
  studyDays: number
  practiceCount: number
  interviewCount: number
  status: 'enabled' | 'disabled'
  lastLoginAt?: string | null
}

export interface StudentListResult {
  list: StudentListItem[]
  total: number
  pageNum: number
  pageSize: number
}

export interface DoneCourse {
  id: number
  name: string
  durationMinutes: number
}

export interface StudentDetail {
  profile: {
    id: number
    nickname: string
    avatarUrl?: string | null
    status: 'enabled' | 'disabled'
    phone: string
    email?: string | null
    registeredAt: string
    lastLoginAt?: string | null
  }
  stats: {
    studyDays: number
    doneCourses: DoneCourse[]
    practiceCount: number
    accuracy: number
  }
  interviewSummary: { count: number }
}

export interface InterviewRecordItem {
  finishedAt: string
  subjectName: string
  difficulty: 'easy' | 'medium' | 'hard'
  questionCount: number
  overallScore: number
}

export interface InterviewRecordResult {
  list: InterviewRecordItem[]
  total: number
  pageNum: number
  pageSize: number
}

export interface StudentQuery {
  keyword?: string
  status?: string
  pageNum?: number
  pageSize?: number
}

export function fetchStudents(params: StudentQuery): Promise<StudentListResult> {
  return request.get('/students', { params })
}

export function fetchStudent(id: number): Promise<StudentDetail> {
  return request.get(`/students/${id}`)
}

export function fetchStudentInterviews(
  id: number,
  params: { pageNum?: number; pageSize?: number },
): Promise<InterviewRecordResult> {
  return request.get(`/students/${id}/interviews`, { params })
}

/** 启用/禁用（禁用后学员端登录态作废） */
export function patchStudentStatus(id: number, status: 'enabled' | 'disabled'): Promise<{ success: boolean }> {
  return request.patch(`/students/${id}/status`, { status })
}

export function deleteStudent(id: number): Promise<{ success: boolean }> {
  return request.delete(`/students/${id}`)
}

export function batchStudentStatus(
  action: 'enable' | 'disable',
  ids: number[],
): Promise<{ affected: number }> {
  return request.post('/students/batch-status', { action, ids })
}

export function batchDeleteStudents(ids: number[]): Promise<{ affected: number }> {
  return request.post('/students/batch-delete', { ids })
}

/** 导出学员列表（按当前筛选，服务端 xlsx 流） */
export async function exportStudents(params: StudentQuery): Promise<void> {
  const blob = (await request.get('/students/export', { params, responseType: 'blob' })) as Blob
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = '学员列表.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}
