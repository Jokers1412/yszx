<script setup lang="ts">
/**
 * 题库中心（prototype/portal/questions.html，需求 3.4 / 04 §3.3 #16-19）。
 * 三级浏览：学科（左栏）→ 阶段列表 ⇄ 题目列表（右侧互斥切换）。
 * 题目卡带题型/难度徽章、N 人做过、正确率、标签；「查看解析」弹窗展示正确答案+解析
 * （列表不含答案防作弊）；「开始练习」跳刷题页（?stage= / ?q=，由练习页承接）。
 * 支持 ?stage= 深链直达题目视图（首页热门学科卡入口）。
 */
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import {
  fetchQuestionDetail,
  fetchStageQuestions,
  fetchSubjectDetail,
  fetchSubjects,
} from '@/api/questions'
import type {
  DifficultyApi,
  QuestionDetail,
  QuestionListItem,
  QuestionTypeApi,
  SubjectCard,
  SubjectDetail,
} from '@/api/questions'
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

// ===================== 状态 =====================
const subjects = ref<SubjectCard[]>([])
const subjectId = ref<number | null>(null)
const subjectDetail = ref<SubjectDetail | null>(null)
const view = ref<'stages' | 'questions'>('stages')
const stageId = ref<number | null>(null)

const filters = reactive<{ type: QuestionTypeApi | ''; difficulty: DifficultyApi | ''; keyword: string }>({
  type: '',
  difficulty: '',
  keyword: '',
})
const questions = ref<QuestionListItem[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const loading = ref(false)
let kwTimer: number | undefined

// 解析弹窗
const analyzeVisible = ref(false)
const analyzeDetail = ref<QuestionDetail | null>(null)
const analyzeLoading = ref(false)

function totalPages() {
  return Math.max(1, Math.ceil(total.value / pageSize.value))
}

function filtersActive() {
  return !!(filters.type || filters.difficulty || filters.keyword.trim())
}

function resetFilters() {
  filters.type = ''
  filters.difficulty = ''
  filters.keyword = ''
  pageNum.value = 1
}

// ===================== 数据加载 =====================
async function loadSubjects() {
  try {
    subjects.value = await fetchSubjects()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '学科加载失败')
  }
}

async function selectSubject(id: number) {
  subjectId.value = id
  view.value = 'stages'
  stageId.value = null
  resetFilters()
  try {
    subjectDetail.value = await fetchSubjectDetail(id)
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '学科加载失败')
  }
}

function openStage(id: number) {
  stageId.value = id
  view.value = 'questions'
  resetFilters()
  loadQuestions()
}

function backToStages() {
  view.value = 'stages'
  stageId.value = null
}

async function loadQuestions() {
  if (stageId.value === null) return
  loading.value = true
  try {
    const res = await fetchStageQuestions(stageId.value, {
      type: filters.type || undefined,
      difficulty: filters.difficulty || undefined,
      keyword: filters.keyword.trim() || undefined,
      pageNum: pageNum.value,
      pageSize: pageSize.value,
    })
    questions.value = res.list
    total.value = res.total
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '题目加载失败')
  } finally {
    loading.value = false
  }
}

function changePage(p: number) {
  pageNum.value = p
  loadQuestions()
}

function onFilterChange() {
  pageNum.value = 1
  loadQuestions()
}

function onKeywordInput() {
  window.clearTimeout(kwTimer)
  kwTimer = window.setTimeout(onFilterChange, 250)
}

// ===================== 查看解析 =====================
async function openAnalyze(id: number) {
  analyzeLoading.value = true
  analyzeVisible.value = true
  try {
    analyzeDetail.value = await fetchQuestionDetail(id)
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '解析加载失败')
    analyzeVisible.value = false
  } finally {
    analyzeLoading.value = false
  }
}

/** 正确答案文案（原型 answerText 口径） */
function answerText(q: QuestionDetail): string {
  if (q.type === 'short') return q.referenceAnswer || '见参考答案'
  if (q.type === 'judge') return q.judgeAnswer ? '正确' : '错误'
  return (q.options ?? [])
    .filter((o) => o.isCorrect)
    .map((o) => o.key)
    .join('、')
}

// ===================== 跳转练习页（练习页承接 ?stage= / ?q=） =====================
function startStagePractice(id: number) {
  router.push({ name: 'practice', query: { stage: id } })
}
function startQuestionPractice(id: number) {
  analyzeVisible.value = false
  router.push({ name: 'practice', query: { q: id } })
}

