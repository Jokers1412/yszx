<script setup lang="ts">
/**
 * 个人中心（prototype/portal/profile.html，需求 3.3 / 04 §3.1）。
 * 左：用户卡片（做题/面试/错题 + 连续学习/注册时间）；
 * 右：基本信息（头像上传/用户名/手机号脱敏只读/邮箱/性别）+ 学习数据。
 * 口径：手机号接口返回完整值、此处只读脱敏展示（S6）；
 * admin 身份（Q4）仅可改昵称/头像（S4），邮箱/性别禁用。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { fetchLearnStats } from '@/api/home'
import {
  fetchProfileStats,
  getProfile,
  updateProfile,
  uploadAvatar,
} from '@/api/auth'
import type { ProfileResult, ProfileStats } from '@/api/auth'
import type { ApiError } from '@shared/types/api'
import { useAuthStore } from '@/stores/auth'
import { animateNumber } from '@/utils/anim'

const router = useRouter()
const auth = useAuthStore()

const loading = ref(false)
const saving = ref(false)
const profile = ref<ProfileResult | null>(null)
const stats = ref<ProfileStats | null>(null)
const streak = ref(0)

// 表单（保存/还原以 saved 为基准）
const form = reactive({
  nickname: '',
  email: '',
  gender: 'secret' as 'male' | 'female' | 'secret',
  avatarUrl: '' as string,
})
const saved = reactive({ ...form })
const nameErr = ref('')
const emailErr = ref('')

const isAdmin = computed(() => profile.value?.isAdmin === true)
const maskedPhone = computed(() => {
  const p = profile.value?.phone ?? ''
  return p.length >= 11 ? `${p.slice(0, 3)}****${p.slice(7)}` : p
})

function fillForm(p: ProfileResult) {
  form.nickname = p.nickname
  form.email = p.email ?? ''
  form.gender = (p.gender ?? 'secret') as 'male' | 'female' | 'secret'
  form.avatarUrl = p.avatarUrl ?? ''
  Object.assign(saved, { ...form })
}

async function load() {
  loading.value = true
  try {
    const [p, s, ls] = await Promise.all([
      getProfile(),
      fetchProfileStats(),
      fetchLearnStats().catch(() => null), // streak 随学习统计取（admin 身份为 0）
    ])
    profile.value = p
    stats.value = s
    streak.value = ls?.streak ?? 0
    fillForm(p)
    auth.patchStudent({ nickname: p.nickname, avatarUrl: p.avatarUrl, phone: p.phone })
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ---------- 头像上传（选中即上传预览，保存后生效） ----------
const avatarInput = ref<HTMLInputElement | null>(null)

function pickAvatar() {
  avatarInput.value?.click()
}

async function onAvatarChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!/image\/(png|jpeg)/.test(file.type)) {
    ElMessage.error('头像仅支持 JPG、PNG 格式')
    return
  }
  if (file.size > 2 * 1024 * 1024) {
    ElMessage.error('头像大小不能超过 2MB')
    return
  }
  try {
    const { url } = await uploadAvatar(file)
    form.avatarUrl = url
    ElMessage.success('头像已更新，记得点击「保存修改」')
  } catch (err) {
    ElMessage.error((err as ApiError)?.message || '头像上传失败')
  }
}

// ---------- 保存 / 还原 ----------
async function handleSave() {
  nameErr.value = ''
  emailErr.value = ''
  if (!form.nickname.trim()) {
    nameErr.value = '用户名不能为空'
    return
  }
  if (form.email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
    emailErr.value = '邮箱格式不正确'
    return
  }
  saving.value = true
  try {
    const p = await updateProfile({
      nickname: form.nickname.trim(),
      email: form.email.trim() || null,
      gender: form.gender,
      avatarUrl: form.avatarUrl || null,
    })
    profile.value = p
    fillForm(p)
    auth.patchStudent({ nickname: p.nickname, avatarUrl: p.avatarUrl })
    ElMessage.success('保存成功')
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleReset() {
  try {
    await ElMessageBox.confirm('将表单恢复为上次保存的内容，确定吗？', '还原修改', {
      type: 'warning',
      confirmButtonText: '还原',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  Object.assign(form, { ...saved })
  nameErr.value = ''
  emailErr.value = ''
  ElMessage.info('已还原')
}

const statEls: (HTMLElement | null)[] = []
function setStatRef(i: number, el: unknown) {
  statEls[i] = (el as HTMLElement | null) ?? null
}
function animateStats() {
  const s = stats.value
  if (!s) return
  const values = [s.practiceCount, s.interviewCount, s.wrongCount, s.doneQuestions, s.accuracy]
  values.forEach((v, i) => {
    const el = statEls[i]
    // 单位由模板静态渲染（% 等），动画只写数字，避免重复后缀
    if (el) animateNumber(el, v, { duration: 900 })
  })
}
// 数据到位后驱动递增动画
watch(stats, () => animateStats(), { flush: 'post' })
</script>

<template>
  <div v-loading="loading" class="container profile-page">
    <h2 class="page-title">个人中心</h2>

    <div class="profile-grid">
      <!-- 左：用户卡片 -->
      <div class="card profile-user-card">
        <img
          v-if="form.avatarUrl"
          :src="form.avatarUrl"
          class="avatar lg avatar-img"
          alt="头像"
        />
        <span v-else class="avatar lg">{{ (profile?.nickname ?? '学').slice(0, 1) }}</span>
        <h3 class="user-name">{{ profile?.nickname ?? '—' }}</h3>
        <div>
          <span class="badge badge-blue">{{ isAdmin ? '管理员' : '学员' }}</span>
        </div>
        <div class="pu-stats">
          <div>
            <div class="num"><span :ref="(el) => setStatRef(0, el)">0</span></div>
            <div class="label">做题数</div>
          </div>
          <div>
            <div class="num"><span :ref="(el) => setStatRef(1, el)">0</span></div>
            <div class="label">面试数</div>
          </div>
          <div>
            <div class="num"><span :ref="(el) => setStatRef(2, el)">0</span></div>
            <div class="label">错题数</div>
          </div>
        </div>
        <div class="divider" />
        <div class="user-meta">
          <div class="meta-row"><span class="muted">连续学习</span><b>{{ streak }} 天</b></div>
          <div class="meta-row">
            <span class="muted">注册时间</span><b>{{ (profile?.createdAt ?? '—').slice(0, 10) }}</b>
          </div>
        </div>
      </div>

      <!-- 右：基本信息 + 学习数据 -->
      <div>
        <div class="card mb-16">
          <div class="card-header"><h3>基本信息</h3></div>
          <div class="card-body">
            <div class="field">
              <label class="field-label">头像</label>
              <div class="avatar-row">
                <div class="upload-box" title="支持 JPG、PNG，建议 200×200" @click="pickAvatar">
                  <img v-if="form.avatarUrl" :src="form.avatarUrl" class="upload-img" alt="头像" />
                  <div v-else class="upload-empty">📷</div>
                </div>
                <div class="avatar-actions">
                  <button class="btn btn-sm" type="button" @click="pickAvatar">上传头像</button>
                  <div class="field-hint">支持 JPG、PNG，建议尺寸 200×200</div>
                  <div class="field-hint">点击头像或按钮选择图片，保存后生效</div>
                </div>
              </div>
              <input ref="avatarInput" type="file" accept="image/png,image/jpeg" hidden @change="onAvatarChange" />
            </div>

            <div class="form-grid">
              <div class="field">
                <label class="field-label">用户名<span class="req">*</span></label>
                <input v-model="form.nickname" class="input" :class="{ error: nameErr }" maxlength="50" />
                <div class="field-error">{{ nameErr }}</div>
              </div>
              <div class="field">
                <label class="field-label">手机号</label>
                <input class="input" :value="maskedPhone" readonly />
                <div class="field-hint">手机号仅脱敏展示，不支持修改</div>
              </div>
              <div class="field">
                <label class="field-label">邮箱</label>
                <input
                  v-model="form.email"
                  class="input"
                  :class="{ error: emailErr }"
                  type="email"
                  placeholder="选填"
                  :disabled="isAdmin"
                />
                <div class="field-error">{{ emailErr }}</div>
              </div>
              <div class="field">
                <label class="field-label">性别</label>
                <select v-model="form.gender" class="select" :disabled="isAdmin">
                  <option value="male">男</option>
                  <option value="female">女</option>
                  <option value="secret">保密</option>
                </select>
                <div v-if="isAdmin" class="field-hint">后台账号仅支持修改昵称与头像</div>
              </div>
            </div>

            <div class="form-actions">
              <button class="btn btn-primary" type="button" :disabled="saving" @click="handleSave">
                {{ saving ? '保存中…' : '保存修改' }}
              </button>
              <button class="btn btn-ghost" type="button" @click="handleReset">还原</button>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3>学习数据</h3>
            <router-link class="btn-link" :to="{ name: 'wrongbook' }">我的错题 ›</router-link>
          </div>
          <div class="card-body">
            <div class="detail-stats">
              <div class="ds-item">
                <div class="ds-icon">📝</div>
                <div class="num"><span :ref="(el) => setStatRef(3, el)">0</span></div>
                <div class="label muted">已完成题目</div>
              </div>
              <div class="ds-item">
                <div class="ds-icon">🎯</div>
                <div class="num"><span :ref="(el) => setStatRef(4, el)">0</span>%</div>
                <div class="label muted">正确率</div>
              </div>
              <div class="ds-item">
                <div class="ds-icon">🤖</div>
                <div class="num">{{ stats?.interviewCount ?? 0 }}</div>
                <div class="label muted">AI面试次数</div>
              </div>
            </div>
            <div class="quick-actions">
              <a class="btn btn-sm" @click.prevent="router.push({ name: 'practice' })">继续刷题</a>
              <a class="btn btn-sm" @click.prevent="router.push({ name: 'interviewConfig' })">开始 AI 面试</a>
              <a class="btn btn-sm" @click.prevent="router.push({ name: 'routes' })">学习路线</a>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.profile-page {
  padding: 24px 24px 64px;
}
.page-title {
  margin-bottom: 18px;
}
.profile-grid {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 20px;
  align-items: start;
}
.profile-user-card {
  padding: 28px 20px;
  text-align: center;
}
.avatar-img {
  object-fit: cover;
}
.user-name {
  margin: 8px 0 4px;
}
.pu-stats {
  display: flex;
  justify-content: space-around;
  margin-top: 18px;
}
.pu-stats .num {
  font-size: 20px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.pu-stats .label {
  font-size: 12px;
  color: var(--ink-3);
}
.user-meta {
  font-size: 13px;
  text-align: left;
}
.meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
}
.meta-row b {
  font-variant-numeric: tabular-nums;
}

/* 基本信息 */
.avatar-row {
  display: flex;
  align-items: center;
  gap: 18px;
}
.avatar-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
.upload-box {
  width: 96px;
  height: 96px;
  border: 1.5px dashed var(--line-strong);
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--ink-3);
  font-size: 12px;
  overflow: hidden;
  flex-shrink: 0;
  transition: border-color 0.15s;
}
.upload-box:hover {
  border-color: var(--brand);
  color: var(--brand);
}
.upload-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
}
.upload-empty {
  font-size: 32px;
}
.form-actions {
  display: flex;
  gap: 10px;
}
.mb-16 {
  margin-bottom: 16px;
}

/* 学习数据 */
.detail-stats {
  display: flex;
  gap: 12px;
}
.ds-item {
  flex: 1;
  text-align: center;
  padding: 20px 16px;
  background: var(--surface-2);
  border-radius: var(--radius);
  transition: box-shadow 0.15s, transform 0.15s;
}
.ds-item:hover {
  box-shadow: var(--shadow);
  transform: translateY(-2px);
}
.ds-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--brand-light);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  margin: 0 auto 10px;
}
.ds-item .num {
  font-size: 22px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.ds-item .label {
  font-size: 12px;
}
.quick-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

@media (max-width: 900px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }
}
</style>
