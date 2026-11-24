<script setup lang="ts">
/**
 * 系统设置（04 §4.12 / 需求 4.5.4 / prototype/admin/settings.html）——system:settings。
 * 平台名称/描述 + Logo/默认头像上传（jpg/png ≤2MB，存 MinIO）+ 保存/重置。
 * goodRate 为首页内部值，管理端不维护（口径 S20）。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadRequestOptions } from 'element-plus'

import type { ApiError } from '@shared/types/api'
import { fetchSettings, saveSettings, uploadSettingImage } from '@/api/settings'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()

const form = reactive({
  platformName: '',
  platformDescription: '',
  logoUrl: '',
  defaultAvatarUrl: '',
})
const saving = ref(false)
const loading = ref(false)

const DEFAULTS = {
  platformName: '云枢智学',
  platformDescription: '',
  logoUrl: '',
  defaultAvatarUrl: '',
}

async function load() {
  loading.value = true
  try {
    const res = await fetchSettings()
    form.platformName = res.platformName
    form.platformDescription = res.platformDescription ?? ''
    form.logoUrl = res.logoUrl ?? ''
    form.defaultAvatarUrl = res.defaultAvatarUrl ?? ''
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

/** 图片上传（受控：走统一封装，返回对象 URL） */
async function doUpload(options: UploadRequestOptions, type: 'logo' | 'defaultAvatar') {
  try {
    const res = await uploadSettingImage(options.file as File, type)
    if (type === 'logo') {
      form.logoUrl = res.url
      settingsStore.applyLocal({ logoUrl: res.url }) // 顶栏/侧栏即时预览
    } else {
      form.defaultAvatarUrl = res.url
      settingsStore.applyLocal({ defaultAvatarUrl: res.url }) // 用户头像即时预览
    }
    ElMessage.success('上传成功')
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '上传失败（仅 jpg/png，≤2MB）')
  }
}

function beforeUpload(file: File): boolean {
  const ok = ['image/jpeg', 'image/png'].includes(file.type)
  if (!ok) {
    ElMessage.warning('仅支持 jpg/png 图片')
    return false
  }
  if (file.size > 2 * 1024 * 1024) {
    ElMessage.warning('图片大小不能超过 2MB')
    return false
  }
  return true
}

function uploadLogo(o: UploadRequestOptions) {
  return doUpload(o, 'logo')
}

function uploadAvatar(o: UploadRequestOptions) {
  return doUpload(o, 'defaultAvatar')
}

async function handleSave() {
  if (!form.platformName.trim()) {
    ElMessage.warning('请输入平台名称')
    return
  }
  saving.value = true
  try {
    await saveSettings({
      platformName: form.platformName.trim(),
      platformDescription: form.platformDescription.trim() || null,
      logoUrl: form.logoUrl || null,
      defaultAvatarUrl: form.defaultAvatarUrl || null,
    })
    ElMessage.success('保存成功')
    // 回读服务端落库值回显（表单=服务端状态），并刷新侧栏品牌区/标题
    await load()
    await settingsStore.load(true)
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleReset() {
  try {
    await ElMessageBox.confirm('确定要恢复默认值吗？恢复后需点击「保存设置」生效。', '重置', {
      type: 'warning',
    })
  } catch {
    return
  }
  Object.assign(form, DEFAULTS)
  ElMessage.success('已恢复默认值')
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="settings-wrap">
    <el-card>
      <template #header>
        <span class="card-header-title">平台基本信息</span>
      </template>
      <el-form :model="form" label-width="100px" style="max-width: 560px">
        <el-form-item label="平台名称" required>
          <el-input v-model="form.platformName" maxlength="50" placeholder="云枢智学" />
        </el-form-item>
        <el-form-item label="平台描述">
          <el-input
            v-model="form.platformDescription"
            type="textarea"
            :rows="3"
            maxlength="500"
            placeholder="展示在学员端页脚/关于区域（选填）"
          />
        </el-form-item>

        <el-form-item label="Logo">
          <div class="upload-row">
            <img v-if="form.logoUrl" :src="form.logoUrl" class="preview-img" alt="Logo" />
            <div v-else class="preview-empty">暂无</div>
            <el-upload
              :show-file-list="false"
              accept="image/jpeg,image/png"
              :before-upload="beforeUpload"
              :http-request="uploadLogo"
            >
              <el-button><el-icon class="btn-ic"><Upload /></el-icon>上传图片</el-button>
            </el-upload>
          </div>
          <div class="upload-hint muted">jpg/png，≤2MB；建议方形透明底</div>
        </el-form-item>

        <el-form-item label="默认头像">
          <div class="upload-row">
            <img
              v-if="form.defaultAvatarUrl"
              :src="form.defaultAvatarUrl"
              class="preview-img"
              alt="默认头像"
            />
            <div v-else class="preview-empty">暂无</div>
            <el-upload
              :show-file-list="false"
              accept="image/jpeg,image/png"
              :before-upload="beforeUpload"
              :http-request="uploadAvatar"
            >
              <el-button><el-icon class="btn-ic"><Upload /></el-icon>上传图片</el-button>
            </el-upload>
          </div>
          <div class="upload-hint muted">jpg/png，≤2MB；新注册学员的默认头像</div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSave"><el-icon class="btn-ic"><Check /></el-icon>保存设置</el-button>
          <el-button @click="handleReset"><el-icon class="btn-ic"><Refresh /></el-icon>重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.settings-wrap {
  max-width: 760px;
}
.card-header-title {
  font-weight: 600;
}
.upload-row {
  display: flex;
  align-items: center;
  gap: 14px;
}
.preview-img {
  width: 72px;
  height: 72px;
  border-radius: var(--radius-sm);
  object-fit: cover;
  border: 1px solid var(--line);
}
.preview-empty {
  width: 72px;
  height: 72px;
  border-radius: var(--radius-sm);
  border: 1px dashed var(--line-strong);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ink-3);
  font-size: 12px;
}
.upload-hint {
  font-size: 12px;
  line-height: 1.6;
  margin-top: 6px;
}
</style>
