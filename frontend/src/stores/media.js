/**
 * 媒体列表 store 工厂 —— 视频与图片共用同一套筛选/分页/操作逻辑。
 *
 * 服务端已经承担筛选与排序，前端只负责保存当前条件、
 * 追加分页结果、并在增删改后就地同步本地列表。
 */
import { computed, ref } from 'vue'

export function createMediaState(apiSet) {
  const { fetchList, renameItem, moveItem, deleteItem } = apiSet

  // ── 状态 ──────────────────────────────────────────
  const list = ref([])
  const loading = ref(false)
  const loadingMore = ref(false)
  const loaded = ref(false)
  const error = ref('')
  const total = ref(0)
  const nextPage = ref(null)

  const filters = ref({
    library: '',
    category: 'all',
    ordering: 'recent',
    favorited: false,
    q: '',
  })

  // ── 派生 ──────────────────────────────────────────
  const count = computed(() => list.value.length)
  const hasMore = computed(() => nextPage.value !== null)
  const isFiltered = computed(() =>
    !!filters.value.library ||
    filters.value.category !== 'all' ||
    filters.value.favorited ||
    !!filters.value.q,
  )

  function buildParams(page = 1) {
    const f = filters.value
    const params = { page, ordering: f.ordering }
    if (f.library) params.library = f.library
    if (f.category && f.category !== 'all') params.category = f.category
    if (f.favorited) params.favorited = 1
    if (f.q) params.q = f.q
    return params
  }

  /**
   * 从 DRF 分页响应里解出下一页页码。
   * 直接存页码而不是 next 的完整 URL —— 后者带绝对主机名，
   * 经代理后会指向错误的源。
   */
  function parsePage(data, currentPage) {
    if (Array.isArray(data)) {
      total.value = data.length
      nextPage.value = null
      return data
    }
    total.value = data?.count ?? 0
    nextPage.value = data?.next ? currentPage + 1 : null
    return data?.results ?? []
  }

  async function load(force = false) {
    if (loaded.value && !force && !loading.value) return
    loading.value = true
    error.value = ''
    try {
      const res = await fetchList(buildParams(1))
      list.value = parsePage(res.data, 1)
      loaded.value = true
    } catch (e) {
      error.value = e.friendlyMessage || e.message || '加载失败'
      list.value = []
    } finally {
      loading.value = false
    }
  }

  async function loadMore() {
    if (!hasMore.value || loadingMore.value || loading.value) return
    const page = nextPage.value
    loadingMore.value = true
    try {
      const res = await fetchList(buildParams(page))
      const items = parsePage(res.data, page)
      // 防御重复：并发触底时同一页可能被请求两次
      const seen = new Set(list.value.map((i) => i.id))
      list.value = list.value.concat(items.filter((i) => !seen.has(i.id)))
    } catch (e) {
      error.value = e.friendlyMessage || '加载更多失败'
    } finally {
      loadingMore.value = false
    }
  }

  /** 改筛选条件 → 重新从第一页拉 */
  async function applyFilters(patch) {
    filters.value = { ...filters.value, ...patch }
    nextPage.value = null
    await load(true)
  }

  function resetFilters() {
    filters.value = {
      library: '', category: 'all', ordering: 'recent', favorited: false, q: '',
    }
  }

  // ── 操作 ──────────────────────────────────────────
  async function rename(id, newName) {
    const res = await renameItem(id, newName)
    const patch = res.data.video || res.data.photo
    if (patch) patchItem(id, patch)
    return res.data
  }

  async function move(id, libraryId) {
    const res = await moveItem(id, libraryId)
    const patch = res.data.video || res.data.photo
    if (patch) patchItem(id, patch)
    return res.data
  }

  async function remove(id) {
    const res = await deleteItem(id)
    dropItem(id)
    return res.data
  }

  function patchItem(id, patch) {
    const idx = list.value.findIndex((i) => i.id === id)
    if (idx !== -1) list.value[idx] = { ...list.value[idx], ...patch }
  }

  function dropItem(id) {
    const before = list.value.length
    list.value = list.value.filter((i) => i.id !== id)
    if (list.value.length < before) total.value = Math.max(total.value - 1, 0)
  }

  function setFavorited(id, favorited) {
    patchItem(id, { is_favorited: favorited })
    // 收藏筛选开启时，取消收藏应立刻从列表消失
    if (filters.value.favorited && !favorited) dropItem(id)
  }

  function invalidate() {
    loaded.value = false
  }

  return {
    list, loading, loadingMore, loaded, error, total, filters,
    count, hasMore, isFiltered,
    load, loadMore, applyFilters, resetFilters,
    rename, move, remove,
    patchItem, dropItem, setFavorited, invalidate,
  }
}
