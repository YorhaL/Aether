import apiClient from './client'

// 异步任务状态
export type AsyncTaskStatus = 'pending' | 'submitted' | 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'

// 异步任务类型
export type AsyncTaskType = 'video'

// 异步任务列表项
export interface AsyncTaskItem {
  id: string
  external_task_id: string
  user_id: string
  username: string
  task_type: AsyncTaskType
  model: string
  prompt: string
  status: AsyncTaskStatus
  progress_percent: number
  progress_message: string | null
  provider_id: string
  provider_name: string
  duration_seconds: number
  resolution: string
  aspect_ratio: string
  video_url: string | null
  error_code: string | null
  error_message: string | null
  poll_count: number
  max_poll_count: number
  created_at: string
  completed_at: string | null
  submitted_at: string | null
}

// 候选 Key 信息
export interface CandidateKeyInfo {
  index: number
  provider_id: string
  provider_name: string
  endpoint_id: string
  key_id: string
  key_name: string | null
  auth_type: string
  has_billing_rule: boolean
  priority: number
  selected?: boolean
}

// 请求元数据
export interface AsyncTaskRequestMetadata {
  candidate_keys: CandidateKeyInfo[]
  selected_key_id: string
  selected_endpoint_id: string
  client_ip: string
  user_agent: string
  request_id: string
  request_headers?: Record<string, string>
  poll_raw_response?: any  // 轮询完成时的原始响应
  billing_snapshot?: any   // 计费快照
}

// 异步任务详情
export interface AsyncTaskDetail extends AsyncTaskItem {
  api_key_id: string
  endpoint_id: string
  key_id: string
  client_api_format: string
  provider_api_format: string
  format_converted: boolean
  original_request_body: any
  converted_request_body: any
  size: string | null
  video_urls: string[] | null
  thumbnail_url: string | null
  video_size_bytes: number | null
  video_duration_seconds: number | null  // 实际视频时长（秒）
  video_expires_at: string | null
  stored_video_path: string | null
  storage_provider: string | null
  retry_count: number
  max_retries: number
  poll_interval_seconds: number
  next_poll_at: string | null
  updated_at: string | null
  endpoint: {
    id: string
    base_url: string
    api_format: string
  } | null
  request_metadata: AsyncTaskRequestMetadata | null
}

// 异步任务列表响应
export interface AsyncTaskListResponse {
  items: AsyncTaskItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

// 异步任务统计响应
export interface AsyncTaskStatsResponse {
  total: number
  by_status: Record<AsyncTaskStatus, number>
  by_model: Record<string, number>
  today_count: number
  active_users?: number  // 仅管理员
  processing_count?: number  // 仅管理员
}

// 异步任务查询参数
export interface AsyncTaskQueryParams {
  status?: AsyncTaskStatus
  task_type?: AsyncTaskType
  user_id?: string
  model?: string
  page?: number
  page_size?: number
}

export const asyncTasksApi = {
  /**
   * 获取异步任务列表
   */
  async list(params: AsyncTaskQueryParams = {}): Promise<AsyncTaskListResponse> {
    const searchParams = new URLSearchParams()
    if (params.status) searchParams.append('status', params.status)
    if (params.task_type) searchParams.append('task_type', params.task_type)
    if (params.user_id) searchParams.append('user_id', params.user_id)
    if (params.model) searchParams.append('model', params.model)
    if (params.page) searchParams.append('page', params.page.toString())
    if (params.page_size) searchParams.append('page_size', params.page_size.toString())

    const query = searchParams.toString()
    // 后端 API 路径保持不变，前端抽象为异步任务
    const url = query ? `/api/admin/video-tasks?${query}` : '/api/admin/video-tasks'
    const response = await apiClient.get(url)
    return response.data
  },

  /**
   * 获取异步任务统计
   */
  async getStats(): Promise<AsyncTaskStatsResponse> {
    const response = await apiClient.get('/api/admin/video-tasks/stats')
    return response.data
  },

  /**
   * 获取异步任务详情
   */
  async getDetail(taskId: string): Promise<AsyncTaskDetail> {
    const response = await apiClient.get(`/api/admin/video-tasks/${taskId}`)
    return response.data
  },

  /**
   * 取消异步任务
   */
  async cancel(taskId: string): Promise<{ id: string; status: string; message: string }> {
    const response = await apiClient.post(`/api/admin/video-tasks/${taskId}/cancel`)
    return response.data
  },
}

export default asyncTasksApi
