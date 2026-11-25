<script setup lang="ts">
/**
 * 数据看板（prototype/admin/dashboard.html，需求 4.2 / 04 §4.2）。
 * 统计卡 4 项+环比趋势文案；快捷操作（路线/新建路线/课程库）；
 * 用户增长折线图（7/30/90 天切换，SVG+悬浮提示）+ 题目学科分布柱状图（S13 全部有效题目）；
 * 最近活动（operation_log 前 5 条）→「查看全部」进操作日志。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  fetchDashboard,
  fetchUserGrowth,
  type DashboardData,
  type GrowthPoint,
} from '@/api/dashboard'
import { ElMessage } from 'element-plus'

const router = useRouter()

const data = ref<DashboardData | null>(null)
const growthRange = ref<7 | 30 | 90>(7)
const growthPoints = ref<GrowthPoint[]>([])
const loading = ref(false)

// ===================== 趋势文案配色（↑绿 ↓红 —灰，文案自带箭头非仅色） =====================
function trendClass(text: string) {
  return text.startsWith('↑') ? 'up' : text.startsWith('↓') ? 'down' : 'flat'
}

// ===================== 折线图（对齐原型 drawGrowth：niceScale/网格/面积/描点） =====================
const W = 720
const H = 240
const padL = 48
const padR = 14
const padT = 16
const padB = 36
const plotW = W - padL - padR
const plotH = H - padT - padB
const plotBottom = H - padB

function niceScale(lo: number, hi: number, ticks: number) {
  if (hi === lo) hi = lo + 1
  const raw = (hi - lo) / ticks
  const mag = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10))
  const norm = raw / mag
  const step = mag * (norm >= 5 ? 5 : norm >= 2 ? 2 : 1)
  const nlo = Math.floor(lo / step) * step
  const nhi = Math.ceil(hi / step) * step
  return { lo: nlo, hi: nhi, step }
}

const chart = computed(() => {
  const data0 = growthPoints.value.map((p) => ({
    date: p.date,
    label: p.date.slice(5),
    value: p.count,
  }))
  if (!data0.length) return null
  const vals = data0.map((d) => d.value)
  let rawMin = Math.min(...vals)
  let rawMax = Math.max(...vals)
  if (rawMin === rawMax) {
    rawMin -= 1
    rawMax += 1
  }
  const pad = (rawMax - rawMin) * 0.14
  const sc = niceScale(rawMin - pad, rawMax + pad, 4)
  const n = data0.length
  const X = (i: number) => (n === 1 ? padL + plotW / 2 : padL + (i * plotW) / (n - 1))
  const Y = (v: number) => padT + ((sc.hi - v) / (sc.hi - sc.lo)) * plotH

  const ticks: number[] = []
  for (let g = sc.lo; g <= sc.hi + 1e-6; g += sc.step) ticks.push(Math.round(g * 100) / 100)

  const pts = data0.map((d, i) => `${X(i)},${Y(d.value)}`)
  const linePath = `M${pts.join(' L')}`
  const areaPath = `M${pts.join(' L')} L${X(n - 1)},${plotBottom} L${X(0)},${plotBottom} Z`

  // x 轴标签抽稀（7 天全显，30 天隔 6，90 天隔 15；末点必显）；90 天描点隔 3
  const lblStep = growthRange.value === 90 ? 15 : growthRange.value === 30 ? 6 : 1
  const dotStep = growthRange.value === 90 ? 3 : 1
  return {
    data: data0,
    sc,
    ticks,
    X,
    Y,
    linePath,
    areaPath,
    showLabel: (i: number) => i % lblStep === 0 || i === n - 1,
    showDot: (i: number) => i % dotStep === 0 || i === n - 1,
  }
})

// ===================== 悬浮提示（原型 chart-tip；动态文本转义防注入） =====================
const tip = reactive({ show: false, x: 0, y: 0, html: '' })
function esc(s: string | number) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}
function showTip(e: MouseEvent, html: string) {
  tip.show = true
  tip.html = html
  tip.x = e.clientX + 12
  tip.y = e.clientY - 10
}
function hideTip() {
  tip.show = false
}

// ===================== 学科分布柱状图 =====================
const distBars = computed(() => {
  const list = data.value?.questionDistribution ?? []
  const max = Math.max(1, ...list.map((d) => d.count))
  return list.map((d) => ({
    ...d,
    height: Math.round((d.count / max) * 140),
  }))
})

// ===================== 数据加载 =====================
async function loadGrowth() {
  try {
    const res = await fetchUserGrowth(growthRange.value)
    growthPoints.value = res.points
  } catch (e) {
    ElMessage.error('用户增长数据加载失败')
  }
}
function setRange(d: 7 | 30 | 90) {
  growthRange.value = d
  loadGrowth()
}

onMounted(async () => {
  loading.value = true
  try {
    data.value = await fetchDashboard()
    await loadGrowth()
  } catch (e) {
    ElMessage.error('看板数据加载失败')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-loading="loading" class="dash-page">
    <!-- 统计卡片 -->
    <div v-if="data" class="stat-grid">
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">学科数量</span><span class="stat-icon">📚</span></div>
        <div class="stat-value">{{ data.cards.subjectCount.toLocaleString('en-US') }}</div>
        <div class="stat-sub" :class="trendClass(data.trends.subject)">{{ data.trends.subject }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">题目数量</span><span class="stat-icon">📝</span></div>
        <div class="stat-value">{{ data.cards.questionCount.toLocaleString('en-US') }}</div>
        <div class="stat-sub" :class="trendClass(data.trends.question)">{{ data.trends.question }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">注册用户</span><span class="stat-icon">👥</span></div>
        <div class="stat-value">{{ data.cards.registeredUsers.toLocaleString('en-US') }}</div>
        <div class="stat-sub" :class="trendClass(data.trends.user)">{{ data.trends.user }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-top"><span class="stat-label">AI面试次数</span><span class="stat-icon">🤖</span></div>
        <div class="stat-value">{{ data.cards.aiInterviewCount.toLocaleString('en-US') }}</div>
        <div class="stat-sub" :class="trendClass(data.trends.interview)">{{ data.trends.interview }}</div>
      </div>
    </div>

    <!-- 快捷操作 -->
    <el-card class="mb-16">
      <template #header><span class="panel-title">快捷操作</span></template>
      <div class="quick-actions">
        <el-button @click="router.push({ name: 'routes' })">🗺️ 管理学习路线</el-button>
        <el-button type="primary" @click="router.push({ name: 'routes', query: { new: '1' } })">
          ➕ 创建新路线
        </el-button>
        <el-button @click="router.push({ name: 'courses' })">🎬 B站课程库</el-button>
      </div>
    </el-card>

    <!-- 图表区 -->
    <div class="chart-2col mb-16">
      <el-card>
        <template #header>
          <div class="panel-head">
            <span class="panel-title">用户增长趋势</span>
            <el-segmented
              :model-value="growthRange"
              :options="[
                { label: '7 天', value: 7 },
                { label: '30 天', value: 30 },
                { label: '90 天', value: 90 },
              ]"
              @change="setRange($event as 7 | 30 | 90)"
            />
          </div>
        </template>
        <svg
          v-if="chart"
          class="line-chart"
          :viewBox="`0 0 ${W} ${H}`"
          role="img"
          aria-label="用户增长趋势折线图"
          @mouseleave="hideTip"
        >
          <!-- 网格 + y 刻度 -->
          <g v-for="g in chart.ticks" :key="'g' + g">
            <line class="grid-line" :x1="padL" :y1="chart.Y(g)" :x2="W - padR" :y2="chart.Y(g)" />
            <text class="axis-label" :x="padL - 8" :y="chart.Y(g) + 4" text-anchor="end">
              {{ g.toLocaleString('en-US') }}
            </text>
          </g>
          <!-- 面积 + 折线 -->
          <path class="data-area" :d="chart.areaPath" />
          <path class="data-line" :d="chart.linePath" />
          <!-- x 刻度 -->
          <template v-for="(d, i) in chart.data" :key="'x' + d.date">
            <text
              v-if="chart.showLabel(i)"
              class="axis-label"
              :x="chart.X(i)"
              :y="H - 12"
              text-anchor="middle"
            >
              {{ d.label }}
            </text>
          </template>
          <!-- 数据点 + 大命中区（悬浮提示） -->
          <template v-for="(d, i) in chart.data" :key="'d' + d.date">
            <circle
              v-if="chart.showDot(i)"
              class="data-dot"
              :cx="chart.X(i)"
              :cy="chart.Y(d.value)"
              r="4"
            />
            <circle
              :cx="chart.X(i)"
              :cy="chart.Y(d.value)"
              r="8"
              fill="transparent"
              pointer-events="all"
              @mousemove="showTip($event, `<b>${esc(d.value)}</b> 人 · ${esc(d.label)}`)"
              @mouseleave="hideTip"
            />
          </template>
        </svg>
      </el-card>

      <el-card>
        <template #header><span class="panel-title">题目学科分布</span></template>
        <div class="bar-chart">
          <div
            v-for="d in distBars"
            :key="d.subjectName"
            class="bar-col"
            @mousemove="showTip($event, `<b>${esc(d.subjectName)}</b> · ${esc(d.count)} 题`)"
            @mouseleave="hideTip"
          >
            <div class="bar" :style="{ height: d.height + 'px' }"></div>
            <div class="bar-label">{{ d.subjectName }}</div>
          </div>
          <div v-if="!distBars.length" class="empty-hint">暂无学科数据</div>
        </div>
      </el-card>
    </div>

    <!-- 最近活动 -->
    <el-card>
      <template #header>
        <div class="panel-head">
          <span class="panel-title">最近活动</span>
          <el-button size="small" @click="router.push({ name: 'logs' })">查看全部</el-button>
        </div>
      </template>
      <el-table :data="data?.recentActivities ?? []" size="default">
        <el-table-column label="用户" prop="adminUsername" min-width="120">
          <template #default="{ row }">{{ row.adminUsername || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" prop="action" min-width="140" />
        <el-table-column label="详情" min-width="240">
          <template #default="{ row }">
            <span class="detail-text">{{ row.detail || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="时间" prop="at" min-width="150" />
      </el-table>
    </el-card>

    <!-- 图表悬浮提示 -->
    <div
      class="chart-tip"
      :style="{ display: tip.show ? 'block' : 'none', left: tip.x + 'px', top: tip.y + 'px' }"
      v-html="tip.html"
    ></div>
  </div>
</template>

<style scoped>
.dash-page {
  padding-bottom: 24px;
}
.mb-16 {
  margin-bottom: 16px;
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.panel-title {
  font-weight: 600;
}
.detail-text {
  color: var(--ink-2, #667085);
}

/* ---- 统计卡片（对齐 subjects.vue 同款）---- */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.stat-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 20px;
}
.stat-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.stat-label {
  font-size: 13px;
  color: var(--ink-3);
}
.stat-icon {
  font-size: 18px;
}
.stat-value {
  font-size: 26px;
  font-weight: 700;
  margin-top: 6px;
}
.stat-sub {
  font-size: 12px;
  margin-top: 6px;
  color: var(--ink-3);
}
.stat-sub.up {
  color: var(--success);
}
.stat-sub.down {
  color: var(--danger);
}

