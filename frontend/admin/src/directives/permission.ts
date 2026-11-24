/**
 * v-permission 按钮级权限指令（02 §4.3、需求 §6）。
 * 用法：v-permission="'question:delete'" 或 v-permission="['question:edit','question:delete']"
 * 无权限时移除元素（无权限的操作入口不展示）。
 */
import type { Directive, DirectiveBinding } from 'vue'

import { useAuthStore } from '@/stores/auth'

function check(el: HTMLElement, binding: DirectiveBinding<string | string[]>) {
  const auth = useAuthStore()
  const codes = Array.isArray(binding.value) ? binding.value : [binding.value]
  const allowed = codes.some((code) => auth.hasPermission(code))
  if (!allowed) {
    el.parentNode?.removeChild(el)
  }
}

export const permission: Directive<HTMLElement, string | string[]> = {
  mounted: check,
  updated: check,
}
