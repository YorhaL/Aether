import axios, { getAdapter } from 'axios'
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig, AxiosAdapter } from 'axios'
import { NETWORK_CONFIG, AUTH_CONFIG } from '@/config/constants'
import { isDemoMode } from '@/config/demo'
import { handleMockRequest, setMockUserToken } from '@/mocks'
import { log } from '@/utils/logger'

// 在开发环境下使用代理,生产环境使用环境变量
const API_BASE_URL = import.meta.env.VITE_API_URL || ''

/**
 * 判断请求是否为公共端点
 */
function isPublicEndpoint(url?: string, method?: string): boolean {
  if (!url) return false

  const isHealthCheck = url.includes('/health') &&
                       method?.toLowerCase() === 'get' &&
                       !url.includes('/api/admin')

  return url.includes('/public') ||
         url.includes('.json') ||
         isHealthCheck
}

/**
 * 判断是否为认证相关请求
 */
function isAuthRequest(url?: string): boolean {
  return url?.includes('/auth/login') || url?.includes('/auth/refresh') || url?.includes('/auth/logout') || false
}

/**
 * 判断是否为可刷新的认证错误
 */
function isRefreshableAuthError(errorDetail: string): boolean {
  const nonRefreshableErrors = [
    '用户不存在或已禁用',
    '需要管理员权限',
    '权限不足',
    '用户已禁用',
  ]

  return !nonRefreshableErrors.some((msg) => errorDetail.includes(msg))
}

/**
 * 创建 Demo 模式的自定义 adapter
 * 在 Demo 模式下拦截请求并返回 mock 数据
 */
function createDemoAdapter(defaultAdapter: AxiosAdapter) {
  return async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
    if (isDemoMode()) {
      try {
        const mockResponse = await handleMockRequest({
          method: config.method?.toUpperCase(),
          url: config.url,
          data: config.data,
          params: config.params,
        })
        if (mockResponse) {
          // 确保响应包含 config
          mockResponse.config = config
          return mockResponse
        }
      } catch (error: any) {
        // Mock 错误需要附加 config，否则 handleResponseError 会崩溃
        if (error.response) {
          error.config = config
          error.response.config = config
        }
        throw error
      }
    }
    // 非 Demo 模式或没有 mock 响应时，使用默认 adapter
    return defaultAdapter(config)
  }
}

class ApiClient {
  private client: AxiosInstance
  private token: string | null = null
  private isRefreshing = false
  private refreshPromise: Promise<AxiosResponse> | null = null

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: NETWORK_CONFIG.API_TIMEOUT,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // 设置自定义 adapter 处理 Demo 模式
    const defaultAdapter = getAdapter(this.client.defaults.adapter)
    this.client.defaults.adapter = createDemoAdapter(defaultAdapter)

