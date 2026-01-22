<template>
  <Card class="overflow-hidden">
    <!-- 标题头部 -->
    <div class="p-4 border-b border-border/60">
      <div class="flex items-center justify-between">
        <h3 class="text-sm font-semibold flex items-center gap-2">
          模型映射
        </h3>
        <Button
          variant="outline"
          size="sm"
          class="h-8"
          @click="openAddDialog"
        >
          <Plus class="w-3.5 h-3.5 mr-1.5" />
          添加映射
        </Button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div
      v-if="loading"
      class="flex items-center justify-center py-12"
    >
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
    </div>

    <!-- 映射列表 -->
    <div
      v-else-if="combinedMappings.length > 0"
      class="divide-y divide-border/40"
    >
      <div
        v-for="(item, index) in combinedMappings"
        :key="item.key"
        class="transition-colors"
      >
        <!-- 行头部（可点击展开） -->
        <div
          class="flex items-center justify-between px-4 py-3 hover:bg-muted/20 cursor-pointer"
          @click="toggleExpand(index)"
        >
          <div class="flex items-center gap-2 flex-1 min-w-0">
            <!-- 展开/收起图标 -->
            <ChevronRight
              class="w-4 h-4 text-muted-foreground shrink-0 transition-transform self-start mt-0.5"
              :class="{ 'rotate-90': expandedItems.has(index) }"
            />
            <!-- 精确映射 -->
            <template v-if="item.type === 'exact'">
              <div class="flex flex-col min-w-0">
                <span class="font-semibold text-sm truncate">
                  {{ item.targetModelName }}
                </span>
                <span
                  v-if="item.group?.model.provider_model_name"
                  class="text-xs text-muted-foreground truncate"
                >
                  {{ item.group.model.provider_model_name }}
                </span>
              </div>
              <!-- 类型标签 -->
              <Badge
                variant="default"
                class="text-xs shrink-0"
              >
                精确
              </Badge>
              <!-- 分隔符 + 映射数量 -->
              <span class="text-xs text-muted-foreground shrink-0">
                | {{ item.mappings.length }} 个映射
              </span>
            </template>
            <!-- 正则映射 -->
            <template v-else>
              <div class="flex flex-col min-w-0">
                <span class="font-semibold text-sm truncate">
                  {{ item.targetModelName }}
                </span>
                <span
                  v-if="item.globalModelName"
                  class="text-xs text-muted-foreground truncate"
                >
                  {{ item.globalModelName }}
                </span>
              </div>
              <!-- 类型标签 -->
              <Badge
                variant="secondary"
                class="text-xs shrink-0"
              >
                正则
              </Badge>
              <!-- 分隔符 + 映射数量 -->
              <span class="text-xs text-muted-foreground shrink-0">
                | {{ item.mappings.length }} 个映射
              </span>
              <!-- Key 数量 -->
              <span
                v-if="item.matchedKeys && item.matchedKeys.length > 0"
                class="text-xs text-muted-foreground shrink-0"
              >
                · {{ item.matchedKeys.length }} Key
              </span>
            </template>
          </div>
          <!-- 操作按钮（仅精确映射可编辑/删除） -->
          <div
            v-if="item.type === 'exact'"
            class="flex items-center gap-1.5 ml-4 shrink-0"
            @click.stop
          >
            <Button
              variant="ghost"
              size="icon"
              class="h-8 w-8"
              title="编辑映射"
              @click="editGroup(item.group!)"
            >
              <Edit class="w-3.5 h-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              class="h-8 w-8 text-destructive hover:text-destructive"
              title="删除映射"
              @click="deleteGroup(item.group!)"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>

        <!-- 展开的映射详情 -->
        <div
          v-show="expandedItems.has(index)"
          class="bg-muted/30 border-t border-border/30"
        >
          <!-- 精确映射详情 -->
          <div
            v-if="item.type === 'exact'"
            class="px-4 py-2 space-y-1"
          >
            <div
              v-for="mapping in item.mappings"
              :key="mapping.name"
              class="flex items-center justify-between gap-2 py-1"
            >
              <span class="font-mono text-sm truncate">
                {{ mapping.name }}
              </span>
              <!-- 测试按钮（支持多格式选择） -->
              <DropdownMenu
                v-if="getItemAvailableFormats(item).length > 1"
                v-model:open="formatMenuOpen[`${item.key}-${mapping.name}`]"
              >
                <DropdownMenuTrigger as-child>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-7 w-7 shrink-0"
                    title="测试映射"
                    :disabled="testingMapping === `${item.key}-${mapping.name}`"
                  >
                    <Loader2
                      v-if="testingMapping === `${item.key}-${mapping.name}`"
                      class="w-3 h-3 animate-spin"
                    />
                    <Play
                      v-else
                      class="w-3 h-3"
                    />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem
                    v-for="fmt in getItemAvailableFormats(item)"
                    :key="fmt"
                    @select="testMapping(item, mapping, fmt)"
                  >
                    {{ fmt }}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              <Button
                v-else
                variant="ghost"
                size="icon"
                class="h-7 w-7 shrink-0"
                title="测试映射"
                :disabled="testingMapping === `${item.key}-${mapping.name}` || getItemAvailableFormats(item).length === 0"
                @click="testMapping(item, mapping, getItemAvailableFormats(item)[0])"
              >
                <Loader2
                  v-if="testingMapping === `${item.key}-${mapping.name}`"
                  class="w-3 h-3 animate-spin"
                />
                <Play
                  v-else
                  class="w-3 h-3"
                />
              </Button>
            </div>
          </div>

          <!-- 正则映射详情（按 Key 分组显示） -->
          <div
            v-else
            class="px-4 py-3 space-y-3"
          >
            <div
              v-for="keyItem in item.matchedKeys"
              :key="keyItem.keyId"
              class="bg-background rounded-md border p-3"
            >
              <!-- Key 信息和正则表达式（两列布局） -->
              <div class="flex items-center gap-3">
                <!-- 第一列：Key 名称 + sk -->
                <div class="flex flex-col shrink-0">
                  <span class="font-medium text-sm">{{ keyItem.keyName || '未命名密钥' }}</span>
                  <span class="text-xs text-muted-foreground font-mono">
                    {{ keyItem.maskedKey }}
                  </span>
                </div>
                <!-- 分隔线 -->
                <div
                  v-if="getKeyPatterns(keyItem).length > 0"
                  class="w-px h-8 bg-border shrink-0"
                />
                <!-- 第二列：正则表达式（限制2行） -->
                <div
                  v-if="getKeyPatterns(keyItem).length > 0"
                  class="flex-1 min-w-0"
                >
                  <div
                    class="font-mono text-[11px] text-muted-foreground line-clamp-2"
                    :title="getKeyPatterns(keyItem).join(', ')"
                  >
                    {{ getKeyPatterns(keyItem).join(', ') }}
                  </div>
                </div>
              </div>
              <!-- 匹配的模型列表 -->
              <div class="mt-2 space-y-1">
                <div
                  v-for="match in keyItem.matches"
                  :key="match.name"
                  class="flex items-center justify-between gap-2 py-1"
                >
                  <span class="font-mono text-sm truncate">{{ match.name }}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-7 w-7 shrink-0"
                    title="测试映射"
                    :disabled="testingMapping === `${item.key}-${keyItem.keyId}-${match.name}`"
                    @click="testRegexMapping(item, keyItem, match)"
                  >
                    <Loader2
                      v-if="testingMapping === `${item.key}-${keyItem.keyId}-${match.name}`"
                      class="w-3 h-3 animate-spin"
                    />
                    <Play
                      v-else
                      class="w-3 h-3"
                    />
                  </Button>
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
      class="p-8 text-center text-muted-foreground"
    >
      <Tag class="w-12 h-12 mx-auto mb-3 opacity-50" />
      <p class="text-sm">
        暂无模型映射
      </p>
      <p class="text-xs mt-1">
        点击上方"添加映射"按钮为模型创建名称映射
      </p>
    </div>
  </Card>

  <!-- 添加/编辑映射对话框 -->
  <ModelMappingDialog
    v-model:open="dialogOpen"
    :provider-id="provider.id"
    :models="models"
    :editing-group="editingGroup"
    :preselected-model-id="preselectedModelId"
    @saved="onDialogSaved"
  />

  <!-- 删除确认对话框 -->
  <AlertDialog
    v-model="deleteConfirmOpen"
    title="删除映射"
    :description="deleteConfirmDescription"
    confirm-text="删除"
    cancel-text="取消"
    type="danger"
    @confirm="confirmDelete"
    @cancel="deleteConfirmOpen = false"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Tag, Plus, Edit, Trash2, ChevronRight, Loader2, Play } from 'lucide-vue-next'