/* ---- 快捷操作 ---- */
.quick-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

/* ---- 图表区（对齐原型 chart-2col / line-chart / bar-chart）---- */
.chart-2col {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 16px;
}
.line-chart {
  width: 100%;
  height: 240px;
  display: block;
}
.line-chart .grid-line {
  stroke: var(--chart-grid);
  stroke-width: 1;
}
.line-chart .axis-label {
  fill: var(--ink-3);
  font-size: 11px;
}
.line-chart .data-line {
  stroke: var(--chart-series);
  stroke-width: 2;
  fill: none;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.line-chart .data-area {
  fill: var(--chart-series-fill);
}
.line-chart .data-dot {
  fill: var(--chart-series);
  stroke: #fff;
  stroke-width: 2;
}
.bar-chart {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  height: 180px;
  overflow-x: auto;
}
.bar-col {
  flex: 1;
  min-width: 34px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  height: 100%;
  justify-content: flex-end;
  cursor: default;
}
.bar-col .bar {
  width: 100%;
  max-width: 34px;
  background: var(--chart-series);
  border-radius: 4px 4px 0 0;
  transition: opacity 0.15s;
  min-height: 2px;
}
.bar-col:hover .bar {
  opacity: 0.82;
}
.bar-col .bar-label {
  font-size: 11px;
  color: var(--ink-3);
  white-space: nowrap;
}
.empty-hint {
  align-self: center;
  margin: auto;
  color: var(--ink-3);
  font-size: 13px;
}

/* ---- 悬浮提示（原型 chart-tip）---- */
.chart-tip {
  position: fixed;
  z-index: 3000;
  pointer-events: none;
  display: none;
  background: #1d2939;
  color: #fff;
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 6px;
  white-space: nowrap;
}
</style>
