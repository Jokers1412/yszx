<script setup lang="ts">
/**
 * 刷题练习（prototype/portal/practice.html，需求 3.5 / 04 §3.3 #20-21）。
 * 入口：?stage= 阶段练习 / ?q= 单题练习 / ?mode=random 随机 10 题预选 / 无参 全部题目。
 * 进入先弹模式选择（顺序/随机，✕/Esc 放弃返回题库）；本地会话 yszx_practice 续做；
 * 答题卡跳题、计时、快捷键 ← → Enter ?；简答 AI 批改（≥6 分通过）；结束练习三分支。
 * 已批改不可修改由前端会话控制（服务端允许重复作答，04 §3.3）。
 */
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  fetchPaper,
  submitPracticeAnswer,
  type AiGrade,
  type DifficultyApi,
  type PaperQuestion,
  type PracticeAnswerValue,
  type PracticeMode,
  type QuestionTypeApi,
  type SubmitAnswerResult,
} from '@/api/practice'
import { fetchQuestionDetail, fetchSubjectDetail, fetchSubjects } from '@/api/questions'
import type { ApiError } from '@shared/types/api'

const route = useRoute()
const router = useRouter()

const TYPE_LABEL: Record<QuestionTypeApi, string> = {
  single: '单选',
  multiple: '多选',
  judge: '判断',
  short: '简答',
}
const DIFF_LABEL: Record<DifficultyApi, string> = { easy: '简单', medium: '中等', hard: '困难' }
const DIFF_BADGE: Record<DifficultyApi, string> = {
  easy: 'badge-green',
  medium: 'badge-orange',
  hard: 'badge-red',
}
/** 判断题固定选项（服务端不下发选项行，作答为 bool） */
const JUDGE_OPTIONS = [
  { key: 'T', content: '正确' },
  { key: 'F', content: '错误' },
]

// ===================== 入口范围 =====================
interface EntryScope {
  kind: 'stage' | 'question' | 'all'
  stageId: number
  questionId: number
  title: string
  stageCount: number // 阶段已上架题量（随机练习=全部打乱时作为 count）
  preferRandom: boolean
}
const entry = reactive<EntryScope>({
  kind: 'all',
  stageId: 0,
  questionId: 0,
  title: '全部题目',
  stageCount: 0,
  preferRandom: false,
})

// ===================== 练习会话（localStorage 持久化） =====================
interface ObjectiveResult {
  kind: 'objective'
  isCorrect: boolean
  correctAnswer: string[] | boolean
  analysis?: string | null
}
interface ShortResult {
  kind: 'short'
  isCorrect: boolean
  grade: AiGrade
  referenceAnswer?: string | null
}
type QuestionResult = ObjectiveResult | ShortResult

interface PracticeSession {
  questions: PaperQuestion[]
  current: number
  answers: Record<number, PracticeAnswerValue>
  graded: Record<number, boolean>
  results: Record<number, QuestionResult>
  elapsed: number
  mode: PracticeMode
  title: string
}

const SESSION_KEY = 'yszx_practice'
const session = ref<PracticeSession | null>(null)
const grading = reactive<Record<number, boolean>>({}) // AI 批改中（不持久化）
let timerHandle: number | undefined

const modeVisible = ref(false)
const resumeVisible = ref(false)
const shortcutVisible = ref(false)

const curQ = computed<PaperQuestion | null>(() => {
  const s = session.value
  return s ? s.questions[s.current] ?? null : null
})
const isLast = computed(() => {
  const s = session.value
  return !!s && s.current >= s.questions.length - 1
})

// ===================== 会话持久化 =====================
function save() {
  try {
    if (session.value) localStorage.setItem(SESSION_KEY, JSON.stringify(session.value))
  } catch {
    /* 存储满/隐私模式忽略 */
  }
}
function loadSaved(): unknown {
  try {
    return JSON.parse(localStorage.getItem(SESSION_KEY) || 'null')
  } catch {
    return null
  }
}
function clearSaved() {
  localStorage.removeItem(SESSION_KEY)
}
function normalize(raw: unknown): PracticeSession | null {
  if (!raw || typeof raw !== 'object') return null
  const s = raw as Partial<PracticeSession>
  const questions = (Array.isArray(s.questions) ? s.questions : []).filter(
    (q) => q && typeof q.id === 'number' && typeof q.content === 'string',
  )
  if (!questions.length) return null
  return {
    questions,
    current: Math.min(Math.max(Number(s.current) || 0, 0), questions.length - 1),
    answers: (s.answers ?? {}) as PracticeSession['answers'],
    graded: (s.graded ?? {}) as PracticeSession['graded'],
    results: (s.results ?? {}) as PracticeSession['results'],
    elapsed: Number(s.elapsed) || 0,
    mode: (s.mode as PracticeMode) || 'sequential',
    title: typeof s.title === 'string' && s.title ? s.title : '练习',
  }
}

