<script setup lang="ts">
/**
 * 面试进行中（prototype/portal/interview.html，需求 3.8.2 / 04 §3.4 #35-36）。
 * 对话式作答：AI 消息支持重播朗读、语音输入（Web Speech，不支持降级模拟）、
 * 每题 5 分钟超时自动提交空作答；分析中 → 评分中 → 思考中动效包住 /answers 调用；
 * 会话本地持久化可续做（S22）；全部答完 → finish 生成报告 + endRemark（S21）。
 */
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  fetchInterviewReplay,
  finishInterview,
  startInterview,
  submitInterviewAnswer,
} from '@/api/interview'
import {
  clearIvSession,
  createIvSession,
  fmtClock,
  fmtHumanDur,
  loadIvSession,
  nowHM,
  saveIvSession,
  type IvMessage,
  type IvSession,
} from '@/utils/iv-session'
import type { ApiError } from '@shared/types/api'

const router = useRouter()

// ===================== 状态 =====================
const session = ref<IvSession | null>(null)
const input = ref('')
const busy = ref(false)
const analyzing = ref<'analyze' | 'grading' | 'thinking' | null>(null)
const online = ref(navigator.onLine)
const voiceOn = ref(true)
const resumeVisible = ref(false)
const resumeDetail = reactive({ answered: 0, count: 0, elapsed: 0 })
const side = reactive({ q: false, stat: false })
const chatBody = ref<HTMLElement | null>(null)
let tickHandle: number | undefined

const curSeq = computed(() => session.value?.questions[session.value.currentQ]?.seq ?? null)
const avgScore = computed(() => {
  const vals = Object.values(session.value?.scores ?? {})
  return vals.length ? (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1) : '—'
})
const progressPct = computed(() => {
  const s = session.value
  return s ? Math.round((s.answered / s.questions.length) * 100) : 0
})

function scoreClass(s?: number) {
  if (s === undefined) return ''
  return s >= 8 ? 'score-green' : s >= 6 ? 'score-orange' : 'score-red'
}
function shortQ(q: string) {
  return q.length > 12 ? `${q.slice(0, 12)}…` : q
}

// ===================== 消息 / 朗读 =====================
function speak(text: string, silent = false) {
  if (!('speechSynthesis' in window)) {
    if (!silent) ElMessage.warning('当前浏览器不支持朗读')
    return
  }
  try {
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'zh-CN'
    window.speechSynthesis.speak(u)
  } catch {
    if (!silent) ElMessage.warning('当前浏览器不支持朗读')
  }
}
function replaySpeak(m: IvMessage) {
  speak(m.kind === 'feedback' ? `评分 ${m.score} 分。${m.text}` : m.text)
}
function pushMsg(m: IvMessage) {
  session.value!.messages.push(m)
  saveIvSession(session.value!)
  if (m.role === 'ai' && voiceOn.value) {
    speak(m.kind === 'feedback' ? `评分 ${m.score} 分。${m.text}` : m.text, true)
  }
}
watch(
  () => [session.value?.messages.length, analyzing.value],
  () => nextTick(() => chatBody.value?.scrollTo({ top: chatBody.value.scrollHeight })),
)

