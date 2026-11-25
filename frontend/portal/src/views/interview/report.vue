<script setup lang="ts">
/**
 * 面试报告（prototype/portal/interview-report.html，需求 3.8.3 / 04 §3.4 #37）。
 * 综合评分环形图 + 明细 + 相比上次（同方向上一场）；六维能力分级着色；
 * 优缺点 / 改进建议 / 能力提升三卡（coaching 文案）；查看面试回放（S12 逐题快照）。
 */
import { nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import {
  fetchInterviewReplay,
  fetchInterviewReport,
  startInterview,
  type DifficultyApi,
  type InterviewReport,
  type ReplayResult,
} from '@/api/interview'
import { clearIvSession, createIvSession, saveIvSession } from '@/utils/iv-session'
import { animateNumber } from '@/utils/anim'
import type { ApiError } from '@shared/types/api'

const route = useRoute()
const router = useRouter()

const DIFF_LABEL: Record<DifficultyApi, string> = { easy: '简单', medium: '中等', hard: '困难' }
const DIM_KEYS = ['专业基础', '表达沟通', '逻辑思维', '项目经验', '应变能力', '岗位匹配']

const report = ref<InterviewReport | null>(null)
const ringNum = ref<HTMLElement | null>(null)
const replayVisible = ref(false)
const replay = ref<ReplayResult | null>(null)
const starting = ref(false) // 「再来一次」防连点（发起即计配额 S1）

const recordId = Number(route.params.id)

function scoreClass(s: number) {
  return s >= 8 ? 'score-green' : s >= 6 ? 'score-orange' : 'score-red'
}
function ringColor(score: number) {
  return score >= 80 ? 'var(--success)' : score >= 60 ? 'var(--warning)' : 'var(--danger)'
}
function dotCls(score: number) {
  return score >= 80 ? 'score-high' : score >= 60 ? 'score-mid' : 'score-low'
}

async function load() {
  try {
    report.value = await fetchInterviewReport(recordId)
    await nextTick() // v-if="report" 渲染后再跑数字动画
    if (ringNum.value) {
      animateNumber(ringNum.value, Math.round(report.value.overallScore))
    }
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '报告加载失败')
  }
}

async function openReplay() {
  try {
    replay.value = await fetchInterviewReplay(recordId)
    replayVisible.value = true
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '回放加载失败')
  }
}

/** 回放按题聚合成 Q/作答/评分行（S12 快照重建） */
function replayRows() {
  const bySeq = new Map<
    number,
    { question: string; answer: string; score?: number | null; aiComment?: string | null }
  >()
  for (const m of replay.value?.messages ?? []) {
    const row = bySeq.get(m.seq) ?? { question: '', answer: '' }
    if (m.role === 'ai') row.question = m.content
    else {
      row.answer = m.content
      row.score = m.score
      row.aiComment = m.aiComment
    }
    bySeq.set(m.seq, row)
  }
  return [...bySeq.entries()].sort((a, b) => a[0] - b[0])
}

