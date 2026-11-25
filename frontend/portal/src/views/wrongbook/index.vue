<script setup lang="ts">
/**
 * 错题本（prototype/portal/wrongbook.html，需求 3.6 / 04 §3.3 #22-28）。
 * 浏览模式：统计卡 + 高频 Top3 + 状态/分类/时间筛选 + 排序 + 错题卡（等级徽章/纠正进度/
 * 你的答案/正确答案）+ 单卡操作与批量操作条（均二次确认）+ 「重做模式」入口（选顺序/乱序）。
 * 重做模式：按待复习顺序（或乱序）逐题作答（复用 /practice/answers scene=wrongReview），
 * 提交后标出正确与错选并展示解析；纠正累计 3 次自动标记已掌握；简答等无选项题仅展示参考答案。
 */
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  batchMasterWrong,
  batchRemoveWrong,
  fetchReviewSet,
  fetchWrongList,
  fetchWrongStats,
  masterWrong,
  removeWrong,
  type AnswerValue,
  type MasteryStatusApi,
  type QuestionTypeApi,
  type ReviewSetItem,
  type WrongLevel,
  type WrongListItem,
  type WrongStats,
} from '@/api/wrongbook'
import { submitPracticeAnswer, type ObjectiveGradeResult } from '@/api/practice'
import type { ApiError } from '@shared/types/api'

const TYPE_LABEL: Record<QuestionTypeApi, string> = {
  single: '单选',
  multiple: '多选',
  judge: '判断',
  short: '简答',
}
const LEVEL_BADGE: Record<WrongLevel, { text: string; cls: string }> = {
  highFreq: { text: '高频易错', cls: 'badge-red' },
  multiple: { text: '多次错误', cls: 'badge-orange' },
  occasional: { text: '偶尔错误', cls: 'badge-gray' },
}
const MASTER_LABEL: Record<MasteryStatusApi, string> = { reviewing: '待复习', mastered: '已掌握' }
/** 判断题固定选项（作答为 bool） */
const JUDGE_OPTIONS = [
  { key: 'T', content: '正确' },
  { key: 'F', content: '错误' },
]

// ===================== 浏览模式状态 =====================
const stats = ref<WrongStats | null>(null)
const list = ref<WrongListItem[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const loading = ref(false)
const filters = reactive({
  mastery: 'all' as 'all' | 'reviewing' | 'mastered',
  category: 'all',
  time: 'all' as 'all' | '7d' | '30d',
  sort: 'lastWrongAt' as 'lastWrongAt' | 'wrongCount',
})
const selected = reactive<Record<number, boolean>>({})

const selectedIds = computed(() =>
  Object.keys(selected)
    .filter((k) => selected[Number(k)])
    .map(Number),
)

function totalPages() {
  return Math.max(1, Math.ceil(total.value / pageSize.value))
}

/** 作答快照 → 展示文本（单/多选=键「、」连接、判断=正确/错误、简答=文本） */
function fmtAnswer(v: AnswerValue | null | undefined, fallback: string): string {
  if (v === null || v === undefined) return fallback
  if (typeof v === 'boolean') return v ? '正确' : '错误'
  if (Array.isArray(v)) return v.join('、') || fallback
  return v || fallback
}
function fmtCategory(stageName: string, subjectName: string) {
  return `${subjectName} / ${stageName}` // S7：分类=阶段名，学科名辅助展示
}

// ===================== 数据加载 =====================
async function loadStats() {
  try {
    stats.value = await fetchWrongStats()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '统计加载失败')
  }
}
async function loadList() {
  loading.value = true
  try {
    const res = await fetchWrongList({
      mastery: filters.mastery,
      category: filters.category === 'all' ? undefined : filters.category,
      timeRange: filters.time,
      sort: filters.sort,
      pageNum: pageNum.value,
      pageSize: pageSize.value,
    })
    list.value = res.list
    total.value = res.total
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '错题加载失败')
  } finally {
    loading.value = false
  }
}
function reload() {
  loadStats()
  loadList()
}
function onFilterChange() {
  pageNum.value = 1
  loadList()
}
function setMastery(v: 'all' | 'reviewing' | 'mastered') {
  filters.mastery = v
  onFilterChange()
}
function changePage(p: number) {
  pageNum.value = p
  loadList()
}

