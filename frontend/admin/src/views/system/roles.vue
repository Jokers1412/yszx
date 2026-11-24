<script setup lang="ts">
/**
 * 角色管理（04 §4.10 / 需求 4.5.2 / prototype/admin/roles.html）——仅超管（Q3）。
 * 角色卡片 + 新增/编辑 + 权限授权（9 组 33 项树，全量覆盖）+ 删除（预置保护/占用校验）。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { CheckboxValueType } from 'element-plus'

import type { ApiError } from '@shared/types/api'
import {
  createRole,
  deleteRole,
  fetchPermissionTree,
  fetchRoles,
  updateRole,
  updateRolePermissions,
} from '@/api/roles'
import type { PermissionGroup, RoleItem } from '@/api/roles'

const roles = ref<RoleItem[]>([])
const loading = ref(false)
const permTree = ref<PermissionGroup[]>([])

async function load() {
  loading.value = true
  try {
    const res = await fetchRoles()
    roles.value = res.list
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  load()
  try {
    permTree.value = await fetchPermissionTree()
  } catch {
    /* 权限树在授权弹窗打开时重试 */
  }
})

// ---- 权限标签展示（截断 3 个 + 展开，需求 4.5.2）----
function tagText(tags: string[]): string {
  return tags.join('、')
}

// ---- 新增/编辑角色 ----
const dialogVisible = ref(false)
const dialogTitle = ref('新增角色')
const editingId = ref<number | null>(null)
const form = ref({ name: '', code: '', description: '' })

function openCreate() {
  editingId.value = null
  dialogTitle.value = '新增角色'
  form.value = { name: '', code: '', description: '' }
  dialogVisible.value = true
}

