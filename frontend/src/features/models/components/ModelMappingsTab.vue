<template>
  <Card class="overflow-hidden">
    <!-- 表头 -->
    <div class="px-4 py-3 border-b border-border/60">
      <div class="flex items-center justify-between">
        <div class="flex items-baseline gap-2">
          <h4 class="text-sm font-semibold">
            映射规则
          </h4>
          <span class="text-xs text-muted-foreground">
            支持正则表达式 ({{ localMappings.length }}/{{ MAX_MAPPINGS_PER_MODEL }})
          </span>
        </div>
        <div class="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            class="h-7 w-7"
            title="添加规则"
            :disabled="localMappings.length >= MAX_MAPPINGS_PER_MODEL"
            @click="addMapping"
          >
            <Plus class="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            class="h-7 w-7"
            title="刷新"
            :disabled="props.loading"
            @click="$emit('refresh')"
          >
            <RefreshCw
              class="w-4 h-4"
              :class="{ 'animate-spin': props.loading }"
            />
          </Button>
        </div>
      </div>
    </div>

    <!-- 规则列表 -->
    <div
      v-if="localMappings.length > 0"
      class="divide-y"
    >
      <div
        v-for="(mapping, index) in localMappings"
        :key="index"
      >
        <!-- 规则行 -->
        <div
          class="px-4 py-3 flex items-center gap-3 cursor-pointer hover:bg-muted/30 transition-colors"
          @click="toggleExpand(index)"
        >
          <ChevronRight
            class="w-4 h-4 text-muted-foreground transition-transform flex-shrink-0"
            :class="{ 'rotate-90': expandedIndex === index }"
          />
          <div class="flex-1 min-w-0">
            <Input
              v-model="localMappings[index]"
              placeholder="例如: claude-haiku-.*"
              :class="`font-mono text-sm ${normalizedMappings[index] && !mappingValidations[index].valid ? 'border-destructive' : ''}`"
              @click.stop
              @input="markDirty"
            />
            <!-- 验证错误提示 -->
            <div
              v-if="normalizedMappings[index] && !mappingValidations[index].valid"
              class="flex items-center gap-1 mt-1 text-xs text-destructive"
            >
              <AlertCircle class="w-3 h-3" />
              <span>{{ mappingValidations[index].error }}</span>
            </div>
          </div>
          <!-- 匹配统计 -->
          <Badge
            v-if="mappingValidations[index].valid && mappingMatchCounts[index] > 0"
            variant="secondary"
            class="text-xs flex-shrink-0 h-6 leading-none"
          >
            {{ mappingMatchCounts[index] }} 匹配
          </Badge>
          <Badge
            v-else-if="normalizedMappings[index] && mappingValidations[index].valid"
            variant="outline"
            class="text-xs text-muted-foreground flex-shrink-0 h-6 leading-none"
          >
            无匹配
          </Badge>
          <!-- 操作按钮 -->
          <div class="flex items-center gap-1 flex-shrink-0">
            <Button
              v-if="isDirty"
              variant="ghost"
              size="icon"
              class="h-7 w-7 text-muted-foreground hover:text-primary"
              title="保存"
              :disabled="saving || hasValidationErrors"
              @click.stop="saveMappings"
            >
              <Save
                v-if="!saving"
                class="w-4 h-4"
              />
              <RefreshCw
                v-else
                class="w-4 h-4 animate-spin"
              />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              class="h-7 w-7 text-muted-foreground hover:text-destructive"
              title="删除"
              :disabled="saving"
              @click.stop="removeMapping(index)"
            >
              <Trash2 class="w-4 h-4" />
            </Button>
          </div>
        </div>

        <!-- 展开内容：匹配的 Key 列表（按提供商分组） -->
        <div
          v-if="expandedIndex === index"
          class="border-t bg-muted/10 px-4 py-3"
        >
          <div
            v-if="loadingPreview"
            class="flex items-center justify-center py-4"
          >
            <RefreshCw class="w-4 h-4 animate-spin text-muted-foreground" />
          </div>

          <div
            v-else-if="expandedGroups.length === 0"
            class="text-center py-4"
          >
            <p class="text-sm text-muted-foreground">
              {{ normalizedMappings[index] ? '此规则暂无匹配的 Key 白名单' : '请输入映射规则' }}
            </p>
          </div>

          <div
            v-else
            class="space-y-3"
          >
            <!-- 按提供商分组 -->
            <div
              v-for="group in expandedGroups"
              :key="group.providerId"
              class="bg-background rounded-md border overflow-hidden"
            >
              <!-- 提供商标题 -->
              <div class="px-3 py-2 bg-muted/30 border-b flex items-center justify-between">
                <div>
                  <span class="text-sm font-medium">{{ group.providerName }}</span>
                  <span class="text-xs text-muted-foreground ml-2">({{ group.keys.length }} Key)</span>
                </div>
                <Badge
                  v-if="group.isLinked"
                  variant="secondary"
                  class="text-xs"
                >
                  已关联
                </Badge>
                <Button
                  v-else
                  variant="ghost"
                  size="icon"
                  class="h-7 w-7"
                  title="关联到当前模型"
                  @click="$emit('linkProvider', group.providerId)"
                >
                  <Link class="w-3.5 h-3.5" />
                </Button>
              </div>
              <!-- Key 列表 -->
              <div class="divide-y divide-border/50">
                <div
                  v-for="keyItem in group.keys"
                  :key="keyItem.keyId"
                  class="px-3 py-2"
                >
                  <div class="flex items-center gap-1.5 text-sm mb-1.5">
                    <span class="font-medium">{{ keyItem.keyName }}</span>
                    <code class="text-xs text-muted-foreground/70">{{ keyItem.maskedKey }}</code>
                  </div>
                  <div class="flex flex-wrap gap-1">
                    <Badge
                      v-for="model in keyItem.matchedModels"
                      :key="model"
                      variant="secondary"
                      class="text-xs font-mono"
                    >
                      {{ model }}
                    </Badge>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div
      v-else
      class="text-center py-32"
    >
      <GitMerge class="w-10 h-10 mx-auto text-muted-foreground/30 mb-3" />
      <p class="text-sm text-muted-foreground">
        暂无映射规则
      </p>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import { Card, Button, Input, Badge } from '@/components/ui'
