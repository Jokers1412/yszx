<script setup lang="ts">
/**
 * 学员端首页（对齐 prototype/portal/index.html，04 §3.2）。
 * Hero 平台数据 + 快速开始 + 核心功能 + 学习统计/近 7 天练习（登录）+ 热门学科 + AI 介绍 + 新手引导。
 * 数据口径（03 §5.2）：Hero 前三项实时统计、好评率静态；学习统计/趋势为登录态个人数据，
 * 游客展示登录引导（口径 S9 游客仅浏览首页）。热门阶段限「有已上架题目」的启用阶段。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchHomeStats, fetchHotStages, fetchLearnStats } from '@/api/home'
import type { HomeStats, HotStage, LearnStats, WeekTrendPoint } from '@/api/home'
import { useAuthStore } from '@/stores/auth'
import { useSiteStore } from '@/stores/site'
import { animateNumber } from '@/utils/anim'
import { SESSION_KEYS, storage } from '@/utils/storage'

const router = useRouter()
const auth = useAuthStore()
const site = useSiteStore()

// ===================== Hero 平台数据（递增动画） =====================
const heroStats = ref<HomeStats | null>(null)
const heroNumEls: (HTMLElement | null)[] = []

function setHeroNumRef(i: number, el: unknown) {
  heroNumEls[i] = (el as HTMLElement | null) ?? null
}

const HERO_ITEMS = [
  { key: 'featuredQuestions', suffix: '+', label: '精选面试题' },
  { key: 'registeredStudents', suffix: '+', label: '注册学员' },
  { key: 'aiInterviews', suffix: '+', label: 'AI面试次数' },
  { key: 'goodRate', suffix: '%', label: '好评率' },
] as const

function animateHero() {
  if (!heroStats.value) return
  HERO_ITEMS.forEach((item, i) => {
    const el = heroNumEls[i]
    if (el) animateNumber(el, Number(heroStats.value![item.key]), { suffix: item.suffix })
  })
}

// ===================== 学习统计 + 近 7 天练习（登录） =====================
const learn = ref<LearnStats | null>(null)

const learnView = computed<LearnStats>(
  () => learn.value ?? { streak: 0, accuracy: 0, totalPracticed: 0, todayDone: 0, weekTrend: [] },
)

/** 近 7 日柱状图：日期 → 周几标签（今天高亮） */
const weekBars = computed(() => {
  const todayStr = new Date().toLocaleDateString('sv-SE') // 本地 YYYY-MM-DD
  return learnView.value.weekTrend.map((p: WeekTrendPoint) => ({
    count: p.count,
    label: p.date === todayStr ? '今天' : weekdayLabel(p.date),
    isToday: p.date === todayStr,
  }))
})

function weekdayLabel(date: string): string {
  const [y, m, d] = date.split('-').map(Number)
  return `周${'日一二三四五六'[new Date(y, m - 1, d).getDay()]}`
}

const weekMax = computed(() => Math.max(...weekBars.value.map((b) => b.count), 1))
function barHeight(count: number): number {
  return Math.round((count / weekMax.value) * 140)
}

// 图表悬浮提示（原型 chart-tip）
const barTip = reactive({ show: false, x: 0, y: 0, text: '' })
function showBarTip(e: MouseEvent, count: number) {
  barTip.show = true
  barTip.x = e.clientX + 12
  barTip.y = e.clientY - 36
  barTip.text = `${count} 题`
}
function moveBarTip(e: MouseEvent) {
  barTip.x = e.clientX + 12
  barTip.y = e.clientY - 36
}
function hideBarTip() {
  barTip.show = false
}

// ===================== 热门学科（阶段卡） =====================
const hotStages = ref<HotStage[]>([])

// ===================== 新手引导（首次访问弹出） =====================
const onboardVisible = ref(false)
const onboardStep = ref(1)
const ONBOARD_STEPS = [
  { icon: '🎯', title: '① 选择技术方向', desc: '从 8 大 AI 技术方向中选定目标岗位，题库与面试都围绕它展开。' },
  { icon: '✍️', title: '② 开始刷题练习', desc: '海量题库按阶段进阶，支持顺序 / 随机练习，错题自动收录方便复盘。' },
  { icon: '🎙️', title: '③ AI面试检验', desc: 'AI 面试官模拟真实面试并实时评分，面试报告帮你定位薄弱点。' },
]