function openEdit(row: RoleItem) {
  editingId.value = row.id
  dialogTitle.value = '编辑角色'
  form.value = { name: row.name, code: row.code, description: row.description ?? '' }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入角色名称')
    return
  }
  try {
    if (editingId.value === null) {
      if (!/^[a-z][a-z0-9_]*$/.test(form.value.code.trim())) {
        ElMessage.warning('角色编码须为小写字母开头（字母/数字/下划线）')
        return
      }
      await createRole({
        name: form.value.name.trim(),
        code: form.value.code.trim(),
        description: form.value.description.trim() || undefined,
      })
      ElMessage.success('新增成功')
    } else {
      await updateRole(editingId.value, {
        name: form.value.name.trim(),
        description: form.value.description.trim() || undefined,
      })
      ElMessage.success('保存成功')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

// ---- 权限授权（全量覆盖）----
const permDialogVisible = ref(false)
const permRoleId = ref<number | null>(null)
const permRoleName = ref('')
const checkedCodes = ref<string[]>([])

/** 分组勾选状态计算 */
const groupState = computed(() => {
  return permTree.value.map((g) => {
    const codes = g.items.map((i) => i.code)
    const checked = codes.filter((c) => checkedCodes.value.includes(c))
    return {
      group: g.group,
      codes,
      checked,
      all: checked.length === codes.length && codes.length > 0,
      indeterminate: checked.length > 0 && checked.length < codes.length,
    }
  })
})

function toggleGroup(codes: string[], checked: boolean) {
  const others = checkedCodes.value.filter((c) => !codes.includes(c))
  checkedCodes.value = checked ? [...others, ...codes] : others
}

async function openPerms(row: RoleItem) {
  permRoleId.value = row.id
  permRoleName.value = row.name
  if (!permTree.value.length) {
    try {
      permTree.value = await fetchPermissionTree()
    } catch (e) {
      ElMessage.error((e as ApiError)?.message || '权限树加载失败')
      return
    }
  }
  // 展示已授权集合（超管=全量 33 码，免检语义一致）
  checkedCodes.value = row.isPreset && row.code === 'super_admin'
    ? permTree.value.flatMap((g) => g.items.map((i) => i.code))
    : row.permissionTags.includes('全部权限')
      ? permTree.value.flatMap((g) => g.items.map((i) => i.code))
      : row.permissionTags.includes('暂无权限')
        ? []
        : [] // 详细码列表未在列表接口返回 → 重新拉取不可行时按标签近似（授权弹窗以服务端为准）
  // 以服务端为准：列表接口仅返回 tags，编码集合从权限树 × tags 反查
  if (!checkedCodes.value.length && !row.permissionTags.includes('暂无权限')) {
    const labelToCode = new Map<string, string>()
    permTree.value.forEach((g) =>
      g.items.forEach((i) => labelToCode.set(`${g.group}·${i.name}`, i.code)),
    )
    checkedCodes.value = row.permissionTags
      .map((t) => labelToCode.get(t))
      .filter((c): c is string => !!c)
  }
  permDialogVisible.value = true
}

async function handleSavePerms() {
  if (permRoleId.value === null) return
  try {
    await updateRolePermissions(permRoleId.value, checkedCodes.value)
    ElMessage.success('授权成功')
    permDialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '授权失败')
  }
}

// ---- 删除 ----
async function handleDelete(row: RoleItem) {
  if (row.isPreset) {
    ElMessage.warning('预置角色不可删除')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定要删除角色「${row.name}」吗？（角色下有用户时不可删除）`,
      '删除角色',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await deleteRole(row.id)
    ElMessage.success('删除成功')
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '删除失败')
  }
}

function onGroupCheck(g: { codes: string[] }, e: CheckboxValueType) {
  toggleGroup(g.codes, e === true)
}
</script>

<template>
  <div v-loading="loading">
    <div class="list-toolbar">
      <el-button type="primary" @click="openCreate"><el-icon class="btn-ic"><Plus /></el-icon>新增角色</el-button>
      <div class="toolbar-actions">
        <span class="count-text">共 {{ roles.length }} 个角色（预置 3 个）</span>
      </div>
    </div>

    <!-- 角色卡片 -->
    <div class="role-grid">
      <div v-for="row in roles" :key="row.id" class="role-card">
        <div class="rc-head">
          <div>
            <div class="rc-name">
              {{ row.name }}
              <el-tag v-if="row.isPreset" size="small" type="warning" effect="plain">预置</el-tag>
            </div>
            <div class="muted rc-code">{{ row.code }}</div>
          </div>
          <div class="rc-count">
            <b>{{ row.userCount }}</b>
            <span class="muted">用户</span>
          </div>
        </div>
        <p class="rc-desc">{{ row.description || '暂无描述' }}</p>
        <div class="perm-tags">
          <el-tag v-for="t in row.permissionTags.slice(0, 3)" :key="t" size="small" effect="plain">
            {{ t }}
          </el-tag>
          <el-tooltip
            v-if="row.permissionTags.length > 3"
            :content="tagText(row.permissionTags)"
            placement="top"
          >
            <el-tag size="small" type="info" effect="plain">+{{ row.permissionTags.length - 3 }}</el-tag>
          </el-tooltip>
        </div>
        <div class="rc-actions">
          <el-button link type="primary" @click="openPerms(row)"><el-icon class="btn-ic"><Lock /></el-icon>授权</el-button>
          <el-button link type="primary" @click="openEdit(row)"><el-icon class="btn-ic"><EditPen /></el-icon>编辑</el-button>
          <el-button
            v-if="!row.isPreset"
            link
            type="danger"
            :disabled="row.userCount > 0"
            @click="handleDelete(row)"
          >
            <el-icon class="btn-ic"><Delete /></el-icon>删除
          </el-button>
        </div>
      </div>
    </div>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="460px">
      <el-form label-width="84px">
        <el-form-item label="角色名称" required>
          <el-input v-model="form.name" maxlength="50" placeholder="如：内容运营" />
        </el-form-item>
        <el-form-item v-if="editingId === null" label="角色编码" required>
          <el-input v-model="form.code" maxlength="50" placeholder="小写字母开头，如 content_operator" />
        </el-form-item>
        <el-form-item v-else label="角色编码">
          <el-input :model-value="form.code" disabled />
        </el-form-item>
        <el-form-item label="角色描述">
          <el-input v-model="form.description" type="textarea" :rows="3" maxlength="255" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false"><el-icon class="btn-ic"><Close /></el-icon>取消</el-button>
        <el-button type="primary" @click="handleSave"><el-icon class="btn-ic"><Check /></el-icon>保存</el-button>
      </template>
    </el-dialog>

    <!-- 权限授权弹窗 -->
    <el-dialog v-model="permDialogVisible" :title="`授权 · ${permRoleName}`" width="560px">
      <div class="perm-tree">
        <div v-for="g in groupState" :key="g.group" class="perm-group">
          <div class="pg-title">
            <el-checkbox
              :model-value="g.all"
              :indeterminate="g.indeterminate"
              @change="onGroupCheck(g, $event)"
            >
              {{ g.group }}
            </el-checkbox>
          </div>
          <div class="perm-items">
            <el-checkbox-group v-model="checkedCodes">
              <el-checkbox v-for="c in g.codes" :key="c" :value="c">
                {{ permTree.find((t) => t.group === g.group)?.items.find((i) => i.code === c)?.name }}
              </el-checkbox>
            </el-checkbox-group>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="permDialogVisible = false"><el-icon class="btn-ic"><Close /></el-icon>取消</el-button>
        <el-button type="primary" @click="handleSavePerms"><el-icon class="btn-ic"><Check /></el-icon>保存授权</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.role-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.role-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: box-shadow .15s;
}
.role-card:hover {
  box-shadow: var(--shadow-lg);
}
.rc-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}
.rc-name {
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
}
.rc-code {
  font-size: 12px;
  margin-top: 2px;
}
.rc-count {
  text-align: right;
  font-size: 12px;
}
.rc-count b {
  display: block;
  font-size: 20px;
}
.rc-desc {
  font-size: 13px;
  color: var(--ink-2);
  margin: 0;
  min-height: 38px;
}
.perm-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.rc-actions {
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px dashed var(--line);
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
.perm-group {
  margin-bottom: 10px;
}
.pg-title {
  font-weight: 600;
  padding: 6px 0;
}
.perm-items {
  padding-left: 24px;
}
@media (max-width: 1100px) {
  .role-grid {
    grid-template-columns: 1fr;
  }
}
</style>
