/** Shared local-only HTTP client and normalized API errors. */
import axios from 'axios'

export const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const data = error.response?.data
    error.friendlyMessage =
      data?.error ||
      (typeof data === 'object' && data
        ? Object.values(data).flat().find((value) => typeof value === 'string')
        : null) ||
      (error.code === 'ECONNABORTED' ? '请求超时' : null) ||
      (error.response ? `请求失败 (${error.response.status})` : '无法连接后端服务，请确认 Django 已启动')
    return Promise.reject(error)
  },
)

export function errMsg(error, fallback = '操作失败') {
  return error?.friendlyMessage || error?.response?.data?.error || error?.message || fallback
}

export default api