function dismissOnboard() {
  storage.set(SESSION_KEYS.beginnerGuide, 1)
  onboardVisible.value = false
}
function nextOnboardStep() {
  onboardStep.value = onboardStep.value >= ONBOARD_STEPS.length ? 1 : onboardStep.value + 1
}
function startLearning() {
  dismissOnboard()
  router.push({ name: 'questions' })
}

// ===================== 数据加载 =====================
onMounted(async () => {
  if (!storage.get(SESSION_KEYS.beginnerGuide)) onboardVisible.value = true
  try {
    heroStats.value = await fetchHomeStats()
    animateHero()
  } catch {
    ElMessage.error('平台数据加载失败')
  }
  try {
    hotStages.value = (await fetchHotStages()).slice(0, 8)
  } catch {
    ElMessage.error('热门学科加载失败')
  }
  if (auth.isLoggedIn) {
    try {
      learn.value = await fetchLearnStats()
    } catch {
      ElMessage.error('学习统计加载失败')
    }
  }
})
</script>

<template>
  <div class="home">
    <!-- ============ Hero 首屏 ============ -->
    <section class="hero">
      <div class="container">
        <h1>{{ site.platformName }} · AI 赋能的智能面试训练平台</h1>
        <p class="hero-sub">
          海量题库 × AI 模拟面试 × 学习路线，从刷题、错题到模拟面试与能力报告，一站式备战技术面试。
        </p>
        <div class="hero-actions">
          <a class="btn btn-lg btn-white" @click.prevent="router.push({ name: 'questions' })">海量题库</a>
          <a class="btn btn-lg btn-outline-white" @click.prevent="router.push({ name: 'interviewConfig' })">
            开始AI面试
          </a>
        </div>
        <div class="hero-stats">
          <div v-for="(item, i) in HERO_ITEMS" :key="item.key" class="hero-stat">
            <div class="num">
              <span :ref="(el) => setHeroNumRef(i, el)">0{{ item.suffix }}</span>
            </div>
            <div class="label">{{ item.label }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 快速开始 ============ -->
    <section class="section">
      <div class="container">
        <div class="section-head">
          <h2>快速开始</h2>
          <span class="sub">选一个入口，马上开始训练</span>
        </div>
        <div class="quick-grid">
          <a class="quick-card" @click.prevent="router.push({ name: 'routes' })">
            <div class="q-icon">🗺️</div>
            <h3>规划学习路线</h3>
            <p>按学习路线系统化进阶</p>
          </a>
          <a class="quick-card" @click.prevent="router.push({ name: 'practice', query: { mode: 'random' } })">
            <div class="q-icon">🎲</div>
            <h3>随机练习10题</h3>
            <p>随机抽取 10 道题，快速热身</p>
          </a>
          <a class="quick-card" @click.prevent="router.push({ name: 'practice' })">
            <div class="q-icon">📖</div>
            <h3>继续上次学习</h3>
            <p>接着上次的练习进度继续刷题</p>
          </a>
          <a class="quick-card" @click.prevent="router.push({ name: 'interviewConfig' })">
            <div class="q-icon">🎙️</div>
            <h3>开始AI面试</h3>
            <p>AI 面试官实时点评你的回答</p>
          </a>
        </div>
      </div>
    </section>

    <!-- ============ 核心功能 ============ -->
    <section class="section">
      <div class="container">
        <div class="section-head">
          <h2>核心功能</h2>
          <span class="sub">刷题 → 错题 → AI 面试 → 报告 → 补强</span>
        </div>
        <div class="feature-grid">
          <a class="card feature-card" @click.prevent="router.push({ name: 'routes' })">
            <div class="f-icon">🗺️</div>
            <h3>学习路线</h3>
            <p>精选 B 站课程串成路线，按序学习</p>
          </a>
          <a class="card feature-card" @click.prevent="router.push({ name: 'questions' })">
            <div class="f-icon">📚</div>
            <h3>海量题库</h3>
            <p>8 大技术方向、按阶段进阶的精选面试题</p>
          </a>
          <a class="card feature-card" @click.prevent="router.push({ name: 'practice' })">
            <div class="f-icon">✍️</div>
            <h3>刷题练习</h3>
            <p>顺序 / 随机练习，错题自动收录</p>
          </a>
          <a class="card feature-card" @click.prevent="router.push({ name: 'interviewConfig' })">
            <div class="f-icon">🤖</div>
            <h3>AI模拟面试</h3>
            <p>还原真实面试场景，逐题实时评分</p>
          </a>
        </div>
      </div>
    </section>

    <!-- ============ 学习统计（登录后可见数据） ============ -->
    <section class="section">
      <div class="container">
        <div class="section-head">
          <h2>学习统计</h2>
          <router-link v-if="auth.isLoggedIn" :to="{ name: 'profile' }">查看全部</router-link>
        </div>
        <template v-if="auth.isLoggedIn">
          <div class="home-stats-grid">
            <div class="card stat-card">
              <div class="stat-label">连续学习天数</div>
              <div class="stat-value">{{ learnView.streak }} 天</div>
              <div class="stat-sub">坚持每日打卡</div>
            </div>
            <div class="card stat-card">
              <div class="stat-label">正确率</div>
              <div class="stat-value">{{ learnView.accuracy }}%</div>
              <div class="stat-sub">全部练习累计</div>
            </div>
            <div class="card stat-card">
              <div class="stat-label">总练习数</div>
              <div class="stat-value">{{ learnView.totalPracticed }} 题</div>
              <div class="stat-sub">累计刷题量</div>
            </div>
          </div>
        </template>
        <div v-else class="card">
          <div class="empty-state">
            <div class="empty-icon">📊</div>
            <div class="empty-title">登录后查看学习数据</div>
            <div class="empty-sub">学习天数、正确率、练习趋势与今日已刷，登录后为你实时统计</div>
            <div class="empty-actions">
              <a class="btn btn-primary" @click.prevent="router.push({ name: 'login' })">登录</a>
              <a class="btn" @click.prevent="router.push({ name: 'register' })">免费注册</a>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 近 7 天练习（登录） ============ -->
    <section v-if="auth.isLoggedIn" class="section">
      <div class="container">
        <div class="section-head">
          <h2>近 7 天练习</h2>
          <span class="sub">每日刷题量</span>
        </div>
        <div class="card">
          <div class="card-body week-chart-wrap">
            <div class="bar-chart">
              <div
                v-for="bar in weekBars"
                :key="bar.label"
                class="bar-col"
                :class="{ today: bar.isToday }"
              >
                <div
                  class="bar"
                  :style="{ height: barHeight(bar.count) + 'px' }"
                  @mousemove="showBarTip($event, bar.count)"
                  @mouseleave="hideBarTip"
                />
                <div class="bar-label">{{ bar.label }}</div>
              </div>
            </div>
            <div class="week-today-box">
              <div class="muted">今日已刷</div>
              <div class="big">{{ learnView.todayDone }} 题</div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 热门学科 ============ -->
    <section class="section">
      <div class="container">
        <div class="section-head">
          <h2>热门学科</h2>
          <span class="sub">按阶段进阶刷题，点击进入题库</span>
        </div>
        <div v-if="hotStages.length" class="stage-grid">
          <a
            v-for="st in hotStages"
            :key="st.id"
            class="card stage-card"
            @click.prevent="router.push({ name: 'questions', query: { stage: st.id } })"
          >
            <div class="st-icon">{{ st.icon || '📘' }}</div>
            <h3>{{ st.name }}</h3>
            <div class="st-sub">{{ st.subjectName }}</div>
            <div class="st-sub">{{ st.questionCount }} 道题目</div>
          </a>
        </div>
        <div v-else class="card">
          <div class="empty-state">
            <div class="empty-icon">🗂️</div>
            <div class="empty-title">暂无热门学科</div>
            <div class="empty-sub">题目上架后将在这里展示</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ AI 面试介绍 ============ -->
    <section class="section">
      <div class="container">
        <div class="ai-intro">
          <div>
            <h2>AI 模拟面试 · 你的私人面试官</h2>
            <ul class="sell-list">
              <li><span>✓</span>智能出题</li>
              <li><span>✓</span>实时评分</li>
              <li><span>✓</span>面试报告</li>
              <li><span>✓</span>海量知识</li>
            </ul>
            <a class="btn btn-lg btn-white" @click.prevent="router.push({ name: 'interviewConfig' })">立即体验</a>
          </div>
          <div class="demo-chat">
            <div class="demo-bubble ai">你好，我是 AI 面试官。请先做一个简短的自我介绍吧。</div>
            <div class="demo-bubble me">面试官您好，我叫林小雨，有两年后端开发经验，最近在做大模型应用方向。</div>
            <div class="demo-bubble ai">很好。请解释一下什么是 RAG？它在企业知识库场景中如何落地？</div>
            <div class="demo-bubble me">RAG 会先检索企业知识库，把相关片段注入提示词，再让大模型生成有依据的回答。</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 新手引导（首次访问） ============ -->
    <div v-if="onboardVisible" class="modal-overlay">
      <div class="modal">
        <div class="modal-header">
          <h3>新手引导</h3>
          <button class="modal-close" type="button" @click="dismissOnboard">×</button>
        </div>
        <div class="modal-body">
          <div class="onboard-step">
            <div class="ob-icon">{{ ONBOARD_STEPS[onboardStep - 1].icon }}</div>
            <h4>{{ ONBOARD_STEPS[onboardStep - 1].title }}</h4>
            <p>{{ ONBOARD_STEPS[onboardStep - 1].desc }}</p>
          </div>
          <div class="onboard-dots">
            <span
              v-for="(s, i) in ONBOARD_STEPS"
              :key="s.title"
              class="dot"
              :class="{ active: onboardStep === i + 1 }"
              @click="onboardStep = i + 1"
            />
          </div>
          <div class="onboard-nav">
            <button class="btn btn-ghost btn-sm" type="button" @click="nextOnboardStep">
              {{ onboardStep >= ONBOARD_STEPS.length ? '重新看一遍' : '下一步' }}
            </button>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" type="button" @click="dismissOnboard">跳过引导</button>
          <button class="btn btn-primary" type="button" @click="startLearning">开始学习</button>
        </div>
      </div>
    </div>

    <!-- 图表悬浮提示 -->
    <div class="chart-tip" :style="{ display: barTip.show ? 'block' : 'none', left: barTip.x + 'px', top: barTip.y + 'px' }">
      <b>{{ barTip.text }}</b>
    </div>
  </div>
</template>

<style scoped>
/* ---- Hero 首屏（对齐 prototype portal.css） ---- */
.hero {
  background: var(--brand-grad);
  color: #fff;
  padding: 72px 0 88px;
  position: relative;
  overflow: hidden;
}
.hero::after {
  content: '';
  position: absolute;
  right: -120px;
  top: -120px;
  width: 420px;
  height: 420px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 50%;
}
.hero h1 {
  color: #fff;
  font-size: 42px;
  margin-bottom: 16px;
  letter-spacing: 1px;
}
.hero .hero-sub {
  font-size: 17px;
  opacity: 0.88;
  margin-bottom: 32px;
  max-width: 560px;
}
.hero-actions {
  display: flex;
  gap: 14px;
  margin-bottom: 48px;
}
.hero-actions .btn {
  border-radius: 8px;
  min-width: 132px;
}
.btn-white {
  background: #fff;
  color: var(--brand-dark);
  border-color: #fff;
}
.btn-white:hover {
  background: var(--brand-light);
  color: var(--brand-dark);
}
.btn-outline-white {
  background: transparent;
  color: #fff;
  border-color: rgba(255, 255, 255, 0.55);
}
.btn-outline-white:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  border-color: #fff;
}
.hero-stats {
  display: flex;
  gap: 56px;
  position: relative;
  z-index: 1;
}
.hero-stat .num {
  font-size: 32px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.hero-stat .label {
  font-size: 13px;
  opacity: 0.8;
}

/* ---- 通用区块 ---- */
.section {
  padding: 56px 0 8px;
}
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 24px;
}
.section-head h2 {
  font-size: 26px;
  margin: 0;
}
.section-head .sub {
  color: var(--ink-3);
  margin-left: 12px;
  font-size: 14px;
}

