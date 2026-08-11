/** Media library management and native folder selection endpoints. */
import api from './client.js'

export const fetchLibraries = (params) => api.get('/libraries/', { params })
export const createLibrary = (data) => api.post('/libraries/', data)
export const updateLibrary = (id, data) => api.patch(`/libraries/${id}/`, data)
export const deleteLibrary = (id, keepItems = false) =>
  api.delete(`/libraries/${id}/`, { params: keepItems ? { keep_items: 1 } : {} })
export const pickAndScanLibrary = () => api.post('/libraries/pick-and-scan/')
export const browseDirectory = (path) => api.get('/browse/', { params: { path } })
