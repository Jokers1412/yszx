<script setup lang="ts">
/**
 * 注册页（prototype/portal/register.html，04 §3.1）。
 * 手机号 + 验证码 + 密码（强度条）+ 协议勾选（前端交互，服务端不存储）；
 * 注册成功即登录（口径 S3）→ 进入个人中心。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchSmsCode, register } from '@/api/auth'
import type { ApiError } from '@shared/types/api'
import { useAuthStore } from '@/stores/auth'
import { useSiteStore } from '@/stores/site'

const router = useRouter()
const auth = useAuthStore()
const site = useSiteStore()

const phone = ref('')
const code = ref('')
const pwd = ref('')
const pwd2 = ref('')
const agreed = ref(false)
const loading = ref(false)

const phoneErr = ref('')
const codeErr = ref('')
const pwdErr = ref('')
const pwd2Err = ref('')

const countdown = ref(0)
let countdownTimer: number | undefined
onBeforeUnmount(() => window.clearInterval(countdownTimer))

onMounted(() => {
  if (auth.isLoggedIn) router.replace({ name: 'profile' })
})

function isPhone(v: string) {
  return /^1\d{10}$/.test(v)
}

/** 密码强度（原型 ui.js strength 口径）：太短/弱/中/强 */
const strength = computed(() => {
  const p = pwd.value
  let score = 0
  if (p && p.length >= 6) score++
  if (/[a-z]/.test(p) && /[A-Z]/.test(p)) score++
  if (/\d/.test(p) && /[^a-zA-Z0-9]/.test(p)) score++
  const labels = ['太短', '弱', '中', '强']
  return { score, label: labels[score] }
})

function startCountdown() {
  countdown.value = 60
  countdownTimer = window.setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) window.clearInterval(countdownTimer)
  }, 1000)
}

async function sendCode() {
  phoneErr.value = ''
  if (!phone.value.trim()) {
    phoneErr.value = '请输入手机号'
    return
  }
  if (!isPhone(phone.value.trim())) {
    phoneErr.value = '请输入正确的 11 位手机号'
    return
  }
  try {
    await fetchSmsCode('register', phone.value.trim())
    ElMessage.success('验证码已发送')
    startCountdown()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '获取验证码失败')
  }
}

function agreement(name: string) {
  ElMessage.info(`${name}暂未接入，敬请期待`)
}