// ===================== 出题 / 作答流程 =====================
function askQuestion(idx: number) {
  const s = session.value!
  const q = s.questions[idx]
  if (!q) return
  s.currentQ = idx
  s.questionStartedAt = Date.now()
  pushMsg({ kind: 'question', role: 'ai', seq: q.seq, text: q.questionText, t: nowHM() })
  saveIvSession(s)
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/** 作答 → 分析中/评分中/思考中动效 + /answers 判分（失败撤回气泡可重试，S2） */
async function gradeCurrent(answer: string, timedOut: boolean, fromMessage = false) {
  const s = session.value
  if (!s || busy.value) return
  const seq = s.questions[s.currentQ]?.seq
  if (!seq) return
  busy.value = true
  if (!fromMessage) {
    pushMsg({ kind: 'user', role: 'me', seq, text: answer, timedOut, t: nowHM() })
    input.value = ''
  }
  s.pendingSeq = seq
  saveIvSession(s)
  analyzing.value = 'analyze'
  // 动效链带取消令牌：接口失败时不再回写 analyzing（避免「思考中」残留）
  const phaseState = { cancelled: false }
  const phases = sleep(800)
    .then(() => {
      if (!phaseState.cancelled) analyzing.value = 'grading'
      return sleep(800)
    })
    .then(() => {
      if (!phaseState.cancelled) analyzing.value = 'thinking'
      return sleep(500)
    })
  try {
    const [res] = await Promise.all([
      submitInterviewAnswer(s.recordId, { seq, answer, timedOut }),
      phases,
    ])
    analyzing.value = null
    s.pendingSeq = null
    pushMsg({ kind: 'feedback', role: 'ai', seq, text: res.aiComment, score: res.score, t: nowHM() })
    s.scores[seq] = res.score
    s.answered += 1
    s.currentQ = s.answered
    saveIvSession(s)
    if (res.isLast) {
      await finishAll()
    } else {
      askQuestion(s.answered)
      busy.value = false
    }
  } catch (e) {
    phaseState.cancelled = true
    analyzing.value = null
    const err = e as ApiError
    if (err?.code === 'BIZ_STATE_INVALID' && fromMessage) {
      // 崩溃前该题已落库：从回放恢复评分后继续
      s.pendingSeq = null
      saveIvSession(s)
      await recoverFromReplay(seq)
      busy.value = false
      return
    }
    s.pendingSeq = null
    // 失败撤回乐观气泡并回填输入（AI 失败不落记录，可重试）
    const last = s.messages[s.messages.length - 1]
    if (!fromMessage && last?.kind === 'user' && last.seq === seq) {
      s.messages.pop()
      input.value = answer
    }
    saveIvSession(s)
    busy.value = false
    ElMessage.error(
      err?.code === 'SYS_AI_UNAVAILABLE'
        ? 'AI 评分暂不可用，请稍后重试'
        : err?.message || '提交失败，请稍后重试',
    )
  }
}

async function recoverFromReplay(seq: number) {
  const s = session.value!
  try {
    const replay = await fetchInterviewReplay(s.recordId)
    const um = replay.messages.find((m) => m.role === 'user' && m.seq === seq)
    if (!um) return
    pushMsg({
      kind: 'feedback',
      role: 'ai',
      seq,
      text: um.aiComment || '已完成评分',
      score: um.score ?? 0,
      t: nowHM(),
    })
    s.scores[seq] = um.score ?? 0
    s.answered += 1
    s.currentQ = s.answered
    saveIvSession(s)
    if (s.answered >= s.questions.length) await finishAll()
    else askQuestion(s.answered)
  } catch {
    ElMessage.warning('进度恢复失败，请重新作答该题')
    s.currentQ = Math.max(0, seq - 1)
  }
}

/** 全部答完：finish 生成报告 → endRemark 结束语 → 引导查看报告（S21） */
async function finishAll() {
  const s = session.value!
  try {
    const res = await finishInterview(s.recordId, false)
    s.finished = true
    saveIvSession(s)
    if (res.endRemark) {
      pushMsg({ kind: 'closing', role: 'ai', text: res.endRemark, t: nowHM() })
    }
    busy.value = false
    try {
      await ElMessageBox.confirm('本次面试已完成，是否立即查看面试报告？', '是否查看面试报告？', {
        confirmButtonText: '查看报告',
        cancelButtonText: '暂不',
      })
      clearIvSession()
      router.push({ name: 'interviewReport', params: { id: s.recordId } })
    } catch {
      /* 暂不：留在本页回顾对话 */
    }
  } catch (e) {
    busy.value = false
    ElMessage.error((e as ApiError)?.message || '报告生成失败，可点击「结束面试」重试')
  }
}

// ===================== 发送 / 超时 =====================
function send() {
  const s = session.value
  if (!s || busy.value || s.finished) return
  const text = input.value.trim()
  if (!text) return
  if (!online.value) {
    ElMessage.error('网络已断开，无法发送，请恢复后重试')
    return
  }
  gradeCurrent(text, false)
}
function onInputKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

// ===================== 语音输入（Web Speech，不支持降级模拟） =====================
const VOICE_SAMPLES = [
  '我在项目里用过 RAG 架构：先把文档切分并向量化入库，用户提问时检索相关片段注入提示词，再交给大模型生成答案。',
  '我会先看调用日志定位循环点，加上最大步数限制和重复状态检测，再给工具调用加缓存与失败降级策略。',
  '我做过最有挑战的是企业知识库问答项目，我负责检索链路优化，最大困难是召回不准，后来用重排序和引用溯源解决了。',
  '我认为最需要补齐的是评估体系和工程化能力，包括效果评测、稳定性保障与成本优化，还要关注多模态等趋势。',
]
let voiceIdx = 0
function voiceInput() {
  if (!online.value) {
    ElMessage.error('网络已断开，语音输入暂不可用')
    return
  }
  const SR = (window as unknown as Record<string, unknown>).SpeechRecognition
    ?? (window as unknown as Record<string, unknown>).webkitSpeechRecognition
  if (!SR) {
    // 不支持 → 降级为模拟识别并提示（需求 3.8.2）
    input.value = VOICE_SAMPLES[voiceIdx % VOICE_SAMPLES.length]
    voiceIdx += 1
    ElMessage.warning('当前浏览器不支持语音识别，已使用模拟输入')
    return
  }
  try {
    const rec = new (SR as new () => {
      lang: string
      interimResults: boolean
      maxAlternatives: number
      onresult: (e: { results: { [i: number]: { [j: number]: { transcript: string } } } }) => void
      onerror: () => void
      start: () => void
    })()
    rec.lang = 'zh-CN'
    rec.interimResults = false
    rec.maxAlternatives = 1
    rec.onresult = (e) => {
      input.value = (input.value ? `${input.value} ` : '') + e.results[0][0].transcript
    }
    rec.onerror = () => ElMessage.warning('语音识别失败，请改用键盘输入')
    rec.start()
    ElMessage.info('正在聆听…')
  } catch {
    input.value = VOICE_SAMPLES[voiceIdx % VOICE_SAMPLES.length]
    voiceIdx += 1
    ElMessage.warning('当前浏览器不支持语音识别，已使用模拟输入')
  }
}

// ===================== 侧栏 =====================
function toggleSide(k: 'q' | 'stat') {
  side[k] = !side[k]
}
function jumpTo(seq: number) {
  const el = document.getElementById(`qmsg-${seq}`)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  else ElMessage.warning('该题尚未开始')
}

// ===================== 退出 / 结束 =====================
async function exitInterview() {
  try {
    await ElMessageBox.confirm('退出后进度将保存，可随时回来继续。确定退出吗？', '退出面试', {
      type: 'warning',
      confirmButtonText: '退出',
      cancelButtonText: '继续面试',
    })
  } catch {
    return
  }
  if (session.value) saveIvSession(session.value)
  router.push({ name: 'interviewConfig' })
}
async function endInterview() {
  const s = session.value
  if (!s || busy.value) return
  try {
    await ElMessageBox.confirm('确定要结束本次面试吗？当前进度将保存并生成面试报告。', '结束面试', {
      type: 'warning',
      confirmButtonText: '结束并生成报告',
      cancelButtonText: '继续答题',
    })
  } catch {
    return
  }
  busy.value = true
  try {
    await finishInterview(s.recordId, true) // S22：结束=finish 生成报告
    clearIvSession()
    ElMessage.success('面试已结束，报告已生成')
    // 报告页参数为面试记录 id（GET /interviews/{recordId}/report），勿传 reportId
    router.push({ name: 'interviewReport', params: { id: s.recordId } })
  } catch (e) {
    busy.value = false
    ElMessage.error((e as ApiError)?.message || '报告生成失败，请稍后重试')
  }
}

// ===================== 续做 / 重新开始 =====================
function doResume() {
  const s = loadIvSession()
  resumeVisible.value = false
  if (!s) {
    router.push({ name: 'interviewConfig' })
    return
  }
  session.value = s
  voiceOn.value = s.voiceOn
  saveIvSession(s)
  ElMessage.success('已恢复上次的面试进度')
  // 重新起算当前题的 5 分钟限时（退出期间暂停，S22 可随时回来继续）
  s.questionStartedAt = Date.now()
  saveIvSession(s)
  // 崩溃在评分中的题：重走提交流程（服务端已落库则自动从回放恢复）
  if (s.pendingSeq && s.scores[s.pendingSeq] === undefined) {
    const um = s.messages.find((m) => m.kind === 'user' && m.seq === s.pendingSeq)
    if (um) gradeCurrent(um.text, !!um.timedOut, true)
    return
  }
  // 当前题消息缺失（崩溃在出题间隙）→ 补出题
  const q = s.questions[s.currentQ]
  if (q && !s.messages.some((m) => m.kind === 'question' && m.seq === q.seq)) {
    askQuestion(s.currentQ)
  }
}
async function doRestart() {
  const s = session.value
  resumeVisible.value = false
  if (!s) return
  try {
    const res = await startInterview({
      subjectId: s.config.subjectId,
      difficulty: s.config.difficulty,
      questionCount: s.config.count,
    })
    const fresh = createIvSession(res, s.config, voiceOn.value)
    clearIvSession()
    session.value = fresh
    saveIvSession(fresh)
    askQuestion(0)
    ElMessage.success('已重新发起面试')
  } catch (e) {
    ElMessage.error((e as ApiError)?.message || '重新开始失败，请稍后重试')
  }
}

// ===================== 网络状态 / 计时 =====================
function onOnline() {
  online.value = true
}
function onOffline() {
  online.value = false
}

onMounted(() => {
  window.addEventListener('online', onOnline)
  window.addEventListener('offline', onOffline)
  tickHandle = window.setInterval(() => {
    const s = session.value
    if (!s || s.finished || resumeVisible.value) return // 续做弹窗未确认前不计时/不超时
    s.elapsed += 1
    if (s.elapsed % 5 === 0) saveIvSession(s)
    // 每题 5 分钟超时 → 自动提交空作答（需求 3.8.2）
    if (!busy.value && s.questionStartedAt) {
      const q = s.questions[s.currentQ]
      if (
        q &&
        s.scores[q.seq] === undefined &&
        Date.now() - s.questionStartedAt > s.config.timeoutSeconds * 1000
      ) {
        ElMessage.warning('回答超时，已自动提交')
        gradeCurrent('', true)
      }
    }
  }, 1000)

  const saved = loadIvSession()
  if (!saved) {
    ElMessage.warning('请先发起面试')
    router.replace({ name: 'interviewConfig' })
    return
  }
  if (saved.finished) {
    clearIvSession()
    router.replace({ name: 'interviewConfig' })
    return
  }
  const hasAsked = saved.messages.some((m) => m.kind === 'question')
  if (hasAsked) {
    // 再次进入：提示续做（需求 3.8.2）
    resumeDetail.answered = saved.answered
    resumeDetail.count = saved.questions.length
    resumeDetail.elapsed = saved.elapsed
    session.value = saved
    voiceOn.value = saved.voiceOn
    resumeVisible.value = true
  } else {
    session.value = saved
    voiceOn.value = saved.voiceOn
    askQuestion(0)
  }
})
onUnmounted(() => {
  window.removeEventListener('online', onOnline)
  window.removeEventListener('offline', onOffline)
  if (tickHandle) window.clearInterval(tickHandle)
  window.speechSynthesis?.cancel()
})
</script>

<template>
  <div class="container run-page">
    <template v-if="session">
      <!-- 顶部：退出/标题/网络/计时/进度/语音播报/结束 -->
      <div class="card run-top">
        <button class="btn btn-sm" type="button" @click="exitInterview">← 退出面试</button>
        <div>
          <h2 class="rt-title">AI 模拟面试</h2>
          <div class="rt-meta">{{ session.config.subjectName }} · {{ session.config.difficultyName }}</div>
        </div>
        <div class="rt-right">
          <span class="badge" :class="online ? 'badge-green' : 'badge-red'">
            {{ online ? '● 在线' : '● 离线' }}
          </span>
          <span class="run-timer">{{ fmtClock(session.elapsed) }}</span>
          <span class="badge badge-blue">
            题目 {{ Math.min(session.currentQ + 1, session.questions.length) }}/{{ session.questions.length }}
          </span>
          <span class="voice-box">
            <label class="switch">
              <input v-model="voiceOn" type="checkbox" @change="session.voiceOn = voiceOn; saveIvSession(session)" />
              <span class="slider"></span>
            </label>
            语音播报
          </span>
          <button v-if="!session.finished" class="btn btn-danger btn-sm" type="button" @click="endInterview">
            结束面试
          </button>
        </div>
      </div>

      <!-- 进度条行 -->
      <div class="card run-progress">
        <span class="rp-text">答题进度 {{ session.answered }}/{{ session.questions.length }}</span>
        <div class="progress">
          <div class="progress-bar" :class="{ success: progressPct >= 100 }" :style="{ width: progressPct + '%' }"></div>
        </div>
        <span class="badge badge-orange">{{ session.config.difficultyName }}</span>
      </div>

      <div class="iv-layout">
        <!-- 对话区 -->
        <div class="card iv-chat-card">
          <div ref="chatBody" class="iv-chat-body">
            <div
              v-for="(m, i) in session.messages"
              :id="m.kind === 'question' ? `qmsg-${m.seq}` : undefined"
              :key="i"
              class="iv-msg"
              :class="m.role === 'me' ? 'me' : 'ai'"
            >
              <div class="iv-avatar">{{ m.role === 'me' ? '我' : 'AI' }}</div>
              <div>
                <div class="iv-bubble">
                  <template v-if="m.kind === 'feedback'">
                    <div class="fb-score" :class="scoreClass(m.score)">{{ m.score }}<span> / 10</span></div>
                    <div>{{ m.text }}</div>
                  </template>
                  <template v-else>{{ m.text }}</template>
                </div>
                <div class="iv-time">
                  {{ m.t }}
                  <template v-if="m.role === 'ai' && m.kind !== 'closing'">
                    · <button class="iv-replay" type="button" @click="replaySpeak(m)">重播朗读</button>
                  </template>
                  <template v-else-if="m.kind === 'closing'">
                    · <button class="iv-replay" type="button" @click="replaySpeak(m)">重播朗读</button>
                  </template>
                </div>
              </div>
            </div>

            <!-- 分析中 → 评分中 → 思考中（瞬时态，不入会话） -->
            <div v-if="analyzing" class="iv-msg ai iv-status-bubble">
              <div class="iv-avatar">AI</div>
              <div>
                <div class="iv-bubble">
                  <template v-if="analyzing === 'analyze'">AI面试官正在分析你的回答...</template>
                  <template v-else-if="analyzing === 'grading'">评分中…</template>
                  <div v-else class="typing-indicator"><span></span><span></span><span></span></div>
                </div>
              </div>
            </div>
          </div>

          <!-- 输入区 -->
          <div class="iv-input-bar">
            <span v-if="!online" class="net-hint">网络已断开，发送暂不可用</span>
            <textarea
              v-model="input"
              class="textarea"
              :disabled="session.finished"
              placeholder="输入你的回答…（Enter 发送，Shift+Enter 换行）"
              @keydown="onInputKeydown"
            ></textarea>
            <button class="btn" type="button" :disabled="session.finished" @click="voiceInput">🎤 语音输入</button>
            <button class="btn btn-primary" type="button" :disabled="session.finished" @click="send">发送</button>
          </div>
        </div>

        <!-- 侧边栏 -->
        <div>
          <div class="iv-side-card card">
            <div class="side-head" @click="toggleSide('q')">
              <h3>面试题目</h3>
              <button class="side-toggle" type="button">{{ side.q ? '▸' : '▾' }}</button>
            </div>
            <div v-show="!side.q" class="q-panel">
              <div
                v-for="(q, i) in session.questions"
                :key="q.seq"
                class="iv-q-item"
                :class="{ current: i === session.currentQ && !session.finished }"
                @click="jumpTo(q.seq)"
              >
                <span>{{ q.seq }}.</span>
                <span class="ivq-text">{{ shortQ(q.questionText) }}</span>
                <span
                  class="ivq-score"
                  :class="session.scores[q.seq] !== undefined ? scoreClass(session.scores[q.seq]) : 'muted'"
                >
                  {{ session.scores[q.seq] ?? '—' }}
                </span>
              </div>
            </div>
          </div>

          <div class="iv-side-card card">
            <div class="side-head" @click="toggleSide('stat')">
              <h3>面试统计</h3>
              <button class="side-toggle" type="button">{{ side.stat ? '▸' : '▾' }}</button>
            </div>
            <div v-show="!side.stat">
              <div class="stat-line"><span>已回答</span><span class="sl-val">{{ session.answered }}</span></div>
              <div class="stat-line"><span>总题数</span><span class="sl-val">{{ session.questions.length }}</span></div>
              <div class="stat-line"><span>平均分</span><span class="sl-val">{{ avgScore }}</span></div>
              <div class="stat-line"><span>已用时间</span><span class="sl-val">{{ fmtHumanDur(session.elapsed) }}</span></div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 续做确认（再次进入未完成会话） -->
    <div v-if="resumeVisible" class="modal-overlay">
      <div class="modal modal-sm">
        <div class="modal-header"><h3>是否继续上次的面试？</h3></div>
        <div class="modal-body">
          <p class="text-2">
            已完成 {{ resumeDetail.answered }}/{{ resumeDetail.count }} 题 · 用时 {{ fmtHumanDur(resumeDetail.elapsed) }}
          </p>
        </div>
        <div class="modal-footer">
          <button class="btn" type="button" @click="doRestart">重新开始</button>
          <button class="btn btn-primary" type="button" @click="doResume">继续</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.run-page {
  padding: 24px 24px 64px;
}
.run-top {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  padding: 12px 16px;
  margin-bottom: 12px;
}
.run-top .rt-title {
  font-size: 17px;
  font-weight: 700;
  margin: 0;
}
.run-top .rt-meta {
  font-size: 12px;
  color: var(--ink-3);
}
.run-top .rt-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.run-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  margin-bottom: 12px;
}
.run-progress .rp-text {
  font-size: 13px;
  color: var(--ink-2);
  white-space: nowrap;
}
.run-progress .progress {
  flex: 1;
}
.voice-box {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--ink-2);
}
.net-hint {
  color: var(--danger-text);
  font-size: 12px;
  white-space: nowrap;
}
.side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  user-select: none;
}
.side-head h3 {
  margin: 0;
  font-size: 15px;
}
.side-toggle {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 13px;
  color: var(--ink-3);
  padding: 2px 6px;
}
.q-panel {
  margin-top: 10px;
}
.iv-side-card {
  padding: 16px;
  margin-bottom: 12px;
}
.stat-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 7px 2px;
  font-size: 13px;
  border-bottom: 1px dashed var(--line);
}
.stat-line:last-child {
  border-bottom: none;
}
.stat-line .sl-val {
  font-weight: 600;
}
.text-2 {
  color: var(--ink-2);
}
</style>