import {
  Card, Button, Badge,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem
} from '@/components/ui'
import AlertDialog from '@/components/common/AlertDialog.vue'
import ModelMappingDialog, { type AliasGroup } from '../ModelMappingDialog.vue'
import { useToast } from '@/composables/useToast'
import {
  getProviderModels,
  getProviderMappingPreview,
  testModel,
  type Model,
  type ProviderModelAlias,
  type ProviderMappingPreviewResponse
} from '@/api/endpoints'
import { getProviderEndpoints } from '@/api/endpoints/endpoints'
import { getProviderKeys, type EndpointAPIKey } from '@/api/endpoints/keys'
import type { ProviderEndpoint } from '@/api/endpoints/types'
import { updateModel } from '@/api/endpoints/models'
import { parseTestModelError } from '@/utils/errorParser'

interface MappingItem {
  name: string
  priority?: number
  pattern?: string
}

interface MatchedKeyInfo {
  keyId: string
  keyName: string
  maskedKey: string
  matches: MappingItem[]
}

interface CombinedMapping {
  key: string
  type: 'exact' | 'regex'
  targetModelName: string
  targetModelId?: string
  globalModelName?: string  // 正则映射的全局模型名称
  mappings: MappingItem[]
  matchedKeys?: MatchedKeyInfo[]  // 正则映射的 Key 信息
  group?: AliasGroup
}

