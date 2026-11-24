<script setup lang="ts">
/**
 * 面试题库管理（04 §4.6 / 需求 4.3.4 / prototype/admin/interview-questions.html）。
 * 主题为自由文本模糊筛选（D4-20：无词表下拉）；编辑仅主题与难度；导入 6 列两段式；
 * 来源标识（题干旁）+ 来源列（文件名·第 N 行 / 手工录入）；删除风险提示按来源区分。
 * 按钮级权限 v-permission（interviewbank:view/edit/delete；学科字典需 subject:view）。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import type { ApiError } from '@shared/types/api'
import {
  confirmInterviewImport,
  createInterviewQuestion,
  deleteInterviewQuestion,
  downloadInterviewTemplate,
  fetchInterviewQuestion,
  fetchInterviewQuestions,
  previewInterviewImport,
  updateInterviewQuestion,
} from '@/api/interviewQuestions'
import type {
  InterviewImportPreviewResult,
  InterviewQuestionDetail,
  InterviewQuestionListItem,
} from '@/api/interviewQuestions'
import { fetchSubjects } from '@/api/subjects'
import type { SubjectItem } from '@/api/subjects'

const DIFF_LABEL: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' }
const DIFF_TAG: Record<string, 'success' | 'warning' | 'danger'> = {
  easy: 'success',
  medium: 'warning',
  hard: 'danger',
}

// ===================== 列表 =====================
const loading = ref(false)
const rows = ref<InterviewQuestionListItem[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const filter = reactive({ keyword: '', subjectId: '' as string | number, topic: '', difficulty: '', unclassifiedOnly: false })
const subjectOptions = ref<SubjectItem[]>([])

function buildQuery() {
  return {
    keyword: filter.keyword.trim() || undefined,
    subjectId: filter.subjectId ? Number(filter.subjectId) : undefined,
    topic: filter.topic.trim() || undefined,
    difficulty: filter.difficulty || undefined,
    unclassifiedOnly: filter.unclassifiedOnly || undefined,
    pageNum: pageNum.value,
    pageSize: pageSize.value,
  }
}

async function load() {
  loading.value = true
  try {
    const res = await fetchInterviewQuestions(buildQuery())
    rows.value = res.list
    total.value = res.total
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

function handleReset() {
  Object.assign(filter, { keyword: '', subjectId: '', topic: '', difficulty: '', unclassifiedOnly: false })
  handleSearch()
}

/** 只看未分类与主题筛选互斥（04 §4.6） */
function onUnclassifiedChange(val: boolean) {
  if (val) filter.topic = ''
  handleSearch()
}

onMounted(() => {
  load()
  fetchSubjects()
    .then((res) => {
      subjectOptions.value = res.list
    })
    .catch(() => {})
})

function sourceLabel(row: InterviewQuestionListItem): string {
  return row.sourceType === 'manual'
    ? '手工录入'
    : row.sourceFile
      ? `${row.sourceFile} · 第 ${row.sourceRow} 行`
      : 'Excel 导入'
}

// ===================== 详情抽屉 =====================
const drawerVisible = ref(false)
const detail = ref<InterviewQuestionDetail | null>(null)

async function openDetail(row: InterviewQuestionListItem) {
  try {
    detail.value = await fetchInterviewQuestion(row.id)
    drawerVisible.value = true
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '加载详情失败')
  }
}

// ===================== 录入弹窗 =====================
const createVisible = ref(false)
const createFormRef = ref<FormInstance>()
const createForm = reactive({
  subjectId: '' as string | number,
  content: '',
  referenceAnswer: '',
  topic: '',
  difficulty: 'medium' as 'easy' | 'medium' | 'hard',
  tagsText: '',
})
const createRules: FormRules = {
  subjectId: [{ required: true, message: '请选择所属知识库', trigger: 'change' }],
  content: [{ required: true, message: '请输入题干', trigger: 'blur' }],
}

