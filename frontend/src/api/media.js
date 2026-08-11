/** Video, photo, favorites, history, and search endpoints. */
import api from './client.js'

export const fetchVideos = (params) => api.get('/videos/', { params })
export const fetchVideo = (id) => api.get(`/videos/${id}/`)
export const renameVideo = (id, name) => api.post(`/videos/${id}/rename/`, { name })
export const moveVideo = (id, libraryId) => api.post(`/videos/${id}/move/`, { library_id: libraryId })
export const deleteVideo = (id) => api.delete(`/videos/${id}/delete/`)
export const saveProgress = (id, position) => api.post(`/videos/${id}/progress/`, { position })
export const openVideoWithDefaultPlayer = (id) => api.post(`/videos/${id}/open/`)

export const fetchPhotos = (params) => api.get('/photos/', { params })
export const renamePhoto = (id, name) => api.post(`/photos/${id}/rename/`, { name })
export const movePhoto = (id, libraryId) => api.post(`/photos/${id}/move/`, { library_id: libraryId })
export const deletePhoto = (id) => api.delete(`/photos/${id}/delete/`)

export const fetchFavorites = (params) => api.get('/favorites/', { params })
export const toggleFavorite = (contentType, objectId) =>
  api.post('/favorites/toggle/', { content_type: contentType, object_id: objectId })

export const fetchHistory = (params) => api.get('/history/', { params })
export const recordHistory = (contentType, objectId, action = 'view', position = 0) =>
  api.post('/history/record/', { content_type: contentType, object_id: objectId, action, position })
export const clearHistory = (params) => api.delete('/history/clear/', { params })
export const deleteHistoryEntry = (id) => api.delete(`/history/${id}/`)

export const searchMedia = (q, scope = 'all') => api.get('/search/', { params: { q, scope } })
