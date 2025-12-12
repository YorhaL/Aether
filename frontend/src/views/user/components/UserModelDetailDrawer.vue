<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div
        v-if="open && model"
        class="fixed inset-0 z-50 flex justify-end"
        @click.self="handleClose"
      >
        <!-- 背景遮罩 -->
        <div
          class="absolute inset-0 bg-black/30 backdrop-blur-sm"
          @click="handleClose"
        />

        <!-- 抽屉内容 -->
        <Card class="relative h-full w-[700px] rounded-none shadow-2xl overflow-y-auto">
          <!-- 标题栏 -->
          <div class="sticky top-0 z-10 bg-background border-b p-6">
            <div class="flex items-start justify-between gap-4">
              <div class="space-y-1 flex-1 min-w-0">
                <h3 class="text-xl font-bold truncate">
                  {{ model.display_name || model.name }}
                </h3>
                <div class="flex items-center gap-2">
                  <Badge
                    :variant="model.is_active ? 'default' : 'secondary'"
                    class="text-xs"
                  >
                    {{ model.is_active ? '可用' : '停用' }}
                  </Badge>
                  <span class="text-sm text-muted-foreground font-mono">{{ model.name }}</span>
                  <button
                    class="p-0.5 rounded hover:bg-muted transition-colors"
                    title="复制模型 ID"
                    @click="copyToClipboard(model.name)"
                  >
                    <Copy class="w-3 h-3 text-muted-foreground" />
                  </button>
                </div>
                <p
                  v-if="model.description"
                  class="text-xs text-muted-foreground"
                >
                  {{ model.description }}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                title="关闭"
                @click="handleClose"
              >
                <X class="w-4 h-4" />
              </Button>
            </div>
          </div>

          <div class="p-6 space-y-6">
            <!-- 模型能力 -->
            <div class="space-y-3">
              <h4 class="font-semibold text-sm">
                模型能力
              </h4>
              <div class="grid grid-cols-2 gap-3">
                <div class="flex items-center gap-2 p-3 rounded-lg border">
                  <Zap class="w-5 h-5 text-muted-foreground" />
                  <div class="flex-1">
                    <p class="text-sm font-medium">
                      Streaming
                    </p>
                    <p class="text-xs text-muted-foreground">
                      流式输出
                    </p>
                  </div>
                  <Badge
                    :variant="model.default_supports_streaming ?? false ? 'default' : 'secondary'"
                    class="text-xs"
                  >
                    {{ model.default_supports_streaming ?? false ? '支持' : '不支持' }}
                  </Badge>
                </div>
                <div class="flex items-center gap-2 p-3 rounded-lg border">
                  <ImageIcon class="w-5 h-5 text-muted-foreground" />
                  <div class="flex-1">
                    <p class="text-sm font-medium">
                      Image Generation
                    </p>
                    <p class="text-xs text-muted-foreground">
                      图像生成
                    </p>
                  </div>
                  <Badge
                    :variant="model.default_supports_image_generation ?? false ? 'default' : 'secondary'"
                    class="text-xs"
                  >
                    {{ model.default_supports_image_generation ?? false ? '支持' : '不支持' }}
                  </Badge>
                </div>
                <div class="flex items-center gap-2 p-3 rounded-lg border">
                  <Eye class="w-5 h-5 text-muted-foreground" />
                  <div class="flex-1">
                    <p class="text-sm font-medium">
                      Vision
                    </p>
                    <p class="text-xs text-muted-foreground">
                      视觉理解
                    </p>
                  </div>
                  <Badge
                    :variant="model.default_supports_vision ?? false ? 'default' : 'secondary'"
                    class="text-xs"
                  >
                    {{ model.default_supports_vision ?? false ? '支持' : '不支持' }}
                  </Badge>
                </div>
                <div class="flex items-center gap-2 p-3 rounded-lg border">
                  <Wrench class="w-5 h-5 text-muted-foreground" />
                  <div class="flex-1">
                    <p class="text-sm font-medium">
                      Tool Use
                    </p>
                    <p class="text-xs text-muted-foreground">
                      工具调用
                    </p>
                  </div>
                  <Badge
                    :variant="model.default_supports_function_calling ?? false ? 'default' : 'secondary'"
                    class="text-xs"
                  >
                    {{ model.default_supports_function_calling ?? false ? '支持' : '不支持' }}
                  </Badge>
                </div>
                <div class="flex items-center gap-2 p-3 rounded-lg border">
                  <Brain class="w-5 h-5 text-muted-foreground" />
                  <div class="flex-1">
                    <p class="text-sm font-medium">
                      Extended Thinking
                    </p>
                    <p class="text-xs text-muted-foreground">
                      深度思考
                    </p>
                  </div>
                  <Badge
                    :variant="model.default_supports_extended_thinking ?? false ? 'default' : 'secondary'"
                    class="text-xs"
                  >
                    {{ model.default_supports_extended_thinking ?? false ? '支持' : '不支持' }}
                  </Badge>
                </div>
              </div>
            </div>

            <!-- 模型偏好 -->
            <div
              v-if="getModelUserConfigurableCapabilities().length > 0"
              class="space-y-3"
            >
              <h4 class="font-semibold text-sm">
                模型偏好
              </h4>
              <div class="space-y-2">
                <div
                  v-for="cap in getModelUserConfigurableCapabilities()"
                  :key="cap.name"
                  class="flex items-center justify-between p-3 rounded-lg border"
                >
                  <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium">
                      {{ cap.display_name }}
                    </p>
                    <p
                      v-if="cap.description"
                      class="text-xs text-muted-foreground truncate"
                    >
                      {{ cap.description }}
                    </p>
                  </div>
                  <button
                    class="relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    :class="[
                      isCapabilityEnabled(cap.name) ? 'bg-primary' : 'bg-muted'
                    ]"
                    role="switch"
                    :aria-checked="isCapabilityEnabled(cap.name)"
                    @click="handleToggleCapability(cap.name)"
                  >
                    <span
                      class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-background shadow-lg ring-0 transition duration-200 ease-in-out"
                      :class="[
                        isCapabilityEnabled(cap.name) ? 'translate-x-4' : 'translate-x-0'
                      ]"
                    />
                  </button>
                </div>
              </div>
            </div>

            <!-- 定价信息 -->
            <div class="space-y-3">
              <h4 class="font-semibold text-sm">
                定价信息
              </h4>

              <!-- 单阶梯（固定价格）展示 -->
              <div
                v-if="getTierCount(model.default_tiered_pricing) <= 1"
                class="space-y-3"
              >
                <div class="grid grid-cols-2 gap-3">
                  <div class="p-3 rounded-lg border">
                    <Label class="text-xs text-muted-foreground">输入价格 ($/M)</Label>
                    <p class="text-lg font-semibold mt-1">
                      {{ getFirstTierPrice(model.default_tiered_pricing, 'input_price_per_1m') }}
                    </p>
                  </div>
                  <div class="p-3 rounded-lg border">
                    <Label class="text-xs text-muted-foreground">输出价格 ($/M)</Label>
                    <p class="text-lg font-semibold mt-1">
                      {{ getFirstTierPrice(model.default_tiered_pricing, 'output_price_per_1m') }}
                    </p>
                  </div>
                  <div class="p-3 rounded-lg border">
                    <Label class="text-xs text-muted-foreground">缓存创建 ($/M)</Label>
                    <p class="text-sm font-mono mt-1">
                      {{ getFirstTierPrice(model.default_tiered_pricing, 'cache_creation_price_per_1m') }}
                    </p>
                  </div>
                  <div class="p-3 rounded-lg border">
                    <Label class="text-xs text-muted-foreground">缓存读取 ($/M)</Label>
                    <p class="text-sm font-mono mt-1">
                      {{ getFirstTierPrice(model.default_tiered_pricing, 'cache_read_price_per_1m') }}
                    </p>
                  </div>
                </div>
                <!-- 1h 缓存 -->
                <div
                  v-if="getFirst1hCachePrice(model.default_tiered_pricing) !== '-'"
                  class="flex items-center gap-3 p-3 rounded-lg border bg-muted/20"
                >
                  <Label class="text-xs text-muted-foreground whitespace-nowrap">1h 缓存创建</Label>
                  <span class="text-sm font-mono">{{ getFirst1hCachePrice(model.default_tiered_pricing) }}</span>
                </div>
                <!-- 按次计费 -->
                <div
                  v-if="model.default_price_per_request && model.default_price_per_request > 0"
                  class="flex items-center gap-3 p-3 rounded-lg border bg-muted/20"
                >
                  <Label class="text-xs text-muted-foreground whitespace-nowrap">按次计费</Label>
                  <span class="text-sm font-mono">${{ model.default_price_per_request.toFixed(3) }}/次</span>
                </div>
              </div>

              <!-- 多阶梯计费展示 -->
              <div
                v-else
                class="space-y-3"
              >
                <div class="flex items-center gap-2 text-sm text-muted-foreground">
                  <Layers class="w-4 h-4" />
                  <span>阶梯计费 ({{ getTierCount(model.default_tiered_pricing) }} 档)</span>
                </div>

                <!-- 阶梯价格表格 -->
                <div class="border rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow class="bg-muted/30">
                        <TableHead class="text-xs h-9">
                          阶梯
                        </TableHead>
                        <TableHead class="text-xs h-9 text-right">
                          输入 ($/M)
                        </TableHead>
                        <TableHead class="text-xs h-9 text-right">
                          输出 ($/M)
                        </TableHead>
                        <TableHead class="text-xs h-9 text-right">
                          缓存创建
                        </TableHead>
                        <TableHead class="text-xs h-9 text-right">
                          缓存读取
                        </TableHead>
                        <TableHead class="text-xs h-9 text-right">
                          1h 缓存
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      <TableRow
                        v-for="(tier, index) in model.default_tiered_pricing?.tiers || []"
                        :key="index"
                        class="text-xs"
                      >
                        <TableCell class="py-2">
                          <span
                            v-if="tier.up_to === null"
                            class="text-muted-foreground"
                          >
                            {{ index === 0 ? '所有' : `> ${formatTierLimit((model.default_tiered_pricing?.tiers || [])[index - 1]?.up_to)}` }}
                          </span>
                          <span v-else>
                            {{ index === 0 ? '0' : formatTierLimit((model.default_tiered_pricing?.tiers || [])[index - 1]?.up_to) }} - {{ formatTierLimit(tier.up_to) }}
                          </span>
                        </TableCell>
                        <TableCell class="py-2 text-right font-mono">
                          ${{ tier.input_price_per_1m?.toFixed(2) || '0.00' }}
                        </TableCell>
                        <TableCell class="py-2 text-right font-mono">
                          ${{ tier.output_price_per_1m?.toFixed(2) || '0.00' }}
                        </TableCell>
                        <TableCell class="py-2 text-right font-mono text-muted-foreground">
                          {{ tier.cache_creation_price_per_1m != null ? `$${tier.cache_creation_price_per_1m.toFixed(2)}` : '-' }}
                        </TableCell>
                        <TableCell class="py-2 text-right font-mono text-muted-foreground">
                          {{ tier.cache_read_price_per_1m != null ? `$${tier.cache_read_price_per_1m.toFixed(2)}` : '-' }}
                        </TableCell>
                        <TableCell class="py-2 text-right font-mono text-muted-foreground">
                          {{ get1hCachePrice(tier) }}
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </div>

                <!-- 按次计费（多阶梯时也显示） -->
                <div
                  v-if="model.default_price_per_request && model.default_price_per_request > 0"
                  class="flex items-center gap-3 p-3 rounded-lg border bg-muted/20"
                >
                  <Label class="text-xs text-muted-foreground whitespace-nowrap">按次计费</Label>
                  <span class="text-sm font-mono">${{ model.default_price_per_request.toFixed(3) }}/次</span>
                </div>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import {
  X,
  Eye,
  Wrench,
  Brain,
  Zap,
  Copy,
  Layers,
  Image as ImageIcon
} from 'lucide-vue-next'
import { useToast } from '@/composables/useToast'
import Card from '@/components/ui/card.vue'
import Badge from '@/components/ui/badge.vue'
import Button from '@/components/ui/button.vue'
import Label from '@/components/ui/label.vue'
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableCell from '@/components/ui/table-cell.vue'

