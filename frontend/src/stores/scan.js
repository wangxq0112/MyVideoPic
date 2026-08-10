/**
 * 扫描状态 —— 纯手动触发，前端只做"点一下 + 轮询进度"。
 *
 * 放在 store 而不是组件里，是为了在设置页与其他页面间切换时
 * 进度不中断；刷新页面后也能通过 /scan/status/ 接回正在跑的任务。
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  cancelScan, getScanProgress, getScanStatus, triggerScan,
} from '../api/api.js'

const POLL_MS = 800
const ACTIVE = new Set(['pending', 'running'])

export const useScanStore = defineStore('scan', () => {
  const task = ref(null)          // 当前/最近一次任务快照
  const lastScan = ref(null)      // 上次扫描记录（ScanRecord）
  const starting = ref(false)
  const error = ref('')

  let timer = null

  const running = computed(() => ACTIVE.has(task.value?.status))
  const percent = computed(() => {
    const t = task.value
    if (!t) return 0
    return t.total > 0 ? Math.min(t.percent ?? 0, 100) : 0
  })
  const indeterminate = computed(() => running.value && !(task.value?.total > 0))

  function stopPolling() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  async function poll(taskId) {
    stopPolling()
    try {
      const res = await getScanProgress(taskId)
      task.value = res.data
      if (ACTIVE.has(res.data.status)) {
        timer = setTimeout(() => poll(taskId), POLL_MS)
        return
      }
    } catch (e) {
      // 任务表是内存态，服务重启后会查不到 —— 停止轮询而不是无限重试
      error.value = e.friendlyMessage || '扫描进度获取失败'
      task.value = null
    }
    await refreshStatus()
  }

  /** 页面挂载时调用：接回正在跑的任务 + 取上次扫描记录 */
  async function refreshStatus() {
    try {
      const res = await getScanStatus()
      lastScan.value = res.data.last_scan || null
      const active = res.data.active
      if (active) {
        task.value = active
        if (!timer) poll(active.task_id)
      }
    } catch {
      // 状态查不到不影响其它功能，静默即可
    }
  }

  async function start() {
    if (running.value || starting.value) return
    starting.value = true
    error.value = ''
    try {
      const res = await triggerScan()
      task.value = { ...(task.value || {}), status: 'pending', task_id: res.data.task_id }
      await poll(res.data.task_id)
    } catch (e) {
      error.value = e.friendlyMessage || '启动扫描失败'
    } finally {
      starting.value = false
    }
  }

  async function cancel() {
    const id = task.value?.task_id
    if (!id) return
    try {
      await cancelScan(id)
    } catch (e) {
      error.value = e.friendlyMessage || '取消失败'
    }
  }

  function dismiss() {
    if (running.value) return
    task.value = null
    error.value = ''
  }

  return {
    task, lastScan, starting, error,
    running, percent, indeterminate,
    start, cancel, dismiss, refreshStatus, stopPolling,
  }
})
