<script setup lang="ts">
/**
 * 面试配置（prototype/portal/interview-config.html，需求 3.8.1 / 04 §3.4 #33-34）。
 * 技术方向（=学科）/难度/题量单选，超时固定 5 分钟；今日剩余配额（发起即计次 S1）；
 * 「开始AI面试」→ POST /interviews（题库不足 AI 补充 Q4、一次下发全部题干 S11）→ 进入面试页。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchConfigMeta, startInterview, type ConfigMeta, type DifficultyApi } from '@/api/interview'
import {
  clearIvSession,
  createIvSession,
  saveIvSession,
} from '@/utils/iv-session'
import type { ApiError } from '@shared/types/api'

const router = useRouter()

/** 方向说明（原型文案；新增学科无文案则只显示名称） */
const DIR_DESC: Record<string, string> = {
  AI应用与智能体开发: '大模型应用、Agent 开发',
  AI大模型开发: '微调、推理与部署',
  AI具身智能机器人开发: '感知、控制与规划',
  AI嵌入式_机器人开发: '嵌入式与驱动开发',
  AI测试: '功能、自动化与 AI 专项测试',
  AI运维: '云原生与智能运维',
  AI视觉设计: '设计基础与 AIGC 绘图',
  AI视频与短剧创作: '分镜脚本与 AI 视频',
}
const DIFFS: { id: DifficultyApi; name: string; desc: string }[] = [
  { id: 'easy', name: '简单', desc: '基础面试 · 适合初学者热身' },
  { id: 'medium', name: '中等', desc: '进阶面试 · 适合有一定项目经验者' },
  { id: 'hard', name: '困难', desc: '高级面试 · 适合冲刺高薪岗位' },
]

const meta = ref<ConfigMeta | null>(null)
const subjectId = ref<number | null>(null)
const difficulty = ref<DifficultyApi>('medium')
const questionCount = ref(10)
const starting = ref(false)

const todayRemaining = computed(() => meta.value?.todayRemaining ?? 0)
const dailyQuota = computed(() => meta.value?.dailyQuota ?? 5)
const diffName = computed(() => DIFFS.find((d) => d.id === difficulty.value)?.name ?? '中等')

async function load() {
  try {
    meta.value = await fetchConfigMeta()
    const list = meta.value.subjects
    const def = list.find((s) => s.name === 'AI应用与智能体开发') ?? list[0]
    subjectId.value = def?.id ?? null
    questionCount.value = meta.value.defaultCount
    if (!list.length) ElMessage.warning('暂无可用的面试方向，请联系管理员维护学科')
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '配置加载失败')
  }
}

async function start() {
  if (starting.value) return
  if (subjectId.value === null) {
    ElMessage.warning('请选择技术方向')
    return
  }
  if (todayRemaining.value <= 0) {
    ElMessage.warning('今日剩余面试次数已用完，明日 0 点重置')
    return
  }
  starting.value = true
  try {
    const subjectName = meta.value?.subjects.find((s) => s.id === subjectId.value)?.name ?? ''
    const res = await startInterview({
      subjectId: subjectId.value,
      difficulty: difficulty.value,
      questionCount: questionCount.value,
    })
    const session = createIvSession(res, {
      subjectId: subjectId.value,
      subjectName,
      difficulty: difficulty.value,
      difficultyName: diffName.value,
      count: questionCount.value,
      timeoutSeconds: res.timeoutSeconds,
    })
    clearIvSession()
    saveIvSession(session)
    ElMessage.success('已创建面试，正在进入…')
    router.push({ name: 'interviewSession' })
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '发起面试失败，请稍后重试')
  } finally {
    starting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="container cfg-page">
    <div class="flex-between mb-16 cfg-head">
      <div>
        <h1 class="cfg-title">AI 模拟面试</h1>
        <div class="muted">选择技术方向与面试难度，开始一场沉浸式 AI 模拟面试</div>
      </div>
      <button class="btn btn-ghost" type="button" @click="router.push({ name: 'interviewRecords' })">
        🎙️ 面试记录
      </button>
    </div>

    <div class="card mb-16">
      <div class="card-header">
        <h3>技术方向</h3>
        <span class="muted">单选 · 共 {{ meta?.subjects.length ?? 0 }} 个方向</span>
      </div>
      <div class="card-body">
        <div class="iv-config-grid">
          <div
            v-for="s in meta?.subjects ?? []"
            :key="s.id"
            class="iv-option"
            :class="{ active: s.id === subjectId }"
            @click="subjectId = s.id"
          >
            <div class="iv-name">{{ s.name }}</div>
            <div v-if="DIR_DESC[s.name]" class="iv-desc">{{ DIR_DESC[s.name] }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="card mb-16">
      <div class="card-header">
        <h3>面试难度</h3>
        <span class="muted">单选</span>
      </div>
      <div class="card-body">
        <div class="iv-config-grid">
          <div
            v-for="d in DIFFS"
            :key="d.id"
            class="iv-option"
            :class="{ active: d.id === difficulty }"
            @click="difficulty = d.id"
          >
            <div class="iv-name">{{ d.name }}</div>
            <div class="iv-desc">{{ d.desc }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="card mb-16">
      <div class="card-header"><h3>面试设置</h3></div>
      <div class="card-body">
        <div class="form-grid">
          <div class="field">
            <label class="field-label" for="count-sel">面试题目数量</label>
            <select id="count-sel" v-model="questionCount" class="select">
              <option v-for="n in meta?.questionCounts ?? [3, 5, 8, 10, 15]" :key="n" :value="n">
                {{ n }} 题<template v-if="n === meta?.defaultCount">（默认）</template>
              </option>
            </select>
            <div class="field-hint">可选 {{ (meta?.questionCounts ?? []).join(' / ') }} 题</div>
          </div>
          <div class="field">
            <label class="field-label" for="timeout-input">回答超时时间</label>
            <input id="timeout-input" class="input" value="5 分钟" disabled />
            <div class="field-hint">固定 5 分钟，不可修改</div>
          </div>
        </div>
      </div>
    </div>

    <div class="card mb-24">
      <div class="card-body cfg-quota">
        <div class="stat-icon">🎟️</div>
        <div>
          <div class="stat-label">今日剩余 AI 面试次数</div>
          <div class="q-num" :class="{ warn: todayRemaining <= 0 }">{{ todayRemaining }}/{{ dailyQuota }}</div>
          <div class="stat-sub">每日限额 {{ dailyQuota }} 次，次日 0 点重置</div>
        </div>
      </div>
    </div>

    <div class="flex-center">
      <button class="btn btn-primary btn-lg" type="button" :disabled="starting" @click="start">
        {{ starting ? '创建中…' : '开始AI面试' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.cfg-page {
  padding: 24px 24px 64px;
}
.cfg-head {
  flex-wrap: wrap;
  gap: 12px;
}
.cfg-title {
  margin-bottom: 4px;
}
.mb-16 {
  margin-bottom: 16px;
}
.mb-24 {
  margin-bottom: 24px;
}
</style>
