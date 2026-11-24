<script setup lang="ts">
/**
 * 根组件：布局与页面切换由 router + layouts/ 承担；
 * 浏览器标题按「页名 - 平台名」展示（平台名随管理端系统设置同步，04 §3.2）。
 */
import { watch } from 'vue'
import { useRoute } from 'vue-router'

import { useSiteStore } from '@/stores/site'

const PAGE_TITLES: Record<string, string> = {
  home: '首页',
  questions: '题库',
  practice: '刷题练习',
  wrongbook: '错题本',
  routes: '学习路线',
  interviewConfig: 'AI面试',
  interviewSession: 'AI面试',
  interviewReport: '面试报告',
  interviewRecords: '面试记录',
  profile: '个人中心',
  login: '登录',
  register: '注册',
  forgotPassword: '找回密码',
}

const route = useRoute()
const site = useSiteStore()

watch(
  () => [route.name, site.platformName] as const,
  () => {
    const page = PAGE_TITLES[String(route.name)] ?? ''
    document.title = page ? `${page} - ${site.platformName}` : site.platformName
  },
  { immediate: true },
)
</script>

<template>
  <router-view />
</template>
