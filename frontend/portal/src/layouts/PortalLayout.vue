<script setup lang="ts">
/**
 * 学员端主布局（对齐 prototype/portal 公共框架 portal.js + portal.css）：
 * 顶栏（Logo / 4 项主导航 / 用户下拉或登录注册）+ 内容区 + 页脚。
 * 导航激活按原型分组：刷题/错题本归「题库」，面试配置/进行/报告/记录归「AI面试」；
 * 退出登录二次确认；页脚占位链接提示「本期不开发」。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { useAuthStore } from '@/stores/auth'
import { useSiteStore } from '@/stores/site'

const auth = useAuthStore()
const site = useSiteStore()
const route = useRoute()
const router = useRouter()

/** 管理后台入口（部署期可经 VITE_ADMIN_URL 覆盖） */
const ADMIN_ENTRY_URL =
  (import.meta.env.VITE_ADMIN_URL as string | undefined) ?? 'http://localhost:5174'

const NAV_ITEMS = [
  { key: 'home', label: '首页', to: { name: 'home' } },
  { key: 'routes', label: '学习路线', to: { name: 'routes' } },
  { key: 'questions', label: '题库', to: { name: 'questions' } },
  { key: 'interview', label: 'AI面试', to: { name: 'interviewConfig' } },
] as const

/** 路由名 → 导航分组（原型 portal.js NAV_GROUP 口径） */
const NAV_GROUP: Record<string, string> = {
  home: 'home',
  routes: 'routes',
  questions: 'questions',
  practice: 'questions',
  wrongbook: 'questions',
  interviewConfig: 'interview',
  interviewSession: 'interview',
  interviewReport: 'interview',
  interviewRecords: 'interview',
  profile: '',
}

function navActive(key: string): boolean {
  return NAV_GROUP[String(route.name)] === key
}

// 用户下拉：点击外部关闭
const dropdownOpen = ref(false)
function onDocClick() {
  dropdownOpen.value = false
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))