/* ---- 快速开始 ---- */
.quick-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.quick-card {
  padding: 24px 20px;
  border-radius: var(--radius);
  background: var(--surface);
  border: 1px solid var(--line);
  cursor: pointer;
  transition: all 0.18s ease;
  text-align: left;
}
.quick-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-lg);
  border-color: var(--brand);
}
.quick-card .q-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: var(--brand-light);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  margin-bottom: 12px;
}
.quick-card h3 {
  font-size: 16px;
  margin: 0 0 4px;
}
.quick-card p {
  color: var(--ink-3);
  font-size: 13px;
  margin: 0;
}

/* ---- 核心功能 ---- */
.feature-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.feature-card {
  padding: 28px 22px;
  text-align: center;
  cursor: pointer;
  transition: all 0.18s ease;
}
.feature-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-lg);
}
.feature-card .f-icon {
  font-size: 34px;
  margin-bottom: 10px;
}
.feature-card h3 {
  font-size: 16px;
}
.feature-card p {
  color: var(--ink-3);
  font-size: 13px;
  margin: 0;
}

/* ---- 学习统计 / 近 7 天练习 ---- */
.home-stats-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr 1fr;
  gap: 16px;
}
.empty-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-top: 16px;
}
.week-chart-wrap {
  display: flex;
  gap: 24px;
  align-items: stretch;
}
.week-chart-wrap .bar-chart {
  flex: 1;
}
.week-today-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 0 20px;
  border-left: 1px solid var(--line);
}
.week-today-box .big {
  font-size: 30px;
  font-weight: 700;
  color: var(--brand);
}