import { Plus, Trash2, GitMerge, RefreshCw, ChevronRight, Save, AlertCircle, Link } from 'lucide-vue-next'
import { updateGlobalModel, getGlobalModel, getGlobalModelRoutingPreview } from '@/api/global-models'
import type { ModelRoutingPreviewResponse } from '@/api/endpoints/types'
import { log } from '@/utils/logger'
import { useToast } from '@/composables/useToast'
import {
  MAX_MAPPINGS_PER_MODEL,
  MAX_MODEL_NAME_LENGTH,
  createLRURegexCache,
  getCompiledModelMappingRegex,
  validateModelMappingPattern,
  type ValidationResult,
} from '@/features/models/utils/model-mapping-regex'

const props = defineProps<{
  globalModelId: string
  modelName: string
  mappings: string[]
  loading?: boolean
}>()
const emit = defineEmits<{
  update: [mappings: string[]]
  refresh: []
  linkProvider: [providerId: string]
  linkProviders: [providerIds: string[]]  // 批量关联
}>()

const { success: toastSuccess, error: toastError } = useToast()

// 本地状态
const localMappings = ref<string[]>([...props.mappings])
const originalMappings = ref<string[]>([...props.mappings])  // 用于保存失败时恢复
const isDirty = ref(false)
const saving = ref(false)
const expandedIndex = ref<number | null>(null)

// 统一以 trim 后的规则做预览/校验（保存时也会 trim），避免前后端行为不一致
const normalizedMappings = computed(() => localMappings.value.map(m => m.trim()))
const mappingValidations = computed<ValidationResult[]>(() => {
  return normalizedMappings.value.map(pattern => {
    if (!pattern) return { valid: true }
    return validateModelMappingPattern(pattern)
  })
})

// 匹配预览状态
const loadingPreview = ref(false)
const routingData = ref<ModelRoutingPreviewResponse | null>(null)

const REGEX_CACHE_MAX_SIZE = 100
const regexCache = createLRURegexCache(REGEX_CACHE_MAX_SIZE)
const matchCountCache = new Map<string, number>()

interface MatchedKeyForMapping {
  keyId: string
  keyName: string
  maskedKey: string
  providerName: string
  providerId: string
  matchedModels: string[]
}