import type { PublicGlobalModel } from '@/api/public-models'
import type { TieredPricingConfig, PricingTier } from '@/api/endpoints/types'
import type { CapabilityDefinition } from '@/api/endpoints'

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'toggleCapability': [modelName: string, capName: string]
}>()

const { success: showSuccess, error: showError } = useToast()

interface Props {
  model: PublicGlobalModel | null
  open: boolean
  capabilities?: CapabilityDefinition[]
  userConfigurableCapabilities?: CapabilityDefinition[]
  modelCapabilitySettings?: Record<string, Record<string, boolean>>
}

// 获取模型支持的用户可配置能力
function getModelUserConfigurableCapabilities(): CapabilityDefinition[] {
  if (!props.model?.supported_capabilities || !props.userConfigurableCapabilities) return []
  return props.userConfigurableCapabilities.filter(cap =>
    props.model!.supported_capabilities!.includes(cap.name)
  )
}

// 检查能力是否已启用
function isCapabilityEnabled(capName: string): boolean {
  if (!props.model) return false
  return props.modelCapabilitySettings?.[props.model.name]?.[capName] || false
}

// 切换能力
function handleToggleCapability(capName: string) {
  if (!props.model) return
  emit('toggleCapability', props.model.name, capName)
}

function handleClose() {
  emit('update:open', false)
}

