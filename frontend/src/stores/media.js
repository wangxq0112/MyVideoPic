import { computed, ref } from 'vue'

const PAGE_SIZE = 24

export function createMediaState(apiSet) {
  const { fetchList, renameItem, moveItem, deleteItem } = apiSet

  const list = ref([])
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref('')
  const total = ref(0)
  const currentPage = ref(1)

  const filters = ref({
    library: '',
    category: 'all',
    ordering: 'recent',
    favorited: false,
    q: '',
  })

  const count = computed(() => list.value.length)
  const totalPages = computed(() => Math.max(Math.ceil(total.value / PAGE_SIZE), 1))
  const isFiltered = computed(() =>
    !!filters.value.library ||
    filters.value.category !== 'all' ||
    filters.value.favorited ||
    !!filters.value.q,
  )

  function buildParams(page = currentPage.value) {
    const f = filters.value
    const params = { page, page_size: PAGE_SIZE, ordering: f.ordering }
    if (f.library) params.library = f.library
    if (f.category && f.category !== 'all') params.category = f.category
    if (f.favorited) params.favorited = 1
    if (f.q) params.q = f.q
    return params
  }

  function parsePage(data) {
    if (Array.isArray(data)) {
      total.value = data.length
      return data
    }
    total.value = data?.count ?? 0
    return data?.results ?? []
  }

  async function load(force = false, page = currentPage.value) {
    if (loaded.value && !force && !loading.value) return
    loading.value = true
    error.value = ''
    try {
      const res = await fetchList(buildParams(page))
      list.value = parsePage(res.data)
      currentPage.value = Math.min(page, totalPages.value)
      loaded.value = true
    } catch (e) {
      error.value = e.friendlyMessage || e.message || '加载失败'
      list.value = []
    } finally {
      loading.value = false
    }
  }

  async function goToPage(page) {
    const target = Math.max(1, Math.min(Number(page) || 1, totalPages.value))
    if (target === currentPage.value && loaded.value) return
    await load(true, target)
  }

  async function applyFilters(patch) {
    filters.value = { ...filters.value, ...patch }
    currentPage.value = 1
    await load(true)
  }

  function resetFilters() {
    filters.value = {
      library: '', category: 'all', ordering: 'recent', favorited: false, q: '',
    }
    currentPage.value = 1
  }

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
    if (!list.value.length && currentPage.value > 1) {
      await load(true, currentPage.value - 1)
    }
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
    if (filters.value.favorited && !favorited) dropItem(id)
  }

  function invalidate() {
    loaded.value = false
  }

  return {
    list, loading, loaded, error, total, currentPage, totalPages, filters,
    count, isFiltered,
    load, goToPage, applyFilters, resetFilters,
    rename, move, remove,
    patchItem, dropItem, setFavorited, invalidate,
  }
}