interface ProviderGroup {
  providerId: string
  providerName: string
  keys: MatchedKeyForMapping[]
  isLinked: boolean  // 是否已关联到当前模型
}

/**
 * 检查是否有验证错误
 */
const hasValidationErrors = computed(() => {
  return mappingValidations.value.some((result, index) => {
    return normalizedMappings.value[index] !== '' && !result.valid
  })
})

function computeMatchCount(pattern: string): number {
  if (!routingData.value) return 0

  const cached = matchCountCache.get(pattern)
  if (cached !== undefined) {
    return cached
  }

  const regex = getCompiledModelMappingRegex(pattern, regexCache)
  if (!regex) {
    matchCountCache.set(pattern, 0)
    return 0
  }

  const keyToMatchedModels = new Map<string, Set<string>>()

  for (const keyItem of routingData.value.all_keys_whitelist || []) {
    if (!keyItem.allowed_models || keyItem.allowed_models.length === 0) continue

    for (const allowedModel of keyItem.allowed_models) {
      if (allowedModel.length > MAX_MODEL_NAME_LENGTH) continue
      if (!regex.test(allowedModel)) continue

      let modelSet = keyToMatchedModels.get(keyItem.key_id)
      if (!modelSet) {
        modelSet = new Set()
        keyToMatchedModels.set(keyItem.key_id, modelSet)
      }
      modelSet.add(allowedModel)
    }
  }

  let total = 0
  for (const models of keyToMatchedModels.values()) {
    total += models.size
  }
  matchCountCache.set(pattern, total)
  return total
}

const mappingMatchCounts = computed(() => {
  if (!routingData.value) {
    return normalizedMappings.value.map(() => 0)
  }

  return normalizedMappings.value.map((pattern, index) => {
    if (!pattern) return 0
    if (!mappingValidations.value[index]?.valid) return 0
    return computeMatchCount(pattern)
  })
})

// 获取指定映射匹配的 Key 列表（使用全局 Key 白名单数据做实时匹配）
function getMatchedKeysForMapping(mapping: string): MatchedKeyForMapping[] {
  if (!routingData.value) return []
  const pattern = mapping.trim()
  if (!pattern) return []

  const regex = getCompiledModelMappingRegex(pattern, regexCache)
  if (!regex) return []

  const keyMap = new Map<string, MatchedKeyForMapping>()

  // 使用 all_keys_whitelist 进行实时匹配（包含所有 Provider 的 Key）
  for (const keyItem of routingData.value.all_keys_whitelist || []) {
    if (!keyItem.allowed_models || keyItem.allowed_models.length === 0) continue

    const matchedModels: string[] = []
    for (const allowedModel of keyItem.allowed_models) {
      if (allowedModel.length > MAX_MODEL_NAME_LENGTH) continue
      if (regex.test(allowedModel)) matchedModels.push(allowedModel)
    }

    if (matchedModels.length > 0) {
      const existing = keyMap.get(keyItem.key_id)
      if (existing) {
        const mergedModels = new Set([...existing.matchedModels, ...matchedModels])
        existing.matchedModels = Array.from(mergedModels)
      } else {
        keyMap.set(keyItem.key_id, {
          keyId: keyItem.key_id,
          keyName: keyItem.key_name,
          maskedKey: keyItem.masked_key,
          providerName: keyItem.provider_name,
          providerId: keyItem.provider_id,
          matchedModels,
        })
      }
    }
  }

  return Array.from(keyMap.values())
}

// 按提供商分组匹配的 Key
function getMatchedKeysGroupedByProvider(mapping: string): ProviderGroup[] {
  const keys = getMatchedKeysForMapping(mapping)
  const providerMap = new Map<string, ProviderGroup>()

  // 获取已关联的提供商 ID 集合
  const linkedProviderIds = new Set(
    (routingData.value?.providers || []).map(p => p.id)
  )

  for (const key of keys) {
    const existing = providerMap.get(key.providerId)
    if (existing) {
      existing.keys.push(key)
    } else {
      providerMap.set(key.providerId, {
        providerId: key.providerId,
        providerName: key.providerName,
        keys: [key],
        isLinked: linkedProviderIds.has(key.providerId),
      })
    }
  }

  return Array.from(providerMap.values())
}

function toggleExpand(index: number) {
  expandedIndex.value = expandedIndex.value === index ? null : index
}