async function copyToClipboard(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    showSuccess('已复制')
  } catch {
    showError('复制失败')
  }
}

function getFirstTierPrice(
  tieredPricing: TieredPricingConfig | undefined | null,
  priceKey: 'input_price_per_1m' | 'output_price_per_1m' | 'cache_creation_price_per_1m' | 'cache_read_price_per_1m'
): string {
  if (!tieredPricing?.tiers?.length) return '-'
  const firstTier = tieredPricing.tiers[0]
  const value = firstTier[priceKey]
  if (value == null || value === 0) return '-'
  return `$${value.toFixed(2)}`
}

function getTierCount(tieredPricing: TieredPricingConfig | undefined | null): number {
  return tieredPricing?.tiers?.length || 0
}

function formatTierLimit(limit: number | null | undefined): string {
  if (limit == null) return ''
  if (limit >= 1000000) {
    return `${(limit / 1000000).toFixed(1)}M`
  } else if (limit >= 1000) {
    return `${(limit / 1000).toFixed(0)}K`
  }
  return limit.toString()
}

function get1hCachePrice(tier: PricingTier): string {
  const ttl1h = tier.cache_ttl_pricing?.find(t => t.ttl_minutes === 60)
  if (ttl1h) {
    return `$${ttl1h.cache_creation_price_per_1m.toFixed(2)}`
  }
  return '-'
}

function getFirst1hCachePrice(tieredPricing: TieredPricingConfig | undefined | null): string {
  if (!tieredPricing?.tiers?.length) return '-'
  return get1hCachePrice(tieredPricing.tiers[0])
}
</script>

<style scoped>
.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.3s ease;
}

.drawer-enter-active .relative,
.drawer-leave-active .relative {
  transition: transform 0.3s ease;
}

.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}

.drawer-enter-from .relative {
  transform: translateX(100%);
}

.drawer-leave-to .relative {
  transform: translateX(100%);
}

.drawer-enter-to .relative,
.drawer-leave-from .relative {
  transform: translateX(0);
}
</style>
