/**
 * 通用工具 —— URL 构造与格式化。
 *
 * 所有媒体 URL 都走同源 /api，路径永不出现在 URL 里（只用 UUID），
 * 既避免中文/空格编码问题，也不会把磁盘结构暴露出去。
 */
import { API_BASE } from './api/api.js'

// ── 媒体 URL ────────────────────────────────────────
export const videoCoverUrl = (id) => `${API_BASE}/thumbnails/video/${id}/`
export const photoCoverUrl = (id) => `${API_BASE}/thumbnails/photo/${id}/`
export const videoStreamUrl = (id) => `${API_BASE}/stream/video/${id}/`
export const photoOriginalUrl = (id) => `${API_BASE}/original/photo/${id}/`

// ── 格式化 ──────────────────────────────────────────
export function fmtSize(bytes) {
  if (!bytes || bytes < 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

/** 秒 → 1:23:45 / 4:05 */
export function fmtDuration(sec) {
  if (!sec || sec < 0) return '—'
  const total = Math.floor(sec)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const pad = (n) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}

/** 秒 → "2 小时 15 分" （统计面板用） */
export function fmtDurationLong(sec) {
  if (!sec || sec < 0) return '0 分钟'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  if (h > 0) return m > 0 ? `${h} 小时 ${m} 分` : `${h} 小时`
  return `${Math.max(m, 1)} 分钟`
}

export function fmtDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 相对时间 —— 历史抽屉里显示"3 分钟前" */
export function fmtRelative(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 86400 * 2) return '昨天'
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)} 天前`
  return fmtDate(iso).slice(0, 10)
}

/** 剩余秒数 → "约 2 分 30 秒" */
export function fmtEta(sec) {
  if (sec === null || sec === undefined) return '计算中…'
  if (sec <= 0) return '即将完成'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  if (m > 60) return `约 ${Math.floor(m / 60)} 小时 ${m % 60} 分`
  if (m > 0) return `约 ${m} 分 ${s} 秒`
  return `约 ${s} 秒`
}

export function fmtCount(n) {
  return (n ?? 0).toLocaleString('zh-CN')
}

/** 取父目录，用于"打开所在文件夹"提示 */
export function parentDir(absPath) {
  if (!absPath) return ''
  const idx = Math.max(absPath.lastIndexOf('\\'), absPath.lastIndexOf('/'))
  return idx > 0 ? absPath.slice(0, idx) : absPath
}

// ── 剪贴板 ──────────────────────────────────────────
export async function copyText(text) {
  if (!text) return false
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // http:// 非安全上下文下 Clipboard API 不可用，回退到 execCommand
    try {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.setAttribute('readonly', '')
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      const ok = document.execCommand('copy')
      document.body.removeChild(ta)
      return ok
    } catch {
      return false
    }
  }
}

/** 简单防抖 —— 搜索输入用 */
export function debounce(fn, wait = 300) {
  let timer = null
  const wrapped = (...args) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), wait)
  }
  wrapped.cancel = () => clearTimeout(timer)
  return wrapped
}
