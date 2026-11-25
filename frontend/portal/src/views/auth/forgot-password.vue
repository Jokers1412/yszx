<script setup lang="ts">
/**
 * 找回密码（prototype/portal/forgot-password.html，需求 3.2）。
 * 三步向导：验证手机（手机号+验证码）→ 重置密码（≥6 位+两次一致）→ 完成（立即登录）。
 * 提交走 POST /auth/password/reset（重置后该端全部登录态失效，S5）；验证码经 Mock 短信下发。
 */
import { onBeforeUnmount, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchSmsCode, resetPassword } from '@/api/auth'
import { showMockSmsCode } from '@/utils/mock-sms'
import { useSiteStore } from '@/stores/site'
import type { ApiError } from '@shared/types/api'

const router = useRouter()
const site = useSiteStore()

const step = ref(1)
const loading = ref(false)

// 步骤 1：验证手机
const phone = ref('')
const code = ref('')
const phoneErr = ref('')
const codeErr = ref('')
const countdown = ref(0)
let countdownTimer: number | undefined
onBeforeUnmount(() => window.clearInterval(countdownTimer))

function isPhone(v: string) {
  return /^1\d{10}$/.test(v)
}

async function sendCode() {
  const p = phone.value.trim()
  if (!isPhone(p)) {
    phoneErr.value = '请输入正确的 11 位手机号'
    return
  }
  phoneErr.value = ''
  try {
    const res = await fetchSmsCode('reset', p)
    ElMessage.success('验证码已发送')
    showMockSmsCode(res.mockCode) // 开发阶段：弹窗直显验证码
    countdown.value = 60
    countdownTimer = window.setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0) window.clearInterval(countdownTimer)
    }, 1000)
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '验证码发送失败')
  }
}

function nextFromVerify() {
  const p = phone.value.trim()
  const c = code.value.trim()
  let ok = true
  if (!p) {
    phoneErr.value = '请输入手机号'
    ok = false
  } else if (!isPhone(p)) {
    phoneErr.value = '请输入正确的 11 位手机号'
    ok = false
  } else {
    phoneErr.value = ''
  }
  if (!c) {
    codeErr.value = '请输入验证码'
    ok = false
  } else if (!/^\d{6}$/.test(c)) {
    codeErr.value = '请输入 6 位验证码'
    ok = false
  } else {
    codeErr.value = ''
  }
  if (ok) step.value = 2
}

// 步骤 2：重置密码
const form = reactive({ pwd: '', pwd2: '' })
const pwdErr = ref('')
const pwd2Err = ref('')

