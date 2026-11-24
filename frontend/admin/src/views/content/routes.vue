<script setup lang="ts">
/**
 * 学习路线管理（04 §4.7 / 需求 4.3.5 / prototype/admin/routes.html）。
 * 路线卡片列表 + 新建/编辑（含课程勾选排序）+ 详情课程管理（排序/移除/从课程库添加）+ 预览；
 * 相较原型的调整：课程缩略图与预览清单不显示 BV号（与课程库口径一致）。
 * 按钮级权限 v-permission（route:view/create/edit/delete）。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import type { ApiError } from '@shared/types/api'
import {
  addRouteItems,
  createRoute,
  deleteRoute,
  fetchRoute,
  fetchRoutes,
  updateRoute,
  updateRouteItems,
} from '@/api/routes'
import type { RouteBasicPayload, RouteCard, RouteDetail } from '@/api/routes'
import { fetchCourses } from '@/api/courses'
import type { CourseItem } from '@/api/courses'
import { fetchSubjects } from '@/api/subjects'
import type { SubjectItem } from '@/api/subjects'

// ===================== 列表视图 =====================
const loading = ref(false)
const rows = ref<RouteCard[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(9)
const filter = reactive({ keyword: '', subjectId: '' as string | number, status: '' })
const subjectOptions = ref<SubjectItem[]>([])

function buildQuery() {
  return {
    keyword: filter.keyword.trim() || undefined,
    subjectId: filter.subjectId ? Number(filter.subjectId) : undefined,
    status: filter.status || undefined,
    pageNum: pageNum.value,
    pageSize: pageSize.value,
  }
}

async function load() {
  loading.value = true
  try {
    const res = await fetchRoutes(buildQuery())
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

/** 时长文案：390 → 「6 小时 30 分钟」（原型 fmtDur） */
function fmtDur(min: number): string {
  const h = Math.floor(min / 60)
  const m = min % 60
  if (h && m) return `${h} 小时 ${m} 分钟`
  if (h) return `${h} 小时`
  return `${m} 分钟`
}