async function goAgain() {
  const r = report.value
  if (!r || starting.value) return
  starting.value = true
  try {
    const res = await startInterview({
      subjectId: r.subjectId,
      difficulty: r.difficulty,
      questionCount: r.questionCount,
    })
    const session = createIvSession(res, {
      subjectId: r.subjectId,
      subjectName: r.subjectName,
      difficulty: r.difficulty,
      difficultyName: DIFF_LABEL[r.difficulty],
      count: r.questionCount,
      timeoutSeconds: res.timeoutSeconds,
    })
    clearIvSession()
    saveIvSession(session)
    router.push({ name: 'interviewSession' })
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '发起面试失败，请稍后重试')
    starting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="container rpt-page">
    <template v-if="report">
      <!-- 报告头 -->
      <div class="report-head">
        <div>
          <h1 class="rpt-title">AI 模拟面试报告</h1>
          <div class="rh-meta">
            {{ report.subjectName }} · {{ DIFF_LABEL[report.difficulty] }} · 面试时间 {{ report.finishedAt }}
          </div>
        </div>
        <button class="btn btn-ghost" type="button" @click="router.push({ name: 'interviewRecords' })">
          🎙️ 面试记录
        </button>
      </div>

      <!-- 总分区 -->
      <div class="card mb-16">
        <div class="score-zone">
          <div class="report-score-ring">
            <svg viewBox="0 0 168 168" width="168" height="168">
              <circle cx="84" cy="84" r="70" fill="none" stroke="var(--line)" stroke-width="12"></circle>
              <circle
                cx="84"
                cy="84"
                r="70"
                fill="none"
                :stroke="ringColor(report.overallScore)"
                stroke-width="12"
                stroke-linecap="round"
                transform="rotate(-90 84 84)"
                :stroke-dasharray="`${(2 * Math.PI * 70 * report.overallScore) / 100} ${2 * Math.PI * 70}`"
              ></circle>
            </svg>
            <div class="ring-value">
              <div ref="ringNum" class="ring-num-txt">0</div>
              <div class="ring-sub">综合评分 / 100</div>
            </div>
          </div>
          <div class="score-detail">
            <div class="sd-item">
              <div class="sd-label">回答准确度</div>
              <div class="sd-value">{{ report.accuracyRate }}%</div>
            </div>
            <div class="sd-item">
              <div class="sd-label">面试时长</div>
              <div class="sd-value">
                {{ Math.floor(report.durationSeconds / 60) }} 分 {{ report.durationSeconds % 60 }} 秒
              </div>
            </div>
            <div class="sd-item">
              <div class="sd-label">答题数量</div>
              <div class="sd-value">{{ report.answeredCount }} 题</div>
            </div>
            <div>
              <div class="sd-label mb-8">同方向历史成绩对比</div>
              <span
                v-if="report.comparedToLast"
                class="trend-badge"
                :class="{
                  'trend-up': report.comparedToLast.trend === 'up',
                  'trend-down': report.comparedToLast.trend === 'down',
                  'trend-flat': report.comparedToLast.trend === 'flat',
                }"
              >
                相比上次 {{ report.comparedToLast.delta > 0 ? '+' : '' }}{{ report.comparedToLast.delta }}（{{
                  { up: '提升', down: '下降', flat: '持平' }[report.comparedToLast.trend]
                }}）
              </span>
              <div v-else class="pc-tip">暂无同方向历史成绩</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 能力分析 -->
      <div class="card mb-16">
        <div class="card-header">
          <h3>能力分析</h3>
          <span class="muted">六维能力评估（0-10 分）</span>
        </div>
        <div class="card-body">
          <div class="dim-grid">
            <div v-for="name in DIM_KEYS" :key="name" class="dim-card">
              <div class="dim-name">{{ name }}</div>
              <div class="dim-score">{{ (report.abilityScores[name] ?? 0).toFixed(1) }}</div>
              <div class="progress">
                <div
                  class="progress-bar"
                  :class="{
                    'pb-warn': (report.abilityScores[name] ?? 0) >= 6 && (report.abilityScores[name] ?? 0) < 8,
                    'pb-danger': (report.abilityScores[name] ?? 0) < 6,
                    success: (report.abilityScores[name] ?? 0) >= 8,
                  }"
                  :style="{ width: (report.abilityScores[name] ?? 0) * 10 + '%' }"
                ></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 优缺点 -->
      <div class="pros-cons mb-16">
        <div class="card">
          <div class="card-header">
            <h3>优点</h3>
            <span class="badge badge-green">表现较好</span>
          </div>
          <div class="card-body">
            <div v-for="(s, i) in report.strengths" :key="i" class="pc-item pc-good">
              <span class="pc-icon">✓</span>
              <div>{{ s }}</div>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-header">
            <h3>待提升</h3>
            <span class="badge badge-orange">重点改进</span>
          </div>
          <div class="card-body">
            <div v-for="(it, i) in report.improvements" :key="i" class="pc-item pc-bad">
              <span class="pc-icon">▲</span>
              <div>
                <div>{{ it.issue }}</div>
                <div class="pc-tip">{{ it.advice }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 改进建议 -->
      <div class="card mb-16">
        <div class="card-header"><h3>改进建议</h3></div>
        <div class="card-body">
          <ol class="advice-list">
            <li v-for="(s, i) in report.suggestions" :key="i">
              <span class="adv-no">{{ i + 1 }}</span>
              <span>{{ s }}</span>
            </li>
          </ol>
        </div>
      </div>

      <!-- 能力提升建议 -->
      <div class="card mb-16">
        <div class="card-header"><h3>能力提升建议</h3></div>
        <div class="card-body">
          <div class="suggest-grid">
            <div class="suggest-card">
              <div class="sg-icon">📚</div>
              <h3>推荐题目</h3>
              <p class="text-2 mb-0">{{ report.coaching.questions }}</p>
            </div>
            <div class="suggest-card">
              <div class="sg-icon">🎬</div>
              <h3>推荐课程</h3>
              <p class="text-2 mb-0">{{ report.coaching.courses }}</p>
            </div>
            <div class="suggest-card">
              <div class="sg-icon">🎙️</div>
              <h3>推荐再次面试</h3>
              <p class="text-2">{{ report.coaching.reinterview }}</p>
              <button class="btn btn-primary" type="button" :disabled="starting" @click="goAgain">再来一次</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 操作 -->
      <div class="report-actions">
        <button class="btn btn-lg" type="button" @click="router.push({ name: 'interviewRecords' })">
          查看历史记录
        </button>
        <button class="btn btn-primary btn-lg" type="button" :disabled="starting" @click="goAgain">再来一次</button>
        <button class="btn btn-lg" type="button" @click="openReplay">查看面试回放</button>
      </div>
    </template>

    <!-- 回放弹窗（S12 问答时间线） -->
    <div v-if="replayVisible" class="modal-overlay" @click.self="replayVisible = false">
      <div class="modal modal-lg">
        <div class="modal-header">
          <h3>面试回放 · 问答时间线</h3>
          <button class="modal-close" type="button" @click="replayVisible = false">×</button>
        </div>
        <div class="modal-body replay-list">
          <div v-for="[seq, row] in replayRows()" :key="seq" class="replay-item">
            <div class="rp-q">Q{{ seq }} · {{ row.question }}</div>
            <div class="rp-a">我的回答：{{ row.answer || '（未作答）' }}</div>
            <div class="rp-fb">
              AI 评分：{{
                row.score !== undefined && row.score !== null
                  ? `${row.score} 分 · ${row.aiComment ?? ''}`
                  : '—'
              }}
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn" type="button" @click="replayVisible = false">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rpt-page {
  padding: 24px 24px 64px;
}
.report-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.rpt-title {
  margin-bottom: 4px;
}
.rh-meta {
  color: var(--ink-3);
  font-size: 13px;
}
.mb-16 {
  margin-bottom: 16px;
}
.mb-8 {
  margin-bottom: 8px;
}
.score-zone {
  display: flex;
  gap: 32px;
  align-items: center;
  flex-wrap: wrap;
  padding: 28px 24px;
}
.score-detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 240px;
}
.sd-item .sd-label {
  font-size: 12px;
  color: var(--ink-3);
}
.sd-item .sd-value {
  font-size: 22px;
  font-weight: 700;
}
.ring-num-txt {
  font-size: 38px;
  font-weight: 700;
  line-height: 1;
}
.ring-sub {
  font-size: 12px;
  color: var(--ink-3);
}
.report-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin: 28px 0 8px;
  flex-wrap: wrap;
}
.text-2 {
  color: var(--ink-2);
}
.mb-0 {
  margin-bottom: 0;
}
</style>