async function submitReset() {
  let ok = true
  if (!form.pwd) {
    pwdErr.value = '请输入新密码'
    ok = false
  } else if (form.pwd.length < 6 || form.pwd.length > 20) {
    pwdErr.value = '密码长度需为 6-20 位'
    ok = false
  } else {
    pwdErr.value = ''
  }
  if (!form.pwd2) {
    pwd2Err.value = '请再次输入新密码'
    ok = false
  } else if (form.pwd2 !== form.pwd) {
    pwd2Err.value = '两次输入的密码不一致'
    ok = false
  } else {
    pwd2Err.value = ''
  }
  if (!ok) return

  loading.value = true
  try {
    await resetPassword({
      phone: phone.value.trim(),
      code: code.value.trim(),
      newPassword: form.pwd,
    })
    step.value = 3
    ElMessage.success('密码重置成功')
  } catch (e) {
    const err = e as ApiError
    ElMessage.error(err?.message || '重置失败，请稍后重试')
    // 验证码问题 → 回到步骤 1 重新获取（手机号保留）
    if (err?.code?.startsWith('AUTH_SMS_CODE')) {
      code.value = ''
      step.value = 1
    }
  } finally {
    loading.value = false
  }
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

    <!-- 右侧三步向导 -->
    <main class="auth-main">
      <div class="auth-card">
        <h1 class="auth-title">找回密码</h1>
        <p class="auth-sub">通过手机验证码重置你的登录密码</p>

        <!-- 横向步骤条 -->
        <div class="steps steps-h">
          <div class="step" :class="{ active: step === 1, done: step > 1 }">
            <div class="step-dot">1</div>
            <div><div class="step-name">验证手机</div></div>
          </div>
          <div class="step" :class="{ active: step === 2, done: step > 2 }">
            <div class="step-dot">2</div>
            <div><div class="step-name">重置密码</div></div>
          </div>
          <div class="step" :class="{ active: step === 3 }">
            <div class="step-dot">3</div>
            <div><div class="step-name">完成</div></div>
          </div>
        </div>

        <!-- 步骤 1：验证手机 -->
        <form v-if="step === 1" class="fp-panel" novalidate @submit.prevent="nextFromVerify">
          <div class="field">
            <label class="field-label" for="fp-phone">手机号</label>
            <input
              id="fp-phone"
              v-model="phone"
              class="input"
              :class="{ error: phoneErr }"
              placeholder="请输入 11 位手机号"
              maxlength="11"
            />
            <div class="field-error">{{ phoneErr }}</div>
          </div>
          <div class="field">
            <label class="field-label" for="fp-code">验证码</label>
            <div class="code-row">
              <input
                id="fp-code"
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
          <div class="fp-actions">
            <button class="btn btn-primary btn-lg" type="submit">下一步</button>
            <a class="btn btn-ghost" @click.prevent="router.push({ name: 'login' })">返回登录</a>
          </div>
        </form>

        <!-- 步骤 2：重置密码 -->
        <form v-else-if="step === 2" class="fp-panel" novalidate @submit.prevent="submitReset">
          <div class="field">
            <label class="field-label" for="fp-pwd">新密码</label>
            <input
              id="fp-pwd"
              v-model="form.pwd"
              class="input"
              :class="{ error: pwdErr }"
              type="password"
              placeholder="请输入新密码（至少 6 位）"
              autocomplete="new-password"
            />
            <div class="field-error">{{ pwdErr }}</div>
          </div>
          <div class="field">
            <label class="field-label" for="fp-pwd2">确认密码</label>
            <input
              id="fp-pwd2"
              v-model="form.pwd2"
              class="input"
              :class="{ error: pwd2Err }"
              type="password"
              placeholder="请再次输入新密码"
              autocomplete="new-password"
            />
            <div class="field-error">{{ pwd2Err }}</div>
          </div>
          <div class="fp-actions">
            <button class="btn btn-primary btn-lg" type="submit" :disabled="loading">
              {{ loading ? '提交中…' : '下一步' }}
            </button>
          </div>
        </form>

        <!-- 步骤 3：完成 -->
        <div v-else class="fp-panel fp-done">
          <div class="ok-icon">✓</div>
          <h3>重置成功</h3>
          <p class="muted">你的密码已重置，请使用新密码登录</p>
          <div class="fp-actions">
            <button class="btn btn-primary btn-lg" type="button" @click="router.push({ name: 'login' })">
              立即登录
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
/* 横向步骤条（原型 steps-h） */
.steps-h {
  flex-direction: row;
  gap: 0;
  margin: 20px 0 24px;
}
.steps-h .step {
  flex: 1;
  padding-bottom: 0;
  align-items: center;
  gap: 8px;
}
.steps-h .step::before {
  display: none;
}
.steps-h .step .step-name {
  font-size: 13px;
}

/* 分步面板淡入 */
@keyframes fp-fade {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
.fp-panel {
  animation: fp-fade 0.25s ease;
}

.fp-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 8px;
}
.fp-done {
  text-align: center;
  padding: 18px 0 8px;
}
.fp-done .ok-icon {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--success-bg);
  color: var(--success);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  margin: 0 auto 16px;
  border: 2px solid var(--success);
}
.fp-done h3 {
  font-size: 20px;
  margin-bottom: 6px;
}
</style>
