<script setup lang="ts">
/**
 * B站课程库（04 §4.4 / 需求 4.3.2 / prototype/admin/courses.html）。
 * 统计卡 + 筛选 + 表格 + 新增/编辑 + 两段式批量导入（预览→确认）+ 删除确认；
 * 相较原型的调整：封面按 B站视频封面 16:10 呈现；不显示 BV号列。
 * 按钮级权限 v-permission（course:view/create/edit/delete）。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import type { ApiError } from '@shared/types/api'
import {
  confirmCourseImport,
  createCourse,
  deleteCourse,
  downloadCourseTemplate,
  exportCourses,
  fetchCourses,
  previewCourseImport,
  updateCourse,
} from '@/api/courses'
import type {
  CourseItem,
  CoursePayload,
  CourseQuery,
  ImportPreviewResult,
} from '@/api/courses'
import { fetchSubjects } from '@/api/subjects'
import type { SubjectItem } from '@/api/subjects'

// ---- 统计卡与列表 ----
const loading = ref(false)
const cards = ref({ total: 0, totalHours: 0, linkedSubjectCount: 0 })
const rows = ref<CourseItem[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)

const filter = reactive({ keyword: '', subjectId: '' as string | number, source: '' })
const subjectOptions = ref<SubjectItem[]>([])

/** 封面加载失败降级为图标占位（URL 失效/跨域不可达时） */
const failedCovers = ref(new Set<number>())

function buildQuery(): CourseQuery {
  return {
    keyword: filter.keyword.trim() || undefined,
    subjectId: filter.subjectId ? Number(filter.subjectId) : undefined,
    source: filter.source || undefined,
    pageNum: pageNum.value,
    pageSize: pageSize.value,
  }
}

