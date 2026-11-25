<script setup lang="ts">
/**
 * 学习路线（prototype/portal/routes.html，需求 3.7 / 04 §3.3 #29-32）。
 * 选择学科（一排 5 个、无路线弱化）→ 路线 Tab（进度 N/M，默认「最近学习」）→
 * 路线头部（适合人群/统计/进度条）→ 有序课程列表（去B站学习 / 标记已学完）。
 * 标记仅可标记不可取消（需求 3.7）；进度按 student_course 全局标记（Q1），标记后 Tab 与头部同步刷新。
 * BV号不展示（用户偏好，去B站学习入口直达视频页）。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  completeCourse,
  fetchRouteDetail,
  fetchRouteSubjects,
  fetchRoutes,
} from '@/api/routes'
import type {
  RouteCourseItem,
  RouteDetail,
  RouteListItem,
  RouteSubjectCard,
} from '@/api/routes'
import type { ApiError } from '@shared/types/api'

const subjects = ref<RouteSubjectCard[]>([])
const subjectId = ref<number | null>(null)
const routes = ref<RouteListItem[]>([])
const routeId = ref<number | null>(null)
const detail = ref<RouteDetail | null>(null)
const detailLoading = ref(false)
const listLoading = ref(false)

/** 当前 Tab 路线（图标等列表侧字段从这里取，契约详情不含 icon） */
const currentRoute = computed(() => routes.value.find((r) => r.id === routeId.value))

// ===================== 工具 =====================
/** 「x 小时 y 分钟」 */
function fmtTotalMin(totalMin: number): string {
  const h = Math.floor(totalMin / 60)
  const m = totalMin % 60
  if (h > 0) return m > 0 ? `${h} 小时 ${m} 分钟` : `${h} 小时`
  return `${m} 分钟`
}

