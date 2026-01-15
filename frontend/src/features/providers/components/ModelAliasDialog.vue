<template>
  <Dialog
    :model-value="open"
    title="管理模型名称映射"
    description="配置 Provider 对此模型使用的名称变体，系统会按优先级顺序选择"
    :icon="Tag"
    size="lg"
    @update:model-value="handleClose"
  >
    <div class="space-y-4">
      <!-- 模型信息 -->
      <div class="rounded-lg border bg-muted/30 p-3">
        <p class="font-medium">
          {{ model?.global_model_display_name || model?.provider_model_name }}
        </p>
        <p class="text-sm text-muted-foreground font-mono">
          主名称: {{ model?.provider_model_name }}
        </p>
      </div>

      <!-- 映射列表 -->
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <Label class="text-sm font-medium">名称映射</Label>
          <Button
            type="button"
            variant="outline"
            size="sm"
            @click="addAlias"
          >
            <Plus class="w-4 h-4 mr-1" />
            添加
          </Button>
        </div>

        <!-- 提示信息 -->
        <div
          v-if="aliases.length > 0"
          class="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground bg-muted/30 rounded-md"
        >
          <Info class="w-3.5 h-3.5 shrink-0" />
          <span>拖拽调整顺序，点击序号可编辑（相同数字为同级，负载均衡）</span>
        </div>

        <div
          v-if="aliases.length > 0"
          class="space-y-2"
        >
          <div
            v-for="(alias, index) in aliases"
            :key="index"
            class="group flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-all duration-200"
            :class="[
              draggedIndex === index
                ? 'border-primary/50 bg-primary/5 shadow-md scale-[1.01]'
                : dragOverIndex === index
                  ? 'border-primary/30 bg-primary/5'
                  : 'border-border/50 bg-background hover:border-border hover:bg-muted/30'
            ]"
            draggable="true"
            @dragstart="handleDragStart(index, $event)"
            @dragend="handleDragEnd"
            @dragover.prevent="handleDragOver(index)"
            @dragleave="handleDragLeave"
            @drop="handleDrop(index)"
          >
            <!-- 拖拽手柄 -->
            <div class="cursor-grab active:cursor-grabbing p-1 rounded hover:bg-muted text-muted-foreground/40 group-hover:text-muted-foreground transition-colors shrink-0">
              <GripVertical class="w-4 h-4" />
            </div>

            <!-- 可编辑优先级 -->
            <div class="shrink-0">
              <input
                v-if="editingPriorityIndex === index"
                type="number"
                min="1"
                :value="alias.priority"
                class="w-8 h-6 rounded-md bg-background border border-primary text-xs font-medium text-center focus:outline-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                autofocus
                @blur="finishEditPriority(index, $event)"
                @keydown.enter="($event.target as HTMLInputElement).blur()"
                @keydown.escape="cancelEditPriority"
              >
              <div
                v-else
                class="w-6 h-6 rounded-md bg-muted/50 flex items-center justify-center text-xs font-medium text-muted-foreground cursor-pointer hover:bg-primary/10 hover:text-primary transition-colors"
                title="点击编辑优先级，相同数字为同级（负载均衡）"
                @click.stop="startEditPriority(index)"
              >
                {{ alias.priority }}
              </div>
            </div>

            <!-- 映射输入框 -->
            <Input
              v-model="alias.name"
              placeholder="映射名称，如 Claude-Sonnet-4.5"
              class="flex-1"
            />

            <!-- 删除按钮 -->
            <Button
              type="button"
              variant="ghost"
              size="icon"
              class="shrink-0 text-destructive hover:text-destructive h-8 w-8"
              @click="removeAlias(index)"
            >
              <X class="w-4 h-4" />
            </Button>
          </div>
        </div>

        <div
          v-else
          class="text-center py-6 text-muted-foreground border rounded-lg border-dashed"
        >
          <Tag class="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p class="text-sm">
            未配置映射
          </p>
          <p class="text-xs mt-1">
            将只使用主模型名称
          </p>
        </div>
      </div>
    </div>

    <template #footer>
      <Button
        variant="outline"
        @click="handleClose(false)"
      >
        取消
      </Button>
      <Button
        :disabled="submitting"
        @click="handleSubmit"
      >
        <Loader2
          v-if="submitting"
          class="w-4 h-4 mr-2 animate-spin"
        />
        保存
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Tag, Plus, X, Loader2, GripVertical, Info } from 'lucide-vue-next'
import { Dialog, Button, Input, Label } from '@/components/ui'
import { useToast } from '@/composables/useToast'
import { updateModel } from '@/api/endpoints/models'
import type { Model, ProviderModelAlias } from '@/api/endpoints'

