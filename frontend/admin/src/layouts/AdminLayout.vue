<script setup lang="ts">
/**
 * 管理端主布局（对齐 prototype/assets/js/admin.js 页架）：
 * <aside.admin-sidebar> + <.admin-main><header.admin-topbar><main.admin-content>
 * - 侧栏：Logo + 固定 4 组 11 项菜单（原型 MENU），可折叠（60px）；
 * - 顶栏：折叠按钮 + 页面标题 + 通知铃 + 用户下拉（返回前台/退出登录）；
 * - 权限过滤菜单在功能开发阶段开启（登录/permissionCodes 就绪后）。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { logout as logoutApi } from '@/api/auth'
import { firstAccessibleRouteName } from '@/router'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const settings = useSettingsStore()

/** 菜单（固定 4 组 11 项，与原型 MENU 一一对应；分组图标为布局阶段增补） */
const menuGroups = [
  {
    title: '概览',
    icon: '🏠',
    items: [{ routeName: 'dashboard', icon: '📊', label: '数据看板' }],
  },
  {
    title: '内容管理',
    icon: '🗂️',
    items: [
      { routeName: 'subjects', icon: '📚', label: '学科管理' },
      { routeName: 'courses', icon: '🎬', label: 'B站课程库' },
      { routeName: 'questions', icon: '📝', label: '题库管理' },
      { routeName: 'interviewQuestions', icon: '💬', label: '面试题库管理' },
      { routeName: 'routes', icon: '🗺️', label: '学习路线' },
    ],
  },
  {
    title: '学员管理',
    icon: '🎓',
    items: [{ routeName: 'students', icon: '👥', label: '学员管理' }],
  },
  {
    title: '系统管理',
    icon: '🛠️',
    items: [
      { routeName: 'users', icon: '🔑', label: '用户管理' },
      { routeName: 'roles', icon: '🛡️', label: '角色管理' },
      { routeName: 'logs', icon: '🧾', label: '操作日志' },
      { routeName: 'settings', icon: '⚙️', label: '系统设置' },
    ],
  },
]

// ---- 侧栏折叠（原型 sidebar-collapse）----
const collapsed = ref(false)

/** 菜单可见性（04 §1.6 / 需求 §6：无权限的菜单不展示） */
function canSee(routeName: string): boolean {
  const r = router.getRoutes().find((x) => x.name === routeName)
  const perm = r?.meta?.perm as string | undefined
  if (r?.meta?.superOnly) return !!auth.admin?.isSuper
  if (perm) return auth.hasPermission(perm)
  return true
}

const visibleMenus = computed(() =>
  menuGroups
    .map((g) => ({ ...g, items: g.items.filter((it) => canSee(it.routeName)) }))
    .filter((g) => g.items.length > 0),
)

// ---- 菜单分组折叠（点击分组标题展开/收起该组菜单项）----
const collapsedGroups = ref<Record<string, boolean>>({})

function toggleGroup(title: string) {
  collapsedGroups.value[title] = !collapsedGroups.value[title]
}

// ---- 用户下拉（点击外部关闭）----
const userMenuOpen = ref(false)
const userDropdownEl = ref<HTMLElement | null>(null)

function onDocumentClick(e: MouseEvent) {
  if (userMenuOpen.value && !userDropdownEl.value?.contains(e.target as Node)) {
    userMenuOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  settings.load() // 平台名称/Logo 驱动侧栏品牌区与标题
})
onUnmounted(() => document.removeEventListener('click', onDocumentClick))

async function handleLogout() {
  // 二次确认（原型 UI.confirm，需求 §6 通用交互约定）
  try {
    await ElMessageBox.confirm('确定要退出管理后台吗？', '退出登录', {
      type: 'warning',
      confirmButtonText: '退出',
      cancelButtonText: '取消',
    })
  } catch {
    return // 用户取消
  }
  try {
    await logoutApi(auth.refreshToken) // refresh 立即失效（04 §4.1）
  } catch {
    // 服务端登出失败也继续清理本地登录态，避免卡死在已失效会话
  }
  auth.clear()
  ElMessage.success('已退出登录')
  router.push({ name: 'login' })
}

/** 返回前台（学员端）；部署地址经 VITE_PORTAL_URL 配置 */
const portalUrl = import.meta.env.VITE_PORTAL_URL || 'http://localhost:5173'

/** 顶栏展示名（昵称优先，缺省回落账号名） */
const displayName = auth.admin?.nickname || auth.admin?.username || '管理员'

/** 用户头像：个人头像 > 平台默认头像（系统设置）> 首字兜底 */
const avatarUrl = computed(() => auth.admin?.avatarUrl || settings.defaultAvatarUrl || '')
</script>

<template>
  <div class="admin-layout">
    <!-- 侧边栏 -->
    <aside class="admin-sidebar" :class="{ collapsed }">
      <router-link class="sidebar-logo" :to="{ name: firstAccessibleRouteName() }">
        <img v-if="settings.logoUrl" class="logo-mark logo-img" :src="settings.logoUrl" alt="" />
        <span v-else class="logo-mark">云</span>
        <span>{{ settings.platformName }}</span>
      </router-link>
      <div
        v-for="group in visibleMenus"
        :key="group.title"
        class="menu-group"
        :class="{ collapsed: collapsedGroups[group.title] }"
      >
        <div class="menu-group-title" @click="toggleGroup(group.title)">
          <span class="group-icon">{{ group.icon }}</span>
          <span class="group-text">{{ group.title }}</span>
          <span class="group-arrow">▾</span>
        </div>
        <div class="menu-items">
          <router-link
            v-for="item in group.items"
            :key="item.routeName"
            class="menu-item"
            :class="{ active: route.name === item.routeName }"
            :to="{ name: item.routeName }"
            :title="item.label"
          >
            <span class="mi-icon">{{ item.icon }}</span><span>{{ item.label }}</span>
          </router-link>
        </div>
      </div>
    </aside>

    <!-- 主区 -->
    <div class="admin-main">
      <header class="admin-topbar">
        <button class="collapse-btn" title="折叠/展开侧栏" @click="collapsed = !collapsed">☰</button>
        <img v-if="settings.logoUrl" class="topbar-logo" :src="settings.logoUrl" alt="" />
        <span class="page-title">{{ route.meta?.title || '管理后台' }}</span>
        <div class="topbar-right">
          <!-- 通知铃（通知数据功能开发阶段接入，含未读角标） -->
          <button class="bell-btn" title="通知"><el-icon><Bell /></el-icon></button>

          <!-- 用户下拉 -->
          <div ref="userDropdownEl" class="dropdown" :class="{ open: userMenuOpen }">
            <button class="admin-user-trigger" @click="userMenuOpen = !userMenuOpen">
              <img v-if="avatarUrl" class="avatar sm avatar-img" :src="avatarUrl" alt="" />
              <span v-else class="avatar sm">{{ displayName.slice(0, 1) }}</span>
              {{ displayName }}⌄
            </button>
            <div class="dropdown-menu">
              <a class="dropdown-item" :href="portalUrl" target="_blank"><el-icon><Link /></el-icon>返回前台</a>
              <div class="dropdown-divider"></div>
              <button class="dropdown-item danger" @click="handleLogout"><el-icon><SwitchButton /></el-icon>退出登录</button>
            </div>
          </div>
        </div>
      </header>
      <main class="admin-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style src="../styles/admin.css"></style>