const props = defineProps<{
  provider: any
}>()

const emit = defineEmits<{
  'refresh': []
}>()

const { error: showError, success: showSuccess } = useToast()

// 状态
const loading = ref(false)
const models = ref<Model[]>([])
const aliasMappingPreview = ref<ProviderMappingPreviewResponse | null>(null)
const dialogOpen = ref(false)
const deleteConfirmOpen = ref(false)
const editingGroup = ref<AliasGroup | null>(null)
const deletingGroup = ref<AliasGroup | null>(null)
const testingMapping = ref<string | null>(null)
const preselectedModelId = ref<string | null>(null)

// 端点数据（用于测试格式选择）
const providerEndpoints = ref<ProviderEndpoint[]>([])

// Key 数据（用于判断支持的格式）
const providerKeys = ref<EndpointAPIKey[]>([])

// 测试下拉菜单状态
const formatMenuOpen = ref<Record<string, boolean>>({})

// 展开状态
const expandedItems = ref<Set<number>>(new Set())

// 生成作用域唯一键
function getApiFormatsKey(formats: string[] | undefined): string {
  if (!formats || formats.length === 0) return ''
  return [...formats].sort().join(',')
}

// 精确映射分组（来自 provider_model_mappings）
const exactMappingGroups = computed<AliasGroup[]>(() => {
  const groups: AliasGroup[] = []
  const groupMap = new Map<string, AliasGroup>()

  for (const model of models.value) {
    if (!model.provider_model_mappings || !Array.isArray(model.provider_model_mappings)) continue

    for (const alias of model.provider_model_mappings) {
      const apiFormatsKey = getApiFormatsKey(alias.api_formats)
      const groupKey = `${model.id}|${apiFormatsKey}`

      if (!groupMap.has(groupKey)) {
        const group: AliasGroup = {
          model,
          apiFormatsKey,
          apiFormats: alias.api_formats || [],
          aliases: []
        }
        groupMap.set(groupKey, group)
        groups.push(group)
      }
      groupMap.get(groupKey)!.aliases.push(alias)
    }
  }

  for (const group of groups) {
    group.aliases.sort((a, b) => a.priority - b.priority)
  }

  return groups
})

