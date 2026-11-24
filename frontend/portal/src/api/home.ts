/**
 * 首页数据接口封装（04 §3.2，stats:*）。
 * /home/stats、/home/hot-stages 游客可访问；/home/learn-stats 需登录。
 */
import request from './request'

export interface HomeStats {
  featuredQuestions: number
  registeredStudents: number
  aiInterviews: number
  goodRate: number
}

export interface WeekTrendPoint {
  date: string // YYYY-MM-DD（Asia/Shanghai 日界）
  count: number
}

export interface LearnStats {
  streak: number
  accuracy: number
  totalPracticed: number
  todayDone: number
  weekTrend: WeekTrendPoint[]
}

export interface HotStage {
  id: number
  name: string
  icon?: string | null
  subjectId: number
  subjectName: string
  questionCount: number
}

/** Hero 平台数据（前三项实时统计 + 好评率静态） */
export function fetchHomeStats(): Promise<HomeStats> {
  return request.get('/home/stats')
}

/** 个人学习统计 + 近 7 日趋势（登录） */
export function fetchLearnStats(): Promise<LearnStats> {
  return request.get('/home/learn-stats')
}

/** 热门阶段（启用阶段、有已上架题目，上限 12） */
export function fetchHotStages(): Promise<HotStage[]> {
  return request.get('/home/hot-stages')
}