// ---- 卡片操作 ----
async function handleToggleStatus(row: RouteCard) {
  const toEnable = row.status !== 'enabled'
  try {
    await ElMessageBox.confirm(
      toEnable
        ? '确定要启用该学习路线吗？学员端将展示此路线。'
        : '确定要禁用该学习路线吗？学员端将不再展示此路线。',
      toEnable ? '启用路线' : '禁用路线',
      { type: 'warning', confirmButtonText: toEnable ? '启用' : '禁用', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    // 基本信息全量更新（04 §4.7）：先取详情再整体回写
    const d = await fetchRoute(row.id)
    const payload: RouteBasicPayload = {
      name: d.name,
      subjectId: d.subjectId,
      status: toEnable ? 'enabled' : 'disabled',
      icon: d.icon,
      targetEducation: d.targetEducation,
      description: d.description,
    }
    await updateRoute(row.id, payload)
    ElMessage.success(toEnable ? '已启用' : '已禁用')
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

async function handleDelete(row: RouteCard) {
  try {
    await ElMessageBox.confirm('确定删除该学习路线吗？删除为逻辑删除，数据保留可恢复。', '删除路线', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteRoute(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '删除失败')
  }
}

// ===================== 详情视图（课程管理） =====================
const view = ref<'list' | 'detail'>('list')
const detail = ref<RouteDetail | null>(null)

async function openDetail(id: number) {
  try {
    detail.value = await fetchRoute(id)
    view.value = 'detail'
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '加载详情失败')
  }
}

function backToList() {
  view.value = 'list'
  load()
}

async function refreshDetail() {
  if (detail.value) detail.value = await fetchRoute(detail.value.id)
}

/** 课程排序（↑↓ → 有序全量保存） */
async function moveCourse(index: number, delta: number) {
  if (!detail.value) return
  const list = [...detail.value.courses]
  const j = index + delta
  if (j < 0 || j >= list.length) return
  const [item] = list.splice(index, 1)
  list.splice(j, 0, item)
  try {
    await updateRouteItems(
      detail.value.id,
      list.map((c) => c.id),
    )
    await refreshDetail()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '排序失败')
    refreshDetail()
  }
}

async function handleRemoveCourse(index: number) {
  if (!detail.value) return
  const course = detail.value.courses[index]
  try {
    await ElMessageBox.confirm(`确定将课程「${course.name}」从路线中移除吗？`, '移除课程', {
      type: 'warning',
      confirmButtonText: '移除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    const ids = detail.value.courses.map((c) => c.id)
    ids.splice(index, 1)
    await updateRouteItems(detail.value.id, ids)
    ElMessage.success('已移除')
    refreshDetail()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '移除失败')
  }
}

// ===================== 新建 / 编辑弹窗 =====================
/** 适合学历预置选项（可下拉选择，也可自由输入） */
const EDUCATION_OPTIONS = ['不限', '大专及以上', '本科及以上', '硕士及以上', '博士']

const formVisible = ref(false)
const formTitle = ref('新建学习路线')
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({
  name: '',
  subjectId: '' as string | number,
  status: 'enabled' as 'enabled' | 'disabled',
  icon: '',
  targetEducation: '',
  description: '',
})
const rules: FormRules = {
  name: [{ required: true, message: '请输入路线名称', trigger: 'blur' }],
  subjectId: [{ required: true, message: '请选择关联学科', trigger: 'change' }],
}

/** 已选课程（有序；第一个为学习顺序起点） */
const selCourses = ref<CourseItem[]>([])
const pickPool = ref<CourseItem[]>([])

async function loadPickPool() {
  if (!form.subjectId) {
    pickPool.value = []
    return
  }
  try {
    const res = await fetchCourses({ subjectId: Number(form.subjectId), pageSize: 100 })
    pickPool.value = res.list
  } catch {
    pickPool.value = []
  }
}

function onTogglePick(course: CourseItem, checked: boolean) {
  if (checked) {
    if (!selCourses.value.some((c) => c.id === course.id)) selCourses.value = [...selCourses.value, course]
  } else {
    selCourses.value = selCourses.value.filter((c) => c.id !== course.id)
  }
}

function moveSel(index: number, delta: number) {
  const list = [...selCourses.value]
  const j = index + delta
  if (j < 0 || j >= list.length) return
  const [item] = list.splice(index, 1)
  list.splice(j, 0, item)
  selCourses.value = list
}

function removeSel(index: number) {
  selCourses.value = selCourses.value.filter((_, i) => i !== index)
}

function openForm(row?: RouteCard) {
  editingId.value = row?.id ?? null
  formTitle.value = row ? '编辑学习路线' : '新建学习路线'
  Object.assign(form, {
    name: row?.name ?? '',
    subjectId: '',
    status: row?.status ?? 'enabled',
    icon: '',
    targetEducation: row?.targetEducation ?? '',
    description: row?.description ?? '',
  })
  selCourses.value = []
  formVisible.value = true

  const init = row
    ? fetchRoute(row.id).then((d) => {
        form.subjectId = d.subjectId
        form.icon = d.icon ?? ''
        selCourses.value = d.courses.map((c) => ({
          id: c.id,
          name: c.name,
          bvid: c.bvid,
          coverUrl: null,
          durationMinutes: c.durationMinutes,
          source: 'bili',
          subjects: [],
          createdAt: '',
          routeRefCount: 0,
        }))
        return loadPickPool()
      })
    : Promise.resolve((form.subjectId = subjectOptions.value[0]?.id ?? '')).then(loadPickPool)
  init.catch(() => {})
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  const basic: RouteBasicPayload = {
    name: form.name.trim(),
    subjectId: Number(form.subjectId),
    status: form.status,
    icon: form.icon.trim() || null,
    targetEducation: form.targetEducation.trim() || null,
    description: form.description.trim() || null,
  }
  const courseIds = selCourses.value.map((c) => c.id)
  try {
    if (editingId.value === null) {
      await createRoute({ ...basic, courseIds })
      ElMessage.success('创建成功')
    } else {
      await updateRoute(editingId.value, basic)
      await updateRouteItems(editingId.value, courseIds) // 课程整体替换（03 S2）
      ElMessage.success('保存成功')
    }
    formVisible.value = false
    if (view.value === 'detail' && editingId.value === detail.value?.id) refreshDetail()
    else load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

// ===================== 预览（学员视角） =====================
const previewVisible = ref(false)
const preview = ref<RouteDetail | null>(null)

async function openPreview(row: RouteCard) {
  try {
    preview.value = await fetchRoute(row.id)
    previewVisible.value = true
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '加载预览失败')
  }
}

// ===================== 从课程库添加 =====================
const addVisible = ref(false)
const addKeyword = ref('')
const addGroup = ref<'' | 'in' | 'out'>('')
const addPool = ref<CourseItem[]>([])
const checkedAdd = ref<number[]>([])
let addTimer: ReturnType<typeof setTimeout> | undefined

function isInGroup(c: CourseItem): boolean {
  return detail.value ? c.subjects.some((s) => s.id === detail.value!.subjectId) : false
}

async function loadAddPool() {
  try {
    const res = await fetchCourses({ keyword: addKeyword.value.trim() || undefined, pageSize: 100 })
    addPool.value = res.list
  } catch {
    addPool.value = []
  }
}

function onAddKeywordInput() {
  clearTimeout(addTimer)
  addTimer = setTimeout(loadAddPool, 300)
}

const groupedPool = computed(() => {
  const inList = addPool.value.filter((c) => isInGroup(c))
  const outList = addPool.value.filter((c) => !isInGroup(c))
  return {
    in: addGroup.value === 'out' ? [] : inList,
    out: addGroup.value === 'in' ? [] : outList,
  }
})

function isAdded(c: CourseItem): boolean {
  return detail.value ? detail.value.courses.some((x) => x.id === c.id) : false
}

function openAdd() {
  addKeyword.value = ''
  addGroup.value = ''
  checkedAdd.value = []
  loadAddPool()
  addVisible.value = true
}

async function handleAddDone() {
  if (!detail.value) return
  if (!checkedAdd.value.length) {
    ElMessage.warning('请先勾选要添加的课程')
    return
  }
  try {
    const res = await addRouteItems(detail.value.id, checkedAdd.value)
    ElMessage.success(`已添加 ${res.affected} 门课程`)
    addVisible.value = false
    refreshDetail()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '添加失败')
  }
}
</script>

<template>
  <div v-loading="loading">
    <!-- ===================== 列表视图 ===================== -->
    <template v-if="view === 'list'">
      <div class="list-toolbar">
        <el-input
          v-model="filter.keyword"
          style="width: 200px"
          placeholder="搜索路线名称"
          clearable
          @input="onKeywordInput"
        />
        <el-select v-model="filter.subjectId" placeholder="全部学科" clearable style="width: 180px" @change="handleSearch">
          <el-option v-for="s in subjectOptions" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-select v-model="filter.status" placeholder="全部状态" style="width: 130px" @change="handleSearch">
          <el-option label="全部状态" value="" />
          <el-option label="启用" value="enabled" />
          <el-option label="禁用" value="disabled" />
        </el-select>
        <div class="toolbar-actions">
          <el-button v-permission="'route:create'" type="primary" @click="openForm()">
            <el-icon class="btn-ic"><Plus /></el-icon>新建路线
          </el-button>
          <span class="count-text">共 {{ total }} 条路线</span>
        </div>
      </div>

      <div v-if="rows.length" class="route-grid">
        <div v-for="row in rows" :key="row.id" class="route-card">
          <div class="rc-body">
            <div class="rc-head">
              <h3 class="rc-title">{{ row.name }}</h3>
              <el-tag size="small" :type="row.status === 'enabled' ? 'success' : 'info'">
                {{ row.status === 'enabled' ? '启用' : '禁用' }}
              </el-tag>
            </div>
            <div class="rc-meta">关联学科：{{ row.subjectName }}</div>
            <div class="rc-meta">适合学历：{{ row.targetEducation || '不限' }}</div>
            <div class="rc-count">共 {{ row.courseCount }} 门 B站课程 · 总计 {{ fmtDur(row.totalMinutes) }}</div>
            <p class="rc-desc">{{ row.description || '' }}</p>
            <div class="rc-preview">
              <div v-for="(p, i) in row.coursePreview" :key="i" class="rc-thumb">
                <img v-if="p.coverUrl" :src="p.coverUrl" alt="" @error="($event.target as HTMLImageElement).style.display = 'none'" />
                <span v-else>🎬</span>
              </div>
            </div>
          </div>
          <div class="rc-actions">
            <el-button v-permission="'route:edit'" size="small" @click="handleToggleStatus(row)">
              <el-icon class="btn-ic"><component :is="row.status === 'enabled' ? 'CircleClose' : 'CircleCheck'" /></el-icon>
              {{ row.status === 'enabled' ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" @click="openPreview(row)"><el-icon class="btn-ic"><View /></el-icon>预览</el-button>
            <el-button size="small" @click="openDetail(row.id)"><el-icon class="btn-ic"><List /></el-icon>课程管理</el-button>
            <el-button v-permission="'route:edit'" size="small" @click="openForm(row)">
              <el-icon class="btn-ic"><EditPen /></el-icon>编辑
            </el-button>
            <el-button v-permission="'route:delete'" size="small" type="danger" plain @click="handleDelete(row)">
              <el-icon class="btn-ic"><Delete /></el-icon>删除
            </el-button>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无学习路线，点击上方新建路线创建一条" />

      <el-pagination
        v-model:current-page="pageNum"
        v-model:page-size="pageSize"
        class="pagination"
        :total="total"
        :page-sizes="[9, 18, 36]"
        layout="total, sizes, prev, pager, next"
        @current-change="load"
        @size-change="handleSearch"
      />
    </template>

    <!-- ===================== 详情视图（课程管理） ===================== -->
    <template v-else-if="detail">
      <div class="detail-header">
        <el-button @click="backToList"><el-icon class="btn-ic"><Back /></el-icon>返回列表</el-button>
        <h3 class="detail-title">{{ detail.name }} - 课程管理</h3>
        <div class="spacer"></div>
        <el-button v-permission="'route:edit'" type="primary" @click="openAdd">
          <el-icon class="btn-ic"><Plus /></el-icon>从课程库添加
        </el-button>
      </div>

      <el-card class="detail-card" shadow="never">
        <dl class="desc-list">
          <dt>学科</dt><dd>{{ detail.subjectName }}</dd>
          <dt>状态</dt>
          <dd>
            <el-tag size="small" :type="detail.status === 'enabled' ? 'success' : 'info'">
              {{ detail.status === 'enabled' ? '启用' : '禁用' }}
            </el-tag>
          </dd>
          <dt>描述</dt><dd>{{ detail.description || '—' }}</dd>
          <dt>课程数</dt><dd>共 {{ detail.courseCount }} 门 B站课程</dd>
          <dt>总时长</dt><dd>{{ fmtDur(detail.totalMinutes) }}</dd>
          <dt>适合学历</dt><dd>{{ detail.targetEducation || '不限' }}</dd>
        </dl>
      </el-card>

      <el-table v-if="detail.courses.length" :data="detail.courses">
        <el-table-column label="序号" width="70">
          <template #default="{ $index }">{{ $index + 1 }}</template>
        </el-table-column>
        <el-table-column prop="name" label="课程名称" min-width="260" show-overflow-tooltip />
        <el-table-column label="时长" width="110">
          <template #default="{ row }">{{ fmtDur(row.durationMinutes) }}</template>
        </el-table-column>
        <el-table-column label="排序" width="110">
          <template #default="{ $index }">
            <el-button
              v-permission="'route:edit'"
              class="sort-btn"
              size="small"
              :disabled="$index === 0"
              @click="moveCourse($index, -1)"
            >
              <el-icon><Top /></el-icon>
            </el-button>
            <el-button
              v-permission="'route:edit'"
              class="sort-btn"
              size="small"
              :disabled="$index === detail.courses.length - 1"
              @click="moveCourse($index, 1)"
            >
              <el-icon><Bottom /></el-icon>
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" class-name="actions-cell">
          <template #default="{ $index }">
            <el-button v-permission="'route:edit'" link type="danger" @click="handleRemoveCourse($index)">
              <el-icon class="btn-ic"><Delete /></el-icon>移除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无课程，点击右上角从课程库添加" />
    </template>

    <!-- ===================== 新建 / 编辑弹窗 ===================== -->
    <el-dialog v-model="formVisible" :title="formTitle" width="680px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <h4 class="section-title">基本信息</h4>
        <div class="form-row">
          <el-form-item label="路线名称" prop="name" class="flex-2">
            <el-input v-model="form.name" maxlength="100" placeholder="请输入路线名称" />
          </el-form-item>
          <el-form-item label="关联学科" prop="subjectId" class="flex-1">
            <el-select v-model="form.subjectId" placeholder="请选择学科" style="width: 100%" @change="loadPickPool">
              <el-option v-for="s in subjectOptions" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
          </el-form-item>
        </div>
        <div class="form-row">
          <el-form-item label="路线图标" class="flex-1">
            <el-input v-model="form.icon" maxlength="10" placeholder="Emoji，如 🚀" />
            <div class="field-hint">
              不知道用什么？到
              <a href="https://www.emojiall.com/zh-hans" target="_blank" rel="noopener">Emoji 大全</a>
              搜索复制
            </div>
          </el-form-item>
          <el-form-item label="适合学历" class="flex-1">
            <el-select
              v-model="form.targetEducation"
              filterable
              allow-create
              default-first-option
              placeholder="选择或输入，如 本科及以上"
              style="width: 100%"
            >
              <el-option v-for="e in EDUCATION_OPTIONS" :key="e" :label="e" :value="e" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="状态">
          <div class="status-row">
            <el-switch v-model="form.status" active-value="enabled" inactive-value="disabled" />
            <span class="muted">{{ form.status === 'enabled' ? '启用（学员端展示）' : '禁用（学员端不展示）' }}</span>
          </div>
        </el-form-item>
        <el-form-item label="路线描述">
          <el-input v-model="form.description" type="textarea" :rows="3" maxlength="500" placeholder="请输入路线描述" />
        </el-form-item>

        <h4 class="section-title">路线课程</h4>
        <div class="field-label">可选课程（按所选学科）</div>
        <div class="pick-list">
          <div v-if="!pickPool.length" class="pick-empty muted">该学科暂无课程</div>
          <label v-for="c in pickPool" :key="c.id" class="pick-row">
            <el-checkbox
              :model-value="selCourses.some((x) => x.id === c.id)"
              @change="onTogglePick(c, $event === true)"
            >
              <span class="pk-name">{{ c.name }}</span>
            </el-checkbox>
            <span class="muted nowrap">{{ fmtDur(c.durationMinutes) }}</span>
          </label>
        </div>
        <div class="field-label sel-label">已选课程（按学习顺序）</div>
        <div class="pick-list">
          <div v-if="!selCourses.length" class="pick-empty muted">
            尚未选择课程
            <div class="pick-sub">在上方勾选课程后会出现在这里</div>
          </div>
          <div v-for="(c, i) in selCourses" :key="c.id" class="pick-row">
            <span class="muted">{{ i + 1 }}</span>
            <span class="pk-name">{{ c.name }}</span>
            <el-button class="sort-btn" size="small" :disabled="i === 0" @click="moveSel(i, -1)">
              <el-icon><Top /></el-icon>
            </el-button>
            <el-button class="sort-btn" size="small" :disabled="i === selCourses.length - 1" @click="moveSel(i, 1)">
              <el-icon><Bottom /></el-icon>
            </el-button>
            <el-button link type="danger" @click="removeSel(i)">移除</el-button>
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false"><el-icon class="btn-ic"><Close /></el-icon>取消</el-button>
        <el-button type="primary" @click="handleSave"><el-icon class="btn-ic"><Check /></el-icon>保存</el-button>
      </template>
    </el-dialog>

    <!-- ===================== 预览弹窗（学员视角） ===================== -->
    <el-dialog v-model="previewVisible" title="路线预览（学员视角）" width="560px">
      <template v-if="preview">
        <h3 class="preview-title">{{ preview.icon || '🗺️' }} {{ preview.name }}</h3>
        <p class="muted">{{ preview.description || '（暂无描述）' }}</p>
        <dl class="desc-list">
          <dt>学科</dt><dd>{{ preview.subjectName }}</dd>
          <dt>适合学历</dt><dd>{{ preview.targetEducation || '不限' }}</dd>
          <dt>课程数</dt><dd>共 {{ preview.courseCount }} 门 B站课程</dd>
          <dt>总时长</dt><dd>{{ fmtDur(preview.totalMinutes) }}</dd>
        </dl>
        <el-divider />
        <div class="field-label">课程清单（按学习顺序）</div>
        <div v-if="preview.courses.length" class="preview-list">
          <div v-for="(c, i) in preview.courses" :key="c.id" class="preview-row">
            <span><b>{{ i + 1 }}.</b> {{ c.name }}</span>
            <span class="muted nowrap">{{ fmtDur(c.durationMinutes) }}</span>
          </div>
        </div>
        <div v-else class="muted">课程筹备中，敬请期待</div>
      </template>
      <template #footer>
        <el-button type="primary" @click="previewVisible = false"><el-icon class="btn-ic"><Check /></el-icon>关闭</el-button>
      </template>
    </el-dialog>

    <!-- ===================== 从课程库添加弹窗 ===================== -->
    <el-dialog v-model="addVisible" title="从课程库添加" width="640px">
      <div class="add-bar">
        <el-input
          v-model="addKeyword"
          style="flex: 1"
          placeholder="搜索课程名称"
          clearable
          @input="onAddKeywordInput"
        />
        <el-select v-model="addGroup" style="width: 220px">
          <el-option label="全部课程" value="" />
          <el-option label="本学科课程" value="in" />
          <el-option label="其他学科课程（跨学科补充）" value="out" />
        </el-select>
      </div>
      <div class="pick-list add-list">
        <template v-if="groupedPool.in.length || groupedPool.out.length">
          <template v-if="groupedPool.in.length">
            <div class="group-title">本学科课程</div>
            <label v-for="c in groupedPool.in" :key="c.id" class="pick-row">
              <el-checkbox
                :model-value="checkedAdd.includes(c.id)"
                :disabled="isAdded(c)"
                @change="checkedAdd = $event === true ? [...checkedAdd, c.id] : checkedAdd.filter((x) => x !== c.id)"
              >
                <span class="pk-name">{{ c.name }}</span>
              </el-checkbox>
              <span class="muted nowrap">{{ fmtDur(c.durationMinutes) }}</span>
              <el-tag v-if="isAdded(c)" size="small" type="info" effect="plain">已添加</el-tag>
            </label>
          </template>
          <template v-if="groupedPool.out.length">
            <div class="group-title">其他学科课程（跨学科补充）</div>
            <label v-for="c in groupedPool.out" :key="c.id" class="pick-row">
              <el-checkbox
                :model-value="checkedAdd.includes(c.id)"
                :disabled="isAdded(c)"
                @change="checkedAdd = $event === true ? [...checkedAdd, c.id] : checkedAdd.filter((x) => x !== c.id)"
              >
                <span class="pk-name">{{ c.name }}</span>
              </el-checkbox>
              <span class="muted nowrap">{{ fmtDur(c.durationMinutes) }}</span>
              <el-tag v-if="isAdded(c)" size="small" type="info" effect="plain">已添加</el-tag>
            </label>
          </template>
        </template>
        <div v-else class="pick-empty muted">没有匹配的课程</div>
      </div>
      <template #footer>
        <el-button @click="addVisible = false"><el-icon class="btn-ic"><Close /></el-icon>取消</el-button>
        <el-button type="primary" @click="handleAddDone"><el-icon class="btn-ic"><Check /></el-icon>完成添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
.nowrap {
  white-space: nowrap;
}

/* ---- 路线卡片（对齐原型 .route-admin-*）---- */
.route-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.route-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  transition: box-shadow .15s;
}
.route-card:hover {
  box-shadow: var(--shadow-lg);
}
.rc-body {
  padding: 18px 20px;
  flex: 1;
}
.rc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.rc-title {
  margin: 0;
  font-size: 15px;
}
.rc-meta {
  font-size: 12px;
  color: var(--ink-3);
  margin-top: 2px;
}
.rc-count {
  font-size: 13px;
  margin-top: 8px;
}
.rc-desc {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 13px;
  margin: 8px 0 0;
  min-height: 40px;
}
.rc-preview {
  display: flex;
  gap: 8px;
  margin: 12px 0 0;
  overflow: hidden;
}
.rc-thumb {
  width: 72px;
  height: 45px; /* B站视频封面 16:10 */
  border-radius: 6px;
  background: var(--brand-grad);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
  overflow: hidden;
}
.rc-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.rc-actions {
  padding: 12px 16px;
  border-top: 1px solid var(--line);
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  flex-wrap: wrap;
}

/* ---- 详情视图 ---- */
.detail-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.detail-title {
  margin: 0;
  font-size: 17px;
}
.detail-header .spacer {
  flex: 1;
}
.detail-card {
  margin-bottom: 16px;
}
.desc-list {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px 18px;
  font-size: 13px;
  margin: 0;
}
.desc-list dt {
  color: var(--ink-3);
}
.desc-list dd {
  margin: 0;
  color: var(--ink);
}
.sort-btn {
  padding: 4px 6px;
}
.sort-btn + .sort-btn {
  margin-left: 2px;
}

/* ---- 表单 ---- */
.section-title {
  margin: 4px 0 12px;
  font-size: 14px;
}
.form-row {
  display: flex;
  gap: 16px;
}
.form-row .el-form-item {
  flex: 1;
  min-width: 0;
}
.form-row .flex-2 {
  flex: 2;
}
.field-hint {
  width: 100%;
  font-size: 12px;
  color: var(--ink-3);
  line-height: 1.6;
}
.field-hint a {
  color: var(--brand);
  text-decoration: none;
}
.field-hint a:hover {
  text-decoration: underline;
}
.status-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.field-label {
  font-size: 13px;
  color: var(--ink-2);
  margin-bottom: 6px;
}
.sel-label {
  margin-top: 14px;
}
.pick-list {
  max-height: 280px;
  overflow-y: auto;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm, 6px);
  padding: 6px;
}
.pick-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 13px;
}
.pick-row:hover {
  background: var(--surface-2);
}
.pick-row .pk-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pick-empty {
  padding: 24px;
  text-align: center;
  font-size: 13px;
}
.pick-sub {
  font-size: 12px;
  margin-top: 4px;
}
.group-title {
  font-size: 12px;
  color: var(--ink-3);
  padding: 8px 8px 4px;
  letter-spacing: 1px;
}

/* ---- 预览 / 添加 ---- */
.preview-title {
  margin: 0 0 8px;
  font-size: 17px;
}
.preview-list {
  margin-top: 4px;
}
.preview-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px dashed var(--line);
  font-size: 13px;
}
.add-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.add-list {
  max-height: 340px;
}

@media (max-width: 1100px) {
  .route-grid {
    grid-template-columns: 1fr;
  }
}
</style>