const expandedGroups = computed<ProviderGroup[]>(() => {
  if (expandedIndex.value === null) return []

  const pattern = normalizedMappings.value[expandedIndex.value] || ''
  if (!pattern) return []

  const validation = mappingValidations.value[expandedIndex.value]
  if (validation && !validation.valid) return []

  return getMatchedKeysGroupedByProvider(pattern)
})

watch(() => props.mappings, (newAliases) => {
  localMappings.value = [...newAliases]
  originalMappings.value = [...newAliases]
  isDirty.value = false
}, { deep: true })

// globalModelId 变化时清空缓存并重新加载预览
watch(() => props.globalModelId, () => {
  regexCache.clear()
  loadMatchPreview()
})

function markDirty() {
  isDirty.value = true
}

function addMapping() {
  if (localMappings.value.length >= MAX_MAPPINGS_PER_MODEL) {
    toastError(`最多支持 ${MAX_MAPPINGS_PER_MODEL} 条映射规则`)
    return
  }
  localMappings.value.push('')
  isDirty.value = true
  expandedIndex.value = localMappings.value.length - 1
}

async function removeMapping(index: number) {
  localMappings.value.splice(index, 1)
  if (expandedIndex.value === index) {
    expandedIndex.value = null
  } else if (expandedIndex.value !== null && expandedIndex.value > index) {
    expandedIndex.value--
  }
  // 删除后自动保存（仅在当前无校验错误时）
  if (hasValidationErrors.value) {
    toastError('存在无效映射规则，请修正后再保存')
    isDirty.value = true
    return
  }
  await saveMappings()
}

async function saveMappings() {
  if (hasValidationErrors.value) {
    toastError('存在无效映射规则，无法保存')
    return
  }

  const cleanedMappings = localMappings.value
    .map(a => a.trim())
    .filter(a => a.length > 0)

  saving.value = true
  try {
    const currentModel = await getGlobalModel(props.globalModelId)
    const currentConfig = currentModel.config || {}

    const updatedConfig = {
      ...currentConfig,
      model_mappings: cleanedMappings.length > 0 ? cleanedMappings : undefined,
    }

    if (!updatedConfig.model_mappings || updatedConfig.model_mappings.length === 0) {
      delete updatedConfig.model_mappings
    }

    await updateGlobalModel(props.globalModelId, {
      config: updatedConfig,
    })

    localMappings.value = cleanedMappings
    originalMappings.value = [...cleanedMappings]  // 更新原始值
    isDirty.value = false

    // 收集所有未关联的提供商 ID
    const unlinkedProviderIds: string[] = []
    for (const mapping of cleanedMappings) {
      const groups = getMatchedKeysGroupedByProvider(mapping)
      for (const group of groups) {
        if (!group.isLinked && !unlinkedProviderIds.includes(group.providerId)) {
          unlinkedProviderIds.push(group.providerId)
        }
      }
    }

    // 自动关联未关联的提供商
    if (unlinkedProviderIds.length > 0) {
      toastSuccess(`映射规则已保存，正在关联 ${unlinkedProviderIds.length} 个提供商...`)
      // linkProviders 处理完成后会由父组件统一刷新数据，无需再 emit update
      emit('linkProviders', unlinkedProviderIds)
    } else {
      toastSuccess('映射规则已保存')
      emit('update', cleanedMappings)
    }
  } catch (err) {
    log.error('保存映射规则失败:', err)
    toastError('保存失败，请重试')
    // 保存失败时恢复到原始值
    localMappings.value = [...originalMappings.value]
    isDirty.value = false
  } finally {
    saving.value = false
  }
}

async function loadMatchPreview() {
  // 清空正则缓存，确保使用最新数据
  regexCache.clear()
  matchCountCache.clear()
  loadingPreview.value = true
  try {
    routingData.value = await getGlobalModelRoutingPreview(props.globalModelId)
  } catch (err) {
    log.error('加载匹配预览失败:', err)
  } finally {
    loadingPreview.value = false
  }
}

onMounted(() => {
  loadMatchPreview()
})

// 组件卸载时清理缓存，防止内存泄漏
onUnmounted(() => {
  regexCache.clear()
  matchCountCache.clear()
})

// 暴露刷新方法给父组件
defineExpose({
  refresh: loadMatchPreview
})
</script>
