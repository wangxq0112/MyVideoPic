/**
 * 请求层 —— 统一走同源 /api。
 *
 * 开发期由 Vite proxy 转发到 Django，部署期由 Nginx 转发，
 * 因此前端代码里不出现任何主机名或端口，也不依赖 CORS。
 */
import axios from 'axios'

export const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

/** 把后端的 {error: '...'} 归一化成 Error.message，方便 UI 直接展示 */
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const data = err.response?.data
    const msg =
      data?.error ||
      (typeof data === 'object' && data
        ? Object.values(data).flat().filter(v => typeof v === 'string')[0]
        : null) ||
      (err.code === 'ECONNABORTED' ? '请求超时' : null) ||
      (err.response ? `请求失败 (${err.response.status})` : '无法连接后端服务，请确认 Django 已启动')
    err.friendlyMessage = msg
    return Promise.reject(err)
  },
)

/** 从任意异常里取出可展示文案 */
export function errMsg(e, fallback = '操作失败') {
  return e?.friendlyMessage || e?.response?.data?.error || e?.message || fallback
}

// ── 视频 ────────────────────────────────────────────
export const fetchVideos = (params) => api.get('/videos/', { params })
export const fetchVideo = (id) => api.get(`/videos/${id}/`)
export const renameVideo = (id, name) => api.post(`/videos/${id}/rename/`, { name })
export const moveVideo = (id, libraryId) =>
  api.post(`/videos/${id}/move/`, { library_id: libraryId })
export const deleteVideo = (id) => api.delete(`/videos/${id}/delete/`)
export const saveProgress = (id, position) =>
  api.post(`/videos/${id}/progress/`, { position })
export const openVideoWithDefaultPlayer = (id) => api.post(`/videos/${id}/open/`)

// ── 图片 ────────────────────────────────────────────
export const fetchPhotos = (params) => api.get('/photos/', { params })
export const renamePhoto = (id, name) => api.post(`/photos/${id}/rename/`, { name })
export const movePhoto = (id, libraryId) =>
  api.post(`/photos/${id}/move/`, { library_id: libraryId })
export const deletePhoto = (id) => api.delete(`/photos/${id}/delete/`)

// ── 媒体库 ──────────────────────────────────────────
export const fetchLibraries = (params) => api.get('/libraries/', { params })
export const createLibrary = (data) => api.post('/libraries/', data)
export const updateLibrary = (id, data) => api.patch(`/libraries/${id}/`, data)
export const deleteLibrary = (id, keepItems = false) =>
  api.delete(`/libraries/${id}/`, { params: keepItems ? { keep_items: 1 } : {} })
export const pickAndScanLibrary = () => api.post('/libraries/pick-and-scan/')

// ── 扫描（纯手动触发）──────────────────────────────
export const triggerScan = () => api.post('/scan/')
export const getScanProgress = (taskId) => api.get(`/scan-progress/${taskId}/`)
export const cancelScan = (taskId) => api.post(`/scan-cancel/${taskId}/`)
export const getScanStatus = () => api.get('/scan/status/')
export const getMoveProgress = (taskId) => api.get(`/move-progress/${taskId}/`)

// ── 收藏 ────────────────────────────────────────────
export const fetchFavorites = (params) => api.get('/favorites/', { params })
export const toggleFavorite = (contentType, objectId) =>
  api.post('/favorites/toggle/', { content_type: contentType, object_id: objectId })

// ── 历史 ────────────────────────────────────────────
export const fetchHistory = (params) => api.get('/history/', { params })
export const recordHistory = (contentType, objectId, action = 'view', position = 0) =>
  api.post('/history/record/', {
    content_type: contentType, object_id: objectId, action, position,
  })
export const clearHistory = (params) => api.delete('/history/clear/', { params })
export const deleteHistoryEntry = (id) => api.delete(`/history/${id}/`)

// ── 搜索 ────────────────────────────────────────────
export const searchMedia = (q, scope = 'all') =>
  api.get('/search/', { params: { q, scope } })

// ── 统计 / 维护 / 设置 ──────────────────────────────
export const fetchStats = () => api.get('/stats/')
export const fetchSettings = () => api.get('/settings/')
export const saveSettings = (data) => api.patch('/settings/', data)
export const clearThumbnailCache = () => api.post('/maintenance/clear-cache/')
export const cleanupOrphans = () => api.post('/maintenance/cleanup-orphans/')
export const browseDirectory = (path) => api.get('/browse/', { params: { path } })

export default api
