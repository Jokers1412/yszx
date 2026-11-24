<script setup lang="ts">
/**
 * 学员管理（04 §4.8 / 需求 4.4 / prototype/admin/students.html）。
 * 学员由前台注册产生（无新增/编辑）；筛选 + 批量启停/删除 + 导出 + 详情
 * （资料 / 学习统计含已学课程 / 面试记录分页）；手机号完整展示不脱敏。
 * 按钮级权限 v-permission（student:view/edit/delete）。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import type { ApiError, PageResult } from '@shared/types/api'
import {
  batchDeleteStudents,
  batchStudentStatus,
  deleteStudent,
  exportStudents,
  fetchStudent,
  fetchStudentInterviews,
  fetchStudents,
  patchStudentStatus,
} from '@/api/students'
import type {
  InterviewRecordItem,
  StudentDetail,
  StudentListItem,
} from '@/api/students'

const DIFF_LABEL: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' }

// ===================== 列表 =====================
const loading = ref(false)
const rows = ref<StudentListItem[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const filter = reactive({ keyword: '', status: '' })
const selected = ref<StudentListItem[]>([])

function buildQuery() {
  return {
    keyword: filter.keyword.trim() || undefined,
    status: filter.status || undefined,
    pageNum: pageNum.value,
    pageSize: pageSize.value,
  }
}

async function load() {
  loading.value = true
  try {
    const res = await fetchStudents(buildQuery())
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
  filter.keyword = ''
  filter.status = ''
  handleSearch()
}

function handleSelectionChange(items: StudentListItem[]) {
  selected.value = items
}

onMounted(load)

// ===================== 行 / 批量操作（均二次确认） =====================
async function handleToggleStatus(row: StudentListItem) {
  const enable = row.status !== 'enabled'
  try {
    await ElMessageBox.confirm(`确定要${enable ? '启用' : '禁用'}学员「${row.nickname}」吗？`, enable ? '启用学员' : '禁用学员', {
      type: 'warning',
      confirmButtonText: enable ? '启用' : '禁用',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await patchStudentStatus(row.id, enable ? 'enabled' : 'disabled')
    ElMessage.success(enable ? '已启用' : '已禁用')
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

async function handleDelete(row: StudentListItem) {
  try {
    await ElMessageBox.confirm(`确定要删除学员「${row.nickname}」吗？`, '删除学员', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteStudent(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '删除失败')
  }
}

async function handleBatch(action: 'enable' | 'disable' | 'delete') {
  const ids = selected.value.map((s) => s.id)
  if (!ids.length) {
    ElMessage.warning('请先勾选学员')
    return
  }
  const label = action === 'enable' ? '启用' : action === 'disable' ? '禁用' : '删除'
  try {
    await ElMessageBox.confirm(
      action === 'delete'
        ? `确定要删除选中的 ${ids.length} 名学员吗？`
        : `确定要${label}选中的 ${ids.length} 名学员吗？`,
      `批量${label}`,
      {
        type: action === 'delete' ? 'warning' : 'warning',
        confirmButtonText: `批量${label}`,
        cancelButtonText: '取消',
      },
    )
  } catch {
    return
  }
  try {
    const res =
      action === 'delete'
        ? await batchDeleteStudents(ids)
        : await batchStudentStatus(action, ids)
    ElMessage.success(`已批量${label} ${res.affected} 项`)
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

const exporting = ref(false)
async function handleExport() {
  exporting.value = true
  try {
    await exportStudents(buildQuery())
    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

// ===================== 详情抽屉 =====================
const drawerVisible = ref(false)
const detail = ref<StudentDetail | null>(null)

// 面试记录（抽屉内分页）
const interviews = ref<InterviewRecordItem[]>([])
const interviewTotal = ref(0)
const interviewPage = ref(1)
const interviewPageSize = ref(5)
const interviewLoading = ref(false)

async function loadInterviews(studentId: number) {
  interviewLoading.value = true
  try {
    const res = await fetchStudentInterviews(studentId, {
      pageNum: interviewPage.value,
      pageSize: interviewPageSize.value,
    })
    interviews.value = res.list
    interviewTotal.value = res.total
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '面试记录加载失败')
  } finally {
    interviewLoading.value = false
  }
}

async function openDetail(row: StudentListItem) {
  try {
    detail.value = await fetchStudent(row.id)
    interviewPage.value = 1
    await loadInterviews(row.id)
    drawerVisible.value = true
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '加载详情失败')
  }
}
</script>

<template>
  <div v-loading="loading">
    <!-- 工具栏：筛选 + 操作（批量按钮常驻） -->
    <div class="list-toolbar">
      <el-input
        v-model="filter.keyword"
        style="width: 220px"
        placeholder="搜索昵称 / 手机号"
        clearable
        @keyup.enter="handleSearch"
      />
      <el-select v-model="filter.status" placeholder="全部状态" clearable style="width: 130px" @change="handleSearch">
        <el-option label="全部状态" value="" />
        <el-option label="已启用" value="enabled" />
        <el-option label="已禁用" value="disabled" />
      </el-select>
      <div class="toolbar-actions">
        <el-button type="primary" @click="handleSearch"><el-icon class="btn-ic"><Search /></el-icon>查询</el-button>
        <el-button @click="handleReset"><el-icon class="btn-ic"><Refresh /></el-icon>重置</el-button>
        <el-button v-permission="'student:edit'" @click="handleBatch('enable')">
          <el-icon class="btn-ic"><CircleCheck /></el-icon>批量启用
        </el-button>
        <el-button v-permission="'student:edit'" @click="handleBatch('disable')">
          <el-icon class="btn-ic"><CircleClose /></el-icon>批量禁用
        </el-button>
        <el-button v-permission="'student:delete'" type="danger" plain @click="handleBatch('delete')">
          <el-icon class="btn-ic"><Delete /></el-icon>批量删除
        </el-button>
        <el-button v-permission="'student:view'" :loading="exporting" @click="handleExport">
          <el-icon class="btn-ic"><Download /></el-icon>导出
        </el-button>
        <span class="count-text">已选 {{ selected.length }} 项 / 共 {{ total }} 名</span>
      </div>
    </div>

    <!-- 表格 -->
    <el-table v-loading="loading" :data="rows" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="42" />
      <el-table-column label="学员" min-width="180">
        <template #default="{ row }">
          <div class="user-cell">
            <img v-if="row.avatarUrl" :src="row.avatarUrl" class="avatar-img" alt="" />
            <span v-else class="avatar-letter">{{ row.nickname.slice(0, 1) }}</span>
            <span class="user-name">{{ row.nickname }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="phone" label="手机号" min-width="130" title="完整手机号，不做脱敏" />
      <el-table-column prop="registeredAt" label="注册时间" min-width="150" />
      <el-table-column label="学习天数" width="90">
        <template #default="{ row }">{{ row.studyDays }}</template>
      </el-table-column>
      <el-table-column label="刷题·面试" width="110">
        <template #default="{ row }">{{ row.practiceCount }} · {{ row.interviewCount }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="row.status === 'enabled' ? 'success' : 'info'">
            {{ row.status === 'enabled' ? '已启用' : '已禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right" class-name="actions-cell">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)"><el-icon class="btn-ic"><View /></el-icon>查看详情</el-button>
          <el-button v-permission="'student:edit'" link :type="row.status === 'enabled' ? 'warning' : 'success'" @click="handleToggleStatus(row)">
            <el-icon class="btn-ic"><component :is="row.status === 'enabled' ? 'CircleClose' : 'CircleCheck'" /></el-icon>
            {{ row.status === 'enabled' ? '禁用' : '启用' }}
          </el-button>
          <el-button v-permission="'student:delete'" link type="danger" @click="handleDelete(row)">
            <el-icon class="btn-ic"><Delete /></el-icon>删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && !rows.length" description="没有找到匹配的学员" />

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

    <!-- ===================== 详情抽屉 ===================== -->
    <el-drawer v-model="drawerVisible" title="学员详情" size="560px">
      <template v-if="detail">
        <!-- 资料区 -->
        <div class="profile-row">
          <img v-if="detail.profile.avatarUrl" :src="detail.profile.avatarUrl" class="avatar-lg" alt="" />
          <span v-else class="avatar-lg avatar-letter">{{ detail.profile.nickname.slice(0, 1) }}</span>
          <div>
            <div class="profile-name">
              {{ detail.profile.nickname }}
              <el-tag size="small" :type="detail.profile.status === 'enabled' ? 'success' : 'info'">
                {{ detail.profile.status === 'enabled' ? '已启用' : '已禁用' }}
              </el-tag>
            </div>
            <div class="muted">注册于 {{ detail.profile.registeredAt }}</div>
          </div>
        </div>
        <el-descriptions :column="1" border class="detail-desc">
          <el-descriptions-item label="手机号">{{ detail.profile.phone }}</el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ detail.profile.email || '—' }}</el-descriptions-item>
          <el-descriptions-item label="最后登录">{{ detail.profile.lastLoginAt || '—' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 学习统计 -->
        <h4 class="drawer-title">学习统计</h4>
        <div class="stats-row">
          <div class="ds-item"><b>{{ detail.stats.studyDays }}</b><span>学习天数</span></div>
          <div class="ds-item"><b>{{ detail.stats.doneCourses.length }}</b><span>已学课程</span></div>
          <div class="ds-item"><b>{{ detail.stats.practiceCount }}</b><span>刷题总数</span></div>
          <div class="ds-item"><b>{{ detail.stats.accuracy }}%</b><span>正确率</span></div>
        </div>
        <template v-if="detail.stats.doneCourses.length">
          <div class="course-list">
            <div v-for="c in detail.stats.doneCourses" :key="c.id" class="course-item">
              <span class="course-name">{{ c.name }}</span>
              <span class="muted nowrap">{{ Math.floor(c.durationMinutes / 60) }}:{{ String(c.durationMinutes % 60).padStart(2, '0') }}</span>
            </div>
          </div>
        </template>

        <!-- 面试记录 -->
        <h4 class="drawer-title">面试记录（累计 {{ detail.interviewSummary.count }} 次）</h4>
        <el-table v-loading="interviewLoading" :data="interviews" size="small">
          <el-table-column prop="finishedAt" label="面试时间" min-width="140" />
          <el-table-column prop="subjectName" label="学科" min-width="130" show-overflow-tooltip />
          <el-table-column label="难度" width="70">
            <template #default="{ row }">{{ DIFF_LABEL[row.difficulty] }}</template>
          </el-table-column>
          <el-table-column prop="questionCount" label="题数" width="60" />
          <el-table-column label="综合评分" width="90">
            <template #default="{ row }">{{ row.overallScore }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!interviewLoading && !interviews.length" description="暂无面试记录" :image-size="56" />
        <el-pagination
          v-if="interviewTotal > interviewPageSize"
          v-model:current-page="interviewPage"
          v-model:page-size="interviewPageSize"
          class="interview-pager"
          :total="interviewTotal"
          :page-sizes="[5, 10]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadInterviews(detail.profile.id)"
          @size-change="loadInterviews(detail.profile.id)"
        />
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}

/* ---- 表格学员单元格 ---- */
.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.avatar-img {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  object-fit: cover;
}
.avatar-letter {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--brand-grad);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}
.user-name {
  font-weight: 600;
}
.nowrap {
  white-space: nowrap;
}

/* ---- 详情抽屉 ---- */
.profile-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 14px;
}
.avatar-lg {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  object-fit: cover;
  font-size: 22px;
}
.profile-name {
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
}
.detail-desc {
  margin-bottom: 4px;
}
.drawer-title {
  margin: 18px 0 8px;
  font-size: 14px;
}
.stats-row {
  display: flex;
  gap: 12px;
}
.ds-item {
  flex: 1;
  text-align: center;
  padding: 10px 6px;
  background: var(--surface-2);
  border-radius: var(--radius-sm, 6px);
}
.ds-item b {
  display: block;
  font-size: 18px;
}
.ds-item span {
  font-size: 12px;
  color: var(--ink-3);
}
.course-list {
  margin-top: 10px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm, 6px);
  padding: 6px 10px;
  max-height: 160px;
  overflow-y: auto;
}
.course-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 5px 0;
  font-size: 13px;
  border-bottom: 1px dashed var(--line);
}
.course-item:last-child {
  border-bottom: none;
}
.course-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.interview-pager {
  margin-top: 10px;
  justify-content: flex-end;
}
</style>
