/** 数字递增动画（原型 ui.js animateNumber：ease-out-cubic，千分位 + 后缀）。 */
export function animateNumber(
  el: HTMLElement,
  target: number,
  opts?: { suffix?: string; duration?: number },
): void {
  const duration = opts?.duration ?? 1400
  const suffix = opts?.suffix ?? ''
  const start = performance.now()
  function step(ts: number) {
    const p = Math.min((ts - start) / duration, 1)
    const eased = 1 - Math.pow(1 - p, 3)
    el.textContent = Math.round(target * eased).toLocaleString('en-US') + suffix
    if (p < 1) requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
}
