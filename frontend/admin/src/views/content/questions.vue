<script setup lang="ts">
/**
 * 题库管理（04 §4.5 / 需求 4.3.3 / prototype/admin/questions.html）。
 * 七统计卡 + 筛选 + 表格（状态流转行操作）+ 新增/编辑（选项管理）+ 详情（答题统计）
 * + 两段式导入 + 导出 + 批量上架/下架/删除；按钮级权限 v-permission（question:*）。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import type { ApiError } from '@shared/types/api'
import {
  batchDeleteQuestions,
  batchReviewQuestions,
  batchStatusQuestions,
  confirmQuestionImport,
  createQuestion,
  deleteQuestion,
  downloadQuestionTemplate,
  exportQuestions,
  fetchQuestion,
  fetchQuestionSummary,
  fetchQuestions,
  previewQuestionImport,
  reviewQuestion,
  submitQuestion,
  unpublishQuestion,
  updateQuestion,
} from '@/api/questions'
import type {
  QuestionDetail,
  QuestionImportPreviewResult,
  QuestionListItem,
  QuestionOption,
  QuestionPayload,
  QuestionSummary,
  QuestionStatus,
  QuestionType,
} from '@/api/questions'
import { fetchSubjects } from '@/api/subjects'
import type { SubjectItem } from '@/api/subjects'

const TYPE_LABEL: Record<string, string> = { single: '单选', multiple: '多选', judge: '判断', short: '简答' }
const DIFF_LABEL: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' }
const STATUS_LABEL: Record<string, string> = {
  onShelf: '已上架',
  offShelf: '已下架',
  pending: '待审核',
  draft: '草稿',
  rejected: '已驳回',
}
const STATUS_TAG: Record<string, 'success' | 'info' | 'warning' | 'danger'> = {
  onShelf: 'success',
  offShelf: 'info',
  pending: 'warning',
  draft: 'info',
  rejected: 'danger',
}
const DIFF_TAG: Record<string, 'success' | 'warning' | 'danger'> = {
  easy: 'success',
  medium: 'warning',
  hard: 'danger',
}

// ===================== 统计卡与列表 =====================
const loading = ref(false)
const summary = ref<QuestionSummary>({ total: 0, onShelf: 0, pending: 0, single: 0, multiple: 0, judge: 0, short: 0 })
const rows = ref<QuestionListItem[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const filter = reactive({ keyword: '', stageId: '' as string | number, type: '', difficulty: '', status: '' })
const subjectOptions = ref<SubjectItem[]>([])

function buildQuery() {
  return {
    keyword: filter.keyword.trim() || undefined,
    stageId: filter.stageId ? Number(filter.stageId) : undefined,
    type: filter.type || undefined,
    difficulty: filter.difficulty || undefined,
    status: filter.status || undefined,
    pageNum: pageNum.value,
    pageSize: pageSize.value,
  }
}

async function load() {
  loading.value = true
  try {
    const res = await fetchQuestions(buildQuery())
    rows.value = res.list
    total.value = res.total
    summary.value = await fetchQuestionSummary()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pageNum.value = 1
  load()
}

let searchTimer: ReturnType<typeof setTimeout> | undefined
function onKeywordInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(handleSearch, 300)
}

onMounted(() => {
  load()
  fetchSubjects()
    .then((res) => {
      subjectOptions.value = res.list
    })
    .catch(() => {})
})

// ---- 批量选择 ----
const selected = ref<QuestionListItem[]>([])
function handleSelectionChange(items: QuestionListItem[]) {
  selected.value = items
}

// ===================== 行操作（状态流转） =====================
async function handleReview(row: QuestionListItem, result: 'pass' | 'reject') {
  const passed = result === 'pass'
  try {
    await ElMessageBox.confirm(
      passed
        ? `确定将题目 #${row.id} 审核通过吗？通过后题目将立即上架。`
        : `确定将题目 #${row.id} 审核不通过吗？将标记为已驳回，可修改后重新提交。`,
      passed ? '审核通过' : '审核不通过',
      {
        type: passed ? 'warning' : 'error',
        confirmButtonText: passed ? '通过' : '驳回',
        cancelButtonText: '取消',
      },
    )
  } catch {
    return
  }
  try {
    await reviewQuestion(row.id, result)
    ElMessage.success(passed ? `题目 #${row.id} 已审核通过并上架` : `题目 #${row.id} 已驳回`)
    load()
    refreshDetail(row.id)
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

async function handleUnpublish(row: QuestionListItem) {
  try {
    await ElMessageBox.confirm(`确定将题目 #${row.id} 下架吗？下架后学员端不可见。`, '下架题目', {
      type: 'warning',
      confirmButtonText: '下架',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await unpublishQuestion(row.id)
    ElMessage.success(`题目 #${row.id} 已下架`)
    load()
    refreshDetail(row.id)
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

async function handleSubmit(row: QuestionListItem, viaOnline: boolean) {
  if (viaOnline) {
    try {
      await ElMessageBox.confirm(
        `确定将题目 #${row.id} 重新上架吗？将转入待审核，审核通过后上架。`,
        '重新上架',
        { type: 'warning', confirmButtonText: '提交上架', cancelButtonText: '取消' },
      )
    } catch {
      return
    }
  }
  try {
    await submitQuestion(row.id)
    ElMessage.success(`题目 #${row.id} 已${viaOnline ? '提交重新上架' : '重新提交'}，转入待审核`)
    load()
    refreshDetail(row.id)
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

async function handleDeleteOne(row: QuestionListItem) {
  try {
    await ElMessageBox.confirm(`确定删除题目 #${row.id} 吗？删除后数据保留可恢复。`, '删除题目', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteQuestion(row.id)
    ElMessage.success('删除成功')
    load()
    if (detail.value?.id === row.id) drawerVisible.value = false
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '删除失败')
  }
}

// ---- 批量操作 ----
async function handleBatchReview() {
  const ids = selected.value.map((q) => q.id)
  if (!ids.length) {
    ElMessage.warning('请先勾选题目')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定批量审核通过选中的 ${ids.length} 道题目吗？仅「待审核」题目可审，其余自动跳过。通过后题目将立即上架。`,
      '批量审核通过',
      { type: 'warning', confirmButtonText: '通过', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    const res = await batchReviewQuestions('pass', ids)
    ElMessage.success(`批量审核完成：通过 ${res.affected} 道、跳过 ${res.skipped.length} 道`)
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

async function handleBatchStatus(action: 'submit' | 'unpublish') {
  const ids = selected.value.map((q) => q.id)
  if (!ids.length) {
    ElMessage.warning('请先勾选题目')
    return
  }
  const label = action === 'submit' ? '上架' : '下架'
  try {
    await ElMessageBox.confirm(
      `确定批量${label}选中的 ${ids.length} 道题目吗？状态不合法的条目将自动跳过。`,
      `批量${label}`,
      { type: 'warning', confirmButtonText: label, cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    const res = await batchStatusQuestions(action, ids)
    ElMessage.success(`批量${label}完成：成功 ${res.affected} 道、跳过 ${res.skipped.length} 道`)
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

async function handleBatchDelete() {
  const ids = selected.value.map((q) => q.id)
  if (!ids.length) {
    ElMessage.warning('请先勾选题目')
    return
  }
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${ids.length} 道题目吗？删除后数据保留可恢复。`, '批量删除题目', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    const res = await batchDeleteQuestions(ids)
    ElMessage.success(`已删除 ${res.affected} 道题目`)
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '删除失败')
  }
}

// ===================== 详情抽屉 =====================
const drawerVisible = ref(false)
const detail = ref<QuestionDetail | null>(null)

async function openDetail(row: QuestionListItem) {
  try {
    detail.value = await fetchQuestion(row.id)
    drawerVisible.value = true
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '加载详情失败')
  }
}

async function refreshDetail(id: number) {
  if (drawerVisible.value && detail.value?.id === id) {
    try {
      detail.value = await fetchQuestion(id)
    } catch {
      drawerVisible.value = false
    }
  }
}

// ===================== 新增 / 编辑弹窗 =====================
const dialogVisible = ref(false)
const dialogTitle = ref('新增题目')
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({
  stageId: '' as string | number,
  type: '' as QuestionType | '',
  difficulty: 'medium' as 'easy' | 'medium' | 'hard',
  content: '',
  tagsText: '',
  analysis: '',
  judgeAnswer: true,
  referenceAnswer: '',
})
const options = ref<QuestionOption[]>([])
const currentStatus = ref<QuestionStatus | ''>('')

const rules: FormRules = {
  content: [{ required: true, message: '请输入题目内容', trigger: 'blur' }],
  stageId: [{ required: true, message: '请选择阶段', trigger: 'change' }],
  type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  difficulty: [{ required: true, message: '请选择难度', trigger: 'change' }],
}

function resetOptions() {
  options.value = [
    { key: 'A', content: '', isCorrect: false },
    { key: 'B', content: '', isCorrect: false },
    { key: 'C', content: '', isCorrect: false },
    { key: 'D', content: '', isCorrect: false },
  ]
}

function addOption() {
  if (options.value.length >= 6) return
  const key = 'ABCDEF'[options.value.length]
  options.value = [...options.value, { key, content: '', isCorrect: false }]
}

function removeOption(index: number) {
  if (options.value.length <= 2) return
  options.value = options.value
    .filter((_, i) => i !== index)
    .map((o, i) => ({ ...o, key: 'ABCDEF'[i] }))
}

function setSingleCorrect(index: number) {
  options.value = options.value.map((o, i) => ({ ...o, isCorrect: i === index }))
}

function openForm(row?: QuestionListItem) {
  editingId.value = row?.id ?? null
  dialogTitle.value = row ? `编辑题目 #${row.id}` : '新增题目'
  currentStatus.value = row?.status ?? ''
  Object.assign(form, {
    stageId: '',
    type: '',
    difficulty: 'medium',
    content: '',
    tagsText: '',
    analysis: '',
    judgeAnswer: true,
    referenceAnswer: '',
  })
  resetOptions()
  dialogVisible.value = true

  if (row) {
    fetchQuestion(row.id)
      .then((d) => {
        form.stageId = d.stageId
        form.type = d.type
        form.difficulty = d.difficulty
        form.content = d.content
        form.tagsText = (d.tags ?? []).join(',')
        form.analysis = d.analysis ?? ''
        form.judgeAnswer = d.judgeAnswer ?? true
        form.referenceAnswer = d.referenceAnswer ?? ''
        if (d.options.length && (d.type === 'single' || d.type === 'multiple')) {
          options.value = d.options.map((o) => ({ ...o }))
        }
      })
      .catch(() => {})
  }
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  const type = form.type as QuestionType
  let payload: QuestionPayload = {
    stageId: Number(form.stageId),
    type,
    difficulty: form.difficulty,
    content: form.content.trim(),
    tags: form.tagsText
      .split(/[,，、]/)
      .map((t) => t.trim())
      .filter(Boolean),
    analysis: form.analysis.trim() || null,
    options: null,
    judgeAnswer: null,
    referenceAnswer: null,
  }
  if (type === 'single' || type === 'multiple') {
    const opts = options.value.filter((o) => o.content.trim())
    if (opts.length < 2 || opts.length > 6 || opts.length !== options.value.length) {
      ElMessage.warning('请填写全部选项内容（选项数量 2~6 项）')
      return
    }
    if (!opts.some((o) => o.isCorrect)) {
      ElMessage.warning('至少勾选 1 个正确答案')
      return
    }
    if (type === 'single' && opts.filter((o) => o.isCorrect).length > 1) {
      ElMessage.warning('单选题仅可有 1 个正确答案')
      return
    }
    payload = {
      ...payload,
      options: opts.map((o) => ({ key: o.key, content: o.content.trim(), isCorrect: o.isCorrect })),
    }
  } else if (type === 'judge') {
    payload = { ...payload, judgeAnswer: form.judgeAnswer }
  } else {
    payload = { ...payload, referenceAnswer: form.referenceAnswer.trim() || null }
  }
  try {
    if (editingId.value === null) {
      await createQuestion(payload)
      ElMessage.success('新增成功（题目进入待审核）')
    } else {
      await updateQuestion(editingId.value, payload)
      ElMessage.success('保存成功')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

// ===================== 导出 =====================
const exporting = ref(false)
async function handleExport() {
  exporting.value = true
  try {
    const truncated = await exportQuestions(buildQuery())
    if (truncated) {
      ElMessage.warning('导出超出 1 万行，已截断导出前 1 万行')
    } else {
      ElMessage.success('导出成功')
    }
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

// ===================== 批量导入（两段式） =====================
const importVisible = ref(false)
const importFileName = ref('')
const importFile = ref<File | null>(null)
const fileInputEl = ref<HTMLInputElement | null>(null)
const importing = ref(false)
const preview = ref<QuestionImportPreviewResult | null>(null)

function resetImport() {
  importFile.value = null
  importFileName.value = ''
  preview.value = null
  if (fileInputEl.value) fileInputEl.value.value = ''
}

function openImport() {
  resetImport()
  importVisible.value = true
}

function pickFile(file: File | undefined | null) {
  if (!file) return
  if (!/\.(xlsx|xls)$/i.test(file.name)) {
    ElMessage.warning('仅支持 .xlsx / .xls 文件')
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.warning('文件不能超过 5MB')
    return
  }
  importFile.value = file
  importFileName.value = file.name
  handlePreview()
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  pickFile(input.files?.[0])
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  pickFile(e.dataTransfer?.files?.[0])
}

async function handlePreview() {
  if (!importFile.value) return
  importing.value = true
  preview.value = null
  try {
    preview.value = await previewQuestionImport(importFile.value)
    if (preview.value.summary.errorCount > 0) {
      ElMessage.error('存在无效行，已整份拒绝导入，请修正后重新上传')
    }
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '文件解析失败')
  } finally {
    importing.value = false
  }
}

async function handleConfirmImport() {
  const token = preview.value?.importToken
  if (!token || !preview.value || preview.value.summary.errorCount > 0) return
  try {
    await ElMessageBox.confirm('确认导入吗？导入的题目将统一进入「待审核」。', '确认导入', {
      type: 'warning',
      confirmButtonText: '确认导入',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  importing.value = true
  try {
    const res = await confirmQuestionImport(token)
    ElMessage.success(`导入成功：新增 ${res.created} 道（待审核）`)
    importVisible.value = false
    handleSearch()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '导入失败')
  } finally {
    importing.value = false
  }
}

async function handleDownloadTemplate() {
  try {
    await downloadQuestionTemplate()
    ElMessage.success('导入模板已下载')
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '模板下载失败')
  }
}

const canConfirmImport = () => !!preview.value?.importToken && preview.value.summary.errorCount === 0

/** 详情/行共用：按状态给操作按钮 */
function rowOps(status: QuestionStatus) {
  if (status === 'pending') return ['pass', 'reject'] as const
  if (status === 'onShelf') return ['unpublish'] as const
  if (status === 'offShelf') return ['online'] as const
  return ['resubmit'] as const
}
</script>

