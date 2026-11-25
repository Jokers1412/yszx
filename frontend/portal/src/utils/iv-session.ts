/**
 * AI 面试本地会话（02 D7 / 需求 3.8.2 会话持久化）。
 * 答题进度、消息、当前题号、用时、得分列表存 localStorage；退出可续做（S22）。
 */
import type { DifficultyApi } from '@/api/interview'

export interface IvMessage {
  kind: 'opening' | 'question' | 'user' | 'feedback' | 'closing'
  role: 'ai' | 'me'
  seq?: number // 题号 1..N（question/user/feedback）
  text: string
  score?: number // feedback：0-10
  timedOut?: boolean // user：超时提交
  t: string // HH:mm 展示时间
}

export interface IvSession {
  recordId: number
  config: {
    subjectId: number
    subjectName: string
    difficulty: DifficultyApi
    difficultyName: string
    count: number
    timeoutSeconds: number
  }
  questions: { seq: number; questionText: string }[]
  messages: IvMessage[]
  currentQ: number // 当前题下标（0 起，= 已答数）
  answered: number
  elapsed: number // 已用秒
  scores: Record<number, number> // seq → 得分
  pendingSeq: number | null // 崩溃时正在评分的题号
  questionStartedAt: number | null // 当前题开始时刻（epoch ms，5 分钟超时）
  finished: boolean
  voiceOn: boolean
}

export const IV_SESSION_KEY = 'yszx_iv_session'

export function saveIvSession(s: IvSession) {
  try {
    localStorage.setItem(IV_SESSION_KEY, JSON.stringify(s))
  } catch {
    /* 存储满/隐私模式忽略 */
  }
}

export function loadIvSession(): IvSession | null {
  try {
    const raw = JSON.parse(localStorage.getItem(IV_SESSION_KEY) || 'null')
    if (!raw || typeof raw !== 'object' || !Array.isArray(raw.questions) || !raw.questions.length) {
      return null
    }
    return {
      recordId: Number(raw.recordId),
      config: raw.config,
      questions: raw.questions,
      messages: Array.isArray(raw.messages) ? raw.messages : [],
      currentQ: Number(raw.currentQ) || 0,
      answered: Number(raw.answered) || 0,
      elapsed: Number(raw.elapsed) || 0,
      scores: (raw.scores ?? {}) as Record<number, number>,
      pendingSeq: raw.pendingSeq ?? null,
      questionStartedAt: raw.questionStartedAt ?? null,
      finished: !!raw.finished,
      voiceOn: raw.voiceOn !== false,
    }
  } catch {
    return null
  }
}

export function clearIvSession() {
  localStorage.removeItem(IV_SESSION_KEY)
}

/** 当前时刻 HH:mm */
export function nowHM(): string {
  const d = new Date()
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

/** 开场白（AI 面试官自我介绍，配置页与会话页共用） */
export function buildOpening(subjectName: string, difficultyName: string, count: number): IvMessage {
  return {
    kind: 'opening',
    role: 'ai',
    text:
      `你好，我是你的 AI 面试官。本次为「${subjectName} · ${difficultyName}」模拟面试，` +
      `共 ${count} 题，每题回答限时 5 分钟。我会根据你的回答给出评分与建议，放轻松，我们开始吧！`,
    t: nowHM(),
  }
}

/** 由发起结果构建新会话（配置页/重新开始/再来一次共用） */
export function createIvSession(
  res: {
    recordId: number
    questions: { seq: number; questionText: string }[]
    timeoutSeconds: number
  },
  config: IvSession['config'],
  voiceOn = true,
): IvSession {
  return {
    recordId: res.recordId,
    config,
    questions: res.questions,
    messages: [buildOpening(config.subjectName, config.difficultyName, config.count)],
    currentQ: 0,
    answered: 0,
    elapsed: 0,
    scores: {},
    pendingSeq: null,
    questionStartedAt: null,
    finished: false,
    voiceOn,
  }
}

/** 时:分:秒 */
export function fmtClock(sec: number): string {
  const p = (n: number) => n.toString().padStart(2, '0')
  return `${p(Math.floor(sec / 3600))}:${p(Math.floor((sec % 3600) / 60))}:${p(sec % 60)}`
}

/** 「12 分 30 秒」 */
export function fmtHumanDur(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return m > 0 ? `${m} 分 ${s ? `${s} 秒` : ''}` : `${s} 秒`
}
