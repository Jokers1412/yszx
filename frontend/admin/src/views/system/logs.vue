<script setup lang="ts">
/**
 * 操作日志（04 §4.11 / 需求 4.5.3 / prototype/admin/logs.html）。
 * 筛选（关键词/操作类型/日期范围）+ 表格 + 详情弹窗 + 导出 CSV（log:view）+ 清空（system:settings）。
 * actionType 映射口径 S9：登出并入 login、审核/授权/重置密码并入 update、导出并入 other。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import type { ApiError, PageResult } from '@shared/types/api'
import { clearLogs, exportLogs, fetchLog, fetchLogs } from '@/api/logs'
import type { LogDetail, LogItem } from '@/api/logs'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const ACTION_TYPES = [
  { value: '', label: '全部类型' },
  { value: 'login', label: '登录类' },
  { value: 'create', label: '新增' },
  { value: 'update', label: '修改' },
  { value: 'delete', label: '删除' },
  { value: 'disable', label: '禁用/启用' },
  { value: 'other', label: '其他' },
]

const ACTION_LABELS: Record<string, string> = {
  login: '登录类',
  create: '新增',
  update: '修改',
  delete: '删除',
  disable: '禁用/启用',
  other: '其他',
}

const filter = reactive({
  keyword: '',
  actionType: '',
  dateRange: null as [string, string] | null, // value-format=YYYY-MM-DD → 字符串
})
const pageNum = ref(1)
const pageSize = ref(10)
const total = ref(0)
const rows = ref<LogItem[]>([])
const loading = ref(false)
const exporting = ref(false)

function buildQuery() {
  return {
    keyword: filter.keyword.trim() || undefined,
    actionType: filter.actionType || undefined,
    dateFrom: filter.dateRange ? filter.dateRange[0] : undefined,
    dateTo: filter.dateRange ? filter.dateRange[1] : undefined,
    pageNum: pageNum.value,
    pageSize: pageSize.value,
  }
}

async function load() {
  loading.value = true
  try {
    const res: PageResult<LogItem> = await fetchLogs(buildQuery())
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
  filter.actionType = ''
  filter.dateRange = null
  handleSearch()
}

// ---- 详情 ----
const detailVisible = ref(false)
const detail = ref<LogDetail | null>(null)
async function openDetail(row: LogItem) {
  try {
    detail.value = await fetchLog(row.id)
    detailVisible.value = true
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '加载详情失败')
  }
}

// ---- 导出 ----
async function handleExport() {
  exporting.value = true
  try {
    await exportLogs(buildQuery())
    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

// ---- 清空 ----
async function handleClear() {
  try {
    await ElMessageBox.confirm(
      '确定要清空全部操作日志吗？清空后不可恢复（逻辑删除）。',
      '清空日志',
      { type: 'warning', confirmButtonText: '清空', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await clearLogs()
    ElMessage.success('日志已清空')
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <!-- 工具栏：筛选 + 操作同行 -->
    <div class="list-toolbar">
      <el-input
        v-model="filter.keyword"
        style="width: 220px"
        placeholder="用户/操作/目标"
        clearable
        @keyup.enter="handleSearch"
      />
      <el-select v-model="filter.actionType" placeholder="操作类型" style="width: 140px">
        <el-option v-for="t in ACTION_TYPES" :key="t.value" :label="t.label" :value="t.value" />
      </el-select>
      <el-date-picker
        v-model="filter.dateRange"
        type="daterange"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        style="width: 260px"
      />
      <el-button type="primary" @click="handleSearch"><el-icon class="btn-ic"><Search /></el-icon>查询</el-button>
      <el-button @click="handleReset"><el-icon class="btn-ic"><Refresh /></el-icon>重置</el-button>
      <div class="toolbar-actions">
        <el-button v-permission="'log:view'" :loading="exporting" @click="handleExport">
          <el-icon class="btn-ic"><Download /></el-icon>导出 CSV
        </el-button>
        <el-button v-permission="'system:settings'" type="danger" plain @click="handleClear">
          <el-icon class="btn-ic"><Delete /></el-icon>清空日志
        </el-button>
        <span class="count-text">共 {{ total }} 条</span>
      </div>
    </div>

    <!-- 表格 -->
    <el-table v-loading="loading" :data="rows">
      <el-table-column label="用户" min-width="110">
        <template #default="{ row }">{{ row.adminUsername || '系统' }}</template>
      </el-table-column>
      <el-table-column label="操作" min-width="220">
        <template #default="{ row }">
          <el-tag size="small" effect="plain" :type="row.actionType === 'delete' ? 'danger' : 'primary'">
            {{ ACTION_LABELS[row.actionType] }}
          </el-tag>
          <span class="action-desc">{{ row.actionDesc }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="target" label="目标" min-width="150">
        <template #default="{ row }">{{ row.target || '—' }}</template>
      </el-table-column>
      <el-table-column prop="ip" label="IP地址" min-width="130" />
      <el-table-column prop="createdAt" label="时间" min-width="155" />
      <el-table-column label="操作" width="86" fixed="right" class-name="actions-cell">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)"><el-icon class="btn-ic"><View /></el-icon>详情</el-button>
        </template>
      </el-table-column>
    </el-table>

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

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="日志详情" width="520px">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="日志 ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="操作人">{{ detail.adminUsername || '系统' }}</el-descriptions-item>
          <el-descriptions-item label="操作类型">{{ ACTION_LABELS[detail.actionType] }}</el-descriptions-item>
          <el-descriptions-item label="操作">{{ detail.actionDesc }}</el-descriptions-item>
          <el-descriptions-item label="目标">{{ detail.target || '—' }}</el-descriptions-item>
          <el-descriptions-item label="详情">{{ detail.detail || '—' }}</el-descriptions-item>
          <el-descriptions-item label="IP 地址">{{ detail.ip }}</el-descriptions-item>
          <el-descriptions-item label="时间">{{ detail.createdAt }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
.action-desc {
  margin-left: 8px;
}
</style>