<template>
  <div v-loading="loading || importing">
    <!-- 统计卡片（需求 4.3.3 七卡） -->
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">题目总数</span><span class="stat-icon">📝</span></div>
        <div class="stat-value">{{ summary.total }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">已上架</span><span class="stat-icon">✅</span></div>
        <div class="stat-value">{{ summary.onShelf }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">待审核</span><span class="stat-icon">⏳</span></div>
        <div class="stat-value">{{ summary.pending }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">单选题</span><span class="stat-icon">🔘</span></div>
        <div class="stat-value">{{ summary.single }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">多选题</span><span class="stat-icon">☑️</span></div>
        <div class="stat-value">{{ summary.multiple }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">判断题</span><span class="stat-icon">⚖️</span></div>
        <div class="stat-value">{{ summary.judge }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">简答题</span><span class="stat-icon">✍️</span></div>
        <div class="stat-value">{{ summary.short }}</div>
      </div>
    </div>

    <!-- 工具栏：筛选 + 操作同行 -->
    <div class="list-toolbar">
      <el-input
        v-model="filter.keyword"
        style="width: 200px"
        placeholder="搜索题干 / 标签关键词"
        clearable
        @input="onKeywordInput"
      />
      <el-select v-model="filter.stageId" placeholder="全部阶段" clearable style="width: 180px" @change="handleSearch">
        <el-option-group v-for="s in subjectOptions.filter((x) => x.stages.length)" :key="s.id" :label="s.name">
          <el-option v-for="st in s.stages" :key="st.id" :label="st.name" :value="st.id" />
        </el-option-group>
      </el-select>
      <el-select v-model="filter.type" placeholder="全部类型" style="width: 120px" @change="handleSearch">
        <el-option label="全部类型" value="" />
        <el-option v-for="(label, key) in TYPE_LABEL" :key="key" :label="label" :value="key" />
      </el-select>
      <el-select v-model="filter.difficulty" placeholder="全部难度" style="width: 120px" @change="handleSearch">
        <el-option label="全部难度" value="" />
        <el-option v-for="(label, key) in DIFF_LABEL" :key="key" :label="label" :value="key" />
      </el-select>
      <el-select v-model="filter.status" placeholder="全部状态" style="width: 130px" @change="handleSearch">
        <el-option label="全部状态" value="" />
        <el-option v-for="(label, key) in STATUS_LABEL" :key="key" :label="label" :value="key" />
      </el-select>
      <div class="toolbar-actions">
        <el-button v-permission="'question:review'" type="primary" plain @click="handleBatchReview">
          <el-icon class="btn-ic"><CircleCheck /></el-icon>批量通过
        </el-button>
        <el-button v-permission="'question:edit'" @click="handleBatchStatus('submit')">
          <el-icon class="btn-ic"><Top /></el-icon>批量上架
        </el-button>
        <el-button v-permission="'question:edit'" @click="handleBatchStatus('unpublish')">
          <el-icon class="btn-ic"><Bottom /></el-icon>批量下架
        </el-button>
        <el-button v-permission="'question:delete'" type="danger" plain @click="handleBatchDelete">
          <el-icon class="btn-ic"><Delete /></el-icon>批量删除
        </el-button>
        <el-button v-permission="'question:import'" @click="openImport">
          <el-icon class="btn-ic"><Upload /></el-icon>导入 Excel
        </el-button>
        <el-button v-permission="'question:export'" :loading="exporting" @click="handleExport">
          <el-icon class="btn-ic"><Download /></el-icon>导出 Excel
        </el-button>
        <el-button v-permission="'question:create'" type="primary" @click="openForm()">
          <el-icon class="btn-ic"><Plus /></el-icon>新增题目
        </el-button>
        <span class="count-text">已选 {{ selected.length }} 项 / 共 {{ total }} 题</span>
      </div>
    </div>

    <!-- 表格 -->
    <el-table v-loading="loading" :data="rows" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="42" />
      <el-table-column label="ID" width="80">
        <template #default="{ row }">#{{ row.id }}</template>
      </el-table-column>
      <el-table-column label="题目" min-width="280" show-overflow-tooltip>
        <template #default="{ row }">
          <el-button link type="primary" class="stem-btn" @click="openDetail(row)">{{ row.content }}</el-button>
        </template>
      </el-table-column>
      <el-table-column label="阶段" min-width="130">
        <template #default="{ row }">
          <div>{{ row.stageName }}</div>
          <div class="muted sub-text">{{ row.subjectName }}</div>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="80">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ TYPE_LABEL[row.type] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="难度" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="DIFF_TAG[row.difficulty]" effect="plain">{{ DIFF_LABEL[row.difficulty] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="STATUS_TAG[row.status]">{{ STATUS_LABEL[row.status] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createdAt" label="创建时间" min-width="150" />
      <el-table-column label="操作" width="272" fixed="right" class-name="actions-cell">
        <template #default="{ row }">
          <template v-for="op in rowOps(row.status)" :key="op">
            <el-button
              v-if="op === 'pass'"
              v-permission="'question:review'"
              link
              type="primary"
              @click="handleReview(row, 'pass')"
            >
              <el-icon class="btn-ic"><CircleCheck /></el-icon>通过
            </el-button>
            <el-button
              v-else-if="op === 'reject'"
              v-permission="'question:review'"
              link
              type="danger"
              @click="handleReview(row, 'reject')"
            >
              <el-icon class="btn-ic"><CircleClose /></el-icon>不通过
            </el-button>
            <el-button
              v-else-if="op === 'unpublish'"
              v-permission="'question:edit'"
              link
              type="warning"
              @click="handleUnpublish(row)"
            >
              <el-icon class="btn-ic"><Bottom /></el-icon>下架
            </el-button>
            <el-button
              v-else-if="op === 'online'"
              v-permission="'question:edit'"
              link
              type="primary"
              @click="handleSubmit(row, true)"
            >
              <el-icon class="btn-ic"><Top /></el-icon>上架
            </el-button>
            <el-button v-else v-permission="'question:edit'" link type="primary" @click="handleSubmit(row, false)">
              <el-icon class="btn-ic"><RefreshRight /></el-icon>重新提交
            </el-button>
          </template>
          <el-button v-permission="'question:edit'" link type="primary" @click="openForm(row)">
            <el-icon class="btn-ic"><EditPen /></el-icon>编辑
          </el-button>
          <el-button v-permission="'question:delete'" link type="danger" @click="handleDeleteOne(row)">
            <el-icon class="btn-ic"><Delete /></el-icon>删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && !rows.length" description="暂无匹配的题目，试试调整筛选条件" />

    <!-- 分页 -->
    <el-pagination
      v-model:current-page="pageNum"
      v-model:page-size="pageSize"
      class="pagination"
      :total="total"
      :page-sizes="[10, 20, 50]"
      layout="total, sizes, prev, pager, next"
      @current-change="load"
      @size-change="handleSearch"
    />

    <!-- ===================== 新增 / 编辑弹窗 ===================== -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="680px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="题目内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="4" maxlength="5000" placeholder="请输入题干" />
        </el-form-item>
        <div class="form-row">
          <el-form-item label="阶段" prop="stageId" class="flex-1">
            <el-select v-model="form.stageId" placeholder="请选择阶段" style="width: 100%">
              <el-option-group v-for="s in subjectOptions.filter((x) => x.stages.length)" :key="s.id" :label="s.name">
                <el-option v-for="st in s.stages" :key="st.id" :label="st.name" :value="st.id" />
              </el-option-group>
            </el-select>
          </el-form-item>
          <el-form-item label="类型" prop="type" class="flex-1">
            <el-select v-model="form.type" placeholder="请选择类型" style="width: 100%">
              <el-option v-for="(label, key) in TYPE_LABEL" :key="key" :label="label" :value="key" />
            </el-select>
          </el-form-item>
          <el-form-item label="难度" prop="difficulty" class="flex-1">
            <el-select v-model="form.difficulty" style="width: 100%">
              <el-option v-for="(label, key) in DIFF_LABEL" :key="key" :label="label" :value="key" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="标签">
          <el-input v-model="form.tagsText" placeholder="多个标签用逗号分隔，如 大模型,基础概念" />
        </el-form-item>

        <!-- 单选/多选：选项管理 -->
        <template v-if="form.type === 'single' || form.type === 'multiple'">
          <div class="field-label">选项管理（2~6 项，勾选正确答案）</div>
          <div v-for="(opt, i) in options" :key="opt.key" class="opt-row">
            <el-radio
              v-if="form.type === 'single'"
              :model-value="opt.isCorrect"
              @change="setSingleCorrect(i)"
            >
              <span class="opt-key">{{ opt.key }}</span>
            </el-radio>
            <el-checkbox v-else :model-value="opt.isCorrect" @change="options[i].isCorrect = $event === true">
              <span class="opt-key">{{ opt.key }}</span>
            </el-checkbox>
            <el-input v-model="opt.content" maxlength="500" :placeholder="`选项 ${opt.key} 内容`" />
            <el-button link type="danger" :disabled="options.length <= 2" @click="removeOption(i)">删除</el-button>
          </div>
          <el-button size="small" :disabled="options.length >= 6" @click="addOption">
            <el-icon class="btn-ic"><Plus /></el-icon>添加选项
          </el-button>
        </template>

        <!-- 判断题 -->
        <el-form-item v-else-if="form.type === 'judge'" label="正确答案">
          <el-radio-group v-model="form.judgeAnswer">
            <el-radio :value="true">正确</el-radio>
            <el-radio :value="false">错误</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- 简答题 -->
        <el-form-item v-else-if="form.type === 'short'" label="参考答案">
          <el-input v-model="form.referenceAnswer" type="textarea" :rows="3" maxlength="5000" placeholder="可留空" />
        </el-form-item>

        <el-form-item label="解析">
          <el-input v-model="form.analysis" type="textarea" :rows="3" maxlength="5000" placeholder="答案解析（选填）" />
        </el-form-item>
        <el-form-item label="状态">
          <div class="muted">
            {{ editingId === null ? '待审核（新增题目保存后进入待审核）' : `当前状态：${STATUS_LABEL[currentStatus]}（状态由流转操作变更，此处只读）` }}
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false"><el-icon class="btn-ic"><Close /></el-icon>取消</el-button>
        <el-button type="primary" @click="handleSave"><el-icon class="btn-ic"><Check /></el-icon>保存</el-button>
      </template>
    </el-dialog>

    <!-- ===================== 详情抽屉 ===================== -->
    <el-drawer v-model="drawerVisible" title="题目详情" size="520px">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="题目 ID">#{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="阶段">{{ detail.subjectName }} · {{ detail.stageName }}</el-descriptions-item>
          <el-descriptions-item label="类型 / 难度">
            {{ TYPE_LABEL[detail.type] }} / {{ DIFF_LABEL[detail.difficulty] }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="STATUS_TAG[detail.status]">{{ STATUS_LABEL[detail.status] }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="题干">{{ detail.content }}</el-descriptions-item>
        </el-descriptions>

        <template v-if="detail.options.length">
          <h4 class="drawer-title">选项</h4>
          <div v-for="o in detail.options" :key="o.key" class="opt-view">
            <el-tag size="small" :type="o.isCorrect ? 'success' : 'info'" effect="plain">{{ o.key }}</el-tag>
            <span :class="{ 'opt-correct': o.isCorrect }">{{ o.content }}</span>
            <el-tag v-if="o.isCorrect" size="small" type="success" effect="plain">正确</el-tag>
          </div>
        </template>
        <template v-if="detail.type === 'judge'">
          <h4 class="drawer-title">正确答案</h4>
          <div>{{ detail.judgeAnswer ? '正确' : '错误' }}</div>
        </template>
        <template v-if="detail.type === 'short'">
          <h4 class="drawer-title">参考答案</h4>
          <div>{{ detail.referenceAnswer || '（可留空）' }}</div>
        </template>

        <h4 class="drawer-title">标签</h4>
        <div>
          <el-tag v-for="t in detail.tags" :key="t" size="small" effect="plain" class="tag-gap">{{ t }}</el-tag>
          <span v-if="!detail.tags.length" class="muted">—</span>
        </div>

        <h4 class="drawer-title">解析</h4>
        <div>{{ detail.analysis || '—' }}</div>

        <h4 class="drawer-title">答题统计</h4>
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="答题次数">{{ detail.stats.answerCount }}</el-descriptions-item>
          <el-descriptions-item label="正确次数">{{ detail.stats.correctCount }}</el-descriptions-item>
          <el-descriptions-item label="正确率">{{ detail.stats.accuracy }}%</el-descriptions-item>
        </el-descriptions>
        <div class="muted created-line">创建于 {{ detail.createdAt }}<template v-if="detail.createdBy"> · 创建人 {{ detail.createdBy }}</template></div>
      </template>
      <template #footer>
        <template v-if="detail">
          <el-button
            v-if="detail.status === 'pending'"
            v-permission="'question:review'"
            type="primary"
            @click="handleReview(detail, 'pass')"
          >
            <el-icon class="btn-ic"><CircleCheck /></el-icon>通过
          </el-button>
          <el-button
            v-if="detail.status === 'pending'"
            v-permission="'question:review'"
            type="danger"
            plain
            @click="handleReview(detail, 'reject')"
          >
            <el-icon class="btn-ic"><CircleClose /></el-icon>不通过
          </el-button>
          <el-button
            v-if="detail.status === 'onShelf'"
            v-permission="'question:edit'"
            type="warning"
            plain
            @click="handleUnpublish(detail)"
          >
            <el-icon class="btn-ic"><Bottom /></el-icon>下架
          </el-button>
          <el-button
            v-if="detail.status === 'offShelf'"
            v-permission="'question:edit'"
            type="primary"
            @click="handleSubmit(detail, true)"
          >
            <el-icon class="btn-ic"><Top /></el-icon>上架
          </el-button>
          <el-button
            v-if="detail.status === 'rejected' || detail.status === 'draft'"
            v-permission="'question:edit'"
            type="primary"
            @click="handleSubmit(detail, false)"
          >
            <el-icon class="btn-ic"><RefreshRight /></el-icon>重新提交
          </el-button>
          <el-button v-permission="'question:edit'" @click="openForm(detail)">
            <el-icon class="btn-ic"><EditPen /></el-icon>编辑
          </el-button>
          <el-button v-permission="'question:delete'" type="danger" plain @click="handleDeleteOne(detail)">
            <el-icon class="btn-ic"><Delete /></el-icon>删除
          </el-button>
        </template>
      </template>
    </el-drawer>

    <!-- ===================== 批量导入弹窗 ===================== -->
    <el-dialog v-model="importVisible" title="手动导入题目" width="680px" @closed="resetImport">
      <div class="import-drop" @click="fileInputEl?.click()" @dragover.prevent @dragleave.prevent @drop="onDrop">
        <div class="drop-icon">📄</div>
        <div class="drop-text">
          将 Excel 文件拖拽到此处，或
          <span class="drop-link" @click.stop="fileInputEl?.click()">选择文件</span>
        </div>
        <div class="field-hint">支持 .xlsx / .xls，单张工作表、单次 ≤ 500 道、≤ 5MB</div>
        <input ref="fileInputEl" type="file" class="hidden-input" accept=".xlsx,.xls" @change="onFileChange" />
      </div>
      <div class="import-bar">
        <span class="muted">{{ importFileName || '尚未选择文件' }}</span>
        <el-button size="small" @click="handleDownloadTemplate">
          <el-icon class="btn-ic"><Download /></el-icon>下载导入模板
        </el-button>
      </div>

      <div class="import-note">
        <b>导入说明</b><br />
        1. 表头按<b>列名识别</b>，列顺序可变；共 14 列：学科、阶段、题干、题型、难度、选项A~F、正确答案、解析、标签；必需列「学科」「阶段」「题干」「题型」「难度」「正确答案」缺一即整份文件报错。<br />
        2. 可混排单选 / 多选 / 判断 / 简答四种题型；判断 / 简答行的选项列请留空。<br />
        3. 阶段按<b>「学科 + 阶段」两级定位</b>，查不到即整份拒绝。<br />
        4. 「正确答案」：单选填 1 个选项字母（如 B）；多选填多个字母（如 ABC）；判断填「正确 / 错误」；简答填参考答案（可留空）。<br />
        5. 任一无效行（题干缺失、题型/难度无效、正确答案与选项不匹配等）即<b>整份拒绝导入</b>，报出行号与原因，一行数据都不写入，修正后重新上传。<br />
        6. 导入的题目统一进入<b>「待审核」</b>，审核通过后上架。
      </div>

      <!-- 预览 -->
      <template v-if="preview">
        <div v-if="preview.summary.errorCount > 0" class="import-alert error">
          解析失败：共 {{ preview.summary.errorCount }} 处无效行，已整份拒绝导入（一行都未写入），请修正后重新上传。
        </div>
        <div v-else class="import-alert ok">
          解析完成：共 {{ preview.summary.totalRows }} 行，全部可导入（新增 {{ preview.summary.newCount }} 道，入库后为「待审核」）
        </div>

        <el-table v-if="preview.errors.length" :data="preview.errors" size="small" class="import-table">
          <el-table-column prop="rowNo" label="行号" width="70">
            <template #default="{ row }">{{ row.rowNo === 0 ? '文件' : row.rowNo }}</template>
          </el-table-column>
          <el-table-column prop="reason" label="原因" />
        </el-table>

        <el-table v-if="preview.rows.length" :data="preview.rows" size="small" class="import-table">
          <el-table-column prop="rowNo" label="行号" width="64" />
          <el-table-column prop="content" label="题干" min-width="220" show-overflow-tooltip />
          <el-table-column label="学科 / 阶段" min-width="150">
            <template #default="{ row }">{{ row.subjectName }} · {{ row.stageName }}</template>
          </el-table-column>
          <el-table-column label="题型" width="70">
            <template #default="{ row }">{{ TYPE_LABEL[row.type] }}</template>
          </el-table-column>
          <el-table-column label="难度" width="70">
            <template #default="{ row }">{{ DIFF_LABEL[row.difficulty] }}</template>
          </el-table-column>
        </el-table>
      </template>

      <template #footer>
        <el-button @click="importVisible = false"><el-icon class="btn-ic"><Close /></el-icon>取消</el-button>
        <el-button type="primary" :disabled="!canConfirmImport()" @click="handleConfirmImport">
          <el-icon class="btn-ic"><Check /></el-icon>确认导入
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.stat-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 14px 16px;
}
.stat-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.stat-label {
  font-size: 12px;
  color: var(--ink-3);
}
.stat-icon {
  font-size: 16px;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  margin-top: 4px;
}
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
.sub-text {
  font-size: 11px;
}
.stem-btn {
  padding: 0;
  justify-content: flex-start;
  white-space: normal;
  text-align: left;
  height: auto;
}

/* ---- 表单 ---- */
.form-row {
  display: flex;
  gap: 16px;
}
.form-row .el-form-item {
  flex: 1;
  min-width: 0;
}
.field-label {
  font-size: 13px;
  color: var(--ink-2);
  margin-bottom: 6px;
}
.field-hint {
  width: 100%;
  font-size: 12px;
  color: var(--ink-3);
  line-height: 1.6;
}
.opt-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.opt-key {
  font-weight: 600;
  min-width: 16px;
}
.opt-view {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
}
.opt-correct {
  color: var(--brand);
}
.tag-gap {
  margin-right: 6px;
}
.drawer-title {
  margin: 16px 0 8px;
  font-size: 14px;
}
.created-line {
  margin-top: 12px;
  font-size: 12px;
}

/* ---- 批量导入 ---- */
.import-drop {
  border: 1px dashed var(--line-strong, var(--line));
  border-radius: var(--radius);
  padding: 28px 16px;
  text-align: center;
  cursor: pointer;
  transition: border-color .2s, background .2s;
}
.import-drop:hover {
  border-color: var(--brand);
  background: var(--brand-light);
}
.drop-icon {
  font-size: 34px;
}
.drop-text {
  margin: 8px 0;
}
.drop-link {
  color: var(--brand);
  cursor: pointer;
  text-decoration: underline;
}
.hidden-input {
  display: none;
}
.import-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
}
.import-note {
  margin-top: 12px;
  padding: 12px 14px;
  background: var(--surface-2);
  border-radius: var(--radius);
  font-size: 12px;
  line-height: 1.9;
  color: var(--ink-2);
}
.import-alert {
  margin-top: 12px;
  padding: 10px 14px;
  border-radius: var(--radius);
  font-size: 13px;
}
.import-alert.ok {
  background: var(--brand-light);
  color: var(--brand);
}
.import-alert.error {
  background: var(--danger-bg, #fef0f0);
  color: var(--danger-text, #f56c6c);
}
.import-table {
  margin-top: 8px;
}

@media (max-width: 1200px) {
  .stat-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}
</style>
