<script setup lang="ts">
/**
 * 学员端主布局：顶部导航 + 内容区（对齐 prototype/portal 首页框架）。
 * 导航项与页面骨架先就位，视觉细节功能开发阶段按原型还原。
 */
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <div class="portal-layout">
    <header class="portal-header">
      <div class="container header-inner">
        <router-link to="/" class="logo">云枢智学</router-link>
        <nav class="nav">
          <router-link :to="{ name: 'home' }">首页</router-link>
          <router-link :to="{ name: 'questions' }">题库中心</router-link>
          <router-link :to="{ name: 'wrongbook' }">错题本</router-link>
          <router-link :to="{ name: 'routes' }">学习路线</router-link>
          <router-link :to="{ name: 'interviewConfig' }">AI 面试</router-link>
        </nav>
        <div class="auth-area">
          <template v-if="auth.isLoggedIn">
            <router-link :to="{ name: 'profile' }">{{ auth.student?.nickname ?? '个人中心' }}</router-link>
          </template>
          <template v-else>
            <router-link :to="{ name: 'login' }">登录</router-link>
            <router-link :to="{ name: 'register' }" class="btn-register">注册</router-link>
          </template>
        </div>
      </div>
    </header>
    <main class="portal-main">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.portal-header {
  height: var(--header-h);
  background: var(--surface);
  border-bottom: 1px solid var(--line);
  position: sticky;
  top: 0;
  z-index: 10;
}
.header-inner {
  height: 100%;
  display: flex;
  align-items: center;
  gap: 32px;
}
.logo {
  font-size: 20px;
  font-weight: 700;
  color: var(--brand);
}
.nav {
  display: flex;
  gap: 24px;
  flex: 1;
}
.nav a {
  color: var(--ink-2);
}
.nav a.router-link-active {
  color: var(--brand);
  font-weight: 600;
}
.auth-area {
  display: flex;
  align-items: center;
  gap: 16px;
}
.btn-register {
  padding: 6px 16px;
  border-radius: var(--radius-sm);
  background: var(--brand);
  color: #fff;
}
.portal-main {
  min-height: calc(100vh - var(--header-h));
}
</style>