interface Props {
  open: boolean
  providerId: string
  model: Model | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'saved': []
}>()

const { error: showError, success: showSuccess } = useToast()

const submitting = ref(false)
const aliases = ref<ProviderModelAlias[]>([])

// 拖拽状态
const draggedIndex = ref<number | null>(null)
const dragOverIndex = ref<number | null>(null)

// 优先级编辑状态
const editingPriorityIndex = ref<number | null>(null)

// 监听 open 变化
watch(() => props.open, (newOpen) => {
  if (newOpen && props.model) {
    // 加载现有映射配置
    if (props.model.provider_model_mappings && Array.isArray(props.model.provider_model_mappings)) {
      aliases.value = JSON.parse(JSON.stringify(props.model.provider_model_mappings))
    } else {
      aliases.value = []
    }
    // 重置状态
    editingPriorityIndex.value = null
    draggedIndex.value = null
    dragOverIndex.value = null
  }
})

// 添加映射
function addAlias() {
  // 新映射优先级为当前最大优先级 + 1，或者默认为 1
  const maxPriority = aliases.value.length > 0
    ? Math.max(...aliases.value.map(a => a.priority))
    : 0
  aliases.value.push({ name: '', priority: maxPriority + 1 })
}

// 移除映射
function removeAlias(index: number) {
  aliases.value.splice(index, 1)
}

// ===== 拖拽排序 =====
function handleDragStart(index: number, event: DragEvent) {
  draggedIndex.value = index
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
  }
}

function handleDragEnd() {
  draggedIndex.value = null
  dragOverIndex.value = null
}

function handleDragOver(index: number) {
  if (draggedIndex.value !== null && draggedIndex.value !== index) {
    dragOverIndex.value = index
  }
}

function handleDragLeave() {
  dragOverIndex.value = null
}

function handleDrop(targetIndex: number) {
  const dragIndex = draggedIndex.value
  if (dragIndex === null || dragIndex === targetIndex) {
    dragOverIndex.value = null
    return
  }

  const items = [...aliases.value]
  const draggedItem = items[dragIndex]

  // 记录每个映射的原始优先级（在修改前）
  const originalPriorityMap = new Map<number, number>()
  items.forEach((alias, idx) => {
    originalPriorityMap.set(idx, alias.priority)
  })

  // 重排数组
  items.splice(dragIndex, 1)
  items.splice(targetIndex, 0, draggedItem)

  // 按新顺序为每个组分配新的优先级
  // 同组的映射保持相同的优先级（被拖动的映射单独成组）
  const groupNewPriority = new Map<number, number>() // 原优先级 -> 新优先级
  let currentPriority = 1

  items.forEach(alias => {
    // 找到这个映射在原数组中的索引
    const originalIdx = aliases.value.findIndex(a => a === alias)
    const originalPriority = originalIdx >= 0 ? originalPriorityMap.get(originalIdx)! : alias.priority

    if (alias === draggedItem) {
      // 被拖动的映射是独立的新组，获得当前优先级
      alias.priority = currentPriority
      currentPriority++
    } else {
      if (groupNewPriority.has(originalPriority)) {
        // 这个组已经分配过优先级，使用相同的值
        alias.priority = groupNewPriority.get(originalPriority)!
      } else {
        // 这个组第一次出现，分配新优先级
        groupNewPriority.set(originalPriority, currentPriority)
        alias.priority = currentPriority
        currentPriority++
      }
    }
  })

  aliases.value = items
  draggedIndex.value = null
  dragOverIndex.value = null
}

// ===== 优先级编辑 =====
function startEditPriority(index: number) {
  editingPriorityIndex.value = index
}

function finishEditPriority(index: number, event: FocusEvent) {
  const input = event.target as HTMLInputElement
  const newPriority = parseInt(input.value) || 1
  aliases.value[index].priority = Math.max(1, newPriority)
  editingPriorityIndex.value = null
}

function cancelEditPriority() {
  editingPriorityIndex.value = null
}

// 关闭对话框
function handleClose(value: boolean) {
  if (!submitting.value) {
    emit('update:open', value)
  }
}

// 提交保存
async function handleSubmit() {
  if (submitting.value || !props.model) return

  submitting.value = true
  try {
    // 过滤掉空的映射
    const validAliases = aliases.value.filter(a => a.name.trim())

    await updateModel(props.providerId, props.model.id, {
      provider_model_mappings: validAliases.length > 0 ? validAliases : null
    })

    showSuccess('映射配置已保存')
    emit('update:open', false)
    emit('saved')
  } catch (err: any) {
    showError(err.response?.data?.detail || '保存失败', '错误')
  } finally {
    submitting.value = false
  }
}
</script>