    this.setupInterceptors()
  }

  /**
   * 配置请求和响应拦截器
   */
  private setupInterceptors(): void {
    // 请求拦截器 - 仅处理认证
    this.client.interceptors.request.use(
      (config) => {
        const requiresAuth = !isPublicEndpoint(config.url, config.method) &&
                           config.url?.includes('/api/')

        if (requiresAuth) {
          const token = this.getToken()
          if (token) {
            config.headers.Authorization = `Bearer ${token}`
          }
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    // 响应拦截器
    this.client.interceptors.response.use(
      (response) => response,
      async (error) => this.handleResponseError(error)
    )
  }

  /**
   * 处理响应错误
   */
  private async handleResponseError(error: any): Promise<any> {
    const originalRequest = error.config

    // 请求被取消
    if (axios.isCancel(error)) {
      return Promise.reject(error)
    }

    // 网络错误或服务器不可达
    if (!error.response) {
      log.warn('Network error or server unreachable', error.message)
      return Promise.reject(error)
    }

    // 认证请求错误,直接返回
    if (isAuthRequest(originalRequest?.url)) {
      return Promise.reject(error)
    }

    // 处理401错误
    if (error.response?.status === 401) {
      return this.handle401Error(error, originalRequest)
    }

    return Promise.reject(error)
  }

  /**
   * 处理401认证错误
   */
  private async handle401Error(error: any, originalRequest: any): Promise<any> {
    // 如果不需要认证,直接返回错误
    if (isPublicEndpoint(originalRequest?.url, originalRequest?.method)) {
      return Promise.reject(error)
    }

    // 如果已经重试过,不再重试
    if (originalRequest._retry) {
      return Promise.reject(error)
    }

    const errorDetail = error.response?.data?.detail || ''
    log.debug('Got 401 error, attempting token refresh', { errorDetail })

    // 检查是否为业务相关的401错误（用户被禁用/删除等）
    if (!isRefreshableAuthError(errorDetail)) {
      log.info('User account issue detected, logging out and redirecting to home', { errorDetail })
      this.clearAuth()
      // 跳转到首页
      window.location.href = '/'
      return Promise.reject(error)
    }

    // 获取refresh token
    const refreshToken = localStorage.getItem('refresh_token')
    if (!refreshToken) {
      log.info('No refresh token available, clearing invalid token')
      this.clearAuth()
      return Promise.reject(error)
    }

    // 标记为已重试
    originalRequest._retry = true
    originalRequest._retryCount = (originalRequest._retryCount || 0) + 1

    // 超过最大重试次数
    if (originalRequest._retryCount > AUTH_CONFIG.MAX_RETRY_COUNT) {
      log.error('Max retry attempts reached')
      return Promise.reject(error)
    }

    // 如果正在刷新,等待刷新完成
    if (this.isRefreshing) {
      try {
        await this.refreshPromise
        originalRequest.headers.Authorization = `Bearer ${this.getToken()}`
        return this.client.request(originalRequest)
      } catch {
        return Promise.reject(error)
      }
    }

    // 开始刷新token
    return this.refreshTokenAndRetry(refreshToken, originalRequest, error)
  }

  /**
   * 刷新token并重试原始请求
   */
  private async refreshTokenAndRetry(
    refreshToken: string,
    originalRequest: any,
    originalError: any
  ): Promise<any> {
    this.isRefreshing = true
    this.refreshPromise = this.refreshToken(refreshToken)

    try {
      const response = await this.refreshPromise
      this.setToken(response.data.access_token)
      localStorage.setItem('refresh_token', response.data.refresh_token)
      this.isRefreshing = false
      this.refreshPromise = null

      // 重试原始请求
      originalRequest.headers.Authorization = `Bearer ${response.data.access_token}`
      return this.client.request(originalRequest)
    } catch (refreshError: any) {
      log.error('Token refresh failed', refreshError)
      this.isRefreshing = false
      this.refreshPromise = null
      this.clearAuth()
      return Promise.reject(originalError)
    }
  }

  setToken(token: string): void {
    this.token = token
    localStorage.setItem('access_token', token)
    // 同步到 mock handler
    if (isDemoMode()) {
      setMockUserToken(token)
    }
  }

  getToken(): string | null {
    if (!this.token) {
      this.token = localStorage.getItem('access_token')
      // 页面刷新时，从 localStorage 恢复 token 到 mock handler
      if (this.token && isDemoMode()) {
        setMockUserToken(this.token)
      }
    }
    return this.token
  }

  clearAuth(): void {
    this.token = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    // 同步清除 mock token
    if (isDemoMode()) {
      setMockUserToken(null)
    }
  }

  async refreshToken(refreshToken: string): Promise<AxiosResponse> {
    // refreshToken 会通过 adapter 处理 Demo 模式
    return this.client.post('/api/auth/refresh', { refresh_token: refreshToken })
  }

  // 以下方法直接委托给 axios client，Demo 模式由 adapter 统一处理
  async request<T = any>(config: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.request<T>(config)
  }

  async get<T = any>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.get<T>(url, config)
  }

  async post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.post<T>(url, data, config)
  }

  async put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.put<T>(url, data, config)
  }

  async patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.patch<T>(url, data, config)
  }

  async delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.delete<T>(url, config)
  }
}

export default new ApiClient()
