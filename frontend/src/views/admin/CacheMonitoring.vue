<script setup lang="ts">
import { ref, computed, onMounted, watch, onBeforeUnmount } from 'vue'
import Card from '@/components/ui/card.vue'
import Button from '@/components/ui/button.vue'
import Badge from '@/components/ui/badge.vue'
import Table from '@/components/ui/table.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableCell from '@/components/ui/table-cell.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableRow from '@/components/ui/table-row.vue'
import Input from '@/components/ui/input.vue'
import Pagination from '@/components/ui/pagination.vue'
import RefreshButton from '@/components/ui/refresh-button.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import SelectValue from '@/components/ui/select-value.vue'
import ScatterChart from '@/components/charts/ScatterChart.vue'
import { Trash2, Eraser, Search, X, BarChart3, ChevronDown, ChevronRight } from 'lucide-vue-next'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { cacheApi, type CacheStats, type CacheConfig, type UserAffinity } from '@/api/cache'
import type { TTLAnalysisUser } from '@/api/cache'
import { formatNumber, formatTokens, formatCost, formatRemainingTime } from '@/utils/format'
import {
  useTTLAnalysis,
  ANALYSIS_HOURS_OPTIONS,
  getTTLBadgeVariant,
  getFrequencyLabel,
  getFrequencyClass
} from '@/composables/useTTLAnalysis'
import { log } from '@/utils/logger'

// ==================== 缓存统计与亲和性列表 ====================

const stats = ref<CacheStats | null>(null)
const config = ref<CacheConfig | null>(null)
const loading = ref(false)
const affinityList = ref<UserAffinity[]>([])
const listLoading = ref(false)
const tableKeyword = ref('')
const matchedUserId = ref<string | null>(null)
const clearingRowAffinityKey = ref<string | null>(null)
const currentPage = ref(1)
const pageSize = ref(20)
const currentTime = ref(Math.floor(Date.now() / 1000))

const { success: showSuccess, error: showError, info: showInfo } = useToast()
const { confirm: showConfirm } = useConfirm()

let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null
let skipNextKeywordWatch = false
let countdownTimer: ReturnType<typeof setInterval> | null = null

// ==================== TTL 分析 (使用 composable) ====================

const {
  ttlAnalysis,
  hitAnalysis,
  ttlAnalysisLoading,
  analysisHours,
  expandedUserId,
  userTimelineData,
  userTimelineLoading,
  userTimelineChartData,
  toggleUserExpand,
  refreshAnalysis
} = useTTLAnalysis()

// ==================== 计算属性 ====================

const paginatedAffinityList = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return affinityList.value.slice(start, end)
})

// ==================== 缓存统计方法 ====================

async function fetchCacheStats() {
  loading.value = true
  try {
    stats.value = await cacheApi.getStats()
  } catch (error) {
    showError('获取缓存统计失败')
    log.error('获取缓存统计失败', error)
  } finally {
    loading.value = false
  }
}

async function fetchCacheConfig() {
  try {
    config.value = await cacheApi.getConfig()
  } catch (error) {
    log.error('获取缓存配置失败', error)
  }
}

async function fetchAffinityList(keyword?: string) {
  listLoading.value = true
  try {
    const response = await cacheApi.listAffinities(keyword)
    affinityList.value = response.items
    matchedUserId.value = response.matched_user_id ?? null

    if (keyword && response.total === 0) {
      showInfo('未找到匹配的缓存记录')
    }
  } catch (error) {
    showError('获取缓存列表失败')
    log.error('获取缓存列表失败', error)
  } finally {
    listLoading.value = false
  }
}

async function resetAffinitySearch() {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }

  if (!tableKeyword.value) {
    currentPage.value = 1
    await fetchAffinityList()
    return
  }

  skipNextKeywordWatch = true
  tableKeyword.value = ''
  currentPage.value = 1
  await fetchAffinityList()
}

async function clearUserCache(identifier: string, displayName?: string) {
  const target = identifier?.trim()
  if (!target) {
    showError('无法识别标识符')
    return
  }

  const label = displayName || target
  const confirmed = await showConfirm({
    title: '确认清除',
    message: `确定要清除 ${label} 的缓存吗？`,
    confirmText: '确认清除',
    variant: 'destructive'
  })

  if (!confirmed) return

  clearingRowAffinityKey.value = target
  try {
    await cacheApi.clearUserCache(target)
    showSuccess('清除成功')
    await fetchCacheStats()
    await fetchAffinityList(tableKeyword.value.trim() || undefined)
  } catch (error) {
    showError('清除失败')
    log.error('清除用户缓存失败', error)
  } finally {
    clearingRowAffinityKey.value = null
  }
}

