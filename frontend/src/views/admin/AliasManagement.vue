<template>
  <div class="flex flex-col">
    <Card class="overflow-hidden">
      <!-- 搜索和过滤区域 -->
      <div class="px-6 py-3.5 border-b border-border/60">
        <div class="flex items-center justify-between gap-4">
          <h3 class="text-base font-semibold">
            别名管理
          </h3>
          <div class="flex items-center gap-2">
            <!-- 搜索框 -->
            <div class="relative">
              <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground z-10 pointer-events-none" />
              <Input
                id="alias-search"
                v-model="aliasesSearch"
                placeholder="搜索别名或关联模型"
                class="w-44 pl-8 pr-3 h-8 text-sm border-border/60 focus-visible:ring-1"
              />
            </div>

            <div class="h-4 w-px bg-border" />

            <!-- 提供商过滤器 -->
            <Select
              v-model:open="aliasProviderSelectOpen"
              :model-value="aliasProviderFilter"
              @update:model-value="aliasProviderFilter = $event"
            >
              <SelectTrigger class="w-40 h-8 text-xs border-border/60">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">
                  全部别名
                </SelectItem>
                <SelectItem value="global">
                  仅全局别名
                </SelectItem>
                <SelectItem
                  v-for="provider in providers"
                  :key="provider.id"
                  :value="provider.id"
                >
                  {{ provider.display_name }}
                </SelectItem>
              </SelectContent>
            </Select>

            <div class="h-4 w-px bg-border" />

            <!-- 操作按钮 -->
            <Button
              variant="ghost"
              size="icon"
              class="h-8 w-8"
              title="新建别名"
              @click="openCreateAliasDialog"
            >
              <Plus class="w-3.5 h-3.5" />
            </Button>
            <RefreshButton
              :loading="loadingAliases"
              @click="loadAliases"
            />
          </div>
        </div>
      </div>
      <div
        v-if="loadingAliases"
        class="flex items-center justify-center py-12"
      >
        <Loader2 class="w-10 h-10 animate-spin text-primary" />
      </div>
      <div v-else>
        <Table class="text-sm">
          <TableHeader>
            <TableRow>
              <TableHead class="w-[200px]">
                别名
              </TableHead>
              <TableHead class="w-[280px]">
                关联模型
              </TableHead>
              <TableHead class="w-[70px] text-center">
                类型
              </TableHead>
              <TableHead class="w-[100px] text-center">
                作用域
              </TableHead>
              <TableHead class="w-[70px] text-center">
                状态
              </TableHead>
              <TableHead class="w-[100px] text-center">
                操作
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-if="filteredAliases.length === 0">
              <TableCell
                colspan="6"
                class="text-center py-8 text-muted-foreground"
              >
                {{ aliasProviderFilter === 'global' ? '暂无全局别名' : '暂无别名' }}
              </TableCell>
            </TableRow>
            <TableRow
              v-for="alias in paginatedAliases"
              :key="alias.id"
            >
              <TableCell>
                <span class="font-mono font-medium">{{ alias.alias }}</span>
              </TableCell>
              <TableCell>
                <div class="flex flex-col gap-0.5">
                  <span class="font-medium">{{ alias.global_model_display_name || alias.global_model_name }}</span>
                  <span class="text-xs text-muted-foreground font-mono">{{ alias.global_model_name }}</span>
                </div>
              </TableCell>
              <TableCell class="text-center">
                <Badge
                  variant="secondary"
                  class="text-xs"
                >
                  {{ alias.mapping_type === 'mapping' ? '映射' : '别名' }}
                </Badge>
              </TableCell>
              <TableCell class="text-center">
                <Badge
                  v-if="alias.provider_id"
                  variant="outline"
                  class="text-xs"
                >
                  {{ alias.provider_name || 'Provider 特定' }}
                </Badge>
                <Badge
                  v-else
                  variant="default"
                  class="text-xs"
                >
                  全局
                </Badge>
              </TableCell>
              <TableCell class="text-center">
                <Badge
                  :variant="alias.is_active ? 'default' : 'secondary'"
                  class="text-xs"
                >
                  {{ alias.is_active ? '活跃' : '停用' }}
                </Badge>
              </TableCell>
              <TableCell class="text-center">
                <div class="flex items-center justify-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-7 w-7"
                    title="编辑别名"
                    @click="openEditAliasDialog(alias)"
                  >
                    <Edit class="w-3.5 h-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-7 w-7"
                    :title="alias.is_active ? '停用别名' : '启用别名'"
                    @click="toggleAliasStatus(alias)"
                  >
                    <Power class="w-3.5 h-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-7 w-7"
                    title="删除别名"
                    @click="confirmDeleteAlias(alias)"
                  >
                    <Trash2 class="w-3.5 h-3.5" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>

        <!-- 分页 -->
        <Pagination
          v-if="!loadingAliases && filteredAliases.length > 0"
          :current="aliasesCurrentPage"
          :total="filteredAliases.length"
          :page-size="aliasesPageSize"
          @update:current="aliasesCurrentPage = $event"
          @update:page-size="aliasesPageSize = $event"
        />
      </div>
    </Card>

    <!-- 创建/编辑别名对话框 -->
    <AliasDialog
      :open="createAliasDialogOpen"
      :editing-alias="editingAlias"
      :global-models="globalModels"
      :providers="providers"
      @update:open="handleAliasDialogUpdate"
      @submit="handleAliasSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  Edit,
  Loader2,
  Plus,
  Power,
  Search,
  Trash2
} from 'lucide-vue-next'
import {
  Card,
  Button,
  Input,
  Badge,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  RefreshButton,
  Pagination
} from '@/components/ui'
import AliasDialog from '@/features/models/components/AliasDialog.vue'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import {
  getAliases,
  createAlias,
  updateAlias,
  deleteAlias,
  type ModelAlias,
  type CreateModelAliasRequest,
  type UpdateModelAliasRequest
} from '@/api/endpoints/aliases'
import { listGlobalModels, type GlobalModelResponse } from '@/api/global-models'
import { getProvidersSummary } from '@/api/endpoints/providers'
import { log } from '@/utils/logger'