function openCreate() {
  Object.assign(createForm, {
    subjectId: subjectOptions.value[0]?.id ?? '',
    content: '',
    referenceAnswer: '',
    topic: '',
    difficulty: 'medium',
    tagsText: '',
  })
  createVisible.value = true
}

async function handleCreate() {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return
  try {
    await createInterviewQuestion({
      subjectId: Number(createForm.subjectId),
      content: createForm.content.trim(),
      referenceAnswer: createForm.referenceAnswer.trim() || null,
      topic: createForm.topic.trim() || null,
      difficulty: createForm.difficulty,
      tags: createForm.tagsText
        .split(/[,，、]/)
        .map((t) => t.trim())
        .filter(Boolean),
    })
    ElMessage.success('录入成功')
    createVisible.value = false
    handleSearch()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '录入失败')
  }
}

// ===================== 编辑弹窗（仅主题与难度） =====================
const editVisible = ref(false)
const editing = ref<InterviewQuestionDetail | null>(null)
const editForm = reactive({ topic: '', difficulty: 'medium' as 'easy' | 'medium' | 'hard' })

function openEdit(row: InterviewQuestionListItem) {
  fetchInterviewQuestion(row.id)
    .then((d) => {
      editing.value = d
      editForm.topic = d.topic ?? ''
      editForm.difficulty = d.difficulty
      editVisible.value = true
    })
    .catch((e) => ElMessage.error((e as ApiError)?.message || '加载失败'))
}

async function handleEditSave() {
  if (!editing.value) return
  try {
    await updateInterviewQuestion(editing.value.id, {
      topic: editForm.topic.trim() || null,
      difficulty: editForm.difficulty,
    })
    ElMessage.success('已保存')
    editVisible.value = false
    load()
    if (drawerVisible.value && detail.value?.id === editing.value.id) {
      detail.value = await fetchInterviewQuestion(editing.value.id)
    }
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '保存失败')
  }
}

// ===================== 删除（风险提示按来源区分） =====================
async function handleDelete(row: InterviewQuestionListItem) {
  const warn =
    row.sourceType === 'manual'
      ? '手工录入无源文档，删除后不可恢复！'
      : `数据来自导入文件 ${row.sourceFile}，删除后可由源文件恢复。`
  try {
    await ElMessageBox.confirm(`${warn}\n确定删除该题目吗？`, '删除题目', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteInterviewQuestion(row.id)
    ElMessage.success('已删除')
    load()
    if (drawerVisible.value && detail.value?.id === row.id) drawerVisible.value = false
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '删除失败')
  }
}

