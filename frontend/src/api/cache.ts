/**
 * 缓存监控 API 客户端
 */

import api from './client'

export interface CacheStats {
  scheduler: string
  cache_reservation_ratio: number
  affinity_stats: {
    storage_type: string
    total_affinities: number
    active_affinities: number | string
    cache_hits: number
    cache_misses: number
    cache_hit_rate: number
    cache_invalidations: number
    provider_switches: number
    key_switches: number
    config: {
      default_ttl: number
    }
  }
}

export interface DynamicReservationConfig {
  probe_phase_requests: number
  probe_reservation: number
  stable_min_reservation: number
  stable_max_reservation: number
  low_load_threshold: number
  high_load_threshold: number
  success_count_for_full_confidence: number
  cooldown_hours_for_full_confidence: number
}

export interface CacheConfig {
  cache_ttl_seconds: number
  cache_reservation_ratio: number
  dynamic_reservation?: {
    enabled: boolean
    config: DynamicReservationConfig
    description: Record<string, string>
  }
  description: {
    cache_ttl: string
    cache_reservation_ratio: string
    dynamic_reservation?: string
  }
}

export interface UserAffinity {
  affinity_key: string
  user_api_key_name: string | null
  user_api_key_prefix: string | null  // 用户 API Key 脱敏显示（前4...后4）
  is_standalone: boolean
  user_id: string | null
  username: string | null
  email: string | null
  provider_id: string
  provider_name: string | null
  endpoint_id: string
  endpoint_api_format: string | null
  endpoint_url: string | null
  key_id: string
  key_name: string | null
  key_prefix: string | null  // Provider Key 脱敏显示（前4...后4）
  rate_multiplier: number
  model_name: string | null  // 模型名称（如 claude-haiku-4-5-20250514）
  model_display_name: string | null  // 模型显示名称（如 Claude Haiku 4.5）
  api_format: string | null  // API 格式 (claude/openai)
  created_at: number
  expire_at: number
  request_count: number
}

export interface AffinityListResponse {
  items: UserAffinity[]
  total: number
  matched_user_id?: string | null
}

export const cacheApi = {
  /**
   * 获取缓存统计信息
   */
  async getStats(): Promise<CacheStats> {
    const response = await api.get('/api/admin/monitoring/cache/stats')
    return response.data.data
  },

  /**
   * 获取缓存配置
   */
  async getConfig(): Promise<CacheConfig> {
    const response = await api.get('/api/admin/monitoring/cache/config')
    return response.data.data
  },

  /**
   * 查询用户缓存亲和性（现在返回该用户所有端点的亲和性列表）
   *
   * @param userIdentifier 用户标识符，支持：用户名、邮箱、User UUID、API Key ID
   */
  async getUserAffinity(userIdentifier: string): Promise<UserAffinity[] | null> {
    const response = await api.get(`/api/admin/monitoring/cache/affinity/${userIdentifier}`)
    if (response.data.status === 'not_found') {
      return null
    }
    return response.data.affinities
  },

  /**
   * 清除用户缓存
   *
   * @param userIdentifier 用户标识符，支持：用户名、邮箱、User UUID、API Key ID
   */
  async clearUserCache(userIdentifier: string): Promise<void> {
    await api.delete(`/api/admin/monitoring/cache/users/${userIdentifier}`)
  },

  /**
   * 清除所有缓存
   */
  async clearAllCache(): Promise<{ count: number }> {
    const response = await api.delete('/api/admin/monitoring/cache')
    return response.data
  },

  /**
   * 清除指定Provider的所有缓存
   */
  async clearProviderCache(providerId: string): Promise<{ count: number; provider_id: string }> {
    const response = await api.delete(`/api/admin/monitoring/cache/providers/${providerId}`)
    return response.data
  },

  /**
   * 获取缓存亲和性列表
   */
  async listAffinities(keyword?: string): Promise<AffinityListResponse> {
    const response = await api.get('/api/admin/monitoring/cache/affinities', {
      params: keyword ? { keyword } : undefined
    })
    return response.data.data
  }
}

// 导出便捷函数
export const {
  getStats,
  getConfig,
  getUserAffinity,
  clearUserCache,
  clearAllCache,
  clearProviderCache,
  listAffinities
} = cacheApi

// ==================== 缓存亲和性分析 API ====================

