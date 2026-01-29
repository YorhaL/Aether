<template>
  <Dialog
    :open="open"
    title="用户认证"
    description="配置提供商的用户认证信息，用于余额查询、签到等操作"
    :icon="KeyRound"
    size="md"
    @update:open="$emit('update:open', $event)"
  >
    <form
      :name="`provider-auth-${Date.now()}`"
      autocomplete="off"
      @submit.prevent
    >
      <!-- 加载状态 -->
      <div
        v-if="isLoadingConfig"
        class="flex items-center justify-center py-8"
      >
        <div class="text-sm text-muted-foreground">
          加载配置中...
        </div>
      </div>
      <div
        v-else
        class="space-y-4"
      >
        <!-- 认证模板选择 -->
        <div class="space-y-2">
          <Label>认证模板</Label>
          <Select
            v-model="selectedTemplateId"
            v-model:open="templateSelectOpen"
            @update:model-value="handleTemplateChange"
          >
            <SelectTrigger>
              <SelectValue placeholder="选择认证模板" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                v-for="template in templates"
                :key="template.id"
                :value="template.id"
              >
                {{ template.name }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <!-- 动态表单字段 -->
        <template v-if="selectedTemplate">
          <template
            v-for="(group, groupIndex) in fieldGroups"
            :key="groupIndex"
          >
            <!-- 可折叠的分组（如代理配置） -->
            <div
              v-if="group.collapsible && group.hasToggle && group.toggleKey"
              class="space-y-2"
            >
              <!-- 标题栏：标题在左，开关在右（在卡片外） -->
              <div class="flex items-center justify-between">
                <span class="text-sm font-medium text-foreground">{{ group.title }}</span>
                <div class="flex items-center gap-2">
                  <span class="text-xs text-muted-foreground">启用代理</span>
                  <Switch
                    :model-value="formData[group.toggleKey] || false"
                    @update:model-value="formData[group.toggleKey] = $event"
                  />
                </div>
              </div>

              <!-- 展开内容（卡片） -->
              <div
                v-if="formData[group.toggleKey]"
                class="rounded-lg border border-border bg-muted/30 px-4 py-3"
              >
                <!-- 横向排列的字段：代理地址占更多空间 -->
                <div class="flex gap-3">
                  <div
                    v-for="(field, fieldIndex) in group.fields"
                    :key="field.key"
                    class="space-y-1"
                    :class="fieldIndex === 0 ? 'flex-[2]' : 'flex-1'"
                  >
                    <Label class="text-xs text-muted-foreground">
                      {{ field.label }}
                    </Label>

                    <!-- 文本输入 -->
                    <Input
                      v-if="field.type === 'text'"
                      v-model="formData[field.key]"
                      :placeholder="field.sensitive ? (sensitivePlaceholders[field.key] || field.placeholder) : field.placeholder"
                      :masked="field.sensitive"
                      disable-autofill
                      class="h-8 text-sm"
                      @update:model-value="handleFieldChange(field.key, $event)"
                    />

                    <!-- 密码/敏感输入 -->
                    <Input
                      v-else-if="field.type === 'password'"
                      v-model="formData[field.key]"
                      :placeholder="sensitivePlaceholders[field.key] || field.placeholder"
                      masked
                      class="h-8 text-sm"
                      @update:model-value="handleFieldChange(field.key, $event)"
                    />
                  </div>
                </div>
              </div>
            </div>

            <!-- 普通分组（非折叠） -->
            <template v-else>
              <!-- 分组标题 -->
              <div
                v-if="group.title"
                class="pt-2 text-sm font-medium text-muted-foreground"
              >
                {{ group.title }}
              </div>

              <!-- inline 布局：字段横向排列 -->
              <div
                v-if="group.layout === 'inline'"
                class="flex gap-3"
              >
                <div
                  v-for="field in group.fields"
                  :key="field.key"
                  class="space-y-2"
                  :style="{ flex: field.flex || 1 }"
                >
                  <Label>
                    {{ field.label }}
                    <span
                      v-if="field.required"
                      class="text-muted-foreground/70"
                    >*</span>
                  </Label>

                  <!-- 文本输入 -->
                  <Input
                    v-if="field.type === 'text'"
                    v-model="formData[field.key]"
                    :placeholder="field.sensitive ? (sensitivePlaceholders[field.key] || field.placeholder) : field.placeholder"
                    :masked="field.sensitive"
                    disable-autofill
                    @update:model-value="handleFieldChange(field.key, $event)"
                  />

                  <!-- 密码/敏感输入 -->
                  <Input
                    v-else-if="field.type === 'password'"
                    v-model="formData[field.key]"
                    :placeholder="sensitivePlaceholders[field.key] || field.placeholder"
                    masked
                    @update:model-value="handleFieldChange(field.key, $event)"
                  />
                </div>
              </div>

              <!-- vertical 布局（默认）：字段垂直排列 -->
              <template v-else>
                <div
                  v-for="field in group.fields"
                  :key="field.key"
                  class="space-y-2"
                >
                  <Label>
                    {{ field.label }}
                    <span
                      v-if="field.required"
                      class="text-muted-foreground/70"
                    >*</span>
                  </Label>

                  <!-- 文本输入 -->
                  <Input
                    v-if="field.type === 'text'"
                    v-model="formData[field.key]"
                    :placeholder="field.sensitive ? (sensitivePlaceholders[field.key] || field.placeholder) : field.placeholder"
                    :masked="field.sensitive"
                    disable-autofill
                    @update:model-value="handleFieldChange(field.key, $event)"
                  />

                  <!-- 密码/敏感输入 -->
                  <Input
                    v-else-if="field.type === 'password'"
                    v-model="formData[field.key]"
                    :placeholder="sensitivePlaceholders[field.key] || field.placeholder"
                    masked
                    @update:model-value="handleFieldChange(field.key, $event)"
                  />

                  <!-- 下拉选择 -->
                  <Select
                    v-else-if="field.type === 'select'"
                    v-model="formData[field.key]"
                    @update:model-value="handleFieldChange(field.key, $event)"
                  >
                    <SelectTrigger>
                      <SelectValue :placeholder="field.placeholder || '请选择'" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem
                        v-for="option in field.options"
                        :key="option.value"
                        :value="option.value"
                      >
                        {{ option.label }}
                      </SelectItem>
                    </SelectContent>
                  </Select>

                  <!-- 多行文本 -->
                  <Textarea
                    v-else-if="field.type === 'textarea'"
                    v-model="formData[field.key]"
                    :placeholder="field.placeholder"
                    rows="3"
                    @update:model-value="handleFieldChange(field.key, $event)"
                  />

                  <!-- 帮助文本 -->
                  <p
                    v-if="field.helpText"
                    class="text-xs text-muted-foreground"
                  >
                    {{ field.helpText }}
                  </p>
                </div>
              </template>
            </template>
          </template>
        </template>
      </div>
    </form>

    <template #footer>
      <Button
        variant="outline"
        @click="$emit('update:open', false)"
      >
        取消
      </Button>
      <Button
        :disabled="isSaving || !canSave"
        @click="handleSave"
      >
        {{ isSaving ? '保存中...' : '保存' }}
      </Button>
      <Button
        variant="outline"
        :disabled="isVerifying || !canVerify"
        @click="handleVerify"
      >
        {{ isVerifying ? '验证中...' : '验证' }}
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { KeyRound } from 'lucide-vue-next'
import {
  Dialog,
  Button,
  Input,
  Label,
  Textarea,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Switch,
} from '@/components/ui'
import { saveProviderOpsConfig, verifyProviderAuth, getProviderOpsConfig } from '@/api/providerOps'
import { useToast } from '@/composables/useToast'
import {
  authTemplateRegistry,
  type AuthTemplate,
  type AuthTemplateFieldGroup,
} from '../auth-templates'

const props = defineProps<{
  open: boolean
  providerId: string
  providerWebsite?: string
  currentConfig?: any
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'saved'): void
}>()