async function clearAllCache() {
  const firstConfirm = await showConfirm({
    title: '危险操作',
    message: '警告：此操作会清除所有用户的缓存亲和性，确定继续吗？',
    confirmText: '继续',
    variant: 'destructive'
  })
  if (!firstConfirm) return

  const secondConfirm = await showConfirm({
    title: '再次确认',
    message: '这将影响所有用户，请再次确认！',
    confirmText: '确认清除',
    variant: 'destructive'
  })
  if (!secondConfirm) return

  try {
    await cacheApi.clearAllCache()
    showSuccess('已清除所有缓存')
    await fetchCacheStats()
    await fetchAffinityList(tableKeyword.value.trim() || undefined)
  } catch (error) {
    showError('清除失败')
    log.error('清除所有缓存失败', error)
  }
}

// ==================== 工具方法 ====================

function getRemainingTime(expireAt?: number): string {
  return formatRemainingTime(expireAt, currentTime.value)
}

function formatIntervalDescription(user: TTLAnalysisUser): string {
  const p90 = user.percentiles.p90
  if (p90 === null || p90 === undefined) return '-'
  if (p90 < 1) {
    const seconds = Math.round(p90 * 60)
    return `90% 请求间隔 < ${seconds} 秒`
  }
  return `90% 请求间隔 < ${p90.toFixed(1)} 分钟`
}

function handlePageChange() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

// ==================== 定时器管理 ====================

function startCountdown() {
  if (countdownTimer) clearInterval(countdownTimer)

  countdownTimer = setInterval(() => {
    currentTime.value = Math.floor(Date.now() / 1000)

    const beforeCount = affinityList.value.length
    affinityList.value = affinityList.value.filter(
      item => item.expire_at && item.expire_at > currentTime.value
    )

    if (beforeCount > affinityList.value.length) {
      const removedCount = beforeCount - affinityList.value.length
      showInfo(`${removedCount} 个缓存已自动过期移除`)
    }
  }, 1000)
}

function stopCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

// ==================== 刷新所有数据 ====================

async function refreshData() {
  await Promise.all([
    fetchCacheStats(),
    fetchCacheConfig(),
    fetchAffinityList()
  ])
}

// ==================== 生命周期 ====================

watch(tableKeyword, (value) => {
  if (skipNextKeywordWatch) {
    skipNextKeywordWatch = false
    return
  }

  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)

  const keyword = value.trim()
  searchDebounceTimer = setTimeout(() => {
    fetchAffinityList(keyword || undefined)
    searchDebounceTimer = null
  }, 600)
})

onMounted(() => {
  fetchCacheStats()
  fetchCacheConfig()
  fetchAffinityList()
  startCountdown()
  refreshAnalysis()
})

onBeforeUnmount(() => {
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
  stopCountdown()
})
</script>