/* ---- 热门学科 ---- */
.stage-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.stage-card {
  padding: 20px;
  cursor: pointer;
  transition: all 0.18s ease;
}
.stage-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-lg);
}
.stage-card .st-icon {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  background: var(--brand-light);
  margin-bottom: 10px;
}
.stage-card h3 {
  font-size: 15px;
  margin: 0 0 2px;
}
.stage-card .st-sub {
  font-size: 12px;
  color: var(--ink-3);
}

/* ---- AI 面试介绍 ---- */
.ai-intro {
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, #12274d 0%, #243b6b 60%, #3d2f6b 100%);
  color: #fff;
  padding: 48px;
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  gap: 40px;
  align-items: center;
}
.ai-intro h2 {
  color: #fff;
  font-size: 28px;
}
.ai-intro .sell-list {
  list-style: none;
  padding: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 20px;
  margin: 20px 0 28px;
}
.ai-intro .sell-list li {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 14px;
  opacity: 0.92;
}
.demo-chat {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: var(--radius);
  padding: 18px;
}
.demo-chat .demo-bubble {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 13px;
  margin-bottom: 10px;
  max-width: 86%;
  line-height: 1.55;
}
.demo-chat .demo-bubble.ai {
  background: rgba(255, 255, 255, 0.14);
  border-top-left-radius: 4px;
}
.demo-chat .demo-bubble.me {
  background: rgba(42, 120, 214, 0.55);
  margin-left: auto;
  border-top-right-radius: 4px;
}

/* ---- 新手引导 ---- */
.onboard-step {
  text-align: center;
  padding: 6px 10px 2px;
}
.onboard-step .ob-icon {
  font-size: 44px;
  line-height: 1.2;
}
.onboard-step h4 {
  margin: 12px 0 6px;
  font-size: 17px;
}
.onboard-step p {
  color: var(--ink-3);
  margin: 0;
}
.onboard-dots {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 16px;
}
.onboard-dots .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--line-strong);
  cursor: pointer;
}
.onboard-dots .dot.active {
  background: var(--brand);
  width: 22px;
  border-radius: 4px;
}
.onboard-nav {
  display: flex;
  justify-content: center;
  margin-top: 10px;
}

/* ---- 响应式兜底 ---- */
@media (max-width: 900px) {
  .quick-grid,
  .feature-grid,
  .stage-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .home-stats-grid {
    grid-template-columns: 1fr;
  }
  .ai-intro {
    grid-template-columns: 1fr;
    padding: 32px;
  }
  .hero h1 {
    font-size: 30px;
  }
}
</style>
