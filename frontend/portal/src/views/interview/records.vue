<script setup lang="ts">
/**
 * 面试记录（prototype/portal/interview-records.html，需求 3.8.4 / 04 §3.4 #38）。
 * 统计卡（总次数/平均分/最高分/累计时长）+ 记录列表（得分圆点配色）+ 分页；
 * 「查看报告」进报告页，「再来一次」按该场配置直接再开一场（S1 发起即计配额）。
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import {
  fetchInterviewRecords,
  startInterview,
  type DifficultyApi,
  type RecordListResult,
} from '@/api/interview'
import { clearIvSession, createIvSession, fmtHumanDur, saveIvSession } from '@/utils/iv-session'
import type { ApiError } from '@shared/types/api'

const router = useRouter()

const DIFF_LABEL: Record<DifficultyApi, string> = { easy: '简单', medium: '中等', hard: '困难' }
const DIFF_BADGE: Record<DifficultyApi, string> = {
  easy: 'badge-green',
  medium: 'badge-blue',
  hard: 'badge-orange',
}

const data = ref<RecordListResult | null>(null)
const pageNum = ref(1)
const pageSize = ref(5)
const loading = ref(false)
const againId = ref<number | null>(null)

function totalPages() {
  return Math.max(1, Math.ceil((data.value?.total ?? 0) / pageSize.value))
}
function dotCls(score: number | null | undefined) {
  const s = score ?? 0
  return s >= 80 ? 'score-high' : s >= 60 ? 'score-mid' : 'score-low'
}

async function load() {
  loading.value = true
  try {
    data.value = await fetchInterviewRecords({ pageNum: pageNum.value, pageSize: pageSize.value })
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '记录加载失败')
  } finally {
    loading.value = false
  }
}
function changePage(p: number) {
  pageNum.value = p
  load()
}

async function goAgain(item: RecordListResult['list'][number]) {
  if (againId.value) return
  againId.value = item.id
  try {
    const res = await startInterview({
      subjectId: item.subjectId,
      difficulty: item.difficulty,
      questionCount: item.questionCount,
    })
    const session = createIvSession(res, {
      subjectId: item.subjectId,
      subjectName: item.subjectName,
      difficulty: item.difficulty,
      difficultyName: DIFF_LABEL[item.difficulty],
      count: item.questionCount,
      timeoutSeconds: res.timeoutSeconds,
    })
    clearIvSession()
    saveIvSession(session)
    router.push({ name: 'interviewSession' })
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '发起面试失败，请稍后重试')
  } finally {
    againId.value = null
  }
}

onMounted(load)
</script>

<template>
  <div class="container rec-page">
    <div class="flex-between mb-16 rec-head">
      <div>
        <h1 class="rec-h1">面试记录</h1>
        <div class="muted">回顾历次 AI 模拟面试成绩，随时再开一场</div>
      </div>
      <button class="btn btn-primary" type="button" @click="router.push({ name: 'interviewConfig' })">
        开始AI面试
      </button>
    </div>

    <!-- 统计卡 -->
    <div v-if="data" class="stat-grid">
      <div class="card stat-card">
        <div class="stat-label">面试总次数</div>
        <div class="stat-value">{{ data.stats.total }}</div>
        <div class="stat-sub">累计 AI 模拟面试场次</div>
      </div>
      <div class="card stat-card">
        <div class="stat-label">平均分数</div>
        <div class="stat-value">{{ data.stats.averageScore }}</div>
        <div class="stat-sub">综合评分均值（百分制）</div>
      </div>
      <div class="card stat-card">
        <div class="stat-label">最高分数</div>
        <div class="stat-value">{{ data.stats.maxScore }}</div>
        <div class="stat-sub">历史最佳成绩</div>
      </div>
      <div class="card stat-card">
        <div class="stat-label">累计时长</div>
        <div class="stat-value">{{ (data.stats.totalSeconds / 3600).toFixed(1) }} 小时</div>
        <div class="stat-sub">全部面试用时合计</div>
      </div>
    </div>

    <!-- 记录列表 -->
    <div class="card">
      <div class="card-header">
        <h3>全部记录</h3>
        <span class="muted">共 {{ data?.total ?? 0 }} 条</span>
      </div>
      <div class="card-body">
        <div v-loading="loading" class="rec-list">
          <div v-for="r in data?.list ?? []" :key="r.id" class="list-row">
            <div class="score-dot" :class="dotCls(r.overallScore)">{{ r.overallScore ?? '—' }}</div>
            <div class="rec-main">
              <div class="rec-title">{{ r.subjectName }} · {{ DIFF_LABEL[r.difficulty] }}</div>
              <div class="rec-meta">
                <span>🕒 {{ r.finishedAt }}</span>
                <span>⏱ {{ fmtHumanDur(r.durationSeconds) }}</span>
                <span>📝 {{ r.questionCount }} 题</span>
                <span class="badge" :class="DIFF_BADGE[r.difficulty]">{{ DIFF_LABEL[r.difficulty] }}</span>
              </div>
            </div>
            <div class="rec-actions">
              <button
                class="btn btn-sm"
                type="button"
                @click="router.push({ name: 'interviewReport', params: { id: r.id } })"
              >
                查看报告
              </button>
              <button class="btn btn-primary btn-sm" type="button" :disabled="againId === r.id" @click="goAgain(r)">
                再来一次
              </button>
            </div>
          </div>

          <div v-if="!loading && !data?.list.length" class="empty-state">
            <div class="empty-icon">🎙️</div>
            <div class="empty-title">暂无面试记录</div>
            <div class="empty-sub">完成一次 AI 模拟面试后，记录会出现在这里</div>
            <button class="btn btn-primary mt-16" type="button" @click="router.push({ name: 'interviewConfig' })">
              开始AI面试
            </button>
          </div>
        </div>
      </div>
      <div v-if="(data?.total ?? 0) > pageSize" class="card-footer">
        <div class="pagination">
          <span class="pg-info">共 {{ data?.total }} 条 · 第 {{ pageNum }}/{{ totalPages() }} 页</span>
          <button class="pg-btn" type="button" :disabled="pageNum <= 1" @click="changePage(pageNum - 1)">
            上一页
          </button>
          <button class="pg-btn" type="button" :disabled="pageNum >= totalPages()" @click="changePage(pageNum + 1)">
            下一页
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rec-page {
  padding: 24px 24px 64px;
}
.rec-head {
  flex-wrap: wrap;
  gap: 12px;
}
.rec-h1 {
  margin-bottom: 4px;
}
.mb-16 {
  margin-bottom: 16px;
}
.mt-16 {
  margin-top: 16px;
}
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.rec-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.rec-main {
  flex: 1;
  min-width: 0;
}
.rec-title {
  font-weight: 600;
  font-size: 14px;
}
.rec-meta {
  font-size: 12px;
  color: var(--ink-3);
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 2px;
  align-items: center;
}
.rec-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
@media (max-width: 900px) {
  .stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
