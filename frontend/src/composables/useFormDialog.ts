import { computed, watch, type Ref, type ComputedRef } from 'vue'

/**
 * 表单对话框通用逻辑
 *
 * 统一处理：
 * - 编辑/创建模式切换
 * - 对话框打开/关闭
 * - 表单重置
 * - 数据加载
 * - Loading 状态阻止关闭
 *
 * @example
 * ```typescript
 * const { isEditMode, handleDialogUpdate, handleCancel } = useFormDialog({
 *   isOpen: () => props.modelValue,
 *   entity: () => props.provider,
 *   isLoading: loading,
 *   onClose: () => emit('update:modelValue', false),
 *   loadData: loadProviderData,
 *   resetForm,
 * })
 * ```
 */
export interface UseFormDialogOptions<E> {
  /** 对话框是否打开（getter 函数） */
  isOpen: () => boolean
  /** 编辑的实体（getter 函数，返回 null/undefined 表示创建模式） */
  entity: () => E | null | undefined
  /** 是否处于加载状态 */
  isLoading: Ref<boolean> | ComputedRef<boolean>
  /** 关闭对话框的回调 */
  onClose: () => void
  /** 加载实体数据的函数（编辑模式时调用） */
  loadData: () => void
  /** 重置表单的函数 */
  resetForm: () => void
  /** 额外的加载状态（如清理缓存等），可选 */
  extraLoadingStates?: Array<Ref<boolean> | ComputedRef<boolean>>
}

export interface UseFormDialogReturn {
  /** 是否为编辑模式 */
  isEditMode: ComputedRef<boolean>
  /** 处理对话框更新事件（用于 @update:model-value） */
  handleDialogUpdate: (value: boolean) => void
  /** 处理取消按钮点击 */
  handleCancel: () => void
}

export function useFormDialog<E>(
  options: UseFormDialogOptions<E>
): UseFormDialogReturn {
  const {
    isOpen,
    entity,
    isLoading,
    onClose,
    loadData,
    resetForm,
    extraLoadingStates = [],
  } = options

  // 是否为编辑模式
  const isEditMode = computed(() => !!entity())

  // 检查是否有任何加载状态
  const isAnyLoading = computed(() => {
    if (isLoading.value) return true
    return extraLoadingStates.some((state) => state.value)
  })

  // 处理对话框更新事件
  function handleDialogUpdate(value: boolean) {
    // 加载中不允许关闭
    if (!value && isAnyLoading.value) {
      return
    }
    // 关闭时重置表单
    if (!value) {
      resetForm()
    }
    onClose()
  }

  // 处理取消按钮
  function handleCancel() {
    if (isAnyLoading.value) return
    onClose()
  }

  // 监听打开状态变化
  watch(isOpen, (val) => {
    if (val) {
      if (isEditMode.value && entity()) {
        loadData()
      } else {
        resetForm()
      }
    }
  })

  // 监听实体变化（编辑模式切换）
  watch(entity, (newEntity) => {
    if (newEntity && isOpen()) {
      loadData()
    }
  }, { immediate: true, deep: true })

  return {
    isEditMode,
    handleDialogUpdate,
    handleCancel,
  }
}
