<script setup lang="ts">
/**
 * 后台登录页（再设计）：全页统一深色渐变背景，
 * 品牌信息与登录卡片横向铺开、同背景悬浮（无任何分割线），
 * 利用整屏宽度避免拥挤；配色沿用管理端品牌体系（#101828 / brand-grad）。
 */
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import type { ApiError } from '@shared/types/api'
import { fetchProfile, login as loginApi } from '@/api/auth'
import { firstAccessibleRouteName } from '@/router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const alertMsg = ref('')

const form = reactive({
  username: '',
  password: '',
  rememberMe: true,
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入管理员账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入登录密码', trigger: 'blur' }],
}

async function handleSubmit() {
  if (loading.value) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  alertMsg.value = ''
  try {
    const res = await loginApi({
      username: form.username.trim(),
      password: form.password,
      rememberMe: form.rememberMe,
    })
    auth.setTokens(res.accessToken, res.refreshToken, form.rememberMe)
    // 权限码经 /auth/profile 获取（登录响应不含 permissionCodes，04 §4.1）
    const profile = await fetchProfile()
    auth.setAdmin(profile.user, profile.permissionCodes)

    ElMessage.success('登录成功')
    // 落地页：优先回跳地址，否则跳首个有权限页（如审核人员无 dashboard:view 落到学科管理）
    const redirect = route.query.redirect as string | undefined
    router.push(redirect || { name: firstAccessibleRouteName() })
  } catch (e) {
    // 服务端文案已面向用户（如 423「账号已锁定，请 X 分钟后重试」）
    alertMsg.value = (e as ApiError)?.message || '登录失败，请稍后再试'
  } finally {
    loading.value = false
  }
}

function handleForgot() {
  // 需求 4.5.1：管理员密码由超管重置，无自助找回流程
  ElMessage.warning('请联系超级管理员重置密码')
}

const portalUrl = import.meta.env.VITE_PORTAL_URL || 'http://localhost:5173'
</script>

<template>
  <div class="login-page">
    <!-- 背景柔光（营造纵深） -->
    <div class="glow glow-1" />
    <div class="glow glow-2" />
    <div class="glow glow-3" />

    <div class="login-layout">
      <!-- 左：品牌信息（直接浮于渐变背景，无面板无分割线） -->
      <section class="brand-side">
        <div class="login-logo">云</div>
        <h1 class="brand-title">云枢智学 · 管理后台</h1>
        <p class="brand-sub">AI 赋能的智能面试训练平台 · 管理端</p>
        <p class="brand-desc">内容运营、学员管理、数据洞察，<br />一站式管理控制台。</p>
        <div class="brand-chips">
          <span class="chip">📊 数据看板</span>
          <span class="chip">🗂️ 内容管理</span>
          <span class="chip">👥 学员管理</span>
          <span class="chip">⚙️ 系统管理</span>
        </div>
      </section>

      <!-- 右：登录卡片（白色悬浮卡片） -->
      <section class="login-card">
        <h2 class="card-title">欢迎回来</h2>
        <p class="card-sub">请使用管理员账号登录</p>

        <el-alert
          v-if="alertMsg"
          class="login-alert"
          :title="alertMsg"
          type="error"
          :closable="false"
          show-icon
        />
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          @submit.prevent="handleSubmit"
        >
          <el-form-item label="管理员账号" prop="username">
            <el-input
              v-model="form.username"
              placeholder="请输入管理员账号"
              size="large"
              @input="alertMsg = ''"
            />
          </el-form-item>
          <el-form-item label="登录密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入登录密码"
              size="large"
              show-password
              @input="alertMsg = ''"
              @keyup.enter="handleSubmit"
            />
          </el-form-item>
          <div class="login-options">
            <el-checkbox v-model="form.rememberMe">记住登录状态</el-checkbox>
            <el-button link type="primary" @click="handleForgot"><el-icon class="btn-ic"><QuestionFilled /></el-icon>忘记密码？</el-button>
          </div>
          <el-button
            type="primary"
            size="large"
            class="login-btn"
            :loading="loading"
            @click="handleSubmit"
          >
            <el-icon class="btn-ic"><Unlock /></el-icon>登录
          </el-button>
        </el-form>

        <div class="login-foot">
          <a :href="portalUrl">← 返回学员前台</a>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
/* ---------- 全页统一渐变背景 ---------- */
.login-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 56px;
  overflow: hidden;
  background: linear-gradient(150deg, #0e1626 0%, #17233f 52%, #223a66 100%);
}

/* 背景柔光 */
.glow {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}
.glow-1 {
  width: 720px; height: 720px; top: -260px; left: -180px;
  background: radial-gradient(circle, rgba(42, 120, 214, .32) 0%, transparent 68%);
}
.glow-2 {
  width: 640px; height: 640px; bottom: -240px; right: -160px;
  background: radial-gradient(circle, rgba(98, 80, 214, .28) 0%, transparent 68%);
}
.glow-3 {
  width: 520px; height: 520px; top: 24%; left: 42%;
  background: radial-gradient(circle, rgba(32, 88, 180, .16) 0%, transparent 70%);
}

/* ---------- 横向铺开构图 ---------- */
.login-layout {
  position: relative;
  width: 100%;
  max-width: 1160px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 96px;
}

/* 左：品牌信息 */
.brand-side {
  flex: 1;
  max-width: 580px;
}
.login-logo {
  width: 64px;
  height: 64px;
  border-radius: 17px;
  background: var(--brand-grad);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 30px;
  font-weight: 700;
  margin-bottom: 28px;
  box-shadow: 0 14px 36px rgba(42, 120, 214, .45);
}
.brand-title {
  font-size: 38px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #fff;
  margin: 0 0 14px;
  line-height: 1.35;
}
.brand-sub {
  font-size: 15px;
  color: rgba(255, 255, 255, .72);
  margin: 0 0 22px;
  letter-spacing: 2px;
}
.brand-desc {
  font-size: 15px;
  color: rgba(255, 255, 255, .55);
  margin: 0 0 36px;
  line-height: 2;
}
.brand-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.brand-chips .chip {
  padding: 7px 16px;
  border-radius: 999px;
  font-size: 13px;
  color: rgba(255, 255, 255, .8);
  background: rgba(255, 255, 255, .08);
  border: 1px solid rgba(255, 255, 255, .14);
}

/* 右：登录卡片 */
.login-card {
  width: 420px;
  flex-shrink: 0;
  background: var(--surface);
  border-radius: var(--radius-lg);
  box-shadow: 0 24px 64px rgba(6, 12, 28, .5);
  padding: 36px 38px 26px;
}
.card-title {
  font-size: 20px;
  font-weight: 700;
  margin: 0 0 4px;
  text-align: center;
}
.card-sub {
  font-size: 13px;
  color: var(--ink-3);
  margin: 0 0 22px;
  text-align: center;
}
.login-alert {
  margin-bottom: 14px;
}
.login-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 2px 0 20px;
}

/* 登录按钮：品牌渐变，与 Logo 同语言 */
.login-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
  font-weight: 600;
  background: var(--brand-grad);
  border: none;
}
.login-btn:hover {
  opacity: .92;
}

.login-foot {
  padding: 18px 0 4px;
  text-align: center;
  font-size: 13px;
}
.login-foot a {
  color: var(--ink-3);
}
.login-foot a:hover {
  color: var(--brand);
}

/* ---------- 响应式：窄屏改为纵向居中 ---------- */
@media (max-width: 1024px) {
  .login-page {
    padding: 40px 24px;
  }
  .login-layout {
    flex-direction: column;
    gap: 36px;
    max-width: 440px;
  }
  .brand-side {
    max-width: 100%;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  .brand-title {
    font-size: 28px;
  }
  .brand-desc {
    display: none;
  }
  .brand-chips {
    justify-content: center;
  }
}
</style>
