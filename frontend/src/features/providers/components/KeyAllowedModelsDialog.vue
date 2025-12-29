<template>
  <Dialog
    :model-value="isOpen"
    title="配置允许的模型"
    description="选择该 API Key 允许访问的模型，留空则允许访问所有模型"
    :icon="Settings2"
    size="2xl"
    @update:model-value="handleDialogUpdate"
  >
    <div class="space-y-4 py-2">
      <!-- 已选模型展示 -->
      <div
        v-if="selectedModels.length > 0"
        class="space-y-2"
      >
        <div class="flex items-center justify-between px-1">
          <div class="text-xs font-medium text-muted-foreground">
            已选模型 ({{ selectedModels.length }})
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            class="h-6 text-xs hover:text-destructive"
            @click="clearModels"
          >
            清空
          </Button>
        </div>
        <div class="flex flex-wrap gap-1.5 p-2 bg-muted/20 rounded-lg border border-border/40 min-h-[40px]">
          <Badge
            v-for="modelName in selectedModels"
            :key="modelName"
            variant="secondary"
            class="text-[11px] px-2 py-0.5 bg-background border-border/60 shadow-sm"
          >
            {{ getModelLabel(modelName) }}
            <button
              class="ml-0.5 hover:text-destructive focus:outline-none"
              @click.stop="toggleModel(modelName, false)"
            >
              &times;
            </button>
          </Badge>
        </div>
      </div>

      <!-- 模型列表区域 -->
      <div class="space-y-2">
        <div class="flex items-center justify-between px-1">
          <div class="text-xs font-medium text-muted-foreground">
            可选模型列表
          </div>
          <div
            v-if="!loadingModels && availableModels.length > 0"
            class="text-[10px] text-muted-foreground/60"
          >
            共 {{ availableModels.length }} 个模型
          </div>
        </div>

        <!-- 加载状态 -->
        <div
          v-if="loadingModels"
          class="flex flex-col items-center justify-center py-12 space-y-3"
        >
          <div class="animate-spin rounded-full h-8 w-8 border-2 border-primary/20 border-t-primary" />
          <span class="text-xs text-muted-foreground">正在加载模型列表...</span>
        </div>

        <!-- 无模型 -->
        <div
          v-else-if="availableModels.length === 0"
          class="flex flex-col items-center justify-center py-12 text-muted-foreground border border-dashed rounded-lg bg-muted/10"
        >
          <Box class="w-10 h-10 mb-2 opacity-20" />
          <span class="text-sm">暂无可选模型</span>
        </div>

        <!-- 模型列表 -->
        <div
          v-else
          class="max-h-[320px] overflow-y-auto pr-1 space-y-1.5 custom-scrollbar"
        >
          <div
            v-for="model in availableModels"
            :key="model.global_model_name"
            class="group flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-all duration-200 cursor-pointer select-none"
            :class="[
              selectedModels.includes(model.global_model_name)
                ? 'border-primary/40 bg-primary/5 shadow-sm'
                : 'border-border/40 bg-background hover:border-primary/20 hover:bg-muted/30'
            ]"
            @click="toggleModel(model.global_model_name, !selectedModels.includes(model.global_model_name))"
          >
            <!-- Checkbox -->
            <Checkbox
              :checked="selectedModels.includes(model.global_model_name)"
              class="data-[state=checked]:bg-primary data-[state=checked]:border-primary"
              @click.stop
              @update:checked="checked => toggleModel(model.global_model_name, checked)"
            />

            <!-- Info -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between gap-2">
                <span class="text-sm font-medium truncate text-foreground/90">{{ model.display_name }}</span>
                <span
                  v-if="hasPricing(model)"
                  class="text-[10px] font-mono text-muted-foreground/80 bg-muted/30 px-1.5 py-0.5 rounded border border-border/30 shrink-0"
                >
                  {{ formatPricingShort(model) }}
                </span>
              </div>
              <div class="text-[11px] text-muted-foreground/60 font-mono truncate mt-0.5">
                {{ model.global_model_name }}
              </div>
            </div>

            <!-- 测试按钮 -->
            <Button
              variant="ghost"
              size="icon"
              class="h-7 w-7 shrink-0"
              title="测试模型连接"
              :disabled="testingModelName === model.global_model_name"
              @click.stop="testModelConnection(model)"
            >
              <Loader2 v-if="testingModelName === model.global_model_name" class="w-3.5 h-3.5 animate-spin" />
              <Play v-else class="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="flex items-center justify-end gap-2 w-full pt-2">
        <Button
          variant="outline"
          class="h-9"
          @click="handleCancel"
        >
          取消
        </Button>
        <Button
          :disabled="saving"
          class="h-9 min-w-[80px]"
          @click="handleSave"
        >
          <Loader2
            v-if="saving"
            class="w-3.5 h-3.5 mr-1.5 animate-spin"
          />
          {{ saving ? '保存中' : '保存配置' }}
        </Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Box, Loader2, Settings2, Play } from 'lucide-vue-next'
