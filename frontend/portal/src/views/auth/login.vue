<script setup lang="ts">
/**
 * 登录页（prototype/portal/login.html，04 §3.1）。
 * 账号密码 / 手机验证码双 Tab；记住我（refresh 30d/7d）；锁定提示（423 AUTH_LOCKED）；
 * 第三方登录入口占位（02 D18）；登录成功回跳 redirect（仅站内路径）。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchSmsCode, loginByPassword, loginBySms } from '@/api/auth'
import type { ApiError } from '@shared/types/api'
import { useAuthStore } from '@/stores/auth'
import { useSiteStore } from '@/stores/site'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const site = useSiteStore()

const tab = ref<'pwd' | 'sms'>('pwd')
const rememberMe = ref(true)
const loading = ref(false)
const lockAlert = ref('')

// 账号密码表单
const account = ref('')
const password = ref('')
const accountErr = ref('')
const passwordErr = ref('')

// 验证码表单
const smsPhone = ref('')
const smsCode = ref('')
const smsPhoneErr = ref('')
const smsCodeErr = ref('')
const countdown = ref(0)
let countdownTimer: number | undefined

onBeforeUnmount(() => window.clearInterval(countdownTimer))

onMounted(() => {
  // 已登录直接回跳（登录页仅游客可见）
  if (auth.isLoggedIn) goAfterLogin()
})

function goAfterLogin() {
  const redirect = String(route.query.redirect ?? '')
  // 仅接受站内路径，防开放跳转
  if (redirect.startsWith('/') && !redirect.startsWith('//')) {
    router.replace(redirect)
  } else {
    router.replace({ name: 'home' })
  }
}

function setErr(input: 'account' | 'smsPhone', msg: string) {
  if (input === 'account') accountErr.value = msg
  else smsPhoneErr.value = msg
}

function isPhone(v: string) {
  return /^1\d{10}$/.test(v)
}

function startCountdown() {
  countdown.value = 60
  countdownTimer = window.setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) window.clearInterval(countdownTimer)
  }, 1000)
}

function onAuthError(e: unknown) {
  const err = e as ApiError
  if (err?.code === 'AUTH_LOCKED') {
    lockAlert.value = err.message || '账号已锁定，请稍后重试'
    ElMessage.error(lockAlert.value)
    return
  }
  if (err?.code === 'AUTH_ACCOUNT_DISABLED') {
    ElMessage.error(err.message || '账号已被禁用')
    return
  }
  ElMessage.error(err?.message || '登录失败')
}

async function submitPassword() {
  lockAlert.value = ''
  accountErr.value = ''
  passwordErr.value = ''
  if (!account.value.trim()) {
    accountErr.value = '请输入手机号或邮箱'
    return
  }
  if (!password.value) {
    passwordErr.value = '请输入密码'
    return
  }
  loading.value = true
  try {
    const res = await loginByPassword({
      account: account.value.trim(),
      password: password.value,
      rememberMe: rememberMe.value,
    })
    auth.applyAuth(res, rememberMe.value)
    ElMessage.success('登录成功')
    goAfterLogin()
  } catch (e) {
    const err = e as ApiError
    if (err?.code === 'AUTH_INVALID_CREDENTIALS') {
      passwordErr.value = '账号或密码错误'
    }
    onAuthError(e)
  } finally {
    loading.value = false
  }
}

async function sendSms() {
  smsPhoneErr.value = ''
  if (!smsPhone.value.trim()) {
    smsPhoneErr.value = '请输入手机号'
    return
  }
  if (!isPhone(smsPhone.value.trim())) {
    smsPhoneErr.value = '请输入正确的 11 位手机号'
    return
  }
  try {
    await fetchSmsCode('login', smsPhone.value.trim())
    ElMessage.success('验证码已发送')
    startCountdown()
  } catch (e) {
    onAuthError(e)
  }
}

async function submitSms() {
  lockAlert.value = ''
  smsPhoneErr.value = ''
  smsCodeErr.value = ''
  const phone = smsPhone.value.trim()
  if (!phone) {
    smsPhoneErr.value = '请输入手机号'
    return
  }
  if (!isPhone(phone)) {
    smsPhoneErr.value = '请输入正确的 11 位手机号'
    return
  }
  if (!/^\d{6}$/.test(smsCode.value.trim())) {
    smsCodeErr.value = '请输入 6 位验证码'
    return
  }
  loading.value = true
  try {
    const res = await loginBySms({
      phone,
      code: smsCode.value.trim(),
      rememberMe: rememberMe.value,
    })
    auth.applyAuth(res, rememberMe.value)
    ElMessage.success('登录成功')
    goAfterLogin()
  } catch (e) {
    onAuthError(e)
  } finally {
    loading.value = false
  }
}

function thirdParty(name: string) {
  ElMessage.info(`${name}登录暂未接入，敬请期待`)
}
</script>

<template>
  <div class="auth-page">
    <!-- 左侧引导区 -->
    <aside class="auth-aside">
      <div class="aside-logo">
        <img v-if="site.logoUrl" :src="site.logoUrl" class="aside-logo-img" alt="logo" />
        <span v-else class="aside-logo-mark">云</span>
        {{ site.platformName }}
      </div>
      <h2>AI 赋能的智能面试训练平台</h2>
      <p>海量题库 × AI 模拟面试 × 学习路线，助你高效备战技术面试。</p>
      <div class="steps">
        <div class="step">
          <div class="step-dot">1</div>
          <div>
            <div class="step-name">选择技术方向</div>
            <div class="step-desc">8 大 AI 技术方向任你选</div>
          </div>
        </div>
        <div class="step">
          <div class="step-dot">2</div>
          <div>
            <div class="step-name">开始刷题练习</div>
            <div class="step-desc">海量题库随时随地练习</div>
          </div>
        </div>
        <div class="step">
          <div class="step-dot">3</div>
          <div>
            <div class="step-name">AI 面试检验</div>
            <div class="step-desc">模拟面试输出能力报告</div>
          </div>
        </div>
      </div>
    </aside>

    <!-- 右侧登录区 -->
    <main class="auth-main">
      <div class="auth-card">
        <h1 class="auth-title">欢迎回来</h1>
        <p class="auth-sub">登录{{ site.platformName }}，继续你的学习之旅</p>

        <div v-if="lockAlert" class="alert alert-error">{{ lockAlert }}</div>

        <div class="auth-tabs">
          <button class="tab" :class="{ active: tab === 'pwd' }" type="button" @click="tab = 'pwd'">
            账号密码登录
          </button>
          <button class="tab" :class="{ active: tab === 'sms' }" type="button" @click="tab = 'sms'">
            手机验证码登录
          </button>
        </div>

        <!-- 账号密码登录 -->
        <form v-if="tab === 'pwd'" novalidate @submit.prevent="submitPassword">
          <div class="field">
            <label class="field-label" for="acc-input">手机号 / 邮箱</label>
            <input
              id="acc-input"
              v-model="account"
              class="input"
              :class="{ error: accountErr }"
              placeholder="请输入手机号或邮箱"
              autocomplete="username"
            />
            <div class="field-error">{{ accountErr }}</div>
          </div>
          <div class="field">
            <label class="field-label" for="pwd-input">密码</label>
            <input
              id="pwd-input"
              v-model="password"
              class="input"
              :class="{ error: passwordErr }"
              type="password"
              placeholder="请输入密码"
              autocomplete="current-password"
            />
            <div class="field-error">{{ passwordErr }}</div>
          </div>
          <div class="flex-between mb-16">
            <label class="checkbox-row"><input v-model="rememberMe" type="checkbox" /> 记住我</label>
            <router-link :to="{ name: 'forgotPassword' }">忘记密码？</router-link>
          </div>
          <button class="btn btn-primary btn-block btn-lg" type="submit" :disabled="loading">
            {{ loading ? '登录中…' : '登录' }}
          </button>
        </form>

        <!-- 手机验证码登录 -->
        <form v-else novalidate @submit.prevent="submitSms">
          <div class="field">
            <label class="field-label" for="sms-phone">手机号</label>
            <input
              id="sms-phone"
              v-model="smsPhone"
              class="input"
              :class="{ error: smsPhoneErr }"
              placeholder="请输入手机号"
              maxlength="11"
              autocomplete="username"
            />
            <div class="field-error">{{ smsPhoneErr }}</div>
          </div>
          <div class="field">
            <label class="field-label" for="sms-code">验证码</label>
            <div class="code-row">
              <input
                id="sms-code"
                v-model="smsCode"
                class="input"
                :class="{ error: smsCodeErr }"
                placeholder="请输入验证码"
                maxlength="6"
              />
              <button class="btn" type="button" :disabled="countdown > 0" @click="sendSms">
                {{ countdown > 0 ? `${countdown}s 后重发` : '获取验证码' }}
              </button>
            </div>
            <div class="field-error">{{ smsCodeErr }}</div>
          </div>
          <button class="btn btn-primary btn-block btn-lg" type="submit" :disabled="loading">
            {{ loading ? '登录中…' : '登录' }}
          </button>
        </form>

        <div class="third-divider">其他登录方式</div>
        <div class="third-login">
          <button class="third-btn" type="button" title="微信登录" @click="thirdParty('微信')">💬</button>
          <button class="third-btn" type="button" title="QQ登录" @click="thirdParty('QQ')">🐧</button>
          <button class="third-btn" type="button" title="GitHub登录" @click="thirdParty('GitHub')">🐙</button>
        </div>

        <div class="auth-foot">还没有账号？<router-link :to="{ name: 'register' }">立即注册</router-link></div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.aside-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 28px;
  font-size: 18px;
  font-weight: 700;
}
.aside-logo-mark {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
}
.aside-logo-img {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  object-fit: cover;
}
.flex-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.mb-16 {
  margin-bottom: 16px;
}
</style>
