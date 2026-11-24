<script setup lang="ts">
/**
 * 用户管理（04 §4.9 / 需求 4.5.1 / prototype/admin/users.html）。
 * 筛选 + 表格 + 分页 + 新增/编辑弹窗 + 详情抽屉（最近操作）+ 行/批量操作；
 * 按钮级权限 v-permission（user:create/edit/disable，删除与重置密码归并 user:edit V3）。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import type { ApiError, PageResult } from '@shared/types/api'
import {
  createUser,
  deleteUsers,
  fetchUser,
  fetchUsers,
  patchUserStatus,
  patchUsersStatus,
  resetUserPassword,
  updateUser,
} from '@/api/users'
import type { UserDetail, UserItem, UserPayload } from '@/api/users'
import { fetchRoles } from '@/api/roles'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

// ---- 筛选与分页 ----
const filter = reactive({ keyword: '', roleCode: '', status: '' })
const pageNum = ref(1)
const pageSize = ref(10)
const total = ref(0)
const rows = ref<UserItem[]>([])
const loading = ref(false)

// ---- 角色选项（/roles 仅超管；无权限时回落预置 3 角色）----
const roleOptions = ref<Array<{ code: string; name: string }>>([
  { code: 'content_reviewer', name: '内容审核' },
  { code: 'operator', name: '运营人员' },
])
async function loadRoleOptions() {
  if (auth.admin?.isSuper) {
    try {
      const res = await fetchRoles()
      roleOptions.value = res.list.map((r) => ({ code: r.code, name: r.name }))
    } catch {
      /* 保持回落列表 */
    }
  }
}

