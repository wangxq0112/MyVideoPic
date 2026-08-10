/**
 * 全局 UI 状态 —— 吐司提示 + 顶栏两个浮层（搜索、历史）。
 *
 * 搜索与历史在概念图里是覆盖在当前页之上的浮层而非独立页面，
 * 因此用状态开关驱动，不占用路由（返回键不会退出浮层）。
 */
import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useUiStore = defineStore('ui', () => {
  const toasts = ref([])
  const searchOpen = ref(false)
  const historyOpen = ref(false)

  let seq = 0

  function toast(message, type = 'ok', ms = 2600) {
    if (!message) return
    const id = ++seq
    toasts.value.push({ id, message, type })
    setTimeout(() => {
      toasts.value = toasts.value.filter((t) => t.id !== id)
    }, ms)
  }

  const ok = (msg) => toast(msg, 'ok')
  const fail = (msg) => toast(msg, 'err', 4000)

  function openSearch() {
    historyOpen.value = false
    searchOpen.value = true
  }

  function openHistory() {
    searchOpen.value = false
    historyOpen.value = true
  }

  function closeOverlays() {
    searchOpen.value = false
    historyOpen.value = false
  }

  return {
    toasts, searchOpen, historyOpen,
    toast, ok, fail, openSearch, openHistory, closeOverlays,
  }
})