// ===================== 计时器 =====================
function pad(n: number) {
  return n < 10 ? `0${n}` : `${n}`
}
function fmtClock(sec: number) {
  return `${pad(Math.floor(sec / 3600))}:${pad(Math.floor((sec % 3600) / 60))}:${pad(sec % 60)}`
}
function startTimer() {
  stopTimer()
  timerHandle = window.setInterval(() => {
    if (!session.value) return
    session.value.elapsed += 1
    save()
  }, 1000)
}
function stopTimer() {
  if (timerHandle) {
    window.clearInterval(timerHandle)
    timerHandle = undefined
  }
}

// ===================== 作答状态辅助 =====================
function answerOf(qid: number): PracticeAnswerValue | undefined {
  return session.value?.answers[qid]
}
function isGraded(qid: number) {
  return !!session.value?.graded[qid]
}
function hasAnswer(qid: number) {
  const a = answerOf(qid)
  if (typeof a === 'boolean') return true // 判断题 false 也是有效作答
  if (Array.isArray(a)) return a.length > 0
  return typeof a === 'string' && !!a.trim()
}
function optionsOf(q: PaperQuestion) {
  return q.options?.length ? q.options : q.type === 'judge' ? JUDGE_OPTIONS : []
}
function selectedKeys(q: PaperQuestion): string[] {
  const a = answerOf(q.id)
  if (Array.isArray(a)) return a
  if (typeof a === 'boolean') return [a ? 'T' : 'F']
  return []
}
function correctKeys(q: PaperQuestion): string[] {
  const r = session.value?.results[q.id] as ObjectiveResult | undefined
  if (!r || r.kind !== 'objective') return []
  return Array.isArray(r.correctAnswer) ? r.correctAnswer : [r.correctAnswer ? 'T' : 'F']
}
function optionClass(q: PaperQuestion, key: string) {
  const cls: Record<string, boolean> = { 'opt-item': true }
  if (isGraded(q.id)) {
    cls.locked = true
    cls.correct = correctKeys(q).includes(key)
    cls.wrong = selectedKeys(q).includes(key) && !cls.correct
  } else {
    cls.selected = selectedKeys(q).includes(key)
  }
  return cls
}
function answerText(q: PaperQuestion): string {
  const keys = correctKeys(q)
  if (q.type === 'judge') return keys[0] === 'T' ? '正确' : '错误'
  return keys.join('、') || '—'
}
function cellClass(idx: number) {
  const s = session.value!
  const q = s.questions[idx]
  const cls: Record<string, boolean> = { acell: true, current: idx === s.current }
  if (s.graded[q.id]) {
    const r = s.results[q.id]
    const ok = r?.kind === 'short' ? r.grade.score >= 6 : !!r?.isCorrect
    cls.done = ok
    cls.wrong = !ok
  } else {
    cls.done = hasAnswer(q.id)
  }
  return cls
}