// ---- 列表 ----
async function load() {
  loading.value = true
  try {
    const res: PageResult<UserItem> = await fetchUsers({
      keyword: filter.keyword.trim() || undefined,
      roleCode: filter.roleCode || undefined,
      status: filter.status || undefined,
      pageNum: pageNum.value,
      pageSize: pageSize.value,
    })
    rows.value = res.list
    total.value = res.total
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pageNum.value = 1 // 筛选变更页码重置（需求 §6）
  load()
}

function handleReset() {
  filter.keyword = ''
  filter.roleCode = ''
  filter.status = ''
  handleSearch()
}

// ---- 批量选择 ----
const selected = ref<UserItem[]>([])
function handleSelectionChange(items: UserItem[]) {
  selected.value = items
}

/** 内置超管行（roleCode=super_admin 仅内置超管持有，A5 禁止授予他人）：禁用/删除不可用 */
function isSuperRow(row: UserItem): boolean {
  return row.roleCode === 'super_admin'
}

/** 批量操作目标（自动跳过内置超管，与后端保护一致） */
function batchTargetIds(): number[] {
  const supers = selected.value.filter(isSuperRow)
  if (supers.length) {
    ElMessage.warning('已跳过内置超管账号（不可批量操作）')
  }
  return selected.value.filter((u) => !isSuperRow(u)).map((u) => u.id)
}

// ---- 新增/编辑弹窗 ----
const dialogVisible = ref(false)
const dialogTitle = ref('新增用户')
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive<UserPayload & { password: string }>({
  username: '',
  phone: '',
  email: '',
  roleCode: '',
  password: '',
  status: 'enabled',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1\d{10}$/, message: '手机号格式不正确', trigger: 'blur' },
  ],
  roleCode: [{ required: true, message: '请选择角色', trigger: 'change' }],
  password: [
    { required: true, message: '请输入密码（6-20 位）', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度 6-20 位', trigger: 'blur' },
  ],
}

function openCreate() {
  editingId.value = null
  dialogTitle.value = '新增用户'
  Object.assign(form, { username: '', phone: '', email: '', roleCode: '', password: '', status: 'enabled' })
  dialogVisible.value = true
}

function openEdit(row: UserItem) {
  editingId.value = row.id
  dialogTitle.value = '编辑用户'
  Object.assign(form, {
    username: row.username,
    phone: row.phone,
    email: '',
    roleCode: row.roleCode,
    password: '',
    status: row.status,
  })
  // 编辑时密码选填
  fetchUser(row.id)
    .then((d) => {
      form.email = d.email ?? ''
    })
    .catch(() => {})
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  try {
    if (editingId.value === null) {
      await createUser(form)
      ElMessage.success('新增成功')
    } else {
      const payload: UserPayload = {
        username: form.username,
        phone: form.phone,
        email: form.email || null,
        roleCode: form.roleCode,
        password: form.password || undefined,
        status: form.status,
      }
      await updateUser(editingId.value, payload)
      ElMessage.success('保存成功')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

// ---- 详情抽屉 ----
const drawerVisible = ref(false)
const detail = ref<UserDetail | null>(null)
async function openDetail(row: UserItem) {
  try {
    detail.value = await fetchUser(row.id)
    drawerVisible.value = true
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '加载详情失败')
  }
}

// ---- 行操作 ----
async function handleToggleStatus(row: UserItem) {
  const next = row.status === 'enabled' ? 'disabled' : 'enabled'
  const label = next === 'enabled' ? '启用' : '禁用'
  try {
    await ElMessageBox.confirm(`确定要${label}用户「${row.username}」吗？`, `${label}用户`, {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await patchUserStatus(row.id, next)
    ElMessage.success(`${label}成功`)
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

async function handleResetPwd(row: UserItem) {
  try {
    await ElMessageBox.confirm(
      `确定要重置用户「${row.username}」的密码吗？重置后需通知对方使用默认密码登录。`,
      '重置密码',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await resetUserPassword(row.id)
    ElMessage.success('已重置为默认密码')
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

async function handleDelete(row?: UserItem) {
  const ids = row ? [row.id] : batchTargetIds()
  if (!ids.length) {
    ElMessage.warning('请先勾选要删除的用户')
    return
  }
  try {
    await ElMessageBox.confirm(
      row ? `确定要删除用户「${row.username}」吗？` : `确定要删除勾选的 ${ids.length} 个用户吗？`,
      '删除用户',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await deleteUsers(ids)
    ElMessage.success('删除成功')
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '删除失败')
  }
}

async function handleBatchStatus(status: 'enabled' | 'disabled') {
  const ids = batchTargetIds()
  if (!ids.length) {
    ElMessage.warning('请先勾选用户')
    return
  }
  const label = status === 'enabled' ? '启用' : '禁用'
  try {
    await ElMessageBox.confirm(`确定要批量${label} ${ids.length} 个用户吗？`, `批量${label}`, {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await patchUsersStatus(ids, status)
    ElMessage.success(`${label}成功`)
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

onMounted(() => {
  load()
  loadRoleOptions()
})
</script>

<template>
  <div>
    <!-- 工具栏：筛选 + 操作同行 -->
    <div class="list-toolbar">
      <el-input
        v-model="filter.keyword"
        style="width: 220px"
        placeholder="用户名/手机号"
        clearable
        @keyup.enter="handleSearch"
      />
      <el-select v-model="filter.roleCode" placeholder="角色" clearable style="width: 150px">
        <el-option v-for="r in roleOptions" :key="r.code" :label="r.name" :value="r.code" />
      </el-select>
      <el-select v-model="filter.status" placeholder="状态" clearable style="width: 120px">
        <el-option label="启用" value="enabled" />
        <el-option label="禁用" value="disabled" />
      </el-select>
      <el-button type="primary" @click="handleSearch"><el-icon class="btn-ic"><Search /></el-icon>查询</el-button>
      <el-button @click="handleReset"><el-icon class="btn-ic"><Refresh /></el-icon>重置</el-button>
      <div class="toolbar-actions">
        <el-button v-permission="'user:create'" type="primary" @click="openCreate"><el-icon class="btn-ic"><Plus /></el-icon>新增用户</el-button>
        <el-button v-permission="'user:disable'" @click="handleBatchStatus('enabled')">
          <el-icon class="btn-ic"><CircleCheck /></el-icon>批量启用
        </el-button>
        <el-button v-permission="'user:disable'" @click="handleBatchStatus('disabled')">
          <el-icon class="btn-ic"><CircleClose /></el-icon>批量禁用
        </el-button>
        <el-button v-permission="'user:edit'" type="danger" plain @click="handleDelete()">
          <el-icon class="btn-ic"><Delete /></el-icon>批量删除
        </el-button>
        <span class="count-text">共 {{ total }} 个用户</span>
      </div>
    </div>

    <!-- 表格 -->
    <el-table v-loading="loading" :data="rows" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="42" />
      <el-table-column label="用户" min-width="180">
        <template #default="{ row }">
          <div class="user-cell">
            <img v-if="row.avatarUrl" :src="row.avatarUrl" class="avatar-img" alt="" />
            <span v-else class="avatar-letter">{{ row.username.slice(0, 1) }}</span>
            <div>
              <div class="user-name">{{ row.username }}</div>
              <div v-if="row.nickname && row.nickname !== row.username" class="muted user-nick">
                {{ row.nickname }}
              </div>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="phone" label="手机号" min-width="120" />
      <el-table-column label="角色" min-width="110">
        <template #default="{ row }">
          <el-tag :type="row.roleCode === 'super_admin' ? 'danger' : 'primary'" effect="plain">
            {{ row.roleName }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" min-width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'enabled' ? 'success' : 'info'">
            {{ row.status === 'enabled' ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="lastLoginAt" label="最后登录" min-width="150">
        <template #default="{ row }">{{ row.lastLoginAt || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right" class-name="actions-cell">
        <template #default="{ row }">
          <el-button v-permission="'user:edit'" link type="primary" @click="openEdit(row)"><el-icon class="btn-ic"><EditPen /></el-icon>编辑</el-button>
          <el-button
            v-permission="'user:disable'"
            link
            type="primary"
            :disabled="isSuperRow(row)"
            :title="isSuperRow(row) ? '内置超管不可禁用' : ''"
            @click="handleToggleStatus(row)"
          >
            <el-icon class="btn-ic"><component :is="row.status === 'enabled' ? 'CircleClose' : 'CircleCheck'" /></el-icon>{{ row.status === 'enabled' ? '禁用' : '启用' }}
          </el-button>
          <el-button v-permission="'user:edit'" link type="warning" @click="handleResetPwd(row)">
            <el-icon class="btn-ic"><Key /></el-icon>重置密码
          </el-button>
          <el-button
            v-permission="'user:edit'"
            link
            type="danger"
            :disabled="isSuperRow(row)"
            :title="isSuperRow(row) ? '内置超管不可删除' : ''"
            @click="handleDelete(row)"
          >
            <el-icon class="btn-ic"><Delete /></el-icon>删除
          </el-button>
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

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="84px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" maxlength="50" placeholder="登录账号" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" maxlength="11" placeholder="11 位手机号" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" maxlength="100" placeholder="选填" />
        </el-form-item>
        <el-form-item label="角色" prop="roleCode">
          <el-select v-model="form.roleCode" placeholder="请选择角色" style="width: 100%">
            <el-option v-for="r in roleOptions" :key="r.code" :label="r.name" :value="r.code" />
          </el-select>
        </el-form-item>
        <el-form-item :label="editingId === null ? '密码' : '重置密码'" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="editingId === null ? '6-20 位' : '留空则不修改'"
          />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-switch v-model="form.status" active-value="enabled" inactive-value="disabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false"><el-icon class="btn-ic"><Close /></el-icon>取消</el-button>
        <el-button type="primary" @click="handleSubmit"><el-icon class="btn-ic"><Check /></el-icon>保存</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" title="用户详情" size="420px">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="用户名">{{ detail.username }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ detail.phone }}</el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ detail.email || '—' }}</el-descriptions-item>
          <el-descriptions-item label="角色">{{ detail.roleName }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="detail.status === 'enabled' ? 'success' : 'info'">
              {{ detail.status === 'enabled' ? '启用' : '禁用' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detail.createdAt }}</el-descriptions-item>
          <el-descriptions-item label="最后登录">{{ detail.lastLoginAt || '—' }}</el-descriptions-item>
        </el-descriptions>
        <h4 class="recent-title">最近操作</h4>
        <div v-if="detail.recentLogs.length" class="recent-list">
          <div v-for="(lg, i) in detail.recentLogs" :key="i" class="recent-item">
            <span>{{ lg.action }}</span>
            <span class="muted">{{ lg.at }}</span>
          </div>
        </div>
        <el-empty v-else description="暂无操作记录" :image-size="64" />
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
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
.user-nick {
  font-size: 12px;
}
.recent-title {
  margin: 18px 0 8px;
}
.recent-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.recent-item {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  padding: 6px 10px;
  background: var(--surface-2);
  border-radius: var(--radius-sm);
}
</style>
