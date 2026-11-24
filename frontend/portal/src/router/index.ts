/**
 * 学员端路由（02 §4.3：路由与登录守卫）。
 * 页面与 prototype/portal 13 页一一对应；未登录跳登录页（游客边界见 04 §1.5 S9：
 * 仅首页/注册/登录/找回密码可游客访问，题库/路线等均需登录）。
 */
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

/** 游客可访问（04 §1.5 公开接口对应页面） */
const GUEST_PAGES = new Set(['home', 'login', 'register', 'forgotPassword'])

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('@/layouts/PortalLayout.vue'),
    children: [
      { path: '', name: 'home', component: () => import('@/views/home/index.vue') },
      { path: 'questions', name: 'questions', component: () => import('@/views/questions/index.vue') },
      { path: 'practice', name: 'practice', component: () => import('@/views/practice/index.vue') },
      { path: 'wrongbook', name: 'wrongbook', component: () => import('@/views/wrongbook/index.vue') },
      { path: 'routes', name: 'routes', component: () => import('@/views/routes/index.vue') },
      {
        path: 'interview',
        children: [
          { path: 'config', name: 'interviewConfig', component: () => import('@/views/interview/config.vue') },
          { path: 'session', name: 'interviewSession', component: () => import('@/views/interview/session.vue') },
          { path: 'report/:id', name: 'interviewReport', component: () => import('@/views/interview/report.vue') },
          { path: 'records', name: 'interviewRecords', component: () => import('@/views/interview/records.vue') },
        ],
      },
      { path: 'profile', name: 'profile', component: () => import('@/views/profile/index.vue') },
    ],
  },
  // 账号页（独立于主布局）
  { path: '/login', name: 'login', component: () => import('@/views/auth/login.vue') },
  { path: '/register', name: 'register', component: () => import('@/views/auth/register.vue') },
  { path: '/forgot-password', name: 'forgotPassword', component: () => import('@/views/auth/forgot-password.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

// 登录守卫（02 §4.3）：非游客页未登录 → 跳登录页
router.beforeEach((to) => {
  const auth = useAuthStore()
  const guest = !to.name || GUEST_PAGES.has(String(to.name))
  if (!guest && !auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