import { Dialog } from '@/components/ui'
import Button from '@/components/ui/button.vue'
import Badge from '@/components/ui/badge.vue'
import Checkbox from '@/components/ui/checkbox.vue'
import { useToast } from '@/composables/useToast'
import { parseApiError, parseTestModelError } from '@/utils/errorParser'
import {
  updateEndpointKey,
  getProviderAvailableSourceModels,
  testModel,
  type EndpointAPIKey,
  type ProviderAvailableSourceModel
} from '@/api/endpoints'

const props = defineProps<{
  open: boolean
  apiKey: EndpointAPIKey | null
  providerId: string | null
}>()

const emit = defineEmits<{
  close: []
  saved: []
}>()

const { success, error: showError } = useToast()

const isOpen = computed(() => props.open)
const saving = ref(false)
const loadingModels = ref(false)
const availableModels = ref<ProviderAvailableSourceModel[]>([])
const selectedModels = ref<string[]>([])
const initialModels = ref<string[]>([])
const testingModelName = ref<string | null>(null)

// 监听对话框打开
watch(() => props.open, (open) => {
  if (open) {
    loadData()
  }
})

async function loadData() {
  // 初始化已选模型
  if (props.apiKey?.allowed_models) {
    selectedModels.value = [...props.apiKey.allowed_models]
    initialModels.value = [...props.apiKey.allowed_models]
  } else {
    selectedModels.value = []
    initialModels.value = []
  }

  // 加载可选模型
  if (props.providerId) {
    await loadAvailableModels()
  }
}

async function loadAvailableModels() {
  if (!props.providerId) return
  try {
    loadingModels.value = true
    const response = await getProviderAvailableSourceModels(props.providerId)
    availableModels.value = response.models
  } catch (err: any) {
    const errorMessage = parseApiError(err, '加载模型列表失败')
    showError(errorMessage, '错误')
  } finally {
    loadingModels.value = false
  }
}

const modelLabelMap = computed(() => {
  const map = new Map<string, string>()
  availableModels.value.forEach(model => {
    map.set(model.global_model_name, model.display_name || model.global_model_name)
  })
  return map
})

function getModelLabel(modelName: string): string {
  return modelLabelMap.value.get(modelName) ?? modelName
}

function hasPricing(model: ProviderAvailableSourceModel): boolean {
  const input = model.price.input_price_per_1m ?? 0
  const output = model.price.output_price_per_1m ?? 0
  return input > 0 || output > 0
}

function formatPricingShort(model: ProviderAvailableSourceModel): string {
  const input = model.price.input_price_per_1m ?? 0
  const output = model.price.output_price_per_1m ?? 0
  if (input > 0 || output > 0) {
    return `$${formatPrice(input)}/$${formatPrice(output)}`
  }
  return ''
}

function formatPrice(value?: number | null): string {
  if (value === undefined || value === null || value === 0) return '0'
  if (value >= 1) {
    return value.toFixed(2)
  }
  return value.toFixed(2)
}

function toggleModel(modelName: string, checked: boolean) {
  if (checked) {
    if (!selectedModels.value.includes(modelName)) {
      selectedModels.value = [...selectedModels.value, modelName]
    }
  } else {
    selectedModels.value = selectedModels.value.filter(name => name !== modelName)
  }
}

function clearModels() {
  selectedModels.value = []
}

// 测试模型连接
async function testModelConnection(model: ProviderAvailableSourceModel) {
  if (!props.providerId || !props.apiKey || testingModelName.value) return

  testingModelName.value = model.global_model_name
  try {
    const result = await testModel({
      provider_id: props.providerId,
      model_name: model.provider_model_name,
      api_key_id: props.apiKey.id,
      message: "hello"
    })

    if (result.success) {
      success(`模型 "${model.display_name}" 测试成功`)
    } else {
      showError(`模型测试失败: ${parseTestModelError(result)}`)
    }
  } catch (err: any) {
    const errorMsg = err.response?.data?.detail || err.message || '测试请求失败'
    showError(`模型测试失败: ${errorMsg}`)
  } finally {
    testingModelName.value = null
  }
}

function areArraysEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false
  const sortedA = [...a].sort()
  const sortedB = [...b].sort()
  return sortedA.every((value, index) => value === sortedB[index])
}

function handleDialogUpdate(value: boolean) {
  if (!value) {
    emit('close')
  }
}

function handleCancel() {
  emit('close')
}

async function handleSave() {
  if (!props.apiKey) return

  // 检查是否有变化
  const hasChanged = !areArraysEqual(selectedModels.value, initialModels.value)
  if (!hasChanged) {
    emit('close')
    return
  }

  saving.value = true
  try {
    await updateEndpointKey(props.apiKey.id, {
      // 空数组时发送 null，表示允许所有模型
      allowed_models: selectedModels.value.length > 0 ? [...selectedModels.value] : null
    })
    success('允许的模型已更新', '成功')
    emit('saved')
    emit('close')
  } catch (err: any) {
    const errorMessage = parseApiError(err, '保存失败')
    showError(errorMessage, '错误')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: hsl(var(--muted-foreground) / 0.2);
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: hsl(var(--muted-foreground) / 0.4);
}
</style>
