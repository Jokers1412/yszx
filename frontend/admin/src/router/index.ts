/**
 * 管理端路由（02 §4.3）。
 * 页面与 prototype/admin 12 页一一对应；菜单按 permissionCodes 渲染（04 §1.6），
 * 无权限菜单不展示；未登录跳 /login。
 */
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '@/stores/auth'

/** 侧栏菜单顺序（无权限回跳时按此找首个可访问页） */
const MENU_ORDER = [
  'dashboard', 'subjects', 'courses', 'questions', 'interviewQuestions', 'routes',
  'students', 'users', 'roles', 'logs', 'settings',
] as const

/** 路由 meta 权限码（对应 04 附录 A；无 meta = 仅需登录） */
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('@/layouts/AdminLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '数据看板', perm: 'dashboard:view' },
      },
      // ---- 内容管理（五页）----
      {
        path: 'content/subjects',
        name: 'subjects',
        component: () => import('@/views/content/subjects.vue'),
        meta: { title: '学科管理', perm: 'subject:view' },
      },
      {
        path: 'content/courses',
        name: 'courses',
        component: () => import('@/views/content/courses.vue'),
        meta: { title: 'B站课程库', perm: 'course:view' },
      },
      {
        path: 'content/questions',
        name: 'questions',
        component: () => import('@/views/content/questions.vue'),
        meta: { title: '题库管理', perm: 'question:view' },
      },
      {
        path: 'content/interview-questions',
        name: 'interviewQuestions',
        component: () => import('@/views/content/interview-questions.vue'),
        meta: { title: '面试题库管理', perm: 'interviewbank:view' },
      },
      {
        path: 'content/routes',
        name: 'routes',
        component: () => import('@/views/content/routes.vue'),
        meta: { title: '学习路线管理', perm: 'route:view' },
      },
      // ---- 学员管理 ----
      {
        path: 'students',
        name: 'students',
        component: () => import('@/views/students/index.vue'),
        meta: { title: '学员管理', perm: 'student:view' },
      },
      // ---- 系统管理（四页）----
      {
        path: 'system/users',
        name: 'users',
        component: () => import('@/views/system/users.vue'),
        meta: { title: '用户管理', perm: 'user:view' },
      },
      {
        path: 'system/roles',
        name: 'roles',
        component: () => import('@/views/system/roles.vue'),
        meta: { title: '角色管理', superOnly: true }, // 仅超管可用（04 Q3），无权限码
      },
      {
        path: 'system/logs',
        name: 'logs',
        component: () => import('@/views/system/logs.vue'),
        meta: { title: '操作日志', perm: 'log:view' },
      },
      {
        path: 'system/settings',
        name: 'settings',
        component: () => import('@/views/system/settings.vue'),
        meta: { title: '系统设置', perm: 'system:settings' },
      },
    ],
  },
  { path: '/login', name: 'login', component: () => import('@/views/login.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

/** 首个有权限访问的页面名（登录后落地/无权限回跳用，避免固定跳 dashboard 造成死循环） */
export function firstAccessibleRouteName(): string {
  const auth = useAuthStore()
  for (const name of MENU_ORDER) {
    const r = router.getRoutes().find((x) => x.name === name)
    const perm = r?.meta?.perm as string | undefined
    const superOnly = !!r?.meta?.superOnly
    if (superOnly && !auth.admin?.isSuper) continue
    if (perm && !auth.hasPermission(perm)) continue
    return name
  }
  return 'dashboard'
}

// 登录守卫 + 权限守卫（04 §1.5/§1.6）：
//   1) 未登录且非 login 页 → 跳 /login（带 redirect 回跳）；
//   2) meta.perm 无权限 / superOnly 非超管 → 提示后跳首个有权限页（需求 §6）。
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.name !== 'login' && !auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && auth.isLoggedIn) {
    return { name: firstAccessibleRouteName() }
  }

  const fallback = firstAccessibleRouteName()
  const perm = to.meta?.perm as string | undefined
  if (perm && !auth.hasPermission(perm)) {
    ElMessage.warning('暂无权限访问该页面')
    return to.name === fallback ? true : { name: fallback }
  }
  if (to.meta?.superOnly && !auth.admin?.isSuper) {
    ElMessage.warning('仅超级管理员可访问该页面')
    return to.name === fallback ? true : { name: fallback }
  }
  return true
})

export default router