// ===================== 作答与提交 =====================
function pickOption(q: PaperQuestion, key: string) {
  if (isGraded(q.id) || grading[q.id] || !session.value) return
  if (q.type === 'multiple') {
    const cur = selectedKeys(q)
    const next = cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key].sort()
    session.value.answers[q.id] = next
  } else if (q.type === 'judge') {
    session.value.answers[q.id] = key === 'T' // 单选/判断互斥
  } else {
    session.value.answers[q.id] = [key]
  }
  save()
}
function onShortInput(q: PaperQuestion, text: string) {
  if (isGraded(q.id) || !session.value) return
  session.value.answers[q.id] = text
  save()
}
function payloadAnswer(q: PaperQuestion): PracticeAnswerValue {
  const a = answerOf(q.id)
  return typeof a === 'string' ? a.trim() : (a ?? '')
}
async function submitCurrent() {
  const s = session.value
  const q = curQ.value
  if (!s || !q || isGraded(q.id) || grading[q.id]) return
  if (!hasAnswer(q.id)) {
    ElMessage.warning(q.type === 'short' ? '请先输入答案' : '请先选择答案')
    return
  }
  grading[q.id] = true
  try {
    const res: SubmitAnswerResult = await submitPracticeAnswer({
      questionId: q.id,
      scene: 'practice',
      answer: payloadAnswer(q),
    })
    if ('aiGrade' in res) {
      s.results[q.id] = {
        kind: 'short',
        isCorrect: res.isCorrect,
        grade: res.aiGrade,
        referenceAnswer: res.referenceAnswer,
      }
      ElMessage({
        type: res.aiGrade.score >= 6 ? 'success' : 'warning',
        message: `AI 评分完成：${res.aiGrade.score} / 10`,
      })
    } else {
      s.results[q.id] = {
        kind: 'objective',
        isCorrect: res.isCorrect,
        correctAnswer: res.correctAnswer,
        analysis: res.analysis,
      }
    }
    s.graded[q.id] = true
    save()
  } catch (e) {
    const err = e as ApiError
    // S2：AI 失败 503 不落记录，可再次提交重试
    ElMessage.error(err?.code === 'SYS_AI_UNAVAILABLE' ? 'AI 批改暂不可用，请稍后重试' : err?.message || '提交失败，请稍后重试')
  } finally {
    grading[q.id] = false
  }
}

// ===================== 导航 =====================
function goTo(i: number) {
  const s = session.value
  if (!s || i < 0 || i >= s.questions.length) return
  s.current = i
  save()
}
function prev() {
  if (session.value && session.value.current > 0) goTo(session.value.current - 1)
}
function canLeave() {
  const q = curQ.value
  if (q && q.type === 'short' && !isGraded(q.id) && !grading[q.id]) {
    ElMessage.warning('请先提交答案再进入下一题')
    return false
  }
  return true
}
function next() {
  if (isLast.value) {
    endPractice()
    return
  }
  if (!canLeave()) return
  goTo(session.value!.current + 1)
}
function viewAnalysis() {
  const q = curQ.value
  if (!q || !isGraded(q.id)) {
    ElMessage.warning('请先提交答案')
    return
  }
  document.getElementById('result-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

// ===================== 结束练习（三分支） =====================
async function endPractice() {
  const s = session.value
  if (!s) return
  // 分支 1：存在未提交简答题 → 提示并跳到该题
  const pendingShort = s.questions.findIndex(
    (q) => q.type === 'short' && !s.graded[q.id] && !grading[q.id],
  )
  if (pendingShort >= 0) {
    ElMessage.warning('还有简答题未提交，请先完成作答')
    goTo(pendingShort)
    return
  }
  // 分支 2/3：二次确认（含「还有 N 道题未完成」分支）
  const undone = s.questions.filter((q) => !s.graded[q.id]).length
  let msg = '确定要结束本次练习吗？结束后本次进度将被清除。'
  if (undone > 0) msg += `<br>还有 ${undone} 道题未完成`
  try {
    await ElMessageBox.confirm(msg, '结束练习', {
      type: 'warning',
      confirmButtonText: '结束练习',
      cancelButtonText: '继续答题',
      dangerouslyUseHTMLString: true,
    })
  } catch {
    return
  }
  stopTimer()
  clearSaved()
  session.value = null
  ElMessage.success('练习已结束')
  router.push({ name: 'questions' })
}

// ===================== 模式选择 / 续做 =====================
async function startPractice(mode: PracticeMode) {
  try {
    const res = await fetchPaper(
      entry.kind === 'question'
        ? { mode: 'single', questionId: entry.questionId }
        : entry.kind === 'stage'
          ? {
              mode,
              stageId: entry.stageId,
              ...(mode === 'random' && entry.stageCount > 0 ? { count: entry.stageCount } : {}),
            }
          : { mode, ...(mode === 'random' ? { count: 10 } : {}) },
    )
    if (!res.questions.length) {
      ElMessage.warning(
        entry.kind === 'all' ? '题库暂无题目，题目正在录入中' : '该阶段暂无题目，题目正在录入中',
      )
      router.push({ name: 'questions' })
      return
    }
    session.value = {
      questions: res.questions,
      current: 0,
      answers: {},
      graded: {},
      results: {},
      elapsed: 0,
      mode,
      title: entry.title,
    }
    save()
    modeVisible.value = false
    resumeVisible.value = false
    startTimer()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '出题失败，请稍后重试')
  }
}
function abandonPractice() {
  modeVisible.value = false
  router.push({ name: 'questions' }) // ✕/Esc = 放弃本次练习，返回题库中心
}
function doResume() {
  const saved = normalize(loadSaved())
  resumeVisible.value = false
  if (!saved) {
    clearSaved()
    modeVisible.value = true
    return
  }
  session.value = saved
  save()
  startTimer()
  ElMessage.success('已恢复上次练习进度')
}
function doRestart() {
  clearSaved()
  resumeVisible.value = false
  modeVisible.value = true
}

// ===================== 快捷键（← → Enter ?，输入框聚焦时忽略） =====================
function onKeydown(e: KeyboardEvent) {
  if (modeVisible.value) {
    if (e.key === 'Escape') {
      e.preventDefault()
      abandonPractice()
    }
    return
  }
  if (resumeVisible.value) {
    if (e.key === 'Escape') {
      e.preventDefault()
      doResume() // Esc = 继续（保留进度）
    }
    return
  }
  if (shortcutVisible.value) {
    if (e.key === 'Escape') shortcutVisible.value = false
    return
  }
  if (!session.value) return
  const t = e.target as HTMLElement | null
  const tag = t?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || t?.isContentEditable) return

  if (e.key === 'ArrowLeft') {
    e.preventDefault()
    prev()
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    next()
  } else if (e.key === 'Enter') {
    if (t?.closest?.('button, a')) return // 避免与按钮原生回车重复触发
    e.preventDefault()
    const q = curQ.value
    if (q && !isGraded(q.id) && !grading[q.id]) {
      if (hasAnswer(q.id)) submitCurrent()
      else ElMessage.warning(q.type === 'short' ? '请先输入答案' : '请先选择答案')
    } else {
      next()
    }
  } else if (e.key === '?') {
    e.preventDefault()
    shortcutVisible.value = true
  }
}