// 正则映射（来自 aliasMappingPreview，按 GlobalModel 分组并保留 Key 信息）
const regexMappings = computed<CombinedMapping[]>(() => {
  if (!aliasMappingPreview.value) return []

  const result: CombinedMapping[] = []
  const modelMap = new Map<string, CombinedMapping>()

  for (const keyInfo of aliasMappingPreview.value.keys) {
    for (const gm of keyInfo.matching_global_models) {
      if (!modelMap.has(gm.global_model_id)) {
        modelMap.set(gm.global_model_id, {
          key: `regex-${gm.global_model_id}`,
          type: 'regex',
          targetModelName: gm.display_name,
          targetModelId: gm.global_model_id,
          globalModelName: gm.global_model_name,
          mappings: [],
          matchedKeys: []
        })
        result.push(modelMap.get(gm.global_model_id)!)
      }

      const mapping = modelMap.get(gm.global_model_id)!

      // 添加 Key 信息
      const keyMatches: MappingItem[] = gm.matched_models.map(m => ({
        name: m.allowed_model,
        pattern: m.mapping_pattern
      }))

      mapping.matchedKeys!.push({
        keyId: keyInfo.key_id,
        keyName: keyInfo.key_name,
        maskedKey: keyInfo.masked_key,
        matches: keyMatches
      })

      // 收集所有映射（去重）
      for (const match of gm.matched_models) {
        if (!mapping.mappings.some(m => m.name === match.allowed_model)) {
          mapping.mappings.push({
            name: match.allowed_model,
            pattern: match.mapping_pattern
          })
        }
      }
    }
  }

  return result
})

// 合并后的映射列表
const combinedMappings = computed<CombinedMapping[]>(() => {
  const result: CombinedMapping[] = []

  // 添加精确映射
  for (const group of exactMappingGroups.value) {
    result.push({
      key: `exact-${group.model.id}-${group.apiFormatsKey}`,
      type: 'exact',
      targetModelName: group.model.global_model_display_name || group.model.provider_model_name,
      targetModelId: group.model.id,
      mappings: group.aliases.map(a => ({
        name: a.name,
        priority: a.priority
      })),
      group
    })
  }

  // 添加正则映射
  for (const mapping of regexMappings.value) {
    result.push(mapping)
  }

  return result.sort((a, b) => {
    // 精确映射排在前面
    if (a.type !== b.type) return a.type === 'exact' ? -1 : 1
    return a.targetModelName.localeCompare(b.targetModelName)
  })
})

// 加载数据
async function loadData() {
  try {
    loading.value = true
    const [modelsData, previewData, endpointsData, keysData] = await Promise.all([
      getProviderModels(props.provider.id),
      getProviderMappingPreview(props.provider.id).catch(() => null),
      getProviderEndpoints(props.provider.id).catch(() => []),
      getProviderKeys(props.provider.id).catch(() => [])
    ])
    models.value = modelsData
    aliasMappingPreview.value = previewData
    providerEndpoints.value = endpointsData
    providerKeys.value = keysData
  } catch (err: any) {
    showError(err.response?.data?.detail || '加载失败', '错误')
  } finally {
    loading.value = false
  }
}

// 删除确认描述
const deleteConfirmDescription = computed(() => {
  if (!deletingGroup.value) return ''
  const { model, aliases } = deletingGroup.value
  const modelName = model.global_model_display_name || model.provider_model_name
  const aliasNames = aliases.map(a => a.name).join(', ')
  return `确定要删除模型「${modelName}」的 ${aliases.length} 个映射吗？\n\n映射名称：${aliasNames}`
})

// 切换展开状态
function toggleExpand(index: number) {
  if (expandedItems.value.has(index)) {
    expandedItems.value.delete(index)
  } else {
    expandedItems.value.add(index)
  }
}

// 获取单个 Key 的去重正则模式列表
function getKeyPatterns(keyItem: MatchedKeyInfo): string[] {
  const patterns = new Set<string>()
  for (const match of keyItem.matches) {
    if (match.pattern) {
      patterns.add(match.pattern)
    }
  }
  return Array.from(patterns)
}

// 打开添加对话框
function openAddDialog() {
  editingGroup.value = null
  preselectedModelId.value = null
  dialogOpen.value = true
}

// 编辑分组
function editGroup(group: AliasGroup) {
  editingGroup.value = group
  preselectedModelId.value = null
  dialogOpen.value = true
}

// 删除分组
function deleteGroup(group: AliasGroup) {
  deletingGroup.value = group
  deleteConfirmOpen.value = true
}

// 确认删除
async function confirmDelete() {
  if (!deletingGroup.value) return

  const { model, aliases, apiFormatsKey } = deletingGroup.value

  try {
    const currentAliases = model.provider_model_mappings || []
    const aliasNamesToRemove = new Set(aliases.map(a => a.name))
    const newAliases = currentAliases.filter((a: ProviderModelAlias) => {
      const currentKey = getApiFormatsKey(a.api_formats)
      return !(currentKey === apiFormatsKey && aliasNamesToRemove.has(a.name))
    })

    await updateModel(props.provider.id, model.id, {
      provider_model_mappings: newAliases.length > 0 ? newAliases : null
    })

    showSuccess('映射已删除')
    deleteConfirmOpen.value = false
    deletingGroup.value = null
    await loadData()
    emit('refresh')
  } catch (err: any) {
    showError(err.response?.data?.detail || '删除失败', '错误')
  }
}

