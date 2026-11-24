/**
 * 浏览器语音能力（02 D6 / 需求 3.8.2）：全浏览器端方案，服务端零改造。
 * - 识别：Web Speech API SpeechRecognition（Chrome/Edge 优先，Safari/Firefox 支持不全）
 * - 播报：window.speechSynthesis（AI 读题、消息朗读，支持开关/重播）
 * 不支持时降级：隐藏/禁用语音入口并提示文字作答（02 §7 风险表）。
 */

export function isSpeechRecognitionSupported(): boolean {
  return typeof window !== 'undefined' && 'webkitSpeechRecognition' in window
}

export function isSpeechSynthesisSupported(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window
}

/** 语音播报（中文）；不支持时静默降级 */
export function speak(text: string, opts?: { rate?: number; onEnd?: () => void }): void {
  if (!isSpeechSynthesisSupported()) {
    opts?.onEnd?.()
    return
  }
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'zh-CN'
  utterance.rate = opts?.rate ?? 1
  utterance.onend = () => opts?.onEnd?.()
  window.speechSynthesis.cancel()
  window.speechSynthesis.speak(utterance)
}

export function stopSpeak(): void {
  if (isSpeechSynthesisSupported()) {
    window.speechSynthesis.cancel()
  }
}

// TODO(feature): createRecognizer() 语音识别封装（连续识别/置信度/停止），
// 按原型面试页作答交互实现。
