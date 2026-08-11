/** Manually triggered scan and background move task endpoints. */
import api from './client.js'

export const triggerScan = () => api.post('/scan/')
export const getScanProgress = (taskId) => api.get(`/scan-progress/${taskId}/`)
export const cancelScan = (taskId) => api.post(`/scan-cancel/${taskId}/`)
export const getScanStatus = () => api.get('/scan/status/')
export const getMoveProgress = (taskId) => api.get(`/move-progress/${taskId}/`)