<template>
  <div class="space-y-6">
    <!-- 标题 -->
    <div>
      <h2 class="text-2xl font-bold">
        缓存监控
      </h2>
      <p class="text-sm text-muted-foreground mt-1">
        管理缓存亲和性，提高 Prompt Caching 命中率
      </p>
    </div>

    <!-- 亲和性系统状态 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <Card class="p-4">
        <div class="text-xs text-muted-foreground">
          活跃亲和性
        </div>
        <div class="text-2xl font-bold mt-1">
          {{ stats?.affinity_stats?.active_affinities || 0 }}
        </div>
        <div class="text-xs text-muted-foreground mt-1">
          TTL {{ config?.cache_ttl_seconds || 300 }}s
        </div>
      </Card>

      <Card class="p-4">
        <div class="text-xs text-muted-foreground">
          Provider 切换
        </div>
        <div
          class="text-2xl font-bold mt-1"
          :class="(stats?.affinity_stats?.provider_switches || 0) > 0 ? 'text-destructive' : ''"
        >
          {{ stats?.affinity_stats?.provider_switches || 0 }}
        </div>
        <div class="text-xs text-muted-foreground mt-1">
          Key 切换 {{ stats?.affinity_stats?.key_switches || 0 }}
        </div>
      </Card>

      <Card class="p-4">
        <div class="text-xs text-muted-foreground">
          缓存失效
        </div>
        <div
          class="text-2xl font-bold mt-1"
          :class="(stats?.affinity_stats?.cache_invalidations || 0) > 0 ? 'text-warning' : ''"
        >
          {{ stats?.affinity_stats?.cache_invalidations || 0 }}
        </div>
        <div class="text-xs text-muted-foreground mt-1">
          因 Provider 不可用
        </div>
      </Card>

      <Card class="p-4">
        <div class="text-xs text-muted-foreground flex items-center gap-1">
          预留比例
          <Badge
            v-if="config?.dynamic_reservation?.enabled"
            variant="outline"
            class="text-[10px] px-1"
          >
            动态
          </Badge>
        </div>
        <div class="text-2xl font-bold mt-1">
          <template v-if="config?.dynamic_reservation?.enabled">
            {{ (config.dynamic_reservation.config.stable_min_reservation * 100).toFixed(0) }}-{{ (config.dynamic_reservation.config.stable_max_reservation * 100).toFixed(0) }}%
          </template>
          <template v-else>
            {{ config ? (config.cache_reservation_ratio * 100).toFixed(0) : '30' }}%
          </template>
        </div>
        <div class="text-xs text-muted-foreground mt-1">
          当前 {{ stats ? (stats.cache_reservation_ratio * 100).toFixed(0) : '-' }}%
        </div>
      </Card>
    </div>

    <!-- 缓存亲和性列表 -->
    <Card class="overflow-hidden">
      <div class="px-6 py-3 border-b border-border/60">
        <div class="flex items-center justify-between gap-4">
          <div class="flex items-center gap-3">
            <h3 class="text-base font-semibold">
              亲和性列表
            </h3>
          </div>
          <div class="flex items-center gap-2">
            <div class="relative">
              <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground z-10 pointer-events-none" />
              <Input
                id="cache-affinity-search"
                v-model="tableKeyword"
                placeholder="搜索用户或 Key"
                class="w-48 h-8 text-sm pl-8 pr-8"
              />
              <button
                v-if="tableKeyword"
                type="button"
                class="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground z-10"
                @click="resetAffinitySearch"
              >
                <X class="h-3.5 w-3.5" />
              </button>
            </div>
            <div class="h-4 w-px bg-border" />
            <Button
              variant="ghost"
              size="icon"
              class="h-8 w-8 text-muted-foreground/70 hover:text-destructive"
              title="清除全部缓存"
              @click="clearAllCache"
            >
              <Eraser class="h-4 w-4" />
            </Button>
            <RefreshButton
              :loading="loading || listLoading"
              @click="refreshData"
            />
          </div>
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead class="w-36">
              用户
            </TableHead>
            <TableHead class="w-28">
              Key
            </TableHead>
            <TableHead class="w-28">
              Provider
            </TableHead>
            <TableHead class="w-40">
              模型
            </TableHead>
            <TableHead class="w-36">
              API 格式 / Key
            </TableHead>
            <TableHead class="w-20 text-center">
              剩余
            </TableHead>
            <TableHead class="w-14 text-center">
              次数
            </TableHead>
            <TableHead class="w-12 text-right">
              操作
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody v-if="!listLoading && affinityList.length">
          <TableRow
            v-for="item in paginatedAffinityList"
            :key="`${item.affinity_key}-${item.endpoint_id}-${item.key_id}`"
          >
            <TableCell>
              <div class="flex items-center gap-1.5">
                <Badge
                  v-if="item.is_standalone"
                  variant="outline"
                  class="text-warning border-warning/30 text-[10px] px-1"
                >
                  独立
                </Badge>
                <span
                  class="text-sm font-medium truncate max-w-[120px]"
                  :title="item.username ?? undefined"
                >{{ item.username || '未知' }}</span>
              </div>
            </TableCell>
            <TableCell>
              <div class="flex items-center gap-1.5">
                <span
                  class="text-sm truncate max-w-[80px]"
                  :title="item.user_api_key_name || undefined"
                >{{ item.user_api_key_name || '未命名' }}</span>
                <Badge
                  v-if="item.rate_multiplier !== 1.0"
                  variant="outline"
                  class="text-warning border-warning/30 text-[10px] px-2"
                >
                  {{ item.rate_multiplier }}x
                </Badge>
              </div>
              <div class="text-xs text-muted-foreground font-mono">
                {{ item.user_api_key_prefix || '---' }}
              </div>
            </TableCell>
            <TableCell>
              <div
                class="text-sm truncate max-w-[100px]"
                :title="item.provider_name || undefined"
              >
                {{ item.provider_name || '未知' }}
              </div>
            </TableCell>
            <TableCell>
              <div
                class="text-sm truncate max-w-[150px]"
                :title="item.model_display_name || undefined"
              >
                {{ item.model_display_name || '---' }}
              </div>
              <div
                class="text-xs text-muted-foreground"
                :title="item.model_name || undefined"
              >
                {{ item.model_name || '---' }}
              </div>
            </TableCell>
            <TableCell>
              <div class="text-sm">
                {{ item.endpoint_api_format || '---' }}
              </div>
              <div class="text-xs text-muted-foreground font-mono">
                {{ item.key_prefix || '---' }}
              </div>
            </TableCell>
            <TableCell class="text-center">
              <span class="text-xs">{{ getRemainingTime(item.expire_at) }}</span>
            </TableCell>
            <TableCell class="text-center">
              <span class="text-sm">{{ item.request_count }}</span>
            </TableCell>
            <TableCell class="text-right">
              <Button
                size="icon"
                variant="ghost"
                class="h-7 w-7 text-muted-foreground/70 hover:text-destructive"
                :disabled="clearingRowAffinityKey === item.affinity_key"
                title="清除缓存"
                @click="clearUserCache(item.affinity_key, item.user_api_key_name || item.affinity_key)"
              >
                <Trash2 class="h-3.5 w-3.5" />
              </Button>
            </TableCell>
          </TableRow>
        </TableBody>
        <TableBody v-else>
          <TableRow>
            <TableCell
              colspan="8"
              class="text-center py-6 text-sm text-muted-foreground"
            >
              {{ listLoading ? '加载中...' : '暂无缓存记录' }}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>

      <Pagination
        v-if="affinityList.length > 0"
        :current="currentPage"
        :total="affinityList.length"
        :page-size="pageSize"
        @update:current="currentPage = $event; handlePageChange()"
        @update:page-size="pageSize = $event"
      />
    </Card>

    <!-- TTL 分析区域 -->
    <Card class="overflow-hidden">
      <div class="px-6 py-3 border-b border-border/60">
        <div class="flex items-center justify-between gap-4">
          <div class="flex items-center gap-3">
            <BarChart3 class="h-5 w-5 text-muted-foreground" />
            <h3 class="text-base font-semibold">
              TTL 分析
            </h3>
            <span class="text-xs text-muted-foreground">分析用户请求间隔，推荐合适的缓存 TTL</span>
          </div>
          <div class="flex items-center gap-2">
            <Select v-model="analysisHours">
              <SelectTrigger class="w-28 h-8">
                <SelectValue placeholder="时间段" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem
                  v-for="option in ANALYSIS_HOURS_OPTIONS"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <!-- 缓存命中概览 -->
      <div
        v-if="hitAnalysis"
        class="px-6 py-4 border-b border-border/40 bg-muted/30"
      >
        <div class="grid grid-cols-2 md:grid-cols-5 gap-6">
          <div>
            <div class="text-xs text-muted-foreground">
              请求命中率
            </div>
            <div class="text-2xl font-bold text-success">
              {{ hitAnalysis.request_cache_hit_rate }}%
            </div>
            <div class="text-xs text-muted-foreground">
              {{ formatNumber(hitAnalysis.requests_with_cache_hit) }} / {{ formatNumber(hitAnalysis.total_requests) }} 请求
            </div>
          </div>
          <div>
            <div class="text-xs text-muted-foreground">
              Token 命中率
            </div>
            <div class="text-2xl font-bold">
              {{ hitAnalysis.token_cache_hit_rate }}%
            </div>
            <div class="text-xs text-muted-foreground">
              {{ formatTokens(hitAnalysis.total_cache_read_tokens) }} tokens 命中
            </div>
          </div>
          <div>
            <div class="text-xs text-muted-foreground">
              缓存创建费用
            </div>
            <div class="text-2xl font-bold">
              {{ formatCost(hitAnalysis.total_cache_creation_cost_usd) }}
            </div>
            <div class="text-xs text-muted-foreground">
              {{ formatTokens(hitAnalysis.total_cache_creation_tokens) }} tokens
            </div>
          </div>
          <div>
            <div class="text-xs text-muted-foreground">
              缓存读取费用
            </div>
            <div class="text-2xl font-bold">
              {{ formatCost(hitAnalysis.total_cache_read_cost_usd) }}
            </div>
            <div class="text-xs text-muted-foreground">
              {{ formatTokens(hitAnalysis.total_cache_read_tokens) }} tokens
            </div>
          </div>
          <div>
            <div class="text-xs text-muted-foreground">
              预估节省
            </div>
            <div class="text-2xl font-bold text-success">
              {{ formatCost(hitAnalysis.estimated_savings_usd) }}
            </div>
          </div>
        </div>
      </div>

      <!-- 用户 TTL 分析表格 -->
      <Table v-if="ttlAnalysis && ttlAnalysis.users.length > 0">
        <TableHeader>
          <TableRow>
            <TableHead class="w-10" />
            <TableHead class="w-[20%]">
              用户
            </TableHead>
            <TableHead class="w-[15%] text-center">
              请求数
            </TableHead>
            <TableHead class="w-[15%] text-center">
              使用频率
            </TableHead>
            <TableHead class="w-[15%] text-center">
              推荐 TTL
            </TableHead>
            <TableHead>说明</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <template
            v-for="user in ttlAnalysis.users"
            :key="user.group_id"
          >
            <TableRow
              class="cursor-pointer hover:bg-muted/50"
              @click="toggleUserExpand(user.group_id)"
            >
              <TableCell class="p-2">
                <button class="p-1 hover:bg-muted rounded">
                  <ChevronDown
                    v-if="expandedUserId === user.group_id"
                    class="h-4 w-4 text-muted-foreground"
                  />
                  <ChevronRight
                    v-else
                    class="h-4 w-4 text-muted-foreground"
                  />
                </button>
              </TableCell>
              <TableCell>
                <span class="text-sm font-medium">{{ user.username || '未知用户' }}</span>
              </TableCell>
              <TableCell class="text-center">
                <span class="text-sm font-medium">{{ user.request_count }}</span>
              </TableCell>
              <TableCell class="text-center">
                <span
                  class="text-sm"
                  :class="getFrequencyClass(user.recommended_ttl_minutes)"
                >
                  {{ getFrequencyLabel(user.recommended_ttl_minutes) }}
                </span>
              </TableCell>
              <TableCell class="text-center">
                <Badge :variant="getTTLBadgeVariant(user.recommended_ttl_minutes)">
                  {{ user.recommended_ttl_minutes }} 分钟
                </Badge>
              </TableCell>
              <TableCell>
                <span class="text-xs text-muted-foreground">
                  {{ formatIntervalDescription(user) }}
                </span>
              </TableCell>
            </TableRow>
            <!-- 展开行：显示用户散点图 -->
            <TableRow
              v-if="expandedUserId === user.group_id"
              class="bg-muted/30"
            >
              <TableCell
                colspan="6"
                class="p-0"
              >
                <div class="px-6 py-4">
                  <div class="flex items-center justify-between mb-3">
                    <h4 class="text-sm font-medium">
                      请求间隔时间线
                    </h4>
                    <div class="flex items-center gap-3 text-xs text-muted-foreground">
                      <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-green-500" /> 0-5分钟</span>
                      <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-blue-500" /> 5-15分钟</span>
                      <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-purple-500" /> 15-30分钟</span>
                      <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-orange-500" /> 30-60分钟</span>
                      <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-red-500" /> >60分钟</span>
                      <span
                        v-if="userTimelineData"
                        class="ml-2"
                      >共 {{ userTimelineData.total_points }} 个数据点</span>
                    </div>
                  </div>
                  <div
                    v-if="userTimelineLoading"
                    class="h-64 flex items-center justify-center"
                  >
                    <span class="text-sm text-muted-foreground">加载中...</span>
                  </div>
                  <div
                    v-else-if="userTimelineData && userTimelineData.points.length > 0"
                    class="h-64"
                  >
                    <ScatterChart :data="userTimelineChartData" />
                  </div>
                  <div
                    v-else
                    class="h-64 flex items-center justify-center"
                  >
                    <span class="text-sm text-muted-foreground">暂无数据</span>
                  </div>
                </div>
              </TableCell>
            </TableRow>
          </template>
        </TableBody>
      </Table>

      <!-- 分析完成但无数据 -->
      <div
        v-else-if="ttlAnalysis && ttlAnalysis.users.length === 0"
        class="px-6 py-12 text-center"
      >
        <BarChart3 class="h-12 w-12 text-muted-foreground/50 mx-auto mb-3" />
        <p class="text-sm text-muted-foreground">
          未找到符合条件的用户数据
        </p>
        <p class="text-xs text-muted-foreground mt-1">
          尝试增加分析天数或降低最小请求数阈值
        </p>
      </div>

      <!-- 加载中 -->
      <div
        v-else-if="ttlAnalysisLoading"
        class="px-6 py-12 text-center"
      >
        <p class="text-sm text-muted-foreground">
          正在分析用户请求数据...
        </p>
      </div>
    </Card>
  </div>
</template>
