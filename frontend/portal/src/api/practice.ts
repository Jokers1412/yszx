/**
 * 刷题练习接口封装（04 §3.3 #20-21）。
 * 出题一次下发全部题干、不含答案（防作弊）；判分结果客观题/简答两形态。
 */
import request from './request'

export type PracticeMode = 'sequential' | 'random' | 'single'
export type PracticeScene = 'practice' | 'wrongReview'
export type QuestionTypeApi = 'single' | 'multiple' | 'judge' | 'short'
export type DifficultyApi = 'easy' | 'medium' | 'hard'

export interface PaperOption {
  key: string
  content: string
}

export interface PaperQuestion {
  id: number
  seq: number
  content: string
  type: QuestionTypeApi
  difficulty: DifficultyApi
  options?: PaperOption[] | null
}

export interface PracticePaper {
  questions: PaperQuestion[]
}

export interface PaperPayload {
  mode: PracticeMode
  stageId?: number
  questionId?: number
  count?: number
}

/** 作答内容：单/多选=选项键数组、判断=bool、简答=文本 */
export type PracticeAnswerValue = string[] | boolean | string

export interface SubmitAnswerPayload {
  questionId: number
  scene: PracticeScene
  answer: PracticeAnswerValue
}

export interface AiGrade {
  score: number
  comment: string
  keyPoints: string[]
}

export interface ObjectiveGradeResult {
  isCorrect: boolean
  correctAnswer: string[] | boolean
  analysis?: string | null
}

export interface ShortGradeResult {
  isCorrect: boolean
  aiGrade: AiGrade
  referenceAnswer?: string | null
}

export type SubmitAnswerResult = ObjectiveGradeResult | ShortGradeResult

/** 练习出题（一次下发全部题干） */
export function fetchPaper(payload: PaperPayload): Promise<PracticePaper> {
  return request.post('/practice/paper', payload)
}

/** 提交作答判分（简答 AI 批改失败 503 SYS_AI_UNAVAILABLE 可重试） */
export function submitPracticeAnswer(payload: SubmitAnswerPayload): Promise<SubmitAnswerResult> {
  return request.post('/practice/answers', payload)
}
