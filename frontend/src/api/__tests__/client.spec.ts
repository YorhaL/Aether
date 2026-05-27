import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AxiosAdapter, AxiosInstance, InternalAxiosRequestConfig } from 'axios'

import apiClient, { AUTH_STATE_CHANGE_EVENT } from '@/api/client'

type TestableApiClient = typeof apiClient & {
  client: AxiosInstance
}

describe('apiClient auth state change event', () => {
  beforeEach(() => {
    localStorage.clear()
    apiClient.clearAuth()
  })

  afterEach(() => {
    localStorage.clear()
    apiClient.clearAuth()
  })

  it('dispatches a same-tab auth change event when clearing auth', () => {
    const handler = vi.fn()
    window.addEventListener(AUTH_STATE_CHANGE_EVENT, handler as EventListener)

    apiClient.setToken('access-token')
    apiClient.clearAuth()

    expect(localStorage.getItem('access_token')).toBeNull()
    expect(handler).toHaveBeenCalledTimes(1)

    const event = handler.mock.calls[0][0] as CustomEvent<{ token: string | null }>
    expect(event.detail).toEqual({ token: null })

    window.removeEventListener(AUTH_STATE_CHANGE_EVENT, handler as EventListener)
  })

  it('sends auth refresh without a request body', async () => {
    const rawClient = apiClient as TestableApiClient
    const previousAdapter = rawClient.client.defaults.adapter
    const requests: InternalAxiosRequestConfig[] = []

    rawClient.client.defaults.adapter = (async (config: InternalAxiosRequestConfig) => {
      requests.push(config)
      return {
        data: { access_token: 'new-access-token' },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }) as AxiosAdapter

    try {
      const response = await apiClient.refreshToken()

      expect(response.data.access_token).toBe('new-access-token')
      expect(requests).toHaveLength(1)
      expect(requests[0].url).toBe('/api/auth/refresh')
      expect(requests[0].method).toBe('post')
      expect(requests[0].data).toBeUndefined()
    } finally {
      rawClient.client.defaults.adapter = previousAdapter
    }
  })
})
