<script setup lang="ts">
/**
 * 学科管理（04 §4.3 / 需求 4.3.1 / prototype/admin/subjects.html）。
 * 统计卡片 + 学科卡片网格（含阶段行）+ 新增/编辑 + 上移/下移排序 + 删除三态确认；
 * 按钮级权限 v-permission（subject:view/create/edit/delete）。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import type { ApiError } from '@shared/types/api'
import {
  createStage,
  createSubject,
  deleteStage,
  deleteSubject,
  fetchSubjects,
  patchStageStatus,
  sortStages,
  sortSubjects,
  updateStage,
  updateSubject,
} from '@/api/subjects'
import type { StageItem, SubjectCards, SubjectItem, SubjectPayload } from '@/api/subjects'

/** 主题色预置色板（04 §4.3 themeColor，与原型 PALETTE 一致，后端同源校验；末位=其他学科兜底灰） */
const THEME_COLORS = ['#2a78d6', '#6250d6', '#1baf7a', '#eb6834', '#e87ba4', '#008300', '#eda100', '#e34948', '#898781']

const loading = ref(false)
const cards = ref<SubjectCards>({ total: 0, withStages: 0, stageTotal: 0, questionTotal: 0 })
const subjects = ref<SubjectItem[]>([])

async function load() {
  loading.value = true
  try {
    const res = await fetchSubjects()
    cards.value = res.cards
    subjects.value = res.list
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)

/** 图标底色 = 主题色 16% 透明度（原型 tint(hex, 0.16)） */
function tint(hex: string, alpha: number): string {
  const h = (hex || '#2a78d6').replace('#', '')
  const full = h.length === 3 ? h.replace(/./g, (ch) => ch + ch) : h
  const r = parseInt(full.slice(0, 2), 16)
  const g = parseInt(full.slice(2, 4), 16)
  const b = parseInt(full.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

// ---- 学科新增/编辑弹窗 ----
const subjectDialogVisible = ref(false)
const subjectDialogTitle = ref('新增学科')
const editingSubjectId = ref<number | null>(null)
const subjectFormRef = ref<FormInstance>()
const subjectForm = reactive({ name: '', icon: '', description: '', sortOrder: 1, themeColor: THEME_COLORS[0] })

const subjectRules: FormRules = {
  name: [{ required: true, message: '请输入学科名称', trigger: 'blur' }],
  icon: [{ required: true, message: '请输入学科图标 Emoji', trigger: 'blur' }],
  description: [{ required: true, message: '请输入学科描述', trigger: 'blur' }],
}

function openSubjectDialog(row?: SubjectItem) {
  editingSubjectId.value = row?.id ?? null
  subjectDialogTitle.value = row ? '编辑学科' : '新增学科'
  Object.assign(subjectForm, {
    name: row?.name ?? '',
    icon: row?.icon ?? '',
    description: row?.description ?? '',
    sortOrder: row?.sortOrder ?? subjects.value.length + 1, // 默认追加末尾（1 起位置）
    themeColor: row?.themeColor ?? THEME_COLORS[0],
  })
  subjectDialogVisible.value = true
}

async function handleSaveSubject() {
  const valid = await subjectFormRef.value?.validate().catch(() => false)
  if (!valid) return
  const payload: SubjectPayload = {
    name: subjectForm.name.trim(),
    icon: subjectForm.icon.trim(),
    description: subjectForm.description.trim(),
    sortOrder: subjectForm.sortOrder,
    themeColor: subjectForm.themeColor,
  }
  try {
    if (editingSubjectId.value === null) {
      await createSubject(payload)
      ElMessage.success(`新增学科「${payload.name}」成功`)
    } else {
      await updateSubject(editingSubjectId.value, payload)
      ElMessage.success(`学科「${payload.name}」已保存`)
    }
    subjectDialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

// ---- 学科删除（三态确认提示，计数取自列表响应，04 §4.3）----
async function handleDeleteSubject(row: SubjectItem) {
  const stN = row.stages.length
  const qN = row.questionCount
  let msg: string
  if (stN > 0 && qN > 0) {
    msg = `该学科下有 ${stN} 个阶段、${qN} 道题目，删除后这些阶段与题目将一并删除（逻辑删除，数据保留可恢复）。确定删除学科「${row.name}」吗？`
  } else if (stN > 0) {
    msg = `该学科下有 ${stN} 个阶段，删除后将一并删除（逻辑删除，数据保留可恢复）。确定删除学科「${row.name}」吗？`
  } else {
    msg = `确定删除学科「${row.name}」吗？删除后数据保留可恢复。`
  }
  try {
    await ElMessageBox.confirm(msg, '删除学科', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteSubject(row.id)
    ElMessage.success(`已删除学科「${row.name}」`)
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '删除失败')
  }
}

// ---- 学科排序（上移/下移 → 全量 id 重排）----
async function moveSubject(index: number, delta: number) {
  const list = [...subjects.value]
  const j = index + delta
  if (j < 0 || j >= list.length) return
  const [item] = list.splice(index, 1)
  list.splice(j, 0, item)
  try {
    await sortSubjects(list.map((s) => s.id))
    subjects.value = list.map((s, i) => ({ ...s, sortOrder: i + 1 }))
    ElMessage.success(`已${delta < 0 ? '上移' : '下移'}学科「${item.name}」`)
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '排序失败')
    load()
  }
}

// ---- 阶段新增/编辑弹窗 ----
const stageDialogVisible = ref(false)
const stageDialogTitle = ref('添加阶段')
const stageSubjectId = ref<number | null>(null)
const editingStageId = ref<number | null>(null)
const stageFormRef = ref<FormInstance>()
const stageForm = reactive({ icon: '', name: '', sortOrder: 1 })

const stageRules: FormRules = {
  name: [{ required: true, message: '请输入阶段名称', trigger: 'blur' }],
}

function openStageDialog(subject: SubjectItem, row?: StageItem) {
  stageSubjectId.value = subject.id
  editingStageId.value = row?.id ?? null
  stageDialogTitle.value = row ? '编辑阶段' : '添加阶段'
  Object.assign(stageForm, {
    icon: row?.icon ?? '',
    name: row?.name ?? '',
    sortOrder: row?.sortOrder ?? subject.stages.length + 1,
  })
  stageDialogVisible.value = true
}

async function handleSaveStage() {
  if (stageSubjectId.value === null) return
  const valid = await stageFormRef.value?.validate().catch(() => false)
  if (!valid) return
  const payload = {
    subjectId: stageSubjectId.value,
    name: stageForm.name.trim(),
    icon: stageForm.icon.trim() || null, // 留空默认 📌（前端展示兜底）
    sortOrder: stageForm.sortOrder,
  }
  try {
    if (editingStageId.value === null) {
      await createStage(payload)
      ElMessage.success(`已添加阶段「${payload.name}」`)
    } else {
      await updateStage(editingStageId.value, payload)
      ElMessage.success(`阶段「${payload.name}」已保存`)
    }
    stageDialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
  }
}

// ---- 阶段启停（确认后生效）----
async function handleStageToggle(subject: SubjectItem, row: StageItem, wantEnable: boolean) {
  try {
    await ElMessageBox.confirm(
      `确定要${wantEnable ? '启用' : '禁用'}阶段「${row.name}」吗？${wantEnable ? '' : '禁用后该阶段在学员端不再展示。'}`,
      wantEnable ? '启用阶段' : '禁用阶段',
      {
        type: 'warning',
        confirmButtonText: wantEnable ? '启用' : '禁用',
        cancelButtonText: '取消',
      },
    )
  } catch {
    return // 取消时开关保持原状（受控 model-value 未变更）
  }
  try {
    await patchStageStatus(row.id, wantEnable ? 'enabled' : 'disabled')
    ElMessage.success(`阶段「${row.name}」已${wantEnable ? '启用' : '禁用'}`)
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '操作失败')
    load()
  }
}

// ---- 阶段排序（上移/下移）----
async function moveStage(subject: SubjectItem, index: number, delta: number) {
  const list = [...subject.stages]
  const j = index + delta
  if (j < 0 || j >= list.length) return
  const [item] = list.splice(index, 1)
  list.splice(j, 0, item)
  try {
    await sortStages(subject.id, list.map((s) => s.id))
    subject.stages = list.map((s, i) => ({ ...s, sortOrder: i + 1 }))
    ElMessage.success(`已${delta < 0 ? '上移' : '下移'}阶段「${item.name}」`)
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '排序失败')
    load()
  }
}

// ---- 阶段删除（二态确认提示）----
async function handleDeleteStage(row: StageItem) {
  const msg =
    row.questionCount > 0
      ? `该阶段下有 ${row.questionCount} 道题目，删除后题目将一并删除（逻辑删除，数据保留可恢复）。确定删除阶段「${row.name}」吗？`
      : `确定删除阶段「${row.name}」吗？删除后数据保留可恢复。`
  try {
    await ElMessageBox.confirm(msg, '删除阶段', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteStage(row.id)
    ElMessage.success(`已删除阶段「${row.name}」`)
    load()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '删除失败')
  }
}
</script>

<template>
  <div v-loading="loading">
    <!-- 统计卡片（04 §4.3 cards） -->
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">总学科数</span><span class="stat-icon">📚</span></div>
        <div class="stat-value">{{ cards.total }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">有阶段的学科</span><span class="stat-icon">🗂️</span></div>
        <div class="stat-value">{{ cards.withStages }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">阶段总数</span><span class="stat-icon">🧩</span></div>
        <div class="stat-value">{{ cards.stageTotal }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">题目总数</span><span class="stat-icon">📝</span></div>
        <div class="stat-value">{{ cards.questionTotal }}</div>
      </div>
    </div>

    <!-- 工具行 -->
    <div class="list-toolbar">
      <span class="count-text">共 {{ cards.total }} 个学科 · 上移 / 下移可调整展示顺序</span>
      <div class="toolbar-actions">
        <el-button v-permission="'subject:create'" type="primary" @click="openSubjectDialog()">
          <el-icon class="btn-ic"><Plus /></el-icon>新增学科
        </el-button>
      </div>
    </div>

    <!-- 学科卡片网格 -->
    <div v-if="subjects.length" class="subject-grid">
      <div v-for="(subject, si) in subjects" :key="subject.id" class="subject-card">
        <div class="sa-head">
          <div class="sa-icon" :style="{ background: tint(subject.themeColor, 0.16) }">{{ subject.icon }}</div>
          <div class="sa-title">
            <div class="sa-name">
              <b>{{ subject.name }}</b>
              <el-tag size="small" effect="plain">排序 {{ subject.sortOrder }}</el-tag>
            </div>
            <div class="muted sa-desc">{{ subject.description }}</div>
          </div>
          <div class="sa-ops">
            <el-button v-permission="'subject:edit'" link type="primary" :disabled="si === 0" @click="moveSubject(si, -1)">
              <el-icon class="btn-ic"><Top /></el-icon>上移
            </el-button>
            <el-button
              v-permission="'subject:edit'"
              link
              type="primary"
              :disabled="si === subjects.length - 1"
              @click="moveSubject(si, 1)"
            >
              <el-icon class="btn-ic"><Bottom /></el-icon>下移
            </el-button>
            <el-button v-permission="'subject:edit'" link type="primary" @click="openSubjectDialog(subject)">
              <el-icon class="btn-ic"><EditPen /></el-icon>编辑学科
            </el-button>
            <el-button v-permission="'subject:delete'" link type="danger" @click="handleDeleteSubject(subject)">
              <el-icon class="btn-ic"><Delete /></el-icon>删除学科
            </el-button>
          </div>
        </div>

        <div class="sa-stats">
          <span><b>{{ subject.courseCount }}</b>课程数</span>
          <span><b>{{ subject.routeCount }}</b>路线数</span>
          <span><b>{{ subject.questionCount }}</b>题目数</span>
        </div>

        <template v-if="subject.stages.length">
          <div v-for="(st, sti) in subject.stages" :key="st.id" class="stage-row" :class="{ disabled: st.status !== 'enabled' }">
            <div class="sm-name">
              {{ st.icon || '📌' }} {{ st.name }} <span class="muted">{{ st.questionCount }} 题</span>
            </div>
            <el-button v-permission="'subject:edit'" link type="primary" :disabled="sti === 0" @click="moveStage(subject, sti, -1)">
              <el-icon class="btn-ic"><Top /></el-icon>上移
            </el-button>
            <el-button
              v-permission="'subject:edit'"
              link
              type="primary"
              :disabled="sti === subject.stages.length - 1"
              @click="moveStage(subject, sti, 1)"
            >
              <el-icon class="btn-ic"><Bottom /></el-icon>下移
            </el-button>
            <el-switch
              v-permission="'subject:edit'"
              class="st-switch"
              :model-value="st.status === 'enabled'"
              :title="st.status === 'enabled' ? '点击禁用该阶段' : '点击启用该阶段'"
              @change="handleStageToggle(subject, st, $event === true)"
            />
            <el-button v-permission="'subject:edit'" link type="primary" @click="openStageDialog(subject, st)">
              <el-icon class="btn-ic"><EditPen /></el-icon>编辑
            </el-button>
            <el-button v-permission="'subject:delete'" link type="danger" @click="handleDeleteStage(st)">
              <el-icon class="btn-ic"><Delete /></el-icon>删除
            </el-button>
          </div>
        </template>
        <div v-else class="stage-row">
          <div class="sm-name muted">暂无阶段，点击下方「+ 添加阶段」录入</div>
        </div>

        <div class="sa-foot">
          <el-button v-permission="'subject:create'" @click="openStageDialog(subject)">
            <el-icon class="btn-ic"><Plus /></el-icon>添加阶段
          </el-button>
        </div>
      </div>
    </div>
    <el-empty v-else description="暂无学科">
      <span class="muted">点击右上角「+ 新增学科」创建第一个学科</span>
    </el-empty>

    <!-- 学科表单弹窗 -->
    <el-dialog v-model="subjectDialogVisible" :title="subjectDialogTitle" width="520px">
      <el-form ref="subjectFormRef" :model="subjectForm" :rules="subjectRules" label-position="top">
        <el-form-item label="学科名称" prop="name">
          <el-input v-model="subjectForm.name" maxlength="50" placeholder="如：AI应用与智能体开发" />
        </el-form-item>
        <el-form-item label="学科图标 Emoji" prop="icon">
          <el-input v-model="subjectForm.icon" maxlength="10" placeholder="如：🤖" />
          <div class="field-hint">
            不知道用什么？到
            <a href="https://www.emojiall.com/zh-hans" target="_blank" rel="noopener">Emoji 大全</a>
            搜索复制
          </div>
        </el-form-item>
        <el-form-item label="学科描述" prop="description">
          <el-input
            v-model="subjectForm.description"
            type="textarea"
            :rows="3"
            maxlength="255"
            placeholder="一句话描述学科定位与培养目标"
          />
        </el-form-item>
        <el-form-item label="排序号">
          <el-input-number v-model="subjectForm.sortOrder" :min="1" :step="1" controls-position="right" />
          <div class="field-hint">数字越小越靠前，保存后按此顺序展示</div>
        </el-form-item>
        <el-form-item label="主题颜色" required>
          <div class="color-row">
            <span
              v-for="c in THEME_COLORS"
              :key="c"
              class="color-dot"
              :class="{ active: subjectForm.themeColor === c }"
              :style="{ background: c }"
              :title="c"
              @click="subjectForm.themeColor = c"
            />
          </div>
          <div class="field-hint">用于卡片图标底色等主题展示</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="subjectDialogVisible = false"><el-icon class="btn-ic"><Close /></el-icon>取消</el-button>
        <el-button type="primary" @click="handleSaveSubject"><el-icon class="btn-ic"><Check /></el-icon>保存</el-button>
      </template>
    </el-dialog>

    <!-- 阶段表单弹窗 -->
    <el-dialog v-model="stageDialogVisible" :title="stageDialogTitle" width="440px">
      <el-form ref="stageFormRef" :model="stageForm" :rules="stageRules" label-position="top">
        <el-form-item label="图标">
          <el-input v-model="stageForm.icon" maxlength="10" placeholder="留空默认 📌" />
          <div class="field-hint">
            留空默认 📌 ·
            <a href="https://www.emojiall.com/zh-hans" target="_blank" rel="noopener">Emoji 大全</a>
            可搜索复制
          </div>
        </el-form-item>
        <el-form-item label="阶段名称" prop="name">
          <el-input v-model="stageForm.name" maxlength="50" placeholder="如：大模型基础" />
        </el-form-item>
        <el-form-item label="排序号">
          <el-input-number v-model="stageForm.sortOrder" :min="1" :step="1" controls-position="right" />
          <div class="field-hint">数字越小越靠前，保存后按此顺序展示</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stageDialogVisible = false"><el-icon class="btn-ic"><Close /></el-icon>取消</el-button>
        <el-button type="primary" @click="handleSaveStage"><el-icon class="btn-ic"><Check /></el-icon>保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* ---- 统计卡片 ---- */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
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

/* ---- 学科卡片网格（对齐原型 .subject-admin-*）---- */
.subject-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}
.subject-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  transition: box-shadow .15s;
}
.subject-card:hover {
  box-shadow: var(--shadow-lg);
}
.sa-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 20px 0;
}
.sa-icon {
  width: 46px;
  height: 46px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 23px;
  flex-shrink: 0;
}
.sa-title {
  flex: 1;
  min-width: 0;
}
.sa-name {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.sa-name b {
  font-size: 15px;
}
.sa-desc {
  font-size: 12px;
}
.sa-ops {
  white-space: nowrap;
  display: flex;
  align-items: center;
}
.sa-ops .el-button {
  padding: 0 4px;
}
.sa-ops .el-button + .el-button {
  margin-left: 2px;
}
.sa-stats {
  display: flex;
  gap: 18px;
  padding: 12px 20px;
  font-size: 12px;
  color: var(--ink-3);
  border-bottom: 1px solid var(--line);
}
.sa-stats b {
  color: var(--ink);
  font-size: 15px;
  margin-right: 3px;
}

/* ---- 阶段行 ---- */
.stage-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 20px;
  font-size: 13px;
  border-bottom: 1px dashed var(--line);
}
.stage-row:last-of-type {
  border-bottom: none;
}
.stage-row.disabled {
  opacity: .55;
}
.stage-row .sm-name {
  flex: 1;
  min-width: 0;
}
.stage-row .el-button {
  padding: 0 4px;
}
.stage-row .el-button + .el-button {
  margin-left: 2px;
}
.st-switch {
  margin: 0 2px;
}
.sa-foot {
  padding: 12px 20px;
}

/* ---- 表单辅助 ---- */
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
.color-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.color-dot {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  cursor: pointer;
  display: inline-block;
  border: 2px solid #fff;
  box-shadow: 0 0 0 1px var(--line-strong, var(--line));
}
.color-dot.active {
  box-shadow: 0 0 0 2px var(--ink);
}

@media (max-width: 1100px) {
  .stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .subject-grid {
    grid-template-columns: 1fr;
  }
}
</style>
