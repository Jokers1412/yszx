/**
 * 数据看板接口封装（04 §4.2，dashboard:view）。
 * 题目分布=各学科全部有效题目（S13）；趋势文案由服务端按环比计算。
 */
import request from './request'

export interface DashboardCards {
  subjectCount: number
  questionCount: number
  registeredUsers: number
  aiInterviewCount: number
}

export interface DashboardTrends {
  subject: string
  question: string
  user: string
  interview: string
}

export interface DistributionItem {
  subjectName: string
  count: number
}

export interface ActivityItem {
  adminUsername?: string | null
  action: string
  detail?: string | null
  at: string
}

export interface DashboardData {
  cards: DashboardCards
  trends: DashboardTrends
  questionDistribution: DistributionItem[]
  recentActivities: ActivityItem[]
}

export interface GrowthPoint {
  date: string // YYYY-MM-DD
  count: number
}

/** 看板汇总（卡片+趋势+分布+最近活动） */
export function fetchDashboard(): Promise<DashboardData> {
  return request.get('/dashboard')
}

/** 用户增长趋势（7/30/90 天，按注册日期沪日界） */
export function fetchUserGrowth(days: 7 | 30 | 90): Promise<{ points: GrowthPoint[] }> {
  return request.get('/dashboard/user-growth', { params: { days } })
}
