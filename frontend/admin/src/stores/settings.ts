/**
 * 系统设置展示态（平台名称/Logo/默认头像）：
 * 驱动侧栏品牌区、顶栏标题旁 Logo、用户头像兜底与浏览器标题。
 * 读取走 GET /settings（system:settings）；无权限时静默回落默认值，不打扰。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

import { fetchSettings } from '@/api/settings'

const DEFAULT_NAME = '云枢智学'

export const useSettingsStore = defineStore('settings', () => {
  const platformName = ref(DEFAULT_NAME)
  const logoUrl = ref('')
  const defaultAvatarUrl = ref('')
  const loaded = ref(false)

  async function load(force = false) {
    if (loaded.value && !force) return
    try {
      const res = await fetchSettings()
      platformName.value = res.platformName?.trim() || DEFAULT_NAME
      logoUrl.value = res.logoUrl || ''
      defaultAvatarUrl.value = res.defaultAvatarUrl || ''
      loaded.value = true
      document.title = `${platformName.value} · 管理后台`
    } catch {
      // 无 system:settings 权限 / 加载失败 → 保持默认品牌，静默
    }
  }

  /** 上传后即时预览（保存前也先展示，保存持久化） */
  function applyLocal(partial: { logoUrl?: string; defaultAvatarUrl?: string }) {
    if (partial.logoUrl !== undefined) logoUrl.value = partial.logoUrl
    if (partial.defaultAvatarUrl !== undefined) defaultAvatarUrl.value = partial.defaultAvatarUrl
  }

  return { platformName, logoUrl, defaultAvatarUrl, loaded, load, applyLocal }
})