async function handleLogout() {
  dropdownOpen.value = false
  try {
    await ElMessageBox.confirm('确定要退出当前账号吗？', '退出登录', {
      type: 'warning',
      confirmButtonText: '退出',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  auth.clear()
  ElMessage.success('已退出登录')
  router.push({ name: 'home' })
}

function placeholderLink() {
  ElMessage.info('该页面为占位链接，本期不开发')
}
</script>

<template>
  <div class="portal-layout">
    <!-- ============ 顶栏 ============ -->
    <header class="site-header">
      <div class="container header-inner">
        <router-link :to="{ name: 'home' }" class="logo">
          <img v-if="site.logoUrl" :src="site.logoUrl" class="logo-mark logo-img" alt="logo" />
          <span v-else class="logo-mark">云</span>
          {{ site.platformName }}
        </router-link>
        <nav class="main-nav">
          <router-link
            v-for="item in NAV_ITEMS"
            :key="item.key"
            :to="item.to"
            :class="{ active: navActive(item.key) }"
          >
            {{ item.label }}
          </router-link>
        </nav>
        <div class="header-right">
          <template v-if="auth.isLoggedIn">
            <div class="dropdown" :class="{ open: dropdownOpen }" @click.stop>
              <button class="user-trigger" type="button" @click="dropdownOpen = !dropdownOpen">
                <img v-if="auth.student?.avatarUrl" :src="auth.student.avatarUrl" class="avatar sm" alt="" />
                <img v-else-if="site.defaultAvatarUrl" :src="site.defaultAvatarUrl" class="avatar sm" alt="" />
                <span v-else class="avatar sm">{{ (auth.student?.nickname ?? '学').slice(0, 1) }}</span>
                <span class="user-name">{{ auth.student?.nickname ?? '个人中心' }}</span>
                <span class="caret">⌄</span>
              </button>
              <div class="dropdown-menu">
                <template v-if="auth.student?.isAdmin">
                  <a class="dropdown-item" :href="ADMIN_ENTRY_URL" target="_blank" rel="noopener">🖥️ 管理后台</a>
                  <div class="dropdown-divider" />
                </template>
                <router-link class="dropdown-item" :to="{ name: 'profile' }" @click="dropdownOpen = false">
                  👤 个人中心
                </router-link>
                <router-link class="dropdown-item" :to="{ name: 'wrongbook' }" @click="dropdownOpen = false">
                  📕 我的错题
                </router-link>
                <router-link class="dropdown-item" :to="{ name: 'interviewRecords' }" @click="dropdownOpen = false">
                  🎙️ 面试记录
                </router-link>
                <div class="dropdown-divider" />
                <button class="dropdown-item danger" type="button" @click="handleLogout">🚪 退出登录</button>
              </div>
            </div>
          </template>
          <template v-else>
            <router-link class="btn btn-ghost btn-sm" :to="{ name: 'login' }">登录</router-link>
            <router-link class="btn btn-primary btn-sm" :to="{ name: 'register' }">免费注册</router-link>
          </template>
        </div>
      </div>
    </header>

    <!-- ============ 内容区 ============ -->
    <main class="portal-main">
      <router-view />
    </main>

    <!-- ============ 页脚 ============ -->
    <footer class="site-footer">
      <div class="container footer-grid">
        <div class="footer-brand">
          <div class="logo">
            <img v-if="site.logoUrl" :src="site.logoUrl" class="logo-mark logo-img" alt="logo" />
            <span v-else class="logo-mark">云</span>
            {{ site.platformName }}
          </div>
          <p>{{ site.brandDesc }}</p>
        </div>
        <div>
          <h4>产品</h4>
          <ul>
            <li><router-link :to="{ name: 'routes' }">学习路线</router-link></li>
            <li><router-link :to="{ name: 'questions' }">题库</router-link></li>
            <li><router-link :to="{ name: 'interviewConfig' }">AI面试</router-link></li>
          </ul>
        </div>
        <div>
          <h4>支持</h4>
          <ul>
            <li><a href="javascript:void(0)" @click="placeholderLink">帮助中心</a></li>
            <li><a href="javascript:void(0)" @click="placeholderLink">意见反馈</a></li>
            <li><a href="javascript:void(0)" @click="placeholderLink">联系我们</a></li>
          </ul>
        </div>
        <div>
          <h4>关于</h4>
          <ul>
            <li><a href="javascript:void(0)" @click="placeholderLink">关于我们</a></li>
            <li><a href="javascript:void(0)" @click="placeholderLink">用户协议</a></li>
            <li><a href="javascript:void(0)" @click="placeholderLink">隐私政策</a></li>
          </ul>
        </div>
      </div>
      <div class="container footer-bottom">
        <span>© 2026 云枢智学</span>
        <a class="footer-admin-entry" :href="ADMIN_ENTRY_URL" target="_blank" rel="noopener">🖥️ 管理后台</a>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* ---------- 顶部导航（对齐 prototype portal.css） ---------- */
.site-header {
  position: sticky;
  top: 0;
  z-index: 800;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--line);
}
.header-inner {
  display: flex;
  align-items: center;
  height: var(--header-h);
  gap: 32px;
}
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;
  color: var(--ink);
}
.logo:hover {
  color: var(--ink);
}
.logo-mark {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: var(--brand-grad);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  font-weight: 700;
  flex-shrink: 0;
}
.logo-img {
  object-fit: cover;
}
.main-nav {
  display: flex;
  gap: 4px;
  flex: 1;
}
.main-nav a {
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--ink-2);
  font-weight: 500;
}
.main-nav a:hover {
  background: var(--brand-light);
  color: var(--brand);
}
.main-nav a.active {
  background: var(--brand-light);
  color: var(--brand);
  font-weight: 600;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.user-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 999px;
  cursor: pointer;
  border: none;
  background: none;
}
.user-trigger:hover {
  background: var(--brand-light);
}
.user-trigger .user-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-2);
}
.user-trigger .caret {
  font-size: 12px;
  color: var(--ink-3);
}

/* ---------- 页脚 ---------- */
.site-footer {
  background: #101828;
  color: #98a2b3;
  margin-top: 64px;
}
.footer-grid {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr;
  gap: 32px;
  padding: 48px 24px 32px;
}
.footer-brand .logo {
  color: #fff;
  margin-bottom: 12px;
}
.footer-brand p {
  font-size: 13px;
  max-width: 280px;
}
.site-footer h4 {
  color: #e5e7eb;
  font-size: 14px;
  margin-bottom: 14px;
}
.site-footer ul {
  list-style: none;
  padding: 0;
  margin: 0;
}
.site-footer li {
  margin-bottom: 8px;
}
.site-footer a {
  color: #98a2b3;
  font-size: 13px;
}
.site-footer a:hover {
  color: #fff;
}
.footer-bottom {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding: 18px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
}
.footer-admin-entry {
  padding: 4px 12px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 6px;
}
.footer-admin-entry:hover {
  border-color: #fff;
}

.portal-main {
  min-height: calc(100vh - var(--header-h) - 200px);
}
</style>
