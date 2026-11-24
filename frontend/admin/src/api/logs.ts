/**
 * 操作日志接口封装（04 §4.11，log:view / system:settings 归并）。
 */
import request from './request'

import type { PageResult } from '@shared/types/api'

export type LogActionType = 'login' | 'create' | 'update' | 'delete' | 'disable' | 'other'

export interface LogItem {
  id: number
  adminUsername?: string | null
  actionType: LogActionType
  actionDesc: string
  target?: string | null
  detail?: string | null
  ip: string
  createdAt: string
}

export interface LogDetail extends LogItem {
  adminUserId?: number | null
}

export interface LogQuery {
  keyword?: string
  actionType?: string // all | login | create | ...
  dateFrom?: string // YYYY-MM-DD
  dateTo?: string
  adminUserId?: number
  pageNum?: number
  pageSize?: number
}

export function fetchLogs(params: LogQuery): Promise<PageResult<LogItem>> {
  return request.get('/logs', { params })
}

export function fetchLog(id: number): Promise<LogDetail> {
  return request.get(`/logs/${id}`)
}

/** 导出 CSV（UTF-8 BOM，按当前筛选同步流） */
export async function exportLogs(params: LogQuery): Promise<void> {
  const blob = (await request.get('/logs/export', {
    params,
    responseType: 'blob',
  })) as Blob
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'operation-logs.csv'
  a.click()
  URL.revokeObjectURL(url)
}

/** 清空日志（批量逻辑删除，system:settings 归并） */
export function clearLogs(): Promise<{ success: boolean }> {
  return request.delete('/logs')
}
