<template>
  <PageContainer>
    <PageHeader
      title="系统设置"
      description="管理系统级别的配置和参数"
    >
      <template #actions>
        <Button
          :disabled="loading"
          @click="saveSystemConfig"
        >
          {{ loading ? '保存中...' : '保存所有配置' }}
        </Button>
      </template>
    </PageHeader>

    <div class="mt-6 space-y-6">
      <!-- 基础配置 -->
      <CardSection
        title="基础配置"
        description="配置系统默认参数"
      >
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <Label
              for="default-quota"
              class="block text-sm font-medium"
            >
              默认用户配额(美元)
            </Label>
            <Input
              id="default-quota"
              v-model.number="systemConfig.default_user_quota_usd"
              type="number"
              step="0.01"
              placeholder="10.00"
              class="mt-1"
            />
            <p class="mt-1 text-xs text-muted-foreground">
              新用户注册时的默认配额
            </p>
          </div>

          <div>
            <Label
              for="rate-limit"
              class="block text-sm font-medium"
            >
              每分钟请求限制
            </Label>
            <Input
              id="rate-limit"
              v-model.number="systemConfig.rate_limit_per_minute"
              type="number"
              placeholder="0"
              class="mt-1"
            />
            <p class="mt-1 text-xs text-muted-foreground">
              0 表示不限制
            </p>
          </div>
        </div>
      </CardSection>

      <!-- 用户注册配置 -->
      <CardSection
        title="用户注册"
        description="控制用户注册和验证"
      >
        <div class="space-y-4">
          <div class="flex items-center space-x-2">
            <Checkbox
              id="enable-registration"
              v-model:checked="systemConfig.enable_registration"
            />
            <Label
              for="enable-registration"
              class="cursor-pointer"
            >
              开放用户注册
            </Label>
          </div>

          <div class="flex items-center space-x-2">
            <Checkbox
              id="require-email-verification"
              v-model:checked="systemConfig.require_email_verification"
            />
            <Label
              for="require-email-verification"
              class="cursor-pointer"
            >
              需要邮箱验证
            </Label>
          </div>
        </div>
      </CardSection>

      <!-- API Key 管理配置 -->
      <CardSection
        title="API Key 管理"
        description="API Key 相关配置"
      >
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <Label
              for="api-key-expire"
              class="block text-sm font-medium"
            >
              API密钥过期天数
            </Label>
            <Input
              id="api-key-expire"
              v-model.number="systemConfig.api_key_expire_days"
              type="number"
              placeholder="0"
              class="mt-1"
            />
            <p class="mt-1 text-xs text-muted-foreground">
              0 表示永不过期
            </p>
          </div>

          <div class="flex items-center h-full pt-6">
            <div class="flex items-center space-x-2">
              <Checkbox
                id="auto-delete-expired-keys"
                v-model:checked="systemConfig.auto_delete_expired_keys"
              />
              <div>
                <Label
                  for="auto-delete-expired-keys"
                  class="cursor-pointer"
                >
                  自动删除过期 Key
                </Label>
                <p class="text-xs text-muted-foreground">
                  关闭时仅禁用过期 Key
                </p>
              </div>
            </div>
          </div>
        </div>
      </CardSection>

      <!-- 日志记录配置 -->
      <CardSection
        title="日志记录"
        description="控制请求日志的记录方式和内容"
      >
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <Label
              for="request-log-level"
              class="block text-sm font-medium mb-2"
            >
              记录详细程度
            </Label>
            <Select
              v-model="systemConfig.request_log_level"
              v-model:open="logLevelSelectOpen"
            >
              <SelectTrigger
                id="request-log-level"
                class="mt-1"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="basic">
                  BASIC - 基本信息 (~1KB/条)
                </SelectItem>
                <SelectItem value="headers">
                  HEADERS - 含请求头 (~2-3KB/条)
                </SelectItem>
                <SelectItem value="full">
                  FULL - 完整请求响应 (~50KB/条)
                </SelectItem>
              </SelectContent>
            </Select>
            <p class="mt-1 text-xs text-muted-foreground">
              敏感信息会自动脱敏
            </p>
          </div>

          <div>
            <Label
              for="max-request-body-size"
              class="block text-sm font-medium"
            >
              最大请求体大小 (KB)
            </Label>
            <Input
              id="max-request-body-size"
              v-model.number="maxRequestBodySizeKB"
              type="number"
              placeholder="512"
              class="mt-1"
            />
            <p class="mt-1 text-xs text-muted-foreground">
              超过此大小的请求体将被截断记录
            </p>
          </div>

          <div>
            <Label
              for="max-response-body-size"
              class="block text-sm font-medium"
            >
              最大响应体大小 (KB)
            </Label>
            <Input
              id="max-response-body-size"
              v-model.number="maxResponseBodySizeKB"
              type="number"
              placeholder="512"
              class="mt-1"
            />
            <p class="mt-1 text-xs text-muted-foreground">
              超过此大小的响应体将被截断记录
            </p>
          </div>

          <div>
            <Label
              for="sensitive-headers"
              class="block text-sm font-medium"
            >
              敏感请求头
            </Label>
            <Input
              id="sensitive-headers"
              v-model="sensitiveHeadersStr"
              placeholder="authorization, x-api-key, cookie"
              class="mt-1"
            />
            <p class="mt-1 text-xs text-muted-foreground">
              逗号分隔，这些请求头会被脱敏处理
            </p>
          </div>
        </div>
      </CardSection>

      <!-- 日志清理策略 -->
      <CardSection
        title="日志清理策略"
        description="配置日志的分级保留和自动清理"
      >
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="md:col-span-2">
            <div class="flex items-center space-x-2 mb-4">
              <Checkbox
                id="enable-auto-cleanup"
                v-model:checked="systemConfig.enable_auto_cleanup"
              />
              <Label
                for="enable-auto-cleanup"
                class="cursor-pointer"
              >
                启用自动清理任务
              </Label>
              <span class="text-xs text-muted-foreground ml-2">
                (每天凌晨执行)
              </span>
            </div>
          </div>

          <div>
            <Label
              for="detail-log-retention-days"
              class="block text-sm font-medium"
            >
              详细日志保留天数
            </Label>
            <Input
              id="detail-log-retention-days"
              v-model.number="systemConfig.detail_log_retention_days"
              type="number"
              placeholder="7"
              class="mt-1"
            />
            <p class="mt-1 text-xs text-muted-foreground">
              超过后压缩 body 字段
            </p>
          </div>

          <div>
            <Label
              for="compressed-log-retention-days"
              class="block text-sm font-medium"
            >
              压缩日志保留天数
            </Label>
            <Input
              id="compressed-log-retention-days"
              v-model.number="systemConfig.compressed_log_retention_days"
              type="number"
              placeholder="90"
              class="mt-1"
            />
            <p class="mt-1 text-xs text-muted-foreground">
              超过后删除 body 字段
            </p>
          </div>

          <div>
            <Label
              for="header-retention-days"
              class="block text-sm font-medium"
            >
              请求头保留天数
            </Label>
            <Input
              id="header-retention-days"
              v-model.number="systemConfig.header_retention_days"
              type="number"
              placeholder="90"
              class="mt-1"
            />
            <p class="mt-1 text-xs text-muted-foreground">
              超过后清空 headers 字段
            </p>
          </div>

          <div>
            <Label
              for="log-retention-days"
              class="block text-sm font-medium"
            >
              完整日志保留天数
            </Label>
            <Input
              id="log-retention-days"
              v-model.number="systemConfig.log_retention_days"
              type="number"
              placeholder="365"
              class="mt-1"
            />
            <p class="mt-1 text-xs text-muted-foreground">
              超过后删除整条记录
            </p>
          </div>

          <div>
            <Label
              for="cleanup-batch-size"
              class="block text-sm font-medium"
            >
              每批次清理记录数
            </Label>
            <Input
              id="cleanup-batch-size"
              v-model.number="systemConfig.cleanup_batch_size"
              type="number"
              placeholder="1000"
              class="mt-1"
            />
            <p class="mt-1 text-xs text-muted-foreground">
              避免单次操作过大影响性能
            </p>
          </div>
        </div>

        <!-- 清理策略说明 -->
        <div class="mt-4 p-4 bg-muted/50 rounded-lg">
          <h4 class="text-sm font-medium mb-2">
            清理策略说明
          </h4>
          <div class="text-xs text-muted-foreground space-y-1">
            <p>1. <strong>详细日志阶段</strong>: 保留完整的 request_body 和 response_body</p>
            <p>2. <strong>压缩日志阶段</strong>: body 字段被压缩存储，节省空间</p>
            <p>3. <strong>统计阶段</strong>: 仅保留 tokens、成本等统计信息</p>
            <p>4. <strong>归档删除</strong>: 超过保留期限后完全删除记录</p>
          </div>
        </div>
      </CardSection>
    </div>
  </PageContainer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Label from '@/components/ui/label.vue'