// ===================== 启动（支持 ?stage= 深链） =====================
onMounted(async () => {
  await loadSubjects()
  const stageParam = Number(route.query.stage ?? 0)
  if (stageParam > 0) {
    // 深链：定位阶段所属学科（契约无阶段反查接口，逐学科探测，命中即止）
    for (const s of subjects.value) {
      try {
        const d = await fetchSubjectDetail(s.id)
        if (d.stages.some((st) => st.id === stageParam)) {
          subjectId.value = s.id
          subjectDetail.value = d
          openStage(stageParam)
          return
        }
      } catch {
        /* 忽略单个学科加载失败，继续探测 */
      }
    }
  }
  if (subjects.value.length) await selectSubject(subjects.value[0].id)
})
</script>

<template>
  <div class="container qb-page">
    <div class="qb-layout">
      <!-- 左侧学科栏 -->
      <aside class="card subject-panel">
        <div
          v-for="s in subjects"
          :key="s.id"
          class="subject-item"
          :class="{ active: s.id === subjectId }"
          @click="selectSubject(s.id)"
        >
          <span class="sb-icon">{{ s.icon || '📘' }}</span>
          <span class="sb-name">{{ s.name }}</span>
          <span class="sb-count">{{ s.stageCount }}</span>
        </div>
        <div v-if="!subjects.length" class="empty-state" style="padding: 24px 8px">
          <div class="empty-sub">暂无学科</div>
        </div>
      </aside>

      <!-- 右侧：阶段列表 / 题目列表 -->
      <section v-loading="loading">
        <!-- 视图 A：阶段列表 -->
        <template v-if="view === 'stages' && subjectDetail">
          <div class="subject-head">
            <div class="sh-icon">{{ subjectDetail.icon || '📘' }}</div>
            <div>
              <h2 class="sh-name">{{ subjectDetail.name }}</h2>
              <div class="muted">{{ subjectDetail.description }}</div>
            </div>
            <div class="sh-badge"><span class="badge">共 {{ subjectDetail.stageCount }} 个阶段</span></div>
          </div>

          <div v-if="!subjectDetail.stages.length" class="card empty-state">
            <div class="empty-icon">📭</div>
            <div class="empty-title">该学科暂无阶段，题目正在录入中</div>
            <div class="empty-sub">请选择其他学科浏览</div>
          </div>
          <div v-for="st in subjectDetail.stages" v-else :key="st.id" class="stage-row">
            <div class="sr-icon">{{ st.icon || '📄' }}</div>
            <div>
              <div class="sr-name">{{ st.name }}</div>
              <div class="sr-sub">共 {{ st.questionCount }} 题</div>
            </div>
            <div class="sr-actions">
              <button class="btn btn-sm" type="button" @click="openStage(st.id)">查看题目</button>
              <button class="btn btn-primary btn-sm" type="button" @click="startStagePractice(st.id)">
                开始练习
              </button>
            </div>
          </div>
        </template>

        <!-- 视图 B：题目列表 -->
        <template v-else-if="view === 'questions'">
          <div><a class="back-link" @click.prevent="backToStages">‹ 返回阶段列表</a></div>
          <div class="breadcrumb mt-8">
            <a @click.prevent="backToStages">{{ subjectDetail?.name }}</a>
            <span class="sep">/</span>
            <span class="current">{{ subjectDetail?.stages.find((s) => s.id === stageId)?.name ?? '' }}</span>
          </div>

          <div class="q-toolbar">
            <select v-model="filters.type" class="select" @change="onFilterChange">
              <option value="">全部题型</option>
              <option value="single">单选</option>
              <option value="multiple">多选</option>
              <option value="judge">判断</option>
              <option value="short">简答</option>
            </select>
            <select v-model="filters.difficulty" class="select" @change="onFilterChange">
              <option value="">全部难度</option>
              <option value="easy">简单</option>
              <option value="medium">中等</option>
              <option value="hard">困难</option>
            </select>
            <input
              v-model="filters.keyword"
              class="input search-input"
              placeholder="搜索题干关键词"
              @input="onKeywordInput"
            />
            <span class="muted">共 {{ total }} 题</span>
          </div>

          <div v-if="!loading && !questions.length" class="card empty-state">
            <template v-if="filtersActive()">
              <div class="empty-icon">🔍</div>
              <div class="empty-title">暂无匹配的题目，试试调整筛选条件</div>
              <div class="empty-sub">可更换题型 / 难度或清空关键词</div>
            </template>
            <template v-else>
              <div class="empty-icon">📭</div>
              <div class="empty-title">该阶段暂无题目，题目正在录入中</div>
              <div class="empty-sub">题目正在录入中，敬请期待</div>
            </template>
          </div>

          <div v-for="q in questions" v-else :key="q.id" class="card question-card">
            <div class="q-meta">
              <span class="badge badge-blue">第 {{ q.seq }} 题</span>
              <span class="badge badge-blue">{{ TYPE_LABEL[q.type] }}</span>
              <span class="badge" :class="DIFF_BADGE[q.difficulty]">{{ DIFF_LABEL[q.difficulty] }}</span>
            </div>
            <div class="q-stem">{{ q.content }}</div>
            <div class="q-sub">
              <span>阶段：{{ q.stageName }}</span>
              <span>{{ q.answeredUsers }} 人做过</span>
              <span>正确率 {{ q.accuracy }}%</span>
            </div>
            <div v-if="q.tags.length" class="q-tags">
              <span v-for="t in q.tags" :key="t" class="tag">{{ t }}</span>
            </div>
            <div class="q-actions">
              <button class="btn btn-sm" type="button" @click="openAnalyze(q.id)">查看解析</button>
              <button class="btn btn-primary btn-sm" type="button" @click="startQuestionPractice(q.id)">
                开始练习
              </button>
            </div>
          </div>

          <!-- 分页 -->
          <div v-if="total > pageSize" class="pagination">
            <span class="pg-info">共 {{ total }} 题 · 第 {{ pageNum }}/{{ totalPages() }} 页</span>
            <button class="pg-btn" type="button" :disabled="pageNum <= 1" @click="changePage(pageNum - 1)">
              上一页
            </button>
            <button class="pg-btn" type="button" :disabled="pageNum >= totalPages()" @click="changePage(pageNum + 1)">
              下一页
            </button>
          </div>
        </template>
      </section>
    </div>

    <!-- 查看解析弹窗 -->
    <div v-if="analyzeVisible" class="modal-overlay" @click.self="analyzeVisible = false">
      <div class="modal modal-lg">
        <div class="modal-header">
          <h3>题目解析</h3>
          <button class="modal-close" type="button" @click="analyzeVisible = false">×</button>
        </div>
        <div v-loading="analyzeLoading" class="modal-body">
          <template v-if="analyzeDetail">
            <div class="q-meta an-meta">
              <span class="badge badge-blue">{{ TYPE_LABEL[analyzeDetail.type] }}</span>
              <span class="badge" :class="DIFF_BADGE[analyzeDetail.difficulty]">{{
                DIFF_LABEL[analyzeDetail.difficulty]
              }}</span>
            </div>
            <h4 class="an-stem">{{ analyzeDetail.content }}</h4>
            <ul v-if="analyzeDetail.options?.length" class="an-opt-list">
              <li v-for="o in analyzeDetail.options" :key="o.key">
                <span class="opt-key">{{ o.key }}</span>{{ o.content }}
              </li>
            </ul>
            <div class="analysis-card">
              <h4>正确答案</h4>
              <p v-if="analyzeDetail.type === 'short'" class="text-2">{{ answerText(analyzeDetail) }}</p>
              <p v-else><strong>{{ answerText(analyzeDetail) }}</strong></p>
              <h4>解析</h4>
              <p class="an-analysis">{{ analyzeDetail.analysis || '暂无解析' }}</p>
            </div>
          </template>
        </div>
        <div class="modal-footer">
          <button class="btn" type="button" @click="analyzeVisible = false">关闭</button>
          <button
            v-if="analyzeDetail"
            class="btn btn-primary"
            type="button"
            @click="startQuestionPractice(analyzeDetail.id)"
          >
            开始练习
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.qb-page {
  padding: 24px 24px 64px;
}
.sb-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sh-name {
  margin: 0;
  font-size: 20px;
}
.sh-badge {
  margin-left: auto;
}
.sr-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
}
.back-link {
  cursor: pointer;
}
.mt-8 {
  margin-top: 8px;
}
.text-2 {
  color: var(--ink-2);
}

/* 解析弹窗 */
.an-meta {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}
.an-stem {
  font-size: 16px;
  line-height: 1.7;
  margin-bottom: 12px;
}
.an-analysis {
  margin: 0;
  color: var(--ink-2);
}

@media (max-width: 900px) {
  .qb-layout {
    grid-template-columns: 1fr;
  }
}
</style>