// ===================== 启动：解析入口范围 → 续做检查 → 模式选择 =====================
onMounted(async () => {
  window.addEventListener('keydown', onKeydown)
  entry.preferRandom = route.query.mode === 'random'

  const qParam = Number(route.query.q ?? 0)
  const stageParam = Number(route.query.stage ?? 0)
  try {
    if (qParam > 0) {
      // 单题练习：取所属阶段名作标题；题目不存在/未上架 → 引导回题库
      const detail = await fetchQuestionDetail(qParam)
      entry.kind = 'question'
      entry.questionId = qParam
      entry.title = detail.stageName || '单题练习'
    } else if (stageParam > 0) {
      // 阶段练习：逐学科探测定位（契约无阶段反查接口），取阶段名与已上架题量
      let found = false
      for (const s of await fetchSubjects()) {
        const d = await fetchSubjectDetail(s.id)
        const st = d.stages.find((x) => x.id === stageParam)
        if (st) {
          entry.kind = 'stage'
          entry.stageId = stageParam
          entry.title = st.name
          entry.stageCount = st.questionCount
          found = true
          break
        }
      }
      if (!found) {
        ElMessage.error('阶段不存在或已停用')
        router.push({ name: 'questions' })
        return
      }
    }
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '题目不存在或已下架')
    router.push({ name: 'questions' })
    return
  }

  const saved = normalize(loadSaved())
  if (saved) {
    resumeVisible.value = true
  } else {
    if (loadSaved()) clearSaved()
    modeVisible.value = true
  }
})
onUnmounted(() => {
  stopTimer()
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="container pb-64">
    <div v-if="session && curQ" class="practice-layout pt-24">
      <!-- 左侧面板 -->
      <aside class="card practice-side">
        <a class="back-link" @click.prevent="router.push({ name: 'questions' })">‹ 返回题库</a>
        <h3>{{ session.title }}</h3>
        <div class="progress">
          <div
            class="progress-bar"
            :class="{ success: session.current + 1 >= session.questions.length }"
            :style="{ width: `${Math.round(((session.current + 1) / session.questions.length) * 100)}%` }"
          ></div>
        </div>
        <div class="flex-between mt-8">
          <span class="muted">当前 {{ session.current + 1 }} / {{ session.questions.length }}</span>
          <span class="muted">{{ Math.round(((session.current + 1) / session.questions.length) * 100) }}%</span>
        </div>
        <div class="side-label">已用时</div>
        <div class="practice-timer">{{ fmtClock(session.elapsed) }}</div>
        <div class="side-label">答题卡</div>
        <div class="answer-card-grid">
          <div
            v-for="(q, i) in session.questions"
            :key="q.id"
            :class="cellClass(i)"
            @click="goTo(i)"
          >
            {{ i + 1 }}
          </div>
        </div>
        <button class="btn btn-soft-danger btn-block" type="button" @click="endPractice">结束练习</button>
      </aside>

      <!-- 答题区 -->
      <section class="card question-panel">
        <div class="flex-between">
          <div class="q-type-row">
            <span class="badge badge-blue">{{ TYPE_LABEL[curQ.type] }}</span>
            <span class="badge" :class="DIFF_BADGE[curQ.difficulty]">{{ DIFF_LABEL[curQ.difficulty] }}</span>
            <span class="muted q-pos">第 {{ session.current + 1 }} / {{ session.questions.length }} 题</span>
          </div>
          <button class="btn btn-ghost btn-sm" type="button" title="快捷键帮助" @click="shortcutVisible = true">
            ？ 快捷键
          </button>
        </div>
        <div class="q-stem-lg">{{ curQ.content }}</div>

        <!-- 简答题：文本域 + 提交 / AI 评分中 / 评分卡 -->
        <template v-if="curQ.type === 'short'">
          <textarea
            class="textarea"
            :value="(answerOf(curQ.id) as string) ?? ''"
            :readonly="isGraded(curQ.id)"
            placeholder="请输入你的答案……"
            @input="onShortInput(curQ, ($event.target as HTMLTextAreaElement).value)"
          ></textarea>
          <div v-if="grading[curQ.id]" class="ai-loading mt-16">
            <span class="muted">AI 评分中</span>
            <div class="typing-indicator"><span></span><span></span><span></span></div>
          </div>
          <div v-else-if="isGraded(curQ.id) && (session.results[curQ.id] as ShortResult)?.kind === 'short'" class="mt-16">
            <div id="result-card" class="ai-grade-card">
              <div class="flex-between">
                <h4 class="gc-title">AI 评分结果</h4>
                <span
                  class="badge"
                  :class="(session.results[curQ.id] as ShortResult).grade.score >= 6 ? 'badge-green' : 'badge-red'"
                >
                  {{ (session.results[curQ.id] as ShortResult).grade.score >= 6 ? '通过' : '未通过' }}
                </span>
              </div>
              <div
                class="grade-score"
                :style="{ color: (session.results[curQ.id] as ShortResult).grade.score >= 6 ? 'var(--success-text)' : 'var(--danger-text)' }"
              >
                {{ (session.results[curQ.id] as ShortResult).grade.score }}
                <span class="muted gs-unit">/ 10</span>
              </div>
              <p class="gc-comment">评语：{{ (session.results[curQ.id] as ShortResult).grade.comment }}</p>
              <div class="gc-points">
                <strong>关键点</strong>
                <ul>
                  <li v-for="k in (session.results[curQ.id] as ShortResult).grade.keyPoints" :key="k">{{ k }}</li>
                </ul>
              </div>
              <div>
                <strong>参考答案</strong>
                <div class="gc-ref">{{ (session.results[curQ.id] as ShortResult).referenceAnswer || '见参考答案' }}</div>
              </div>
            </div>
          </div>
          <div v-else class="mt-16">
            <button class="btn btn-primary" type="button" @click="submitCurrent">提交答案</button>
          </div>
        </template>

        <!-- 选择/判断题：选项列表 + 提交 / 答案解析 -->
        <template v-else>
          <div class="opt-list">
            <div
              v-for="o in optionsOf(curQ)"
              :key="o.key"
              :class="optionClass(curQ, o.key)"
              @click="pickOption(curQ, o.key)"
            >
              <span class="opt-key">{{ o.key }}</span>
              <span>{{ o.content }}</span>
            </div>
          </div>
          <div v-if="!isGraded(curQ.id)" class="submit-row">
            <button class="btn btn-primary" type="button" @click="submitCurrent">提交答案</button>
          </div>
          <div v-else id="result-card" class="analysis-card">
            <h4>
              答案解析
              <span
                class="badge"
                :class="
                  !hasAnswer(curQ.id)
                    ? 'badge-gray'
                    : (session.results[curQ.id] as ObjectiveResult)?.isCorrect
                      ? 'badge-green'
                      : 'badge-red'
                "
              >
                {{
                  !hasAnswer(curQ.id)
                    ? '未作答'
                    : (session.results[curQ.id] as ObjectiveResult)?.isCorrect
                      ? '回答正确'
                      : '回答错误'
                }}
              </span>
            </h4>
            <p>正确答案：<strong>{{ answerText(curQ) }}</strong></p>
            <p class="an-analysis">解析：{{ (session.results[curQ.id] as ObjectiveResult)?.analysis || '暂无解析' }}</p>
          </div>
        </template>

        <!-- 底部操作 -->
        <div class="practice-footer-actions">
          <button class="btn" type="button" :disabled="session.current === 0" @click="prev">‹ 上一题</button>
          <button class="btn" type="button" @click="viewAnalysis">查看解析</button>
          <button class="btn btn-primary" type="button" @click="next">
            {{ isLast ? '完成' : '下一题 ›' }}
          </button>
        </div>
      </section>
    </div>

    <!-- 练习模式选择弹窗（仅 ✕/Esc = 放弃本次练习，data-static 口径） -->
    <div v-if="modeVisible" class="modal-overlay">
      <div class="modal">
        <div class="modal-header">
          <h3>练习模式选择</h3>
          <button class="modal-close" type="button" @click="abandonPractice">×</button>
        </div>
        <div class="modal-body">
          <p class="muted mb-16">请选择本次练习的出题方式</p>
          <div class="mode-grid">
            <div class="mode-card" @click="startPractice('sequential')">
              <div class="mc-icon">📖</div>
              <div class="mc-name">顺序练习</div>
              <div class="mc-desc">按题库顺序逐题作答</div>
            </div>
            <div class="mode-card" :class="{ selected: entry.preferRandom }" @click="startPractice('random')">
              <div class="mc-icon">🔀</div>
              <div class="mc-name">随机练习</div>
              <div class="mc-desc">打乱题目顺序作答</div>
            </div>
          </div>
          <p class="mode-tip">按 Esc 或点击右上角 ✕ 取消，放弃本次练习并返回题库</p>
        </div>
      </div>
    </div>

    <!-- 续做确认弹窗（✕ = 继续，保留进度；data-static 口径） -->
    <div v-if="resumeVisible" class="modal-overlay">
      <div class="modal modal-sm">
        <div class="modal-header">
          <h3>继续练习</h3>
          <button class="modal-close" type="button" @click="doResume">×</button>
        </div>
        <div class="modal-body"><p class="text-2">检测到未完成的练习，是否继续？</p></div>
        <div class="modal-footer">
          <button class="btn" type="button" @click="doRestart">重新开始</button>
          <button class="btn btn-primary" type="button" @click="doResume">继续</button>
        </div>
      </div>
    </div>

    <!-- 快捷键面板 -->
    <div v-if="shortcutVisible" class="modal-overlay" @click.self="shortcutVisible = false">
      <div class="modal modal-sm">
        <div class="modal-header">
          <h3>快捷键</h3>
          <button class="modal-close" type="button" @click="shortcutVisible = false">×</button>
        </div>
        <div class="modal-body">
          <div class="shortcut-grid">
            <span><span class="kbd">←</span></span><span>上一题</span>
            <span><span class="kbd">→</span></span><span>下一题</span>
            <span><span class="kbd">Enter</span></span><span>提交答案 / 下一题</span>
            <span><span class="kbd">?</span></span><span>显示快捷键面板</span>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-primary" type="button" @click="shortcutVisible = false">知道了</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pt-24 {
  padding-top: 24px;
}
.pb-64 {
  padding-bottom: 64px;
}
.mt-8 {
  margin-top: 8px;
}
.mt-16 {
  margin-top: 16px;
}
.mb-16 {
  margin-bottom: 16px;
}
.back-link {
  cursor: pointer;
}
.text-2 {
  color: var(--ink-2);
}
.q-pos {
  font-size: 12px;
}
.submit-row {
  margin-bottom: 22px;
}
.textarea {
  min-height: 140px;
}
.mode-tip {
  margin: 16px 0 0;
  font-size: 12px;
  color: var(--ink-3);
}
.an-analysis {
  margin: 0;
  color: var(--ink-2);
}

/* AI 评分卡排版 */
.gc-title {
  margin: 0;
}
.gs-unit {
  font-size: 14px;
  font-weight: 400;
}
.gc-comment {
  margin: 8px 0;
}
.gc-points {
  margin-bottom: 8px;
}
.gc-points ul {
  margin: 8px 0 0;
  padding-left: 20px;
}
.gc-ref {
  color: var(--ink-2);
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 10px 12px;
  margin-top: 6px;
}
</style>