import Checkbox from '@/components/ui/checkbox.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectValue from '@/components/ui/select-value.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import { PageHeader, PageContainer, CardSection } from '@/components/layout'
import { useToast } from '@/composables/useToast'
import { adminApi } from '@/api/admin'
import { log } from '@/utils/logger'

const { success, error } = useToast()

interface SystemConfig {
  // 基础配置
  default_user_quota_usd: number
  rate_limit_per_minute: number
  // 用户注册
  enable_registration: boolean
  require_email_verification: boolean
  // API Key 管理
  api_key_expire_days: number
  auto_delete_expired_keys: boolean
  // 日志记录
  request_log_level: string
  max_request_body_size: number
  max_response_body_size: number
  sensitive_headers: string[]
  // 日志清理
  enable_auto_cleanup: boolean
  detail_log_retention_days: number
  compressed_log_retention_days: number
  header_retention_days: number
  log_retention_days: number
  cleanup_batch_size: number
}

const loading = ref(false)
const logLevelSelectOpen = ref(false)

const systemConfig = ref<SystemConfig>({
  // 基础配置
  default_user_quota_usd: 10.0,
  rate_limit_per_minute: 0,
  // 用户注册
  enable_registration: false,
  require_email_verification: false,
  // API Key 管理
  api_key_expire_days: 0,
  auto_delete_expired_keys: false,
  // 日志记录
  request_log_level: 'basic',
  max_request_body_size: 1048576,
  max_response_body_size: 1048576,
  sensitive_headers: ['authorization', 'x-api-key', 'api-key', 'cookie', 'set-cookie'],
  // 日志清理
  enable_auto_cleanup: true,
  detail_log_retention_days: 7,
  compressed_log_retention_days: 90,
  header_retention_days: 90,
  log_retention_days: 365,
  cleanup_batch_size: 1000,
})

