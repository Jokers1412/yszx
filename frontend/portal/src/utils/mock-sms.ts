/**
 * ⚠️ 开发阶段专用：Mock 短信验证码页面弹窗直显（2026-11-25 需求变更）。
 * 真实短信供应商接入后，删除本文件及各调用点。
 */
import { ElMessageBox } from 'element-plus'

/** 发码成功后弹窗展示验证码（仅 mockCode 存在时） */
export function showMockSmsCode(code: string | null | undefined, ttlMinutes = 3) {
  if (!code) return
  ElMessageBox.alert(
    `验证码：<b style="font-size:20px;letter-spacing:3px">${code}</b><br/>` +
      `<span style="color:#667085;font-size:12px">有效期 ${ttlMinutes} 分钟 · 开发阶段直接展示，接入短信服务后取消</span>`,
    '开发阶段 · 短信验证码',
    {
      dangerouslyUseHTMLString: true,
      confirmButtonText: '知道了',
      customClass: 'mock-sms-box',
    },
  ).catch(() => {})
}