// 敏感字段列表（用于验证和加载配置时的特殊处理）
const SENSITIVE_FIELDS = ['api_key', 'password', 'session_token', 'session_cookie', 'token_cookie', 'auth_cookie', 'cookie_string', 'cookie', 'proxy_password'] as const

const { success: showSuccess, error: showError } = useToast()

// State
const isSaving = ref(false)
const isVerifying = ref(false)
const isLoadingConfig = ref(false)
const verifyStatus = ref<'success' | 'error' | null>(null)
const formChanged = ref(false)

// 敏感字段的 placeholder（存储脱敏后的已保存值）
const sensitivePlaceholders = ref<Record<string, string>>({})
// 是否有已保存的配置（编辑模式）
const hasExistingConfig = ref(false)

// Select 下拉框状态
const templateSelectOpen = ref(false)

// 模板选择
const selectedTemplateId = ref('new_api')
const formData = ref<Record<string, any>>({})

// 表单是否可以验证（必填字段已填写）
const canVerify = computed(() => {
  const template = selectedTemplate.value
  if (!template) return false

  // 编辑模式下，敏感字段可以为空（使用已保存的值）
  if (hasExistingConfig.value) {
    // 创建一个临时数据，把空的敏感字段填充为占位值以通过验证
    const tempData = { ...formData.value }
    for (const field of SENSITIVE_FIELDS) {
      if (!tempData[field] && sensitivePlaceholders.value[field]) {
        tempData[field] = 'placeholder'
      }
    }
    const error = template.validate(tempData)
    if (error) return false
  } else {
    const error = template.validate(formData.value)
    if (error) return false
  }

  const effectiveBaseUrl = formData.value.base_url || props.providerWebsite
  return !!effectiveBaseUrl
})