// 计算属性：KB 和 字节 之间的转换
const maxRequestBodySizeKB = computed({
  get: () => Math.round(systemConfig.value.max_request_body_size / 1024),
  set: (val: number) => {
    systemConfig.value.max_request_body_size = val * 1024
  }
})

const maxResponseBodySizeKB = computed({
  get: () => Math.round(systemConfig.value.max_response_body_size / 1024),
  set: (val: number) => {
    systemConfig.value.max_response_body_size = val * 1024
  }
})

// 计算属性：敏感请求头数组和字符串之间的转换
const sensitiveHeadersStr = computed({
  get: () => systemConfig.value.sensitive_headers.join(', '),
  set: (val: string) => {
    systemConfig.value.sensitive_headers = val
      .split(',')
      .map(s => s.trim().toLowerCase())
      .filter(s => s.length > 0)
  }
})

onMounted(async () => {
  await loadSystemConfig()
})

async function loadSystemConfig() {
  try {
    const configs = [
      // 基础配置
      'default_user_quota_usd',
      'rate_limit_per_minute',
      // 用户注册
      'enable_registration',
      'require_email_verification',
      // API Key 管理
      'api_key_expire_days',
      'auto_delete_expired_keys',
      // 日志记录
      'request_log_level',
      'max_request_body_size',
      'max_response_body_size',
      'sensitive_headers',
      // 日志清理
      'enable_auto_cleanup',
      'detail_log_retention_days',
      'compressed_log_retention_days',
      'header_retention_days',
      'log_retention_days',
      'cleanup_batch_size',
    ]

    for (const key of configs) {
      try {
        const response = await adminApi.getSystemConfig(key)
        if (response.value !== null && response.value !== undefined) {
          (systemConfig.value as any)[key] = response.value
        }
      } catch {
        // 配置不存在时使用默认值，无需处理
      }
    }
  } catch (err) {
    error('加载系统配置失败')
    log.error('加载系统配置失败:', err)
  }
}