export interface TTLAnalysisUser {
  group_id: string
  username: string | null
  email: string | null
  request_count: number
  interval_distribution: {
    within_5min: number
    within_15min: number
    within_30min: number
    within_60min: number
    over_60min: number
  }
  interval_percentages: {
    within_5min: number
    within_15min: number
    within_30min: number
    within_60min: number
    over_60min: number
  }
  percentiles: {
    p50: number | null
    p75: number | null
    p90: number | null
  }
  avg_interval_minutes: number | null
  min_interval_minutes: number | null
  max_interval_minutes: number | null
  recommended_ttl_minutes: number
  recommendation_reason: string
}

export interface TTLAnalysisResponse {
  analysis_period_hours: number
  total_users_analyzed: number
  ttl_distribution: {
    '5min': number
    '15min': number
    '30min': number
    '60min': number
  }
  users: TTLAnalysisUser[]
}

export interface CacheHitAnalysisResponse {
  analysis_period_hours: number
  total_requests: number
  requests_with_cache_hit: number
  request_cache_hit_rate: number
  total_input_tokens: number
  total_cache_read_tokens: number
  total_cache_creation_tokens: number
  token_cache_hit_rate: number
  total_cache_read_cost_usd: number
  total_cache_creation_cost_usd: number
  estimated_savings_usd: number
}

export interface IntervalTimelinePoint {
  x: string  // ISO 时间字符串
  y: number  // 间隔分钟数
  user_id?: string  // 用户 ID（仅 include_user_info=true 时存在）
  model?: string  // 模型名称
}

export interface IntervalTimelineResponse {
  analysis_period_hours: number
  total_points: number
  points: IntervalTimelinePoint[]
  users?: Record<string, string>  // user_id -> username 映射（仅 include_user_info=true 时存在）
  models?: string[]  // 出现的模型列表
}

export const cacheAnalysisApi = {
  /**
   * 分析缓存亲和性 TTL 推荐
   */
  async analyzeTTL(params?: {
    user_id?: string
    api_key_id?: string
    hours?: number
  }): Promise<TTLAnalysisResponse> {
    const response = await api.get('/api/admin/usage/cache-affinity/ttl-analysis', { params })
    return response.data
  },

  /**
   * 分析缓存命中情况
   */
  async analyzeHit(params?: {
    user_id?: string
    api_key_id?: string
    hours?: number
  }): Promise<CacheHitAnalysisResponse> {
    const response = await api.get('/api/admin/usage/cache-affinity/hit-analysis', { params })
    return response.data
  },

  /**
   * 获取请求间隔时间线数据
   *
   * @param params.include_user_info 是否包含用户信息（用于管理员多用户视图）
   */
  async getIntervalTimeline(params?: {
    hours?: number
    limit?: number
    user_id?: string
    include_user_info?: boolean
  }): Promise<IntervalTimelineResponse> {
    const response = await api.get('/api/admin/usage/cache-affinity/interval-timeline', { params })
    return response.data
  }
}

// ==================== 模型映射缓存管理 API ====================

// 映射条目
export interface ModelMappingItem {
  mapping_name: string
  global_model_name: string | null
  global_model_display_name: string | null
  providers: string[]
  ttl: number | null
}

// 未映射的条目（NOT_FOUND、invalid、error）
export interface UnmappedEntry {
  mapping_name: string
  status: 'not_found' | 'invalid' | 'error'
  ttl: number | null
}

export interface ModelMappingCacheStats {
  available: boolean
  message?: string
  ttl_seconds?: number
  total_keys?: number
  breakdown?: {
    model_by_id: number
    model_by_provider_global: number
    global_model_by_id: number
    global_model_by_name: number
    global_model_resolve: number
  }
  mappings?: ModelMappingItem[]
  unmapped?: UnmappedEntry[] | null
}

export interface ClearModelMappingCacheResponse {
  status: string
  message: string
  deleted_count?: number
  model_name?: string
  deleted_keys?: string[]
}

export const modelMappingCacheApi = {
  /**
   * 获取模型映射缓存统计
   */
  async getStats(): Promise<ModelMappingCacheStats> {
    const response = await api.get('/api/admin/monitoring/cache/model-mapping/stats')
    return response.data.data
  },

  /**
   * 清除所有模型映射缓存
   */
  async clearAll(): Promise<ClearModelMappingCacheResponse> {
    const response = await api.delete('/api/admin/monitoring/cache/model-mapping')
    return response.data
  },

  /**
   * 清除指定模型名称的映射缓存
   */
  async clearByName(modelName: string): Promise<ClearModelMappingCacheResponse> {
    const response = await api.delete(`/api/admin/monitoring/cache/model-mapping/${encodeURIComponent(modelName)}`)
    return response.data
  }
}
