/**
 * 站点公开配置（Pinia）：管理端系统设置经 GET /settings/public 同步（04 §3.2）。
 * 顶栏/页脚 Logo 与名称、页脚描述、浏览器标题、头像兜底均取自此；
 * 拉取失败或字段为空时回落默认值，页面不受影响。
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { fetchPublicSettings } from '@/api/site'

export const DEFAULT_PLATFORM_NAME = '云枢智学'
export const DEFAULT_PLATFORM_DESC =
  'AI 赋能的智能面试训练平台。海量题库 × AI 模拟面试 × 学习路线，助你高效备战技术面试。'

export const useSiteStore = defineStore('site', () => {
  const platformName = ref(DEFAULT_PLATFORM_NAME)
  const platformDescription = ref('')
  const logoUrl = ref('')
  const defaultAvatarUrl = ref('')

  /** 页脚描述：管理端未设置时用默认文案 */
  const brandDesc = computed(() => platformDescription.value || DEFAULT_PLATFORM_DESC)

  let loading: Promise<void> | null = null

  /** 加载公开配置（幂等，失败保持默认值） */
  function load(): Promise<void> {
    if (loading) return loading
    loading = fetchPublicSettings()
      .then((s) => {
        platformName.value = s.platformName?.trim() || DEFAULT_PLATFORM_NAME
        platformDescription.value = s.platformDescription ?? ''
        logoUrl.value = s.logoUrl ?? ''
        defaultAvatarUrl.value = s.defaultAvatarUrl ?? ''
      })
      .catch(() => undefined)
      .finally(() => {
        loading = null
      })
    return loading
  }

  return { platformName, platformDescription, logoUrl, defaultAvatarUrl, brandDesc, load }
})