// 保存按钮是否可用：验证成功且表单未变动
const canSave = computed(() => {
  return verifyStatus.value === 'success' && !formChanged.value
})

// Computed
const templates = computed(() => authTemplateRegistry.getAll())

const selectedTemplate = computed<AuthTemplate | undefined>(() => {
  return authTemplateRegistry.get(selectedTemplateId.value)
})

const fieldGroups = computed<AuthTemplateFieldGroup[]>(() => {
  if (!selectedTemplate.value) return []
  return selectedTemplate.value.getFields(props.providerWebsite)
})

// Methods
function handleTemplateChange() {
  // 重置表单数据
  resetFormData()
  // 重置验证状态
  verifyStatus.value = null
  formChanged.value = true
}

function handleFieldChange(fieldKey: string, value: any) {
  // 标记表单已变动
  formChanged.value = true

  // 调用模板的 onFieldChange 回调
  const template = selectedTemplate.value
  if (template?.onFieldChange) {
    template.onFieldChange(fieldKey, value, formData.value)
  }
}

// 监听 formData 变化，验证成功后的修改需要重新验证
watch(
  formData,
  () => {
    // 验证成功后任何修改都需要重新验证
    if (verifyStatus.value === 'success') {
      formChanged.value = true
    }
  },
  { deep: true }
)

function resetFormData() {
  const template = selectedTemplate.value
  if (!template) {
    formData.value = {}
    return
  }

  // 初始化表单数据，设置默认值
  const data: Record<string, any> = {}
  const groups = template.getFields(props.providerWebsite)

  for (const group of groups) {
    for (const field of group.fields) {
      data[field.key] = field.defaultValue ?? ''
    }
  }

  formData.value = data
}

function formatQuota(quota: number): string {
  const template = selectedTemplate.value
  if (template?.formatQuota) {
    return template.formatQuota(quota)
  }
  // 默认格式化
  return quota.toLocaleString()
}

async function handleVerify() {
  const template = selectedTemplate.value
  if (!template) return

  // 验证表单（编辑模式下敏感字段可以为空）
  let dataToValidate = formData.value
  if (hasExistingConfig.value) {
    dataToValidate = { ...formData.value }
    for (const field of SENSITIVE_FIELDS) {
      if (!dataToValidate[field] && sensitivePlaceholders.value[field]) {
        dataToValidate[field] = 'placeholder'
      }
    }
  }
  const error = template.validate(dataToValidate)
  if (error) {
    showError(error)
    return
  }

  // 检查 base_url
  const effectiveBaseUrl = formData.value.base_url || props.providerWebsite
  if (!effectiveBaseUrl) {
    showError('请填写 API 地址')
    return
  }

  isVerifying.value = true

  try {
    const request = template.buildRequest(formData.value, props.providerWebsite)
    // 确保 base_url 是有效字符串，用于 VerifyAuthRequest
    const verifyRequest = {
      ...request,
      base_url: request.base_url || effectiveBaseUrl,
    }
    const result = await verifyProviderAuth(props.providerId, verifyRequest)

    if (result.success) {
      // 检查是否获取到有效的用户信息和余额
      const username = result.data?.username?.trim() || result.data?.display_name?.trim()
      const quota = result.data?.quota

      if (!username || quota === undefined || quota === null) {
        // 没有获取到必要信息，视为验证失败
        verifyStatus.value = 'error'
        const missing: string[] = []
        if (!username) missing.push('用户信息')
        if (quota === undefined || quota === null) missing.push('余额')
        showError(`验证响应缺少: ${missing.join('、')}`)
      } else {
        verifyStatus.value = 'success'
        formChanged.value = false  // 验证成功后重置表单变动标记
        // Toast 提示
        const displayName = result.data?.display_name || result.data?.username
        showSuccess(`用户: ${displayName} | 余额: ${formatQuota(quota)}`, '验证成功')
      }
    } else {
      verifyStatus.value = 'error'
      showError(result.message || '验证失败')
    }
  } catch (error: any) {
    verifyStatus.value = 'error'
    const errMsg = error.response?.data?.detail || error.message || '验证失败'
    showError(errMsg)
  } finally {
    isVerifying.value = false
  }
}

