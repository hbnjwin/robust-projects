import axios, { AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios'
import { getAccessToken, getRefreshToken, setToken } from './auth'

const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000
})

let isRefreshing = false
let pendingRequests: Array<(token: string) => void> = []

service.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken()
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

service.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const originalRequest = error.config
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      if (isRefreshing) {
        // BUG: 排队的请求在 token 刷新完成后应该被 replay，
        // 但这里 resolve 的 promise 没有正确链回原始请求
        return new Promise((resolve) => {
          pendingRequests.push((newToken: string) => {
            originalRequest.headers['Authorization'] = `Bearer ${newToken}`
            resolve(service(originalRequest))
          })
        })
      }

      isRefreshing = true

      try {
        const refreshToken = getRefreshToken()
        const { data } = await axios.post('/api/system/auth/refresh-token', {
          refreshToken
        })
        const newToken = data.data.accessToken
        setToken(newToken, data.data.refreshToken)

        // BUG: pendingRequests 在遍历时可能有新的请求被 push 进来
        // 用 forEach 遍历后清空，但遍历期间新 push 的请求会丢失
        pendingRequests.forEach((cb) => cb(newToken))
        pendingRequests = []

        originalRequest.headers['Authorization'] = `Bearer ${newToken}`
        return service(originalRequest)
      } catch (refreshError) {
        // BUG: 刷新失败时没有 reject 排队的请求
        // 导致排队的请求 promise 永远 pending，请求"丢了"
        pendingRequests = []
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }
    return Promise.reject(error)
  }
)

export default service