// 对话框保存后回调
async function onDialogSaved() {
  await loadData()
  emit('refresh')
}

// 获取可用的 API 格式（有活跃端点，去重）
const availableApiFormats = computed(() => {
  const formats = new Set(
    providerEndpoints.value
      .filter(ep => ep.is_active)
      .map(ep => ep.api_format)
  )
  return [...formats]
})

// 获取映射项支持的 API 格式
// 逻辑：找到支持该映射格式的所有活跃 Key，获取这些 Key 支持的所有格式，与活跃端点格式取交集
function getItemAvailableFormats(item: CombinedMapping): string[] {
  // 精确映射：基于 group.apiFormats 筛选
  if (item.type === 'exact' && item.group?.apiFormats && item.group.apiFormats.length > 0) {
    const mappingFormats = item.group.apiFormats

    // 找到所有支持该映射格式的活跃 Key
    const supportingKeys = providerKeys.value.filter(key => {
      if (!key.is_active) return false
      // Key 的 api_formats 与映射的 apiFormats 有交集
      return key.api_formats?.some(fmt => mappingFormats.includes(fmt))
    })

    if (supportingKeys.length === 0) {
      return []
    }

    // 收集这些 Key 支持的所有格式
    const keyFormats = new Set<string>()
    for (const key of supportingKeys) {
      for (const fmt of key.api_formats || []) {
        keyFormats.add(fmt)
      }
    }

    // 与活跃端点格式取交集
    return availableApiFormats.value.filter(fmt => keyFormats.has(fmt))
  }

  // 正则映射或无限制：返回所有有活跃 Key 支持的端点格式
  const allKeyFormats = new Set<string>()
  for (const key of providerKeys.value) {
    if (!key.is_active) continue
    for (const fmt of key.api_formats || []) {
      allKeyFormats.add(fmt)
    }
  }
  return availableApiFormats.value.filter(fmt => allKeyFormats.has(fmt))
}

// 测试精确映射（直接发请求或显示下拉菜单选择格式）
async function testMapping(item: CombinedMapping, mapping: MappingItem, apiFormat?: string) {
  const testingKey = `${item.key}-${mapping.name}`
  testingMapping.value = testingKey
  formatMenuOpen.value[testingKey] = false

  try {
    const result = await testModel({
      provider_id: props.provider.id,
      model_name: mapping.name,
      message: "hello",
      api_format: apiFormat
    })

    if (result.success) {
      showSuccess(`映射 "${mapping.name}" 测试成功`)
    } else {
      showError(`映射测试失败: ${parseTestModelError(result)}`)
    }
  } catch (err: any) {
    const errorMsg = err.response?.data?.detail || err.message || '测试请求失败'
    showError(`映射测试失败: ${errorMsg}`)
  } finally {
    testingMapping.value = null
  }
}

// 测试正则映射（指定 Key，直接发请求，因为已经有 Key 信息）
async function testRegexMapping(item: CombinedMapping, keyItem: MatchedKeyInfo, match: MappingItem) {
  const testingKey = `${item.key}-${keyItem.keyId}-${match.name}`
  testingMapping.value = testingKey

  try {
    const result = await testModel({
      provider_id: props.provider.id,
      model_name: match.name,
      message: "hello",
      api_key_id: keyItem.keyId
    })

    if (result.success) {
      showSuccess(`映射 "${match.name}" 测试成功`)
    } else {
      showError(`映射测试失败: ${parseTestModelError(result)}`)
    }
  } catch (err: any) {
    const errorMsg = err.response?.data?.detail || err.message || '测试请求失败'
    showError(`映射测试失败: ${errorMsg}`)
  } finally {
    testingMapping.value = null
  }
}

// 监听 provider 变化
watch(() => props.provider?.id, (newId) => {
  if (newId) {
    loadData()
  }
}, { immediate: true })

// 暴露给父组件
defineExpose({
  dialogOpen: computed(() => dialogOpen.value || deleteConfirmOpen.value),
  reload: loadData
})
</script>