async function handleSave() {
  const template = selectedTemplate.value
  if (!template) return

  // 验证表单（编辑模式下敏感字段可以为空）
  let dataToValidate = formData.value
  if (hasExistingConfig.value) {
    dataToValidate = { ...formData.value }
    for (const field of SENSITIVE_FIELDS) {
      if (!dataToValidate[field] && sensitivePlaceholders.value[field]) {
        dataToValidate[field] = 'placeholder'
      }
    }
  }
  const error = template.validate(dataToValidate)
  if (error) {
    showError(error)
    return
  }

  // 检查 base_url
  const effectiveBaseUrl = formData.value.base_url || props.providerWebsite
  if (!effectiveBaseUrl) {
    showError('请填写 API 地址')
    return
  }

  isSaving.value = true
  try {
    const request = template.buildRequest(formData.value, props.providerWebsite)
    const result = await saveProviderOpsConfig(props.providerId, request)
    if (result.success) {
      showSuccess(result.message || '配置已保存', '保存成功')
      emit('saved')
      emit('update:open', false)
    } else {
      showError(result.message || '保存失败')
    }
  } catch (error: any) {
    showError(error.response?.data?.detail || error.message, '保存失败')
  } finally {
    isSaving.value = false
  }
}

function loadFromConfig(config: any) {
  if (!config?.connector) return

  hasExistingConfig.value = true

  // 根据已保存的 architecture_id 选择对应模板，不存在则回退到 new_api
  const architectureId = config.architecture_id || 'new_api'
  selectedTemplateId.value = authTemplateRegistry.get(architectureId) ? architectureId : 'new_api'
  const template = authTemplateRegistry.get(selectedTemplateId.value)

  if (template) {
    const parsedData = template.parseConfig(config)

    // 敏感字段：脱敏值放到 placeholder，表单值设为空
    sensitivePlaceholders.value = {}
    for (const field of SENSITIVE_FIELDS) {
      if (parsedData[field]) {
        // 保存脱敏值作为 placeholder 提示
        sensitivePlaceholders.value[field] = `${parsedData[field]}`
        // 表单值设为空
        parsedData[field] = ''
      }
    }

    formData.value = parsedData
  }
}

// 打开对话框时初始化
watch(
  () => props.open,
  async (newVal) => {
    if (newVal) {
      verifyStatus.value = null
      formChanged.value = false

      // 如果传入了 currentConfig，直接使用
      if (props.currentConfig?.connector) {
        loadFromConfig(props.currentConfig)
        return
      }

      // 否则尝试从后端加载现有配置
      if (props.providerId) {
        isLoadingConfig.value = true
        try {
          const config = await getProviderOpsConfig(props.providerId)
          if (config.is_configured && config.architecture_id) {
            // 构建与 loadFromConfig 兼容的格式
            const configData = {
              architecture_id: config.architecture_id,
              base_url: config.base_url,
              connector: config.connector,
            }
            loadFromConfig(configData)
          } else {
            hasExistingConfig.value = false
            sensitivePlaceholders.value = {}
            selectedTemplateId.value = 'new_api'
            resetFormData()
          }
        } catch {
          // 加载失败，使用默认值
          hasExistingConfig.value = false
          sensitivePlaceholders.value = {}
          selectedTemplateId.value = 'new_api'
          resetFormData()
        } finally {
          isLoadingConfig.value = false
        }
      } else {
        hasExistingConfig.value = false
        sensitivePlaceholders.value = {}
        selectedTemplateId.value = 'new_api'
        resetFormData()
      }
    }
  }
)
</script>