async function load() {
  loading.value = true
  try {
    const res = await fetchCourses(buildQuery())
    cards.value = res.cards
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

// 关键词防抖即时筛选（原型交互）
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

/** 时长展示：分钟 → 小时:分钟（如 390 → 6:30） */
function fmtHM(min: number): string {
  return `${Math.floor(min / 60)}:${String(min % 60).padStart(2, '0')}`
}

function parseDuration(str: string): number | null {
  const m = /^(\d{1,3}):([0-5]\d)$/.exec(str.trim())
  if (!m) return null
  const minutes = parseInt(m[1], 10) * 60 + parseInt(m[2], 10)
  return minutes >= 1 ? minutes : null
}

function sourceLabel(source: string): string {
  return source === 'bili' ? 'B站' : '其他'
}

function mainSubject(row: CourseItem) {
  return row.subjects.find((s) => s.isPrimary) ?? row.subjects[0]
}

function subjectTooltip(row: CourseItem): string {
  return row.subjects.map((s) => `${s.isPrimary ? '主·' : ''}${s.name}`).join('、')
}

// ---- 新增 / 编辑弹窗 ----
const dialogVisible = ref(false)
const dialogTitle = ref('新增课程')
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({
  name: '',
  bvid: '',
  duration: '',
  coverUrl: '',
  source: 'bili' as 'bili' | 'other',
  playUrl: '',
})

/** 所属学科勾选顺序（第一个=主学科；「其他学科」排他单选，04 §4.4） */
const checkedOrder = ref<number[]>([])

function otherSubjectId(): number | null {
  return subjectOptions.value.find((s) => s.name === '其他学科')?.id ?? null
}

function isSubjectDisabled(id: number): boolean {
  const otherId = otherSubjectId()
  return otherId !== null && checkedOrder.value.includes(otherId) && id !== otherId
}

function onSubjectCheck(id: number, checked: boolean) {
  const otherId = otherSubjectId()
  if (id === otherId) {
    checkedOrder.value = checked ? [id] : []
    return
  }
  if (checked) {
    if (!checkedOrder.value.includes(id)) checkedOrder.value = [...checkedOrder.value, id]
  } else {
    checkedOrder.value = checkedOrder.value.filter((x) => x !== id)
  }
}

const rules: FormRules = {
  name: [{ required: true, message: '请输入课程名称', trigger: 'blur' }],
  duration: [
    { required: true, message: '请输入时长，格式「小时:分钟」', trigger: 'blur' },
    {
      validator: (_r, value, cb) =>
        parseDuration(String(value ?? '')) ? cb() : cb(new Error('时长格式应为「小时:分钟」，如 6:30')),
      trigger: 'blur',
    },
  ],
}

function openDialog(row?: CourseItem) {
  editingId.value = row?.id ?? null
  dialogTitle.value = row ? '编辑课程' : '新增课程'
  Object.assign(form, {
    name: row?.name ?? '',
    bvid: row?.bvid ?? '',
    duration: row ? fmtHM(row.durationMinutes) : '',
    coverUrl: row?.coverUrl ?? '',
    source: row?.source ?? 'bili',
    playUrl: row?.playUrl ?? '',
  })
  checkedOrder.value = row ? [...row.subjects].sort((a, b) => Number(b.isPrimary) - Number(a.isPrimary)).map((s) => s.id) : []
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  const minutes = parseDuration(form.duration)
  if (!minutes) return
  if (!checkedOrder.value.length) {
    ElMessage.warning('请至少勾选一个所属学科')
    return
  }
  const payload: CoursePayload = {
    name: form.name.trim(),
    bvid: form.bvid.trim() || null,
    coverUrl: form.coverUrl.trim() || null,
    durationMinutes: minutes,
    source: form.source,
    playUrl: form.playUrl.trim() || null,
    subjectIds: checkedOrder.value,
  }
  try {
    if (editingId.value === null) {
      await createCourse(payload)
      ElMessage.success(`新增课程「${payload.name}」成功`)
    } else {
      await updateCourse(editingId.value, payload)
      ElMessage.success(`课程「${payload.name}」已保存`)
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

// ---- 删除（确认提示由列表数据给出，04 §4.4）----
async function handleDelete(row: CourseItem) {
  const msg =
    row.routeRefCount > 0
      ? `该课程已被 ${row.routeRefCount} 条学习路线引用，删除后（逻辑删除，数据保留可恢复）路线中将不可见。确定删除课程「${row.name}」吗？`
      : `确定删除课程「${row.name}」吗？删除后数据保留可恢复。`
  try {
    await ElMessageBox.confirm(msg, '删除课程', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteCourse(row.id)
    ElMessage.success(`已删除课程「${row.name}」`)
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '删除失败')
  }
}

// ---- 导出 Excel（按当前筛选，服务端导出 + 落操作审计）----
const exporting = ref(false)
async function handleExport() {
  exporting.value = true
  try {
    await exportCourses(buildQuery())
    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

// ---- 批量导入（两段式：预览 → 确认）----
const importVisible = ref(false)
const importFileName = ref('')
const importFile = ref<File | null>(null)
const fileInputEl = ref<HTMLInputElement | null>(null)
const importing = ref(false)
const preview = ref<ImportPreviewResult | null>(null)

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
    preview.value = await previewCourseImport(importFile.value)
    if (preview.value.summary.errorCount > 0) {
      ElMessage.error('存在无效行，已整份拒绝导入，请修正后重新上传')
    }
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '文件解析失败')
  } finally {
    importing.value = false
  }
}

const IMPORT_RESULT_LABEL: Record<string, string> = {
  new: '新增',
  update: '覆盖更新',
  warning: '警告',
}

function importResultType(result: string): 'success' | 'primary' | 'warning' {
  return result === 'new' ? 'success' : result === 'update' ? 'primary' : 'warning'
}

async function handleConfirmImport() {
  const token = preview.value?.importToken
  if (!token || !preview.value || preview.value.summary.errorCount > 0) return
  try {
    await ElMessageBox.confirm(
      'Excel 为权威数据源：BV 号重复的课程将被覆盖更新，为空的可选列按空值写入。确定导入吗？',
      '确认导入',
      { type: 'warning', confirmButtonText: '确认导入', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  importing.value = true
  try {
    const res = await confirmCourseImport(token)
    ElMessage.success(`导入成功：新增 ${res.created} 门、更新 ${res.updated} 门`)
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
    await downloadCourseTemplate()
    ElMessage.success('导入模板已下载')
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '模板下载失败')
  }
}

const canConfirmImport = () =>
  !!preview.value?.importToken && preview.value.summary.errorCount === 0
</script>

<template>
  <div v-loading="loading || importing">
    <!-- 统计卡片 -->
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">课程总数</span><span class="stat-icon">🎬</span></div>
        <div class="stat-value">{{ cards.total }}</div>
        <div class="stat-sub">课程库在库课程</div>
      </div>
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">总时长</span><span class="stat-icon">⏱️</span></div>
        <div class="stat-value">{{ cards.totalHours.toFixed(1) }}</div>
        <div class="stat-sub">小时（全部课程合计）</div>
      </div>
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">关联学科数</span><span class="stat-icon">📚</span></div>
        <div class="stat-value">{{ cards.linkedSubjectCount }}</div>
        <div class="stat-sub">不含「其他学科」</div>
      </div>
    </div>

    <!-- 工具栏：筛选 + 操作同行 -->
    <div class="list-toolbar">
      <el-input
        v-model="filter.keyword"
        style="width: 220px"
        placeholder="搜索课程标题"
        clearable
        @input="onKeywordInput"
      />
      <el-select v-model="filter.subjectId" placeholder="全部学科" clearable style="width: 180px" @change="handleSearch">
        <el-option v-for="s in subjectOptions" :key="s.id" :label="s.name" :value="s.id" />
      </el-select>
      <el-select v-model="filter.source" placeholder="全部来源" style="width: 130px" @change="handleSearch">
        <el-option label="全部来源" value="" />
        <el-option label="B站" value="bili" />
        <el-option label="其他" value="other" />
      </el-select>
      <div class="toolbar-actions">
        <el-button v-permission="'course:create'" type="primary" @click="openDialog()">
          <el-icon class="btn-ic"><Plus /></el-icon>新增课程
        </el-button>
        <el-button v-permission="'course:create'" @click="openImport">
          <el-icon class="btn-ic"><Upload /></el-icon>批量导入
        </el-button>
        <el-button v-permission="'course:view'" :loading="exporting" @click="handleExport">
          <el-icon class="btn-ic"><Download /></el-icon>导出 Excel
        </el-button>
        <span class="count-text">共 {{ total }} 门课程</span>
      </div>
    </div>

    <!-- 表格 -->
    <el-table v-loading="loading" :data="rows">
      <el-table-column label="序号" width="60">
        <template #default="{ $index }">{{ (pageNum - 1) * pageSize + $index + 1 }}</template>
      </el-table-column>
      <el-table-column label="封面" width="132">
        <template #default="{ row }">
          <!-- B站视频封面 16:10；URL 失效降级为主学科图标 -->
          <div class="cover-thumb">
            <img
              v-if="row.coverUrl && !failedCovers.has(row.id)"
              :src="row.coverUrl"
              alt=""
              @error="failedCovers.add(row.id)"
            />
            <span v-else class="cover-fallback" :style="{ background: 'var(--brand-light)' }">
              {{ subjectOptions.find((s) => s.id === mainSubject(row)?.id)?.icon || '📚' }}
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="课程名称" min-width="240" show-overflow-tooltip>
        <template #default="{ row }">{{ row.name }}</template>
      </el-table-column>
      <el-table-column label="时长" width="80">
        <template #default="{ row }">{{ fmtHM(row.durationMinutes) }}</template>
      </el-table-column>
      <el-table-column label="学科" min-width="200">
        <template #default="{ row }">
          <template v-if="row.subjects.length">
            <el-tag size="small" effect="plain" type="primary">{{ mainSubject(row)?.name }}</el-tag>
            <el-tooltip v-if="row.subjects.length > 1" :content="subjectTooltip(row)" placement="top">
              <el-tag size="small" type="info" effect="plain" class="rel-tag">+{{ row.subjects.length - 1 }} 关联</el-tag>
            </el-tooltip>
          </template>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="来源" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="row.source === 'bili' ? 'primary' : 'info'" effect="plain">
            {{ sourceLabel(row.source) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right" class-name="actions-cell">
        <template #default="{ row }">
          <el-button v-permission="'course:edit'" link type="primary" @click="openDialog(row)">
            <el-icon class="btn-ic"><EditPen /></el-icon>编辑
          </el-button>
          <el-button v-permission="'course:delete'" link type="danger" @click="handleDelete(row)">
            <el-icon class="btn-ic"><Delete /></el-icon>删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && !rows.length" description="暂无匹配的课程，试试调整筛选条件" />

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

    <!-- 新增 / 编辑课程弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="课程名称" prop="name">
          <el-input v-model="form.name" maxlength="200" placeholder="请输入课程名称" />
        </el-form-item>
        <div class="form-row">
          <el-form-item label="BV号">
            <el-input v-model="form.bvid" maxlength="20" placeholder="选填，如 BV1xK4y1E7qA" />
            <div class="field-hint">选填，全库唯一；重复保存会报错</div>
          </el-form-item>
          <el-form-item label="时长" prop="duration">
            <el-input v-model="form.duration" placeholder="格式 小时:分钟，如 6:30" />
            <div class="field-hint">必填，格式「小时:分钟」，如 6:30</div>
          </el-form-item>
        </div>
        <el-form-item label="封面图片 URL">
          <el-input v-model="form.coverUrl" maxlength="255" placeholder="https://…（选填，B站视频封面 16:10）" />
        </el-form-item>
        <el-form-item label="所属学科" required>
          <div class="subject-checks">
            <label v-for="s in subjectOptions" :key="s.id" class="check-row">
              <el-checkbox
                :model-value="checkedOrder.includes(s.id)"
                :disabled="isSubjectDisabled(s.id)"
                @change="onSubjectCheck(s.id, $event === true)"
              >
                {{ s.icon }} {{ s.name }}
              </el-checkbox>
              <el-tag v-if="checkedOrder[0] === s.id" size="small" type="primary" effect="plain">主</el-tag>
            </label>
          </div>
          <div class="field-hint">
            可多选：按勾选顺序第一个为主学科，其余为关联学科；「其他学科」为兜底项，需单独勾选、不可与其他学科同时选中
          </div>
        </el-form-item>
        <div class="form-row">
          <el-form-item label="来源" required>
            <el-radio-group v-model="form.source">
              <el-radio value="bili">B站</el-radio>
              <el-radio value="other">其他</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="课程链接">
            <el-input v-model="form.playUrl" maxlength="255" placeholder="https://www.bilibili.com/…（选填）" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false"><el-icon class="btn-ic"><Close /></el-icon>取消</el-button>
        <el-button type="primary" @click="handleSave"><el-icon class="btn-ic"><Check /></el-icon>保存</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入弹窗 -->
    <el-dialog v-model="importVisible" title="批量导入课程" width="680px" @closed="resetImport">
      <div
        class="import-drop"
        @click="fileInputEl?.click()"
        @dragover.prevent
        @dragleave.prevent
        @drop="onDrop"
      >
        <div class="drop-icon">📄</div>
        <div class="drop-text">
          将 Excel 文件拖拽到此处，或
          <span class="drop-link" @click.stop="fileInputEl?.click()">选择文件</span>
        </div>
        <div class="field-hint">支持 .xlsx / .xls，单次 ≤ 2000 行、≤ 5MB</div>
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
        1. 表头按<b>列名识别</b>，列顺序可变；必需列「课程名称」「时长（分钟）」缺一即整份文件报错。<br />
        2. 可选列：所属学科、来源、BV号、封面、播放链接；单次 ≤ 2000 行、文件 ≤ 5MB。<br />
        3. 「所属学科」一格内可写多个学科（中英文逗号分隔），<b>第一个为主学科，其余为关联学科</b>；不属于任何已有学科的课程归入「其他学科」。<br />
        4. <b>Excel 为权威数据源</b>：BV号与库中已有课程重复时<b>覆盖更新</b>该课程；无 BV号时按「课程名称 + 来源」匹配；为空的可选列按空值写入（所属学科为空 → 归入「其他学科」），不保留库中原值；关联学科整体替换。<br />
        5. 列中学科名无法识别的行视为<b>警告行</b>，归入「其他学科」导入。<br />
        6. 任一无效行（课程名称缺失、时长非数字等）即<b>整份拒绝导入</b>，报出行号与原因，一行数据都不写入，修正后重新上传。
      </div>

      <!-- 预览 -->
      <template v-if="preview">
        <div v-if="preview.summary.errorCount > 0" class="import-alert error">
          解析失败：共 {{ preview.summary.errorCount }} 处无效行，已整份拒绝导入（一行都未写入），请修正后重新上传。
        </div>
        <div v-else class="import-alert ok">
          解析完成：共 {{ preview.summary.totalRows }} 行：新增 {{ preview.summary.newCount }} /
          覆盖更新 {{ preview.summary.updateCount }} / 警告 {{ preview.summary.warningCount }}
          <el-tag v-if="preview.affectedRoutes.courses > 0" size="small" type="warning" effect="plain" class="rel-tag">
            其中 {{ preview.affectedRoutes.courses }} 门课程已被 {{ preview.affectedRoutes.routes }} 条学习路线引用
          </el-tag>
        </div>

        <el-table v-if="preview.errors.length" :data="preview.errors" size="small" class="import-table">
          <el-table-column prop="rowNo" label="行号" width="70">
            <template #default="{ row }">{{ row.rowNo === 0 ? '文件' : row.rowNo }}</template>
          </el-table-column>
          <el-table-column prop="reason" label="原因" />
        </el-table>

        <el-table v-if="preview.rows.length" :data="preview.rows" size="small" class="import-table">
          <el-table-column prop="rowNo" label="行号" width="64" />
          <el-table-column prop="name" label="课程名称" min-width="200" show-overflow-tooltip />
          <el-table-column label="时长" width="72">
            <template #default="{ row }">{{ fmtHM(row.durationMinutes) }}</template>
          </el-table-column>
          <el-table-column prop="subjectNames" label="所属学科" min-width="150" show-overflow-tooltip />
          <el-table-column label="来源" width="64">
            <template #default="{ row }">{{ sourceLabel(row.source) }}</template>
          </el-table-column>
          <el-table-column label="结果" width="88">
            <template #default="{ row }">
              <el-tag size="small" :type="importResultType(row.result)" effect="plain">
                {{ IMPORT_RESULT_LABEL[row.result] }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>

        <template v-if="preview.warnings.length">
          <div class="import-alert warn">
            警告明细（{{ preview.warnings.length }} 条，警告行按「其他学科」导入）：
          </div>
          <el-table :data="preview.warnings" size="small" class="import-table">
            <el-table-column prop="rowNo" label="行号" width="70" />
            <el-table-column prop="reason" label="原因" />
          </el-table>
        </template>
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
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.stat-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 20px;
}
.stat-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.stat-label {
  font-size: 13px;
  color: var(--ink-3);
}
.stat-icon {
  font-size: 18px;
}
.stat-value {
  font-size: 26px;
  font-weight: 700;
  margin-top: 6px;
}
.stat-sub {
  font-size: 12px;
  color: var(--ink-3);
  margin-top: 2px;
}
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}

/* ---- 封面：B站视频封面 16:10 ---- */
.cover-thumb {
  width: 112px;
  aspect-ratio: 16 / 10;
  border-radius: 6px;
  overflow: hidden;
  background: var(--surface-2);
}
.cover-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.cover-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
}
.rel-tag {
  margin-left: 6px;
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
.field-hint {
  width: 100%;
  font-size: 12px;
  color: var(--ink-3);
  line-height: 1.6;
}
.subject-checks {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px 12px;
  width: 100%;
}
.check-row {
  display: flex;
  align-items: center;
  gap: 6px;
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
.import-alert.warn {
  background: #fdf6ec;
  color: #e6a23c;
}
.import-table {
  margin-top: 8px;
}

@media (max-width: 900px) {
  .stat-grid {
    grid-template-columns: 1fr;
  }
  .subject-checks {
    grid-template-columns: 1fr;
  }
  .form-row {
    flex-direction: column;
    gap: 0;
  }
}
</style>
