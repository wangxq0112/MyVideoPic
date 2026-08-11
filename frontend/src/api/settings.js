/** Local settings, statistics, and maintenance endpoints. */
import api from './client.js'

export const fetchStats = () => api.get('/stats/')
export const fetchSettings = () => api.get('/settings/')
export const saveSettings = (data) => api.patch('/settings/', data)
export const clearThumbnailCache = () => api.post('/maintenance/clear-cache/')
export const cleanupOrphans = () => api.post('/maintenance/cleanup-orphans/')