/** 课程封面：优先 coverUrl，缺失时生成渐变占位图（原型 coverUri 口径） */
function coverUri(c: Pick<RouteCourseItem, 'id' | 'name' | 'coverUrl'>): string {
  if (c.coverUrl) return c.coverUrl
  const grads: [string, string][] = [
    ['#2a78d6', '#6250d6'],
    ['#eb6834', '#e34948'],
    ['#1baf7a', '#2a78d6'],
    ['#6250d6', '#e87ba4'],
    ['#eda100', '#eb6834'],
    ['#008300', '#1baf7a'],
  ]
  let h = 0
  for (let i = 0; i < String(c.id).length; i++) h = (h * 31 + String(c.id).charCodeAt(i)) >>> 0
  const g = grads[h % grads.length]
  const t = c.name.length > 11 ? `${c.name.slice(0, 11)}…` : c.name
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="168" height="96" viewBox="0 0 168 96">` +
    `<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">` +
    `<stop offset="0" stop-color="${g[0]}"/><stop offset="1" stop-color="${g[1]}"/></linearGradient></defs>` +
    `<rect width="168" height="96" fill="url(#g)"/>` +
    `<text x="84" y="53" font-size="13" fill="#ffffff" text-anchor="middle" font-family="sans-serif">${t
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')}</text></svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

/** 默认 Tab：「最近学习」的路线（lastStudiedAt 最新），无学习记录取第一条 */
function pickDefaultRoute(list: RouteListItem[]): RouteListItem {
  return [...list].sort((a, b) =>
    String(b.lastStudiedAt ?? '').localeCompare(String(a.lastStudiedAt ?? '')),
  )[0]
}

// ===================== 数据加载 =====================
async function loadSubjects() {
  try {
    subjects.value = await fetchRouteSubjects()
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '学科加载失败')
  }
}

async function loadRoutes(subject: number, keepRoute = false) {
  listLoading.value = true
  try {
    routes.value = await fetchRoutes(subject)
    const current = routes.value.find((r) => r.id === routeId.value)
    if (keepRoute && current) return
    routeId.value = routes.value.length ? pickDefaultRoute(routes.value).id : null
    if (routeId.value !== null) await loadDetail(routeId.value)
    else detail.value = null
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '路线加载失败')
  } finally {
    listLoading.value = false
  }
}

async function loadDetail(id: number) {
  detailLoading.value = true
  try {
    detail.value = await fetchRouteDetail(id)
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '路线详情加载失败')
  } finally {
    detailLoading.value = false
  }
}

function selectSubject(id: number) {
  subjectId.value = id
  routeId.value = null // 切学科后重新选默认路线
  loadRoutes(id)
}

function selectRoute(id: number) {
  routeId.value = id
  loadDetail(id)
}

// ===================== 标记已学完 =====================
async function markComplete(course: RouteCourseItem) {
  try {
    await ElMessageBox.confirm(
      `确定将《${course.name}》标记为已学完吗？仅可标记、不可取消。`,
      '标记已学完',
      { type: 'warning', confirmButtonText: '标记已学完', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await completeCourse(course.id)
    ElMessage.success('已标记为已学完')
    // 路线 Tab 与路线头部进度同步刷新（需求 3.7）
    if (subjectId.value !== null) await loadRoutes(subjectId.value, true)
    if (routeId.value !== null) await loadDetail(routeId.value)
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '标记失败')
  }
}

function openBilibili(course: RouteCourseItem) {
  if (course.playUrl) window.open(course.playUrl, '_blank')
}

onMounted(loadSubjects)
</script>

<template>
  <div class="container routes-page">
    <h1 class="page-title">学习路线</h1>

    <!-- 选择学科 -->
    <h3 class="route-section-title">选择学科</h3>
    <div class="route-subject-grid">
      <div
        v-for="s in subjects"
        :key="s.id"
        class="route-subject-card"
        :class="{ active: subjectId === s.id, 'disabled-sub': s.routeCount === 0 }"
        @click="selectSubject(s.id)"
      >
        <div class="rs-icon">{{ s.icon || '📘' }}</div>
        <div class="rs-name">{{ s.name }}</div>
        <div class="rs-count">{{ s.routeCount }} 条路线</div>
      </div>
    </div>

    <!-- 路线详情 -->
    <div v-loading="listLoading || detailLoading">
      <!-- 未选学科 -->
      <div v-if="subjectId === null" class="empty-state card">
        <div class="empty-icon">🧭</div>
        <div class="empty-title">请选择一个学科方向</div>
        <div class="empty-sub">在上方学科卡片中选择一个方向，查看该学科的学习路线</div>
      </div>

      <!-- 无启用路线 -->
      <div v-else-if="!routes.length" class="empty-state card">
        <div class="empty-icon">🚧</div>
        <div class="empty-title">该学科暂无学习路线</div>
        <div class="empty-sub">路线筹备中，敬请期待</div>
      </div>

      <template v-else-if="detail">
        <!-- 路线 Tab（进度徽标） -->
        <div class="tabs mb-16">
          <button
            v-for="r in routes"
            :key="r.id"
            class="tab"
            :class="{ active: r.id === routeId }"
            type="button"
            @click="selectRoute(r.id)"
          >
            <span class="route-tab">
              {{ r.name }}
              <span class="badge badge-blue">{{ r.progress.done }}/{{ r.progress.total }}</span>
            </span>
          </button>
        </div>

        <!-- 路线头部 -->
        <div class="card route-head">
          <h2 class="rh-title">
            <span v-if="currentRoute?.icon" class="rh-icon">{{ currentRoute.icon }}</span>{{ detail.name }}
          </h2>
          <div class="rh-audience"><strong>适合人群：</strong>{{ detail.targetEducation || '不限' }}</div>
          <p v-if="detail.description" class="rh-desc">{{ detail.description }}</p>
          <div class="rh-stats">
            <span>共 {{ detail.courseCount }} 门课程</span>
            <span>总计时长 {{ fmtTotalMin(detail.totalMinutes) }}</span>
            <span>按列表顺序学习</span>
          </div>
          <div class="rh-progress-line">
            <span>学习进度 <strong>{{ detail.progress.done }}/{{ detail.progress.total }}</strong></span>
            <span class="muted">{{ detail.progress.percent }}%</span>
          </div>
          <div class="progress">
            <div
              class="progress-bar"
              :class="{ success: detail.progress.total > 0 && detail.progress.done >= detail.progress.total }"
              :style="{ width: detail.progress.percent + '%' }"
            />
          </div>
        </div>

        <!-- 课程列表 -->
        <div v-if="!detail.courses.length" class="empty-state card">
          <div class="empty-icon">📦</div>
          <div class="empty-title">课程筹备中，敬请期待</div>
        </div>
        <ol v-else class="course-list">
          <li v-for="c in detail.courses" :key="c.id" class="course-row" :class="{ done: c.completed }">
            <div class="c-index">{{ c.seq }}</div>
            <div class="c-cover">
              <img :src="coverUri(c)" :alt="`${c.name} 封面`" />
            </div>
            <div class="c-body">
              <div class="c-title">{{ c.name }}</div>
              <div class="c-sub"><span>时长 {{ fmtTotalMin(c.durationMinutes) }}</span></div>
            </div>
            <button class="btn btn-sm" type="button" :disabled="!c.playUrl" @click="openBilibili(c)">
              去B站学习
            </button>
            <button v-if="c.completed" class="btn btn-sm" type="button" disabled>✓ 已学完</button>
            <button v-else class="btn btn-primary btn-sm" type="button" @click="markComplete(c)">
              标记已学完
            </button>
          </li>
        </ol>
      </template>
    </div>
  </div>
</template>

<style scoped>
.routes-page {
  padding: 24px 24px 64px;
}
.page-title {
  font-size: 22px;
  margin-bottom: 16px;
}
.route-section-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 10px;
}
.course-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

/* 路线头部 */
.rh-title {
  margin: 0 0 8px;
  font-size: 22px;
}
.rh-title .rh-icon {
  margin-right: 6px;
}
.rh-audience {
  color: var(--ink-2);
  margin-bottom: 8px;
}
.rh-desc {
  color: var(--ink-2);
  margin: 0;
}
.rh-progress-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: var(--ink-2);
  margin: 4px 0 8px;
}

/* 课程行 */
.c-body {
  flex: 1;
  min-width: 0;
}
.course-row .c-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .route-subject-grid {
    grid-template-columns: repeat(3, 1fr);
  }
  .course-row {
    flex-wrap: wrap;
  }
}
</style>