// ===================== 勾选与批量操作 =====================
function toggleCheck(id: number, checked: boolean) {
  if (checked) selected[id] = true
  else delete selected[id]
}
function clearSelection() {
  Object.keys(selected).forEach((k) => delete selected[Number(k)])
}

async function masterOne(item: WrongListItem) {
  try {
    await ElMessageBox.confirm('确定将该错题标记为已掌握吗？', '标记已掌握', {
      type: 'warning',
      confirmButtonText: '标记已掌握',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await masterWrong(item.id)
    ElMessage.success('已标记为已掌握')
    reload()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败，请稍后重试')
  }
}
async function removeOne(item: WrongListItem) {
  try {
    await ElMessageBox.confirm('确定将该题从错题本移除吗？移除后可在刷题中重新积累。', '移除错题', {
      type: 'warning',
      confirmButtonText: '移除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await removeWrong(item.id)
    ElMessage.success('已移除错题')
    delete selected[item.id]
    reload()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败，请稍后重试')
  }
}
async function batchMaster() {
  const ids = selectedIds.value
  if (!ids.length) return
  try {
    await ElMessageBox.confirm(`确定将选中的 ${ids.length} 道错题标记为已掌握吗？`, '批量标记已掌握', {
      type: 'warning',
      confirmButtonText: '批量标记',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    const res = await batchMasterWrong(ids)
    ElMessage.success(`已批量标记 ${res.affected} 项为已掌握`)
    clearSelection()
    reload()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败，请稍后重试')
  }
}
async function batchRemove() {
  const ids = selectedIds.value
  if (!ids.length) return
  try {
    await ElMessageBox.confirm(`确定移除选中的 ${ids.length} 道错题吗？移除后可在刷题中重新积累。`, '批量移除', {
      type: 'warning',
      confirmButtonText: '批量移除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    const res = await batchRemoveWrong(ids)
    ElMessage.success(`已批量移除 ${res.affected} 道错题`)
    clearSelection()
    reload()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败，请稍后重试')
  }
}
async function batchClear() {
  const ids = selectedIds.value
  if (!ids.length) return
  try {
    await ElMessageBox.confirm(`确定取消已勾选的 ${ids.length} 项吗？`, '取消选择', {
      confirmButtonText: '取消选择',
      cancelButtonText: '返回',
    })
  } catch {
    return
  }
  clearSelection()
  ElMessage.success('已取消选择')
}

// ===================== 重做模式 =====================
type RedoOrder = 'sequential' | 'shuffle'

interface RedoAnswer {
  selected: string[]
  submitted: boolean
  isCorrect: boolean
  correctAnswer: string[]
  analysis: string
}
const redo = ref<{
  items: ReviewSetItem[]
  idx: number
  answers: Record<number, RedoAnswer>
  order: RedoOrder
} | null>(null)
const redoModeVisible = ref(false) // 顺序/乱序选择弹窗

const curItem = computed(() => (redo.value ? redo.value.items[redo.value.idx] ?? null : null))

function shuffle<T>(arr: T[]): T[] {
  const out = arr.slice()
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

function ansOf(item: ReviewSetItem): RedoAnswer {
  return redo.value!.answers[item.id]
}
function optionsOf(item: ReviewSetItem) {
  return item.options?.length ? item.options : item.type === 'judge' ? JUDGE_OPTIONS : []
}
function isShort(item: ReviewSetItem) {
  return item.type === 'short' // 无选项题：仅展示参考答案（需求 3.6）
}
function redoOptClass(item: ReviewSetItem, key: string) {
  const ans = ansOf(item)
  const cls: Record<string, boolean> = { 'opt-item': true }
  if (ans.submitted) {
    cls.locked = true
    cls.correct = ans.correctAnswer.includes(key)
    cls.wrong = ans.selected.includes(key) && !cls.correct
  } else {
    cls.selected = ans.selected.includes(key)
  }
  return cls
}
function itemLevel(item: ReviewSetItem): WrongLevel {
  return item.wrongCount >= 3 ? 'highFreq' : item.wrongCount === 2 ? 'multiple' : 'occasional'
}

async function startRedo(focusId?: number, order: RedoOrder = 'sequential') {
  try {
    const res = await fetchReviewSet('reviewing')
    // 乱序=客户端打乱（题目集一次下发；顺序=服务端最近答错倒序）
    const items = order === 'shuffle' ? shuffle(res.questions) : res.questions
    const answers: Record<number, RedoAnswer> = {}
    items.forEach((q) => {
      answers[q.id] = { selected: [], submitted: false, isCorrect: false, correctAnswer: [], analysis: '' }
    })
    let idx = 0
    if (focusId !== undefined) {
      const found = items.findIndex((q) => q.id === focusId)
      if (found >= 0) idx = found
    }
    redo.value = { items, idx, answers, order }
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '重做题目加载失败')
  }
}
function startRedoWith(order: RedoOrder) {
  redoModeVisible.value = false
  startRedo(undefined, order)
}
function exitRedo() {
  redo.value = null
  reload() // 重做提交会改变纠正进度/掌握状态
  ElMessage.success('已退出重做模式')
}
function redoPrev() {
  if (redo.value && redo.value.idx > 0) redo.value.idx -= 1
}
function redoNext() {
  if (redo.value && redo.value.idx < redo.value.items.length - 1) redo.value.idx += 1
}
function pickRedoOption(item: ReviewSetItem, key: string) {
  const ans = ansOf(item)
  if (ans.submitted) return
  if (item.type === 'multiple') {
    ans.selected = ans.selected.includes(key)
      ? ans.selected.filter((k) => k !== key)
      : [...ans.selected, key].sort()
  } else {
    ans.selected = [key] // 单选/判断互斥
  }
}
async function submitRedo() {
  const item = curItem.value
  if (!item || !redo.value) return
  const ans = ansOf(item)
  if (ans.submitted) return
  if (!ans.selected.length) {
    ElMessage.warning('请先选择答案')
    return
  }
  try {
    const res = (await submitPracticeAnswer({
      questionId: item.questionId,
      scene: 'wrongReview',
      answer: item.type === 'judge' ? ans.selected.includes('T') : ans.selected,
    })) as ObjectiveGradeResult
    ans.submitted = true
    ans.isCorrect = res.isCorrect
    ans.correctAnswer = Array.isArray(res.correctAnswer)
      ? res.correctAnswer
      : [res.correctAnswer ? 'T' : 'F']
    ans.analysis = res.analysis || ''
    if (res.isCorrect) {
      item.corrected = Math.min(item.corrected + 1, 3)
      if (item.corrected >= 3) {
        ElMessage.success('已连续纠正 3 次，自动标记为已掌握')
      } else {
        ElMessage.success(`回答正确！已纠正次数 +1（${item.corrected}/3）`)
      }
    } else {
      item.corrected = 0 // Q3：重做答错清零
      item.wrongCount += 1 // 任意场景答错计数续增
      ElMessage.warning('回答错误，查看解析后再接再厉')
    }
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '提交失败，请稍后重试')
  }
}

function onKeydown(e: KeyboardEvent) {
  if (redoModeVisible.value && e.key === 'Escape') {
    e.preventDefault()
    redoModeVisible.value = false
  }
}
onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  reload()
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="container wb-page">
    <!-- ============ 重做模式 ============ -->
    <div v-if="redo" class="redo-wrap">
      <div class="flex-between mb-16">
        <h2 class="redo-title">
          重做模式<template v-if="redo.items.length"> · 第 {{ redo.idx + 1 }}/{{ redo.items.length }} 题</template>
        </h2>
        <span class="muted redo-order">{{ redo.order === 'shuffle' ? '乱序练习' : '顺序练习' }}</span>
      </div>

      <div class="card question-panel">
        <!-- 空态：无待复习 -->
        <div v-if="!redo.items.length" class="empty-state">
          <div class="empty-icon">🎉</div>
          <div class="empty-title">没有待复习的错题</div>
          <div class="empty-sub">所有错题都已掌握，去题库继续练习吧</div>
          <button class="btn btn-primary mt-16" type="button" @click="exitRedo">返回浏览</button>
        </div>

        <!-- 题目 -->
        <template v-else-if="curItem">
          <div class="q-type-row">
            <span class="badge badge-blue">{{ TYPE_LABEL[curItem.type] }}</span>
            <span class="badge" :class="LEVEL_BADGE[itemLevel(curItem)].cls">
              {{ LEVEL_BADGE[itemLevel(curItem)].text }}
            </span>
            <span class="badge">已纠正 {{ curItem.corrected }}/3 次</span>
            <span v-if="curItem.corrected >= 3" class="badge badge-green">已掌握</span>
          </div>
          <div class="q-stem-lg">{{ curItem.content }}</div>

          <!-- 无选项题（简答）：提示 + 参考答案 -->
          <template v-if="isShort(curItem)">
            <div class="alert alert-info">此题暂无可选的答题选项，请自行复习</div>
            <div class="analysis-card">
              <h4>参考答案</h4>
              <p>正确答案：<strong class="w-ans-right">{{ fmtAnswer(curItem.rightAnswer, '见参考答案') }}</strong></p>
              <p class="mb-0 text-2">{{ curItem.analysis || '暂无解析' }}</p>
            </div>
          </template>

          <!-- 有选项题：作答 + 解析 -->
          <template v-else>
            <div class="opt-list">
              <div
                v-for="o in optionsOf(curItem)"
                :key="o.key"
                :class="redoOptClass(curItem, o.key)"
                @click="pickRedoOption(curItem, o.key)"
              >
                <span class="opt-key">{{ o.key }}</span>
                <span>{{ o.content }}</span>
              </div>
            </div>
            <div v-if="!ansOf(curItem).submitted" class="submit-row">
              <button class="btn btn-primary" type="button" @click="submitRedo">提交答案</button>
            </div>
            <div v-else class="analysis-card">
              <h4>
                答案解析
                <span class="badge" :class="ansOf(curItem).isCorrect ? 'badge-green' : 'badge-red'">
                  {{ ansOf(curItem).isCorrect ? '回答正确' : '回答错误' }}
                </span>
              </h4>
              <p>正确答案：<strong class="w-ans-right">{{ fmtAnswer(curItem.rightAnswer, '见参考答案') }}</strong></p>
              <p class="mb-0 text-2">{{ ansOf(curItem).analysis || curItem.analysis || '暂无解析' }}</p>
            </div>
          </template>
        </template>
      </div>

      <div v-if="redo.items.length" class="practice-footer-actions">
        <button class="btn" type="button" :disabled="redo.idx === 0" @click="redoPrev">‹ 上一题</button>
        <button class="btn" type="button" :disabled="redo.idx >= redo.items.length - 1" @click="redoNext">
          下一题 ›
        </button>
        <button class="btn btn-ghost" type="button" @click="exitRedo">退出练习</button>
      </div>
    </div>

    <!-- ============ 浏览模式 ============ -->
    <div v-else>
      <div class="flex-between wb-head">
        <h1 class="wb-title">错题本</h1>
        <button class="btn btn-primary" type="button" @click="redoModeVisible = true">重做模式</button>
      </div>

      <!-- 统计卡 -->
      <div v-if="stats" class="wb-stats">
        <div class="card stat-card">
          <div class="stat-label">错题总数</div>
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-sub">全部错题记录</div>
        </div>
        <div class="card stat-card">
          <div class="stat-label">待复习</div>
          <div class="stat-value">{{ stats.reviewing }}</div>
          <div class="stat-sub">尚未掌握，需继续巩固</div>
        </div>
        <div class="card stat-card">
          <div class="stat-label">已掌握</div>
          <div class="stat-value">{{ stats.mastered }}</div>
          <div class="stat-sub">已连续纠正 3 次或手动标记</div>
        </div>
        <div class="card stat-card">
          <div class="stat-label">掌握率</div>
          <div class="stat-value">{{ stats.masteryRate }}%</div>
          <div class="stat-sub">已掌握 / 错题总数</div>
        </div>
      </div>

      <!-- 高频错题 Top3 -->
      <div class="flex-between mb-8">
        <h3 class="top3-title">高频错题 Top3</h3>
        <span class="muted top3-hint">按错误次数降序 · 点击卡片进入重做并定位该题</span>
      </div>
      <div class="top3-strip">
        <template v-if="stats?.top3.length">
          <div
            v-for="(t, i) in stats.top3"
            :key="t.id"
            class="card top3-card"
            title="点击进入重做模式并定位该题"
            @click="startRedo(t.id)"
          >
            <div class="flex-between">
              <span class="t3-rank badge badge-red">TOP {{ i + 1 }}</span>
              <span class="muted t3-count">错误 {{ t.wrongCount }} 次</span>
            </div>
            <div class="t3-stem">{{ t.content }}</div>
          </div>
        </template>
        <div v-else class="card empty-state top3-empty">
          <div class="empty-title">暂无待复习的高频错题</div>
        </div>
      </div>

      <!-- 筛选栏 -->
      <div class="wrong-filter-bar">
        <div class="fb-group">
          <span class="fb-label">状态</span>
          <div class="chip-row">
            <button
              v-for="c in [
                { v: 'all', t: '全部' },
                { v: 'reviewing', t: '待复习' },
                { v: 'mastered', t: '已掌握' },
              ]"
              :key="c.v"
              class="chip"
              :class="{ active: filters.mastery === c.v }"
              type="button"
              @click="setMastery(c.v as 'all' | 'reviewing' | 'mastered')"
            >
              {{ c.t }}
            </button>
          </div>
        </div>
        <div class="fb-group">
          <span class="fb-label">分类</span>
          <select v-model="filters.category" class="select" @change="onFilterChange">
            <option value="all">全部分类</option>
            <option v-for="c in stats?.categories ?? []" :key="`${c.subjectName}/${c.stageName}`" :value="c.stageName">
              {{ fmtCategory(c.stageName, c.subjectName) }}
            </option>
          </select>
        </div>
        <div class="fb-group">
          <span class="fb-label">时间</span>
          <select v-model="filters.time" class="select" @change="onFilterChange">
            <option value="all">全部</option>
            <option value="7d">近 7 天</option>
            <option value="30d">近 30 天</option>
          </select>
        </div>
        <div class="fb-group">
          <span class="fb-label">排序</span>
          <select v-model="filters.sort" class="select" @change="onFilterChange">
            <option value="lastWrongAt">最近答错时间倒序</option>
            <option value="wrongCount">错误次数倒序</option>
          </select>
        </div>
      </div>

      <!-- 错题列表 -->
      <div v-loading="loading">
        <div v-if="!loading && !list.length" class="card empty-state">
          <div class="empty-icon">📭</div>
          <div class="empty-title">暂无错题</div>
          <div class="empty-sub">调整筛选条件，或去刷题积累错题后再来看看</div>
        </div>

        <div
          v-for="w in list"
          v-else
          :key="w.id"
          class="card wrong-card"
          :class="{ mastered: w.masteryStatus === 'mastered' }"
        >
          <label class="checkbox-row">
            <input type="checkbox" :checked="!!selected[w.id]" @change="toggleCheck(w.id, ($event.target as HTMLInputElement).checked)" />
          </label>
          <div class="w-body">
            <div class="w-badges">
              <span class="badge" :class="LEVEL_BADGE[w.level].cls">{{ LEVEL_BADGE[w.level].text }}</span>
              <span class="badge">已纠正 {{ w.corrected }}/3 次</span>
              <span v-if="w.masteryStatus === 'mastered'" class="badge badge-green">{{ MASTER_LABEL.mastered }}</span>
            </div>
            <div class="w-stem">{{ w.content }}</div>
            <div class="w-info">
              <span>分类：{{ fmtCategory(w.category.stageName, w.category.subjectName) }}</span>
              <span>最近答错：{{ w.lastWrongAt }}</span>
              <span>错误次数：{{ w.wrongCount }} 次</span>
            </div>
            <div class="w-answers">
              <span class="w-ans-wrong">你的答案：{{ fmtAnswer(w.myAnswer, '—') }}</span>
              <span class="w-ans-right">正确答案：{{ fmtAnswer(w.rightAnswer, '见参考答案') }}</span>
            </div>
            <div class="w-actions">
              <button class="btn btn-primary btn-sm" type="button" @click="startRedo(w.id)">重新做题</button>
              <button
                v-if="w.masteryStatus !== 'mastered'"
                class="btn btn-sm"
                type="button"
                @click="masterOne(w)"
              >
                标记已掌握
              </button>
              <button class="btn btn-soft-danger btn-sm" type="button" @click="removeOne(w)">移除错题</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="total > pageSize" class="pagination">
        <span class="pg-info">共 {{ total }} 条 · 第 {{ pageNum }}/{{ totalPages() }} 页</span>
        <button class="pg-btn" type="button" :disabled="pageNum <= 1" @click="changePage(pageNum - 1)">上一页</button>
        <button class="pg-btn" type="button" :disabled="pageNum >= totalPages()" @click="changePage(pageNum + 1)">
          下一页
        </button>
      </div>

      <!-- 批量操作条 -->
      <div v-if="selectedIds.length" class="batch-bar">
        <span class="batch-count">已选择 {{ selectedIds.length }} 项</span>
        <button class="btn btn-sm" type="button" @click="batchMaster">批量标记已掌握</button>
        <button class="btn btn-danger btn-sm" type="button" @click="batchRemove">批量移除</button>
        <button class="btn btn-ghost btn-sm" type="button" @click="batchClear">取消选择</button>
      </div>
    </div>

    <!-- 重做模式选择弹窗（顺序 / 乱序） -->
    <div v-if="redoModeVisible" class="modal-overlay" @click.self="redoModeVisible = false">
      <div class="modal">
        <div class="modal-header">
          <h3>重做模式</h3>
          <button class="modal-close" type="button" @click="redoModeVisible = false">×</button>
        </div>
        <div class="modal-body">
          <p class="muted mb-16">请选择本次重做练习的作答顺序</p>
          <div class="mode-grid">
            <div class="mode-card" @click="startRedoWith('sequential')">
              <div class="mc-icon">📖</div>
              <div class="mc-name">顺序练习</div>
              <div class="mc-desc">按待复习顺序逐题作答</div>
            </div>
            <div class="mode-card" @click="startRedoWith('shuffle')">
              <div class="mc-icon">🔀</div>
              <div class="mc-name">乱序练习</div>
              <div class="mc-desc">打乱题目顺序作答</div>
            </div>
          </div>
          <p class="mode-tip">按 Esc 或点击右上角 ✕ 取消</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wb-page {
  padding: 24px 24px 64px;
}
.wb-head {
  margin-bottom: 16px;
}
.wb-title {
  font-size: 22px;
  margin: 0;
}
.redo-order {
  font-size: 13px;
}
.mode-tip {
  margin: 16px 0 0;
  font-size: 12px;
  color: var(--ink-3);
}
.top3-title {
  margin: 0;
  font-size: 16px;
}
.top3-hint {
  font-size: 12px;
}
.t3-count {
  font-size: 12px;
}
.top3-empty {
  grid-column: 1 / -1;
  padding: 24px;
}
.mb-8 {
  margin-bottom: 8px;
}
.mb-16 {
  margin-bottom: 16px;
}
.mt-16 {
  margin-top: 16px;
}
.redo-title {
  margin: 0;
  font-size: 20px;
}
.w-badges {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.submit-row {
  margin-bottom: 22px;
}
.text-2 {
  color: var(--ink-2);
}
</style>