async function saveSystemConfig() {
  loading.value = true
  try {
    const configItems = [
      // 基础配置
      {
        key: 'default_user_quota_usd',
        value: systemConfig.value.default_user_quota_usd,
        description: '默认用户配额（美元）'
      },
      {
        key: 'rate_limit_per_minute',
        value: systemConfig.value.rate_limit_per_minute,
        description: '每分钟请求限制'
      },
      // 用户注册
      {
        key: 'enable_registration',
        value: systemConfig.value.enable_registration,
        description: '是否开放用户注册'
      },
      {
        key: 'require_email_verification',
        value: systemConfig.value.require_email_verification,
        description: '是否需要邮箱验证'
      },
      // API Key 管理
      {
        key: 'api_key_expire_days',
        value: systemConfig.value.api_key_expire_days,
        description: 'API密钥过期天数'
      },
      {
        key: 'auto_delete_expired_keys',
        value: systemConfig.value.auto_delete_expired_keys,
        description: '是否自动删除过期的API Key'
      },
      // 日志记录
      {
        key: 'request_log_level',
        value: systemConfig.value.request_log_level,
        description: '请求记录级别'
      },
      {
        key: 'max_request_body_size',
        value: systemConfig.value.max_request_body_size,
        description: '最大请求体记录大小（字节）'
      },
      {
        key: 'max_response_body_size',
        value: systemConfig.value.max_response_body_size,
        description: '最大响应体记录大小（字节）'
      },
      {
        key: 'sensitive_headers',
        value: systemConfig.value.sensitive_headers,
        description: '敏感请求头列表'
      },
      // 日志清理
      {
        key: 'enable_auto_cleanup',
        value: systemConfig.value.enable_auto_cleanup,
        description: '是否启用自动清理任务'
      },
      {
        key: 'detail_log_retention_days',
        value: systemConfig.value.detail_log_retention_days,
        description: '详细日志保留天数'
      },
      {
        key: 'compressed_log_retention_days',
        value: systemConfig.value.compressed_log_retention_days,
        description: '压缩日志保留天数'
      },
      {
        key: 'header_retention_days',
        value: systemConfig.value.header_retention_days,
        description: '请求头保留天数'
      },
      {
        key: 'log_retention_days',
        value: systemConfig.value.log_retention_days,
        description: '完整日志保留天数'
      },
      {
        key: 'cleanup_batch_size',
        value: systemConfig.value.cleanup_batch_size,
        description: '每批次清理的记录数'
      },
    ]

    const promises = configItems.map(item =>
      adminApi.updateSystemConfig(item.key, item.value, item.description)
    )

    await Promise.all(promises)
    success('系统配置已保存')
  } catch (err) {
    error('保存配置失败')
    log.error('保存配置失败:', err)
  } finally {
    loading.value = false
  }
}
</script>