async function submit() {
  phoneErr.value = ''
  codeErr.value = ''
  pwdErr.value = ''
  pwd2Err.value = ''

  if (!phone.value.trim()) {
    phoneErr.value = '请输入手机号'
    return
  }
  if (!isPhone(phone.value.trim())) {
    phoneErr.value = '请输入正确的 11 位手机号'
    return
  }
  if (!/^\d{6}$/.test(code.value.trim())) {
    codeErr.value = '请输入 6 位验证码'
    return
  }
  if (!pwd.value) {
    pwdErr.value = '请设置密码'
    return
  }
  if (pwd.value.length < 6 || pwd.value.length > 20) {
    pwdErr.value = '密码长度需为 6-20 位'
    return
  }
  if (!pwd2.value) {
    pwd2Err.value = '请再次输入密码'
    return
  }
  if (pwd2.value !== pwd.value) {
    pwd2Err.value = '两次输入的密码不一致'
    return
  }
  if (!agreed.value) {
    ElMessage.warning('请先阅读并同意《用户协议》和《隐私政策》')
    return
  }

  loading.value = true
  try {
    const res = await register({
      phone: phone.value.trim(),
      code: code.value.trim(),
      password: pwd.value,
    })
    auth.applyAuth(res, true) // 注册即登录（S3）
    ElMessage.success(`注册成功，欢迎加入${site.platformName}`)
    router.replace({ name: 'profile' })
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <!-- 左侧三步引导（仅第 1 步激活） -->
    <aside class="auth-aside">
      <div class="aside-logo">
        <img v-if="site.logoUrl" :src="site.logoUrl" class="aside-logo-img" alt="logo" />
        <span v-else class="aside-logo-mark">云</span>
        {{ site.platformName }}
      </div>
      <h2>三步开启你的求职训练</h2>
      <p>注册后即可刷题练习、AI 模拟面试，一站式备战技术面试。</p>
      <div class="steps">
        <div class="step active">
          <div class="step-dot">1</div>
          <div>
            <div class="step-name">创建账号</div>
            <div class="step-desc">手机号验证，激活你的账号</div>
          </div>
        </div>
        <div class="step">
          <div class="step-dot">2</div>
          <div>
            <div class="step-name">完善信息</div>
            <div class="step-desc">完善个人资料，选择技术方向</div>
          </div>
        </div>
        <div class="step">
          <div class="step-dot">3</div>
          <div>
            <div class="step-name">开始训练</div>
            <div class="step-desc">刷题练习，AI 面试检验成果</div>
          </div>
        </div>
      </div>
    </aside>

    <!-- 右侧注册表单 -->
    <main class="auth-main">
      <div class="auth-card">
        <h1 class="auth-title">创建账号</h1>
        <p class="auth-sub">注册{{ site.platformName }}，开启智能面试训练之旅</p>

        <form novalidate @submit.prevent="submit">
          <div class="field">
            <label class="field-label" for="reg-phone">手机号</label>
            <input
              id="reg-phone"
              v-model="phone"
              class="input"
              :class="{ error: phoneErr }"
              placeholder="请输入 11 位手机号"
              maxlength="11"
            />
            <div class="field-error">{{ phoneErr }}</div>
          </div>
          <div class="field">
            <label class="field-label" for="reg-code">验证码</label>
            <div class="code-row">
              <input
                id="reg-code"
                v-model="code"
                class="input"
                :class="{ error: codeErr }"
                placeholder="请输入 6 位验证码"
                maxlength="6"
              />
              <button class="btn" type="button" :disabled="countdown > 0" @click="sendCode">
                {{ countdown > 0 ? `${countdown}s 后重发` : '获取验证码' }}
              </button>
            </div>
            <div class="field-error">{{ codeErr }}</div>
          </div>
          <div class="field">
            <label class="field-label" for="reg-pwd">设置密码</label>
            <input
              id="reg-pwd"
              v-model="pwd"
              class="input"
              :class="{ error: pwdErr }"
              type="password"
              placeholder="建议 6-20 位，含大小写字母、数字与特殊字符"
              autocomplete="new-password"
            />
            <div class="strength-meter">
              <div v-for="i in 3" :key="i" class="seg" :class="pwd && i <= strength.score ? `on-${strength.score}` : ''" />
            </div>
            <div class="strength-text">
              {{ pwd ? `密码强度：${strength.label}` : '建议 6-20 位，含大小写字母、数字与特殊字符' }}
            </div>
            <div class="field-error">{{ pwdErr }}</div>
          </div>
          <div class="field">
            <label class="field-label" for="reg-pwd2">确认密码</label>
            <input
              id="reg-pwd2"
              v-model="pwd2"
              class="input"
              :class="{ error: pwd2Err }"
              type="password"
              placeholder="请再次输入密码"
              autocomplete="new-password"
            />
            <div class="field-error">{{ pwd2Err }}</div>
          </div>
          <div class="agree-row">
            <input id="reg-agree" v-model="agreed" type="checkbox" />
            <label for="reg-agree">
              我已阅读并同意<a href="javascript:void(0)" @click.prevent.stop="agreement('用户协议')">《用户协议》</a
              >和<a href="javascript:void(0)" @click.prevent.stop="agreement('隐私政策')">《隐私政策》</a>
            </label>
          </div>
          <button class="btn btn-primary btn-block btn-lg" type="submit" :disabled="loading">
            {{ loading ? '注册中…' : '注册' }}
          </button>
        </form>

        <div class="auth-foot">已有账号？<router-link :to="{ name: 'login' }">立即登录</router-link></div>
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
</style>
