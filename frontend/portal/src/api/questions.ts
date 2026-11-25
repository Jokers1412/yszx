/**
 * 题库中心接口封装（04 §3.3 #16-19）。
 * 列表不含正确答案（防作弊）；查看解析走题目详情（含正确答案+解析）。
 */
import request from './request'

export interface SubjectCard {
  id: number
  name: string
  icon?: string | null
  description?: string | null
  themeColor?: string | null
  stageCount: number
}

export interface StageItem {
  id: number
  name: string
  icon?: string | null
  questionCount: number
}

export interface SubjectDetail {
  id: number
  name: string
  icon?: string | null
  description?: string | null
  stageCount: number
  stages: StageItem[]
}

export type QuestionTypeApi = 'single' | 'multiple' | 'judge' | 'short'
export type DifficultyApi = 'easy' | 'medium' | 'hard'

export interface QuestionListItem {
  id: number
  seq: number
  content: string
  type: QuestionTypeApi
  difficulty: DifficultyApi
  stageName: string
  answeredUsers: number
  accuracy: number
  tags: string[]
  hasAnalysis: boolean
}

export interface QuestionListResult {
  list: QuestionListItem[]
  total: number
  pageNum: number
  pageSize: number
}

export interface QuestionOptionOut {
  key: string
  content: string
  isCorrect: boolean
}

export interface QuestionDetail {
  id: number
  content: string
  type: QuestionTypeApi
  difficulty: DifficultyApi
  tags: string[]
  options?: QuestionOptionOut[] | null
  judgeAnswer?: boolean | null
  referenceAnswer?: string | null
  analysis?: string | null
  stageName: string
  answeredUsers: number
  accuracy: number
}

export interface StageQuestionQuery {
  type?: QuestionTypeApi | ''
  difficulty?: DifficultyApi | ''
  keyword?: string
  pageNum?: number
  pageSize?: number
}

/** 学科列表（题库中心左栏，含「其他学科」） */
export function fetchSubjects(): Promise<SubjectCard[]> {
  return request.get('/subjects')
}

/** 学科信息头 + 阶段列表（questionCount 限已上架） */
export function fetchSubjectDetail(id: number): Promise<SubjectDetail> {
  return request.get(`/subjects/${id}`)
}

/** 阶段题目列表（筛选/分页） */
export function fetchStageQuestions(
  stageId: number,
  params: StageQuestionQuery,
): Promise<QuestionListResult> {
  return request.get(`/stages/${stageId}/questions`, { params })
}

/** 题目详情（查看解析） */
export function fetchQuestionDetail(id: number): Promise<QuestionDetail> {
  return request.get(`/questions/${id}`)
}