// ===================== 批量导入（两段式） =====================
const importVisible = ref(false)
const importFileName = ref('')
const importFile = ref<File | null>(null)
const fileInputEl = ref<HTMLInputElement | null>(null)
const importing = ref(false)
const preview = ref<InterviewImportPreviewResult | null>(null)

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
    preview.value = await previewInterviewImport(importFile.value)
    if (preview.value.summary.errorCount > 0) {
      ElMessage.error('校验未通过，整份文件已拒绝导入，请修正后重新上传')
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
    await ElMessageBox.confirm(`确认导入 ${preview.value.summary.totalRows} 道面试题吗？`, '确认导入', {
      type: 'warning',
      confirmButtonText: '确认导入',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  importing.value = true
  try {
    const res = await confirmInterviewImport(token)
    ElMessage.success(`导入成功：新增 ${res.created} 道`)
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
    await downloadInterviewTemplate()
    ElMessage.success('导入模板已下载')
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '模板下载失败')
  }
}

const canConfirmImport = () => !!preview.value?.importToken && preview.value.summary.errorCount === 0
</script>

<template>
  <div v-loading="loading || importing">
    <!-- 工具栏：筛选 + 操作（需求 4.3.4：查询/重置/手动导入/录入题目） -->
    <div class="list-toolbar">
      <el-input
        v-model="filter.keyword"
        style="width: 200px"
        placeholder="搜索题干关键词"
        clearable
        @keyup.enter="handleSearch"
      />
      <el-select v-model="filter.subjectId" placeholder="全部知识库" clearable style="width: 190px" @change="handleSearch">
        <el-option v-for="s in subjectOptions" :key="s.id" :label="s.name" :value="s.id" />
      </el-select>
      <el-input
        v-model="filter.topic"
        style="width: 150px"
        placeholder="主题（模糊）"
        clearable
        :disabled="filter.unclassifiedOnly"
        @keyup.enter="handleSearch"
      />
      <el-select v-model="filter.difficulty" placeholder="全部难度" style="width: 120px" @change="handleSearch">
        <el-option label="全部难度" value="" />
        <el-option v-for="(label, key) in DIFF_LABEL" :key="key" :label="label" :value="key" />
      </el-select>
      <el-checkbox v-model="filter.unclassifiedOnly" @change="onUnclassifiedChange">只看未分类</el-checkbox>
      <div class="toolbar-actions">
        <el-button type="primary" @click="handleSearch"><el-icon class="btn-ic"><Search /></el-icon>查询</el-button>
        <el-button @click="handleReset"><el-icon class="btn-ic"><Refresh /></el-icon>重置</el-button>
        <el-button v-permission="'interviewbank:edit'" @click="openImport">
          <el-icon class="btn-ic"><Upload /></el-icon>手动导入
        </el-button>
        <el-button v-permission="'interviewbank:edit'" type="primary" @click="openCreate">
          <el-icon class="btn-ic"><Plus /></el-icon>录入题目
        </el-button>
        <span class="count-text">共 {{ total }} 题</span>
      </div>
    </div>

    <!-- 表格（铺满内容区宽度） -->
    <el-table v-loading="loading" :data="rows">
      <el-table-column label="题目" min-width="380">
        <template #default="{ row }">
          <div class="stem-cell">
            <span class="stem-link" :title="row.content" @click="openDetail(row)">{{ row.content }}</span>
            <el-tooltip :content="sourceLabel(row)" placement="top">
              <el-tag size="small" type="info" effect="plain" class="source-mark">
                {{ row.sourceType === 'manual' ? '手工录入' : 'Excel 导入' }}
              </el-tag>
            </el-tooltip>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="来源" min-width="180">
        <template #default="{ row }">
          <span class="muted">{{ sourceLabel(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="难度" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="DIFF_TAG[row.difficulty]" effect="plain">{{ DIFF_LABEL[row.difficulty] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="主题" min-width="120">
        <template #default="{ row }">
          <span v-if="row.topic">{{ row.topic }}</span>
          <span v-else class="muted">未分类</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="212" fixed="right" class-name="actions-cell">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)"><el-icon class="btn-ic"><View /></el-icon>详情</el-button>
          <el-button v-permission="'interviewbank:edit'" link type="primary" @click="openEdit(row)">
            <el-icon class="btn-ic"><EditPen /></el-icon>编辑
          </el-button>
          <el-button v-permission="'interviewbank:delete'" link type="danger" @click="handleDelete(row)">
            <el-icon class="btn-ic"><Delete /></el-icon>删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty
      v-if="!loading && !rows.length"
      :description="filter.unclassifiedOnly ? '没有未分类的题目 —— 题库里的题都标好主题了' : '没有符合条件的题目'"
    />

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

    <!-- ===================== 录入弹窗 ===================== -->
    <el-dialog v-model="createVisible" title="录入题目" width="640px">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-position="top">
        <el-form-item label="所属知识库" prop="subjectId">
          <el-select v-model="createForm.subjectId" placeholder="请选择知识库" style="width: 100%">
            <el-option v-for="s in subjectOptions" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="题干" prop="content">
          <el-input v-model="createForm.content" type="textarea" :rows="4" maxlength="5000" placeholder="请输入面试题题干" />
        </el-form-item>
        <el-form-item label="参考答案">
          <el-input
            v-model="createForm.referenceAnswer"
            type="textarea"
            :rows="4"
            maxlength="10000"
            placeholder="可留空"
          />
        </el-form-item>
        <div class="form-row">
          <el-form-item label="主题" class="flex-1">
            <el-input v-model="createForm.topic" maxlength="100" placeholder="留空表示未分类" />
          </el-form-item>
          <el-form-item label="难度" class="flex-1">
            <el-select v-model="createForm.difficulty" style="width: 100%">
              <el-option v-for="(label, key) in DIFF_LABEL" :key="key" :label="label" :value="key" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="标签">
          <el-input v-model="createForm.tagsText" placeholder="多个标签用逗号分隔" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false"><el-icon class="btn-ic"><Close /></el-icon>取消</el-button>
        <el-button type="primary" @click="handleCreate"><el-icon class="btn-ic"><Check /></el-icon>保存</el-button>
      </template>
    </el-dialog>

    <!-- ===================== 编辑弹窗（仅主题与难度） ===================== -->
    <el-dialog v-model="editVisible" title="编辑题目" width="560px">
      <template v-if="editing">
        <div class="field-label">题干</div>
        <div class="readonly-box">{{ editing.content }}</div>
        <div class="field-label">参考答案</div>
        <div class="readonly-box">{{ editing.referenceAnswer || '（无参考答案）' }}</div>
        <el-form label-position="top" class="edit-form">
          <div class="form-row">
            <el-form-item label="主题" class="flex-1">
              <el-input v-model="editForm.topic" maxlength="100" placeholder="留空表示未分类（可清空）" />
            </el-form-item>
            <el-form-item label="难度" class="flex-1">
              <el-select v-model="editForm.difficulty" style="width: 100%">
                <el-option v-for="(label, key) in DIFF_LABEL" :key="key" :label="label" :value="key" />
              </el-select>
            </el-form-item>
          </div>
          <div class="field-hint">题干与参考答案录入后不可修改（需求 4.3.4），仅主题与难度可调整</div>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="editVisible = false"><el-icon class="btn-ic"><Close /></el-icon>取消</el-button>
        <el-button type="primary" @click="handleEditSave"><el-icon class="btn-ic"><Check /></el-icon>保存</el-button>
      </template>
    </el-dialog>

    <!-- ===================== 详情抽屉 ===================== -->
    <el-drawer v-model="drawerVisible" title="题目详情" size="520px">
      <template v-if="detail">
        <div class="field-label">题干</div>
        <div class="readonly-box">{{ detail.content }}</div>
        <div class="field-label">参考答案</div>
        <div class="readonly-box">{{ detail.referenceAnswer || '（无参考答案）' }}</div>
        <el-descriptions :column="1" border class="detail-desc">
          <el-descriptions-item label="来源">
            <el-tag size="small" type="info" effect="plain">
              {{ detail.sourceType === 'manual' ? '手工录入' : 'Excel 导入' }}
            </el-tag>
            <span class="muted source-detail">{{ sourceLabel(detail) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="难度">
            <el-tag size="small" :type="DIFF_TAG[detail.difficulty]" effect="plain">
              {{ DIFF_LABEL[detail.difficulty] }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="主题">{{ detail.topic || '未分类' }}</el-descriptions-item>
          <el-descriptions-item label="标签">
            <el-tag v-for="t in detail.tags" :key="t" size="small" effect="plain" class="tag-gap">{{ t }}</el-tag>
            <span v-if="!detail.tags.length" class="muted">（无）</span>
          </el-descriptions-item>
          <el-descriptions-item label="所属知识库">{{ detail.subjectName }}</el-descriptions-item>
        </el-descriptions>
        <div class="muted created-line">创建于 {{ detail.createdAt }}</div>
      </template>
      <template #footer>
        <template v-if="detail">
          <el-button v-permission="'interviewbank:edit'" type="primary" @click="openEdit(detail)">
            <el-icon class="btn-ic"><EditPen /></el-icon>编辑
          </el-button>
          <el-button v-permission="'interviewbank:delete'" type="danger" plain @click="handleDelete(detail)">
            <el-icon class="btn-ic"><Delete /></el-icon>删除
          </el-button>
        </template>
      </template>
    </el-drawer>

    <!-- ===================== 手动导入弹窗 ===================== -->
    <el-dialog v-model="importVisible" title="手动导入题目" width="680px" @closed="resetImport">
      <div class="import-drop" @click="fileInputEl?.click()" @dragover.prevent @dragleave.prevent @drop="onDrop">
        <div class="drop-icon">📄</div>
        <div class="drop-text">
          将 Excel 文件拖拽到此处，或
          <span class="drop-link" @click.stop="fileInputEl?.click()">选择文件</span>
        </div>
        <div class="field-hint">支持 .xlsx / .xls，单个文件、单次 ≤ 500 行、≤ 5MB，仅读第一张工作表</div>
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
        1. 表头按<b>列名识别</b>，列顺序可变；共 6 列：所属学科、题干、难度、主题、标签、参考答案；「所属学科」「题干」为必需列。<br />
        2. 弹窗内不再选择所属学科，<b>一律以文件「所属学科」列为准</b>，一个文件可含多个学科。<br />
        3. 确认时逐行按文件中的<b>主题 / 难度 / 标签</b>入库；难度留空按「中等」，主题留空为「未分类」。<br />
        4. 任一无效行（所属学科在系统中不存在、题干为空等）即<b>整份拒绝导入</b>，报出行号与原因，修正后重新上传。<br />
        5. 导入题目来源记「文件名 + 第 N 行」，后续可按来源追溯。
      </div>

      <!-- 预览 -->
      <template v-if="preview">
        <div v-if="preview.summary.errorCount > 0" class="import-alert error">
          校验未通过，整份文件已拒绝导入：{{ preview.summary.errorCount }} 处无效行，请修正后重新上传。
        </div>
        <template v-else>
          <div class="import-alert ok">解析完成：共 {{ preview.summary.totalRows }} 行，全部可导入</div>
          <div class="field-label subject-sum-label">涉及学科汇总</div>
          <div class="subject-chips">
            <el-tag v-for="s in preview.subjects" :key="s.subjectName" size="small" effect="plain" class="tag-gap">
              {{ s.subjectName }} × {{ s.count }}
            </el-tag>
          </div>
        </template>

        <el-table v-if="preview.errors.length" :data="preview.errors" size="small" class="import-table">
          <el-table-column prop="rowNo" label="行号" width="70">
            <template #default="{ row }">{{ row.rowNo === 0 ? '文件' : row.rowNo }}</template>
          </el-table-column>
          <el-table-column prop="reason" label="原因" />
        </el-table>

        <el-table v-if="preview.rows.length" :data="preview.rows" size="small" class="import-table">
          <el-table-column prop="rowNo" label="行号" width="64" />
          <el-table-column prop="content" label="题干" min-width="220" show-overflow-tooltip />
          <el-table-column prop="subjectName" label="所属学科" min-width="150" show-overflow-tooltip />
          <el-table-column label="难度" width="70">
            <template #default="{ row }">{{ DIFF_LABEL[row.difficulty] }}</template>
          </el-table-column>
          <el-table-column label="主题" width="100">
            <template #default="{ row }">{{ row.topic || '未分类' }}</template>
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
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}

/* ---- 题目单元格：题干（可点击进详情）+ 来源标识 ---- */
.stem-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.stem-link {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--brand);
  cursor: pointer;
}
.stem-link:hover {
  text-decoration: underline;
}
.source-mark {
  flex-shrink: 0;
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
.readonly-box {
  padding: 10px 12px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm, 6px);
  font-size: 13px;
  line-height: 1.7;
  margin-bottom: 14px;
  white-space: pre-wrap;
  word-break: break-word;
}
.edit-form {
  margin-top: 6px;
}
.tag-gap {
  margin-right: 6px;
}
.detail-desc {
  margin-top: 14px;
}
.source-detail {
  margin-left: 8px;
  font-size: 12px;
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
.subject-sum-label {
  margin-top: 12px;
}
.subject-chips {
  margin-bottom: 4px;
}
.import-table {
  margin-top: 8px;
}
</style>
