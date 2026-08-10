/**
 * 媒体库状态 —— 设置页管理，视频/图片页取分类胶囊，卡片菜单取"移动到"目标。
 *
 * 分类胶囊直接从库列表推导，不再单独请求接口：库的数量是个位数，
 * 前端聚合比多一个后端端点更简单。
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  createLibrary, deleteLibrary, fetchLibraries, updateLibrary,
} from '../api/api.js'

export const useLibrariesStore = defineStore('libraries', () => {
  const list = ref([])
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref('')

  const videoLibs = computed(() => list.value.filter((l) => l.library_type === 'video'))
  const photoLibs = computed(() => list.value.filter((l) => l.library_type === 'photo'))

  /** 某一类库里出现过的分类标签（去重后按字典序） */
  function categoriesOf(type) {
    const set = new Set()
    for (const lib of list.value) {
      if (lib.library_type === type && lib.category) set.add(lib.category)
    }
    return [...set].sort((a, b) => a.localeCompare(b, 'zh-CN'))
  }

  const videoCategories = computed(() => categoriesOf('video'))
  const photoCategories = computed(() => categoriesOf('photo'))

  const offlineCount = computed(() => list.value.filter((l) => !l.path_exists).length)

  async function load(force = false) {
    if (loaded.value && !force) return
    loading.value = true
    error.value = ''
    try {
      const res = await fetchLibraries()
      list.value = Array.isArray(res.data) ? res.data : (res.data?.results ?? [])
      loaded.value = true
    } catch (e) {
      error.value = e.friendlyMessage || '媒体库加载失败'
    } finally {
      loading.value = false
    }
  }

  async function create(payload) {
    const res = await createLibrary(payload)
    list.value = [...list.value, res.data]
    return res.data
  }

  async function update(id, payload) {
    const res = await updateLibrary(id, payload)
    const idx = list.value.findIndex((l) => l.id === id)
    if (idx !== -1) list.value[idx] = res.data
    return res.data
  }

  async function remove(id, keepItems = false) {
    await deleteLibrary(id, keepItems)
    list.value = list.value.filter((l) => l.id !== id)
  }

  function findById(id) {
    return list.value.find((l) => l.id === id) || null
  }

  return {
    list, loading, loaded, error,
    videoLibs, photoLibs, videoCategories, photoCategories, offlineCount,
    load, create, update, remove, findById,
  }
})