const { success, error: showError } = useToast()
const { confirmDanger } = useConfirm()

// 状态
const loadingAliases = ref(false)
const submitting = ref(false)
const aliasesSearch = ref('')
const aliasProviderFilter = ref<string>('all')
const aliasProviderSelectOpen = ref(false)
const createAliasDialogOpen = ref(false)
const editingAliasId = ref<string | null>(null)

// 数据
const allAliases = ref<ModelAlias[]>([])
const globalModels = ref<GlobalModelResponse[]>([])
const providers = ref<any[]>([])

// 分页
const aliasesCurrentPage = ref(1)
const aliasesPageSize = ref(20)

// 编辑中的别名对象
const editingAlias = computed(() => {
  if (!editingAliasId.value) return null
  return allAliases.value.find(a => a.id === editingAliasId.value) || null
})

// 筛选后的别名列表
const filteredAliases = computed(() => {
  let result = allAliases.value

  // 按 Provider 筛选
  if (aliasProviderFilter.value === 'global') {
    result = result.filter(alias => !alias.provider_id)
  } else if (aliasProviderFilter.value !== 'all') {
    result = result.filter(alias => alias.provider_id === aliasProviderFilter.value)
  }

  // 按搜索关键词筛选
  const keyword = aliasesSearch.value.trim().toLowerCase()
  if (keyword) {
    result = result.filter(alias =>
      alias.alias.toLowerCase().includes(keyword) ||
      alias.global_model_name?.toLowerCase().includes(keyword) ||
      alias.global_model_display_name?.toLowerCase().includes(keyword)
    )
  }

  return result
})

// 分页计算
const paginatedAliases = computed(() => {
  const start = (aliasesCurrentPage.value - 1) * aliasesPageSize.value
  const end = start + aliasesPageSize.value
  return filteredAliases.value.slice(start, end)
})

// 搜索或筛选变化时重置到第一页
watch([aliasesSearch, aliasProviderFilter], () => {
  aliasesCurrentPage.value = 1
})

async function loadAliases() {
  loadingAliases.value = true
  try {
    allAliases.value = await getAliases({ limit: 1000 })
  } catch (err: any) {
    showError(err.response?.data?.detail || err.message, '加载别名失败')
  } finally {
    loadingAliases.value = false
  }
}

async function loadGlobalModelsList() {
  try {
    const response = await listGlobalModels()
    globalModels.value = response.models || []
  } catch (err: any) {
    log.error('加载模型失败:', err)
  }
}

async function loadProviders() {
  try {
    providers.value = await getProvidersSummary()
  } catch (err: any) {
    showError(err.response?.data?.detail || err.message, '加载 Provider 列表失败')
  }
}

function openCreateAliasDialog() {
  editingAliasId.value = null
  createAliasDialogOpen.value = true
}

function openEditAliasDialog(alias: ModelAlias) {
  editingAliasId.value = alias.id
  createAliasDialogOpen.value = true
}

function handleAliasDialogUpdate(value: boolean) {
  createAliasDialogOpen.value = value
  if (!value) {
    editingAliasId.value = null
  }
}

async function handleAliasSubmit(data: CreateModelAliasRequest | UpdateModelAliasRequest, isEdit: boolean) {
  submitting.value = true
  try {
    if (isEdit && editingAliasId.value) {
      await updateAlias(editingAliasId.value, data as UpdateModelAliasRequest)
      success(data.mapping_type === 'mapping' ? '映射已更新' : '别名已更新')
    } else {
      await createAlias(data as CreateModelAliasRequest)
      success(data.mapping_type === 'mapping' ? '映射已创建' : '别名已创建')
    }
    createAliasDialogOpen.value = false
    editingAliasId.value = null
    await loadAliases()
  } catch (err: any) {
    const detail = err.response?.data?.detail || err.message
    let errorMessage = detail
    if (detail === '映射已存在') {
      errorMessage = '目标作用域已存在同名别名，请先删除冲突的映射或选择其他作用域'
    }
    showError(errorMessage, isEdit ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

async function confirmDeleteAlias(alias: ModelAlias) {
  const confirmed = await confirmDanger(
    `确定要删除别名 "${alias.alias}" 吗？`,
    '删除别名'
  )
  if (!confirmed) return

  try {
    await deleteAlias(alias.id)
    success('别名已删除')
    await loadAliases()
  } catch (err: any) {
    showError(err.response?.data?.detail || err.message, '删除失败')
  }
}

async function toggleAliasStatus(alias: ModelAlias) {
  try {
    await updateAlias(alias.id, { is_active: !alias.is_active })
    alias.is_active = !alias.is_active
    success(alias.is_active ? '别名已启用' : '别名已停用')
  } catch (err: any) {
    showError(err.response?.data?.detail || err.message, '操作失败')
  }
}

onMounted(async () => {
  await Promise.all([
    loadAliases(),
    loadGlobalModelsList(),
    loadProviders()
  ])
})
</script>
