/**
 * AI 面试接口封装（04 §3.4 #33-38 + 回放）。
 * 发起即计配额（S1）；逐题评分失败 503 可重试（S2）；回放由逐题快照重建（S12）。
 */
import request from './request'

export type DifficultyApi = 'easy' | 'medium' | 'hard'

export interface ConfigMetaSubject {
  id: number
  name: string
}

export interface ConfigMeta {
  subjects: ConfigMetaSubject[]
  difficulties: DifficultyApi[]
  questionCounts: number[]
  defaultCount: number
  timeoutSeconds: number
  todayRemaining: number
  dailyQuota: number
}

export interface InterviewQuestionItem {
  seq: number
  questionText: string
}

export interface StartInterviewPayload {
  subjectId: number
  difficulty: DifficultyApi
  questionCount: number
}

export interface StartInterviewResult {
  recordId: number
  questions: InterviewQuestionItem[]
  timeoutSeconds: number
}

export interface AnswerSubmitPayload {
  seq: number
  answer: string
  timedOut?: boolean
}

export interface AnswerSubmitResult {
  seq: number
  score: number // 0-10
  aiComment: string
  isLast: boolean
}

export interface FinishResult {
  endRemark?: string | null
  reportId: number
  overallScore: number
}

export interface ComparedToLast {
  delta: number
  trend: 'up' | 'down' | 'flat'
}

export interface ReportQuestionDetail {
  seq: number
  questionText: string
  userAnswer?: string | null
  score?: number | null
  aiComment?: string | null
  timedOut: boolean
}

export interface InterviewReport {
  recordId: number
  subjectId: number
  subjectName: string
  difficulty: DifficultyApi
  finishedAt: string
  overallScore: number
  accuracyRate: number
  durationSeconds: number
  answeredCount: number
  questionCount: number
  comparedToLast?: ComparedToLast | null
  abilityScores: Record<string, number>
  strengths: string[]
  improvements: { issue: string; advice: string }[]
  suggestions: string[]
  coaching: Record<string, string>
  questionDetails: ReportQuestionDetail[]
}

export interface RecordListItem {
  id: number
  subjectId: number
  subjectName: string
  difficulty: DifficultyApi
  questionCount: number
  answeredCount: number
  overallScore?: number | null
  durationSeconds: number
  finishedAt?: string | null
}

export interface RecordListResult {
  stats: { total: number; averageScore: number; maxScore: number; totalSeconds: number }
  list: RecordListItem[]
  total: number
  pageNum: number
  pageSize: number
}

export interface ReplayMessage {
  seq: number
  role: 'ai' | 'user'
  content: string
  score?: number | null
  aiComment?: string | null
  timedOut?: boolean | null
  at?: string | null
}

export interface ReplayResult {
  id: number
  subjectName: string
  difficulty: DifficultyApi
  finishedAt?: string | null
  overallScore?: number | null
  messages: ReplayMessage[]
}

/** 面试配置页数据（方向/难度/题量/超时/今日剩余配额） */
export function fetchConfigMeta(): Promise<ConfigMeta> {
  return request.get('/interviews/config-meta')
}

/** 发起面试（S1 发起即计配额；S11 一次下发全部题干） */
export function startInterview(payload: StartInterviewPayload): Promise<StartInterviewResult> {
  return request.post('/interviews', payload)
}

/** 提交逐题作答（AI 评分；失败 503 可重试） */
export function submitInterviewAnswer(
  recordId: number,
  payload: AnswerSubmitPayload,
): Promise<AnswerSubmitResult> {
  return request.post(`/interviews/${recordId}/answers`, payload)
}

/** 结束并生成报告（endRemark 仅全部答完场景，S21） */
export function finishInterview(recordId: number, graceful = false): Promise<FinishResult> {
  return request.post(`/interviews/${recordId}/finish`, { graceful })
}

/** 面试报告 */
export function fetchInterviewReport(recordId: number): Promise<InterviewReport> {
  return request.get(`/interviews/${recordId}/report`)
}

/** 面试记录列表 + 统计卡 */
export function fetchInterviewRecords(params: {
  pageNum?: number
  pageSize?: number
}): Promise<RecordListResult> {
  return request.get('/interviews', { params })
}

/** 面试回放（S12 逐题问答快照） */
export function fetchInterviewReplay(recordId: number): Promise<ReplayResult> {
  return request.get(`/interviews/${recordId}`)
}
