/**
 * 错题本接口封装（04 §3.3 #22-28）。
 * 重做判分复用 /practice/answers（scene=wrongReview，见 api/practice.ts）。
 */
import request from './request'

export type WrongLevel = 'highFreq' | 'multiple' | 'occasional'
export type MasteryStatusApi = 'reviewing' | 'mastered'
export type QuestionTypeApi = 'single' | 'multiple' | 'judge' | 'short'
/** 作答快照形态（03 附录 A）：单/多选=选项键数组、判断=bool、简答=文本 */
export type AnswerValue = string[] | boolean | string

export interface WrongCategory {
  stageName: string
  subjectName: string
}

export interface WrongTop3Item {
  id: number
  questionId: number
  content: string
  wrongCount: number
}

export interface WrongStats {
  total: number
  reviewing: number
  mastered: number
  masteryRate: number
  top3: WrongTop3Item[]
  categories: WrongCategory[]
}

export interface WrongListItem {
  id: number
  questionId: number
  content: string
  type: QuestionTypeApi
  level: WrongLevel
  corrected: number
  masteryStatus: MasteryStatusApi
  lastWrongAt: string
  wrongCount: number
  myAnswer: AnswerValue | null
  rightAnswer: AnswerValue | null
  category: WrongCategory
}

export interface WrongListResult {
  list: WrongListItem[]
  total: number
  pageNum: number
  pageSize: number
}

export interface WrongListQuery {
  mastery?: 'all' | 'reviewing' | 'mastered'
  category?: string
  keyword?: string
  timeRange?: 'all' | '7d' | '30d'
  sort?: 'lastWrongAt' | 'wrongCount'
  pageNum?: number
  pageSize?: number
}

export interface ReviewSetItem {
  id: number // 错题 id
  questionId: number
  content: string
  type: QuestionTypeApi
  options?: { key: string; content: string }[] | null // 仅单选/多选
  myAnswer: AnswerValue | null
  rightAnswer: AnswerValue | null
  wrongCount: number
  corrected: number
  level: WrongLevel
  analysis?: string | null
}

export interface ReviewSet {
  questions: ReviewSetItem[]
}

/** 统计卡 + Top3 + 分类下拉 */
export function fetchWrongStats(): Promise<WrongStats> {
  return request.get('/wrong-questions/stats')
}

/** 错题列表（筛选/排序/分页） */
export function fetchWrongList(params: WrongListQuery): Promise<WrongListResult> {
  return request.get('/wrong-questions', { params })
}

/** 重做题目集（默认待复习） */
export function fetchReviewSet(mastery: 'all' | 'reviewing' | 'mastered' = 'reviewing'): Promise<ReviewSet> {
  return request.post('/wrong-questions/review-set', { mastery })
}

/** 标记已掌握（幂等，掌握单向） */
export function masterWrong(id: number): Promise<{ success: boolean }> {
  return request.post(`/wrong-questions/${id}/master`)
}

/** 移除错题（逻辑删除，再答错复活） */
export function removeWrong(id: number): Promise<{ success: boolean }> {
  return request.delete(`/wrong-questions/${id}`)
}

/** 批量标记已掌握 */
export function batchMasterWrong(ids: number[]): Promise<{ success: boolean; affected: number; skipped?: number[] }> {
  return request.post('/wrong-questions/batch-master', { ids })
}

/** 批量移除 */
export function batchRemoveWrong(ids: number[]): Promise<{ success: boolean; affected: number; skipped?: number[] }> {
  return request.post('/wrong-questions/batch-remove', { ids })
}
