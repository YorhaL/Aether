<template>
  <div class="space-y-6 pb-8">
    <Card
      variant="default"
      class="overflow-hidden"
    >
      <!-- 加载状态 -->
      <div
        v-if="loading"
        class="py-16 text-center space-y-4"
      >
        <Skeleton class="mx-auto h-10 w-10 rounded-full" />
        <Skeleton class="mx-auto h-4 w-32" />
      </div>

      <div v-else>
        <div class="px-6 py-3.5 border-b border-border/60">
          <div class="flex items-center justify-between gap-4">
            <div>
              <h3 class="text-base font-semibold">
                独立余额 API Keys
              </h3>
              <p class="text-xs text-muted-foreground mt-0.5">
                活跃 {{ activeKeyCount }} · 禁用 {{ inactiveKeyCount }} · 无限 Key {{ unlimitedKeyCount }}
                <span
                  v-if="expiringSoonCount > 0"
                  class="text-amber-600"
                > · 即将到期 {{ expiringSoonCount }}</span>
              </p>
            </div>
            <div class="flex items-center gap-2">
              <!-- 搜索框 -->
              <div class="relative">
                <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground z-10 pointer-events-none" />
                <Input
                  v-model="searchQuery"
                  type="text"
                  placeholder="搜索..."
                  class="h-8 w-40 pl-8 pr-2 text-xs"
                />
              </div>

              <!-- 分隔线 -->
              <div class="h-4 w-px bg-border" />

              <!-- 状态筛选 -->
              <Select
                v-model="filterStatus"
                v-model:open="filterStatusOpen"
              >
                <SelectTrigger class="w-28 h-8 text-xs border-border/60">
                  <SelectValue placeholder="全部状态" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem
                    v-for="status in statusFilters"
                    :key="status.value"
                    :value="status.value"
                  >
                    {{ status.label }}
                  </SelectItem>
                </SelectContent>
              </Select>

              <!-- 余额类型筛选 -->
              <Select
                v-model="filterBalance"
                v-model:open="filterBalanceOpen"
              >
                <SelectTrigger class="w-28 h-8 text-xs border-border/60">
                  <SelectValue placeholder="全部类型" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem
                    v-for="balance in balanceFilters"
                    :key="balance.value"
                    :value="balance.value"
                  >
                    {{ balance.label }}
                  </SelectItem>
                </SelectContent>
              </Select>

              <!-- 分隔线 -->
              <div class="h-4 w-px bg-border" />

              <!-- 创建独立 Key 按钮 -->
              <Button
                variant="ghost"
                size="icon"
                class="h-8 w-8"
                title="创建独立 Key"
                @click="openCreateDialog"
              >
                <Plus class="w-3.5 h-3.5" />
              </Button>

              <!-- 刷新按钮 -->
              <RefreshButton
                :loading="loading"
                @click="loadApiKeys"
              />
            </div>
          </div>
        </div>

        <div class="hidden xl:block overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow class="border-b border-border/60 hover:bg-transparent">
                <TableHead class="w-[200px] h-12 font-semibold">
                  密钥信息
                </TableHead>
                <TableHead class="w-[160px] h-12 font-semibold">
                  余额 (已用/总额)
                </TableHead>
                <TableHead class="w-[130px] h-12 font-semibold">
                  使用统计
                </TableHead>
                <TableHead class="w-[110px] h-12 font-semibold">
                  有效期
                </TableHead>
                <TableHead class="w-[140px] h-12 font-semibold">
                  最近使用
                </TableHead>
                <TableHead class="w-[70px] h-12 font-semibold text-center">
                  状态
                </TableHead>
                <TableHead class="w-[130px] h-12 font-semibold text-center">
                  操作
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-if="filteredApiKeys.length === 0">
                <TableCell
                  colspan="7"
                  class="h-64 text-center"
                >
                  <div class="flex flex-col items-center justify-center space-y-4">
                    <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                      <Key class="h-8 w-8 text-muted-foreground" />
                    </div>
                    <div v-if="hasActiveFilters">
                      <h3 class="text-lg font-semibold">
                        未找到匹配的 Key
                      </h3>
                      <p class="mt-2 text-sm text-muted-foreground">
                        尝试调整筛选条件
                      </p>
                      <Button
                        variant="outline"
                        size="sm"
                        class="mt-3"
                        @click="clearFilters"
                      >
                        清除筛选
                      </Button>
                    </div>
                    <div v-else>
                      <h3 class="text-lg font-semibold">
                        暂无独立余额 Key
                      </h3>
                      <p class="mt-2 text-sm text-muted-foreground">
                        点击右上角按钮创建独立余额 Key
                      </p>
                    </div>
                  </div>
                </TableCell>
              </TableRow>
              <TableRow
                v-for="apiKey in filteredApiKeys"
                :key="apiKey.id"
                class="border-b border-border/40 hover:bg-muted/30 transition-colors"
              >
                <TableCell class="py-4">
                  <div class="space-y-1">
                    <div
                      class="text-sm font-semibold text-foreground truncate"
                      :title="apiKey.name || '未命名 Key'"
                    >
                      {{ apiKey.name || '未命名 Key' }}
                    </div>
                    <div class="flex items-center gap-1.5">
                      <code class="text-xs font-mono text-muted-foreground">
                        {{ apiKey.key_display || 'sk-****' }}
                      </code>
                      <Button
                        variant="ghost"
                        size="icon"
                        class="h-6 w-6"
                        title="复制完整密钥"
                        @click="copyKeyPrefix(apiKey)"
                      >
                        <Copy class="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                </TableCell>
                <TableCell class="py-4">
                  <div class="text-xs">
                    <div class="flex items-center gap-1.5">
                      <span class="font-mono font-medium">${{ (apiKey.balance_used_usd || 0).toFixed(2) }}</span>
                      <span class="text-muted-foreground">/</span>
                      <span :class="isBalanceLimited(apiKey) ? 'font-mono font-medium text-primary' : 'font-mono text-muted-foreground'">
                        {{ isBalanceLimited(apiKey) ? `$${(apiKey.current_balance_usd || 0).toFixed(2)}` : '无限' }}
                      </span>
                    </div>
                  </div>
                </TableCell>
                <TableCell class="py-4">
                  <div class="space-y-1 text-xs">
                    <div class="text-muted-foreground">
                      请求: <span class="font-medium text-foreground">{{ (apiKey.total_requests || 0).toLocaleString() }}</span>
                    </div>
                    <div class="text-muted-foreground">
                      速率: <span class="font-medium text-foreground">{{ apiKey.rate_limit ? `${apiKey.rate_limit}/min` : '未设置' }}</span>
                    </div>
                  </div>
                </TableCell>
                <TableCell class="py-4">
                  <div class="text-xs">
                    <div
                      v-if="apiKey.expires_at"
                      class="space-y-1"
                    >
                      <div class="text-foreground">
                        {{ formatDate(apiKey.expires_at) }}
                      </div>
                      <div class="text-muted-foreground">
                        {{ getRelativeTime(apiKey.expires_at) }}
                      </div>
                    </div>
                    <div
                      v-else
                      class="text-muted-foreground"
                    >
                      永不过期
                    </div>
                  </div>
                </TableCell>
                <TableCell class="py-4">
                  <div class="text-xs">
                    <span
                      v-if="apiKey.last_used_at"
                      class="text-foreground"
                    >{{ formatDate(apiKey.last_used_at) }}</span>
                    <span
                      v-else
                      class="text-muted-foreground"
                    >暂无记录</span>
                  </div>
                </TableCell>
                <TableCell class="py-4 text-center">
                  <Badge
                    :variant="apiKey.is_active ? 'success' : 'destructive'"
                    class="font-medium"
                  >
                    {{ apiKey.is_active ? '活跃' : '禁用' }}
                  </Badge>
                </TableCell>
                <TableCell class="py-4">
                  <div class="flex justify-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      class="h-8 w-8"
                      title="编辑"
                      @click="editApiKey(apiKey)"
                    >
                      <SquarePen class="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="h-8 w-8"
                      title="调整余额"
                      @click="openAddBalanceDialog(apiKey)"
                    >
                      <DollarSign class="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="h-8 w-8"
                      :title="apiKey.is_active ? '禁用' : '启用'"
                      @click="toggleApiKey(apiKey)"
                    >
                      <Power class="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="h-8 w-8"
                      title="删除"
                      @click="deleteApiKey(apiKey)"
                    >
                      <Trash2 class="h-4 w-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        <div class="xl:hidden divide-y divide-border/40">
          <div
            v-if="apiKeys.length === 0"
            class="p-8 text-center"
          >
            <Key class="h-12 w-12 mx-auto mb-3 text-muted-foreground/50" />
            <p class="text-muted-foreground">
              暂无独立余额 Key
            </p>
          </div>
          <div
            v-for="apiKey in apiKeys"
            :key="apiKey.id"
            class="p-4 sm:p-5 hover:bg-muted/30 transition-colors"
          >
            <div class="space-y-4">
              <div class="flex items-start justify-between gap-3">
                <div class="space-y-2">
                  <div class="flex items-center gap-2">
                    <code class="inline-flex rounded-lg bg-muted px-3 py-1.5 text-xs font-mono font-semibold">
                      {{ apiKey.key_display || 'sk-****' }}
                    </code>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="h-7 w-7 hover:bg-muted flex-shrink-0"
                      title="复制完整密钥"
                      @click="copyKeyPrefix(apiKey)"
                    >
                      <Copy class="h-3.5 w-3.5" />
                    </Button>
                  </div>
                  <div
                    class="text-sm font-semibold text-foreground"
                    :class="{ 'text-muted-foreground': !apiKey.name }"
                  >
                    {{ apiKey.name || '未命名 Key' }}
                  </div>
                </div>
                <Badge
                  :variant="apiKey.is_active ? 'success' : 'destructive'"
                  class="text-xs flex-shrink-0"
                >
                  {{ apiKey.is_active ? '活跃' : '禁用' }}
                </Badge>
              </div>

              <div class="flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                <span class="inline-flex items-center gap-1 rounded-full border border-border/60 px-2.5 py-0.5">
                  {{ isBalanceLimited(apiKey) ? '限额 Key' : '无限额度' }}
                </span>
                <span
                  v-if="apiKey.auto_delete_on_expiry"
                  class="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5"
                >
                  过期自动删除
                </span>
              </div>

              <div class="space-y-2 p-3 bg-muted/50 rounded-lg text-xs">
                <div class="flex items-center justify-between text-muted-foreground">
                  <span>已用</span>
                  <span class="font-semibold">${{ (apiKey.balance_used_usd || 0).toFixed(2) }}</span>
                </div>
                <div class="flex items-center justify-between text-muted-foreground">
                  <span>剩余</span>
                  <span :class="getBalanceRemaining(apiKey) > 0 ? 'font-semibold text-emerald-600' : 'font-semibold text-rose-600'">
                    {{ isBalanceLimited(apiKey) ? `$${getBalanceRemaining(apiKey).toFixed(2)}` : '无限制' }}
                  </span>
                </div>
                <div class="flex items-center justify-between text-amber-600">
                  <span>总费用</span>
                  <span>${{ (apiKey.total_cost_usd || 0).toFixed(4) }}</span>
                </div>
                <div
                  v-if="isBalanceLimited(apiKey)"
                  class="h-1.5 rounded-full bg-background/40 overflow-hidden"
                >
                  <div
                    class="h-full rounded-full bg-emerald-500"
                    :style="{ width: `${getBalanceProgress(apiKey)}%` }"
                  />
                </div>
              </div>

              <div class="grid grid-cols-2 gap-2 text-xs">
                <div class="p-2 bg-muted/40 rounded-lg">
                  <div class="text-muted-foreground mb-1">
                    速率限制
                  </div>
                  <div class="font-semibold">
                    {{ apiKey.rate_limit ? `${apiKey.rate_limit}/min` : '未设置' }}
                  </div>
                </div>
                <div class="p-2 bg-muted/40 rounded-lg">
                  <div class="text-muted-foreground mb-1">
                    请求次数
                  </div>
                  <div class="font-semibold">
                    {{ (apiKey.total_requests || 0).toLocaleString() }}
                  </div>
                </div>
                <div class="p-2 bg-muted/40 rounded-lg col-span-2">
                  <div class="text-muted-foreground mb-1">
                    有效期
                  </div>
                  <div class="font-semibold">
                    {{ apiKey.expires_at ? formatDate(apiKey.expires_at) : '永不过期' }}
                  </div>
                  <div
                    v-if="apiKey.expires_at"
                    class="text-[11px] text-muted-foreground"
                  >
                    {{ getRelativeTime(apiKey.expires_at) }}
                  </div>
                </div>
              </div>

              <div class="text-xs text-muted-foreground space-y-1">
                <p>创建: {{ formatDate(apiKey.created_at) }}</p>
                <p>
                  最近使用:
                  <span
                    v-if="apiKey.last_used_at"
                    class="font-medium text-foreground"
                  >{{ formatDate(apiKey.last_used_at) }}</span>
                  <span v-else>暂无记录</span>
                </p>
                <p v-if="apiKey.expires_at">
                  过期后: {{ apiKey.auto_delete_on_expiry ? '自动删除' : '仅禁用' }}
                </p>
              </div>

              <div class="grid grid-cols-2 gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  @click="editApiKey(apiKey)"
                >
                  <SquarePen class="h-3.5 w-3.5 mr-1.5" />
                  编辑
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  class="text-blue-600"
                  @click="openAddBalanceDialog(apiKey)"
                >
                  <DollarSign class="h-3.5 w-3.5 mr-1.5" />
                  调整
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  @click="toggleApiKey(apiKey)"
                >
                  <Power class="h-3.5 w-3.5 mr-1.5" />
                  {{ apiKey.is_active ? '禁用' : '启用' }}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  class="text-rose-600"
                  @click="deleteApiKey(apiKey)"
                >
                  <Trash2 class="h-3.5 w-3.5 mr-1.5" />
                  删除
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <Pagination
        v-if="!loading && apiKeys.length > 0"
        :current="currentPage"
        :total="total"
        :page-size="limit"
        :show-page-size-selector="false"
        @update:current="handlePageChange"
      />
    </Card>

    <!-- 创建/编辑独立Key对话框 -->
    <StandaloneKeyFormDialog
      ref="keyFormDialogRef"
      :open="showKeyFormDialog"
      :api-key="editingKeyData"
      @close="closeKeyFormDialog"
      @submit="handleKeyFormSubmit"
    />

    <!-- 新 Key 显示对话框 -->
    <Dialog
      v-model="showNewKeyDialog"
      size="lg"
    >
      <template #header>
        <div class="border-b border-border px-6 py-4">
          <div class="flex items-center gap-3">
            <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-900/30 flex-shrink-0">
              <CheckCircle class="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <div class="flex-1 min-w-0">
              <h3 class="text-lg font-semibold text-foreground leading-tight">
                创建成功
              </h3>
              <p class="text-xs text-muted-foreground">
                请妥善保管, 切勿泄露给他人.
              </p>
            </div>
          </div>
        </div>
      </template>

      <div class="space-y-4">
        <div class="space-y-2">
          <Label class="text-sm font-medium">API Key</Label>
          <div class="flex items-center gap-2">
            <Input
              ref="keyInput"
              type="text"
              :value="newKeyValue"
              readonly
              class="flex-1 font-mono text-sm bg-muted/50 h-11"
              @click="selectKey"
            />
            <Button
              class="h-11"
              @click="copyKey"
            >
              复制
            </Button>
          </div>
        </div>
      </div>

      <template #footer>
        <Button
          class="h-10 px-5"
          @click="closeNewKeyDialog"
        >
          确定
        </Button>
      </template>
    </Dialog>

    <!-- 余额调整对话框 -->
    <Dialog
      v-model="showAddBalanceDialog"
      size="md"
    >
      <template #header>
        <div class="border-b border-border px-6 py-4">
          <div class="flex items-center gap-3">
            <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900/30 flex-shrink-0">
              <DollarSign class="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div class="flex-1 min-w-0">
              <h3 class="text-lg font-semibold text-foreground leading-tight">
                余额调整
              </h3>
              <p class="text-xs text-muted-foreground">
                增加或扣除 API Key 余额
              </p>
            </div>
          </div>
        </div>
      </template>

      <div class="space-y-4">
        <div class="p-3 bg-muted/50 rounded-lg text-sm">
          <div class="font-medium mb-2">
            当前余额信息
          </div>
          <div class="space-y-1 text-xs text-muted-foreground">
            <div>已用: <span class="font-semibold text-foreground">${{ (addBalanceKey.balance_used_usd || 0).toFixed(2) }}</span></div>
            <div>当前余额: <span class="font-semibold text-foreground">${{ (addBalanceKey.current_balance_usd || 0).toFixed(2) }}</span></div>
          </div>
        </div>

        <div class="space-y-2">
          <Label
            for="addBalanceAmount"
            class="text-sm font-medium"
          >调整金额 (USD)</Label>
          <Input
            id="addBalanceAmount"
            :model-value="addBalanceAmount ?? ''"
            type="number"
            step="0.01"
            placeholder="正数为增加，负数为扣除"
            class="h-11"
            @update:model-value="(v) => addBalanceAmount = parseNumberInput(v, { allowFloat: true })"
          />
          <p class="text-xs text-muted-foreground">
            <span
              v-if="addBalanceAmount && addBalanceAmount > 0"
              class="text-emerald-600"
            >
              增加 ${{ addBalanceAmount.toFixed(2) }}，调整后余额: ${{ ((addBalanceKey.current_balance_usd || 0) + addBalanceAmount).toFixed(2) }}
            </span>
            <span
              v-else-if="addBalanceAmount && addBalanceAmount < 0"
              class="text-rose-600"
            >
              扣除 ${{ Math.abs(addBalanceAmount).toFixed(2) }}，调整后余额: ${{ Math.max(0, (addBalanceKey.current_balance_usd || 0) + addBalanceAmount).toFixed(2) }}
            </span>
            <span
              v-else
              class="text-muted-foreground"
            >
              输入正数增加余额，负数扣除余额
            </span>
          </p>
        </div>
      </div>

      <template #footer>
        <div class="flex gap-3 justify-end">
          <Button
            variant="outline"
            class="h-10 px-5"
            @click="showAddBalanceDialog = false"
          >
            取消
          </Button>
          <Button
            :disabled="addingBalance || !addBalanceAmount || addBalanceAmount === 0"
            class="h-10 px-5"
            @click="handleAddBalance"
          >
            {{ addingBalance ? '调整中...' : '确认调整' }}
          </Button>
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { adminApi, type AdminApiKey, type CreateStandaloneApiKeyRequest } from '@/api/admin'

import {
  Dialog,
  Card,
  Button,
  Badge,
  Input,
  Skeleton,
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  Pagination,
  RefreshButton,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
  Label
} from '@/components/ui'

import {
  Plus,
  Key,
  Trash2,
  Power,
  DollarSign,
  Copy,
  CheckCircle,
  SquarePen,
  Search
} from 'lucide-vue-next'

import { StandaloneKeyFormDialog, type StandaloneKeyFormData } from '@/features/api-keys'
import { parseNumberInput } from '@/utils/form'
import { log } from '@/utils/logger'

const { success, error } = useToast()
const { confirmDanger } = useConfirm()

const apiKeys = ref<AdminApiKey[]>([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const limit = ref(100)
const showNewKeyDialog = ref(false)
const newKeyValue = ref('')
const keyInput = ref<HTMLInputElement>()

// 统一的表单对话框状态
const showKeyFormDialog = ref(false)
const editingKeyData = ref<StandaloneKeyFormData | null>(null)
const keyFormDialogRef = ref<InstanceType<typeof StandaloneKeyFormDialog>>()

const EXPIRY_SOON_DAYS = 7

// 筛选相关
const searchQuery = ref('')
const filterStatus = ref<'all' | 'active' | 'inactive'>('all')
const filterStatusOpen = ref(false)
const filterBalance = ref<'all' | 'limited' | 'unlimited'>('all')
const filterBalanceOpen = ref(false)

const statusFilters = [
  { value: 'all' as const, label: '全部状态' },
  { value: 'active' as const, label: '活跃' },
  { value: 'inactive' as const, label: '禁用' }
]

const balanceFilters = [
  { value: 'all' as const, label: '全部类型' },
  { value: 'limited' as const, label: '限额' },
  { value: 'unlimited' as const, label: '无限' }
]

const hasActiveFilters = computed(() => {
  return searchQuery.value !== '' || filterStatus.value !== 'all' || filterBalance.value !== 'all'
})

function clearFilters() {
  searchQuery.value = ''
  filterStatus.value = 'all'
  filterBalance.value = 'all'
}

const skip = computed(() => (currentPage.value - 1) * limit.value)

const activeKeyCount = computed(() => apiKeys.value.filter(key => key.is_active).length)
const inactiveKeyCount = computed(() => Math.max(0, apiKeys.value.length - activeKeyCount.value))
const limitedKeyCount = computed(() => apiKeys.value.filter(isBalanceLimited).length)
const unlimitedKeyCount = computed(() => Math.max(0, apiKeys.value.length - limitedKeyCount.value))
const expiringSoonCount = computed(() => apiKeys.value.filter(key => isExpiringSoon(key)).length)

// 筛选后的 API Keys
const filteredApiKeys = computed(() => {
  let result = apiKeys.value

  // 搜索筛选
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(key =>
      (key.name && key.name.toLowerCase().includes(query)) ||
      (key.key_display && key.key_display.toLowerCase().includes(query)) ||
      (key.username && key.username.toLowerCase().includes(query)) ||
      (key.user_email && key.user_email.toLowerCase().includes(query))
    )
  }

  // 状态筛选
  if (filterStatus.value === 'active') {
    result = result.filter(key => key.is_active)
  } else if (filterStatus.value === 'inactive') {
    result = result.filter(key => !key.is_active)
  }

  // 余额类型筛选
  if (filterBalance.value === 'limited') {
    result = result.filter(isBalanceLimited)
  } else if (filterBalance.value === 'unlimited') {
    result = result.filter(key => !isBalanceLimited(key))
  }

  return result
})

// 充值相关状态
const showAddBalanceDialog = ref(false)
const addBalanceKey = ref({
  id: '',
  name: '',
  balance_used_usd: 0,
  current_balance_usd: 0
})
const addBalanceAmount = ref<number | undefined>(undefined)
const addingBalance = ref(false)

onMounted(async () => {
  await loadApiKeys()
})

async function loadApiKeys() {
  loading.value = true
  try {
    const response = await adminApi.getAllApiKeys({
      skip: skip.value,
      limit: limit.value
    })
    apiKeys.value = response.api_keys
    total.value = response.total
  } catch (err: any) {
    log.error('加载独立Keys失败:', err)
    error(err.response?.data?.detail || '加载独立 Keys 失败')
  } finally {
    loading.value = false
  }
}

function handlePageChange(page: number) {
  currentPage.value = page
  loadApiKeys()
}

async function toggleApiKey(apiKey: AdminApiKey) {
  try {
    const response = await adminApi.toggleApiKey(apiKey.id)
    const index = apiKeys.value.findIndex(k => k.id === apiKey.id)
    if (index !== -1) {
      apiKeys.value[index].is_active = response.is_active
    }
    success(response.message)
  } catch (err: any) {
    log.error('切换密钥状态失败:', err)
    error(err.response?.data?.detail || '操作失败')
  }
}

async function deleteApiKey(apiKey: AdminApiKey) {
  const confirmed = await confirmDanger(
    `确定要删除这个独立余额 Key 吗？\n\n${apiKey.name || apiKey.key_display || 'sk-****'}\n\n此操作无法撤销。`,
    '删除独立 Key'
  )

  if (!confirmed) return

  try {
    const response = await adminApi.deleteApiKey(apiKey.id)
    apiKeys.value = apiKeys.value.filter(k => k.id !== apiKey.id)
    total.value = total.value - 1
    success(response.message)
  } catch (err: any) {
    log.error('删除密钥失败:', err)
    error(err.response?.data?.detail || '删除失败')
  }
}

function editApiKey(apiKey: AdminApiKey) {
  // 计算过期天数
  let expireDays: number | undefined = undefined
  let neverExpire = true

  if (apiKey.expires_at) {
    const expiresDate = new Date(apiKey.expires_at)
    const now = new Date()
    const diffMs = expiresDate.getTime() - now.getTime()
    const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))

    if (diffDays > 0) {
      expireDays = diffDays
      neverExpire = false
    }
  }

  editingKeyData.value = {
    id: apiKey.id,
    name: apiKey.name || '',
    expire_days: expireDays,
    never_expire: neverExpire,
    rate_limit: apiKey.rate_limit || 100,
    auto_delete_on_expiry: apiKey.auto_delete_on_expiry || false,
    allowed_providers: apiKey.allowed_providers || [],
    allowed_api_formats: apiKey.allowed_api_formats || [],
    allowed_models: apiKey.allowed_models || []
  }

  showKeyFormDialog.value = true
}

function openAddBalanceDialog(apiKey: AdminApiKey) {
  addBalanceKey.value = {
    id: apiKey.id,
    name: apiKey.name || apiKey.key_display || 'sk-****',
    balance_used_usd: apiKey.balance_used_usd || 0,
    current_balance_usd: apiKey.current_balance_usd || 0
  }

  addBalanceAmount.value = undefined
  showAddBalanceDialog.value = true
}

async function handleAddBalance() {
  if (!addBalanceAmount.value || addBalanceAmount.value === 0) {
    error('调整金额不能为 0')
    return
  }

  // 验证扣除金额不能超过当前余额
  if (addBalanceAmount.value < 0 && Math.abs(addBalanceAmount.value) > (addBalanceKey.value.current_balance_usd || 0)) {
    error('扣除金额不能超过当前余额')
    return
  }

  addingBalance.value = true
  try {
    const response = await adminApi.addApiKeyBalance(addBalanceKey.value.id, addBalanceAmount.value)

    // 重新加载列表
    await loadApiKeys()

    showAddBalanceDialog.value = false
    const action = addBalanceAmount.value > 0 ? '增加' : '扣除'
    const amount = Math.abs(addBalanceAmount.value).toFixed(2)
    success(response.message || `余额${action}成功，${action} $${amount}`)
  } catch (err: any) {
    log.error('余额调整失败:', err)
    error(err.response?.data?.detail || '调整失败')
  } finally {
    addingBalance.value = false
  }
}

function selectKey() {
  keyInput.value?.select()
}

async function copyKey() {
  try {
    await navigator.clipboard.writeText(newKeyValue.value)
    success('API Key 已复制到剪贴板')
  } catch {
    error('复制失败，请手动复制')
  }
}

async function copyKeyPrefix(apiKey: AdminApiKey) {
  try {
    // 调用后端 API 获取完整密钥
    const response = await adminApi.getFullApiKey(apiKey.id)
    await navigator.clipboard.writeText(response.key)
    success('完整密钥已复制到剪贴板')
  } catch (err) {
    log.error('复制密钥失败:', err)
    error('复制失败，请重试')
  }
}

function closeNewKeyDialog() {
  showNewKeyDialog.value = false
  newKeyValue.value = ''
}

function isBalanceLimited(apiKey: AdminApiKey): boolean {
  return apiKey.current_balance_usd !== null && apiKey.current_balance_usd !== undefined
}

function getBalanceProgress(apiKey: AdminApiKey): number {
  if (!isBalanceLimited(apiKey)) {
    return 0
  }

  // 总额 = 当前余额 + 已使用
  const used = apiKey.balance_used_usd || 0
  const remaining = apiKey.current_balance_usd || 0
  const total = used + remaining

  if (total <= 0) {
    return 0
  }

  // 进度条显示剩余比例（绿色部分）
  const ratio = (remaining / total) * 100
  const normalized = Number.isFinite(ratio) ? ratio : 0
  return Math.max(0, Math.min(100, normalized))
}

function isExpiringSoon(apiKey: AdminApiKey): boolean {
  if (!apiKey.expires_at) {
    return false
  }

  const expiresAt = new Date(apiKey.expires_at).getTime()
  const now = Date.now()
  const diffDays = (expiresAt - now) / (1000 * 60 * 60 * 24)
  return diffDays > 0 && diffDays <= EXPIRY_SOON_DAYS
}

function getBalanceRemaining(apiKey: AdminApiKey): number {
  // 计算剩余余额 = 当前余额 - 已使用余额
  if (apiKey.current_balance_usd === null || apiKey.current_balance_usd === undefined) {
    return 0
  }
  const remaining = apiKey.current_balance_usd - (apiKey.balance_used_usd || 0)
  return Math.max(0, remaining)  // 不能为负数
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function getRelativeTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diff = date.getTime() - now.getTime()

  if (diff < 0) return '已过期'

  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  const hours = Math.floor(diff / (1000 * 60 * 60))

  if (days > 0) return `${days}天后过期`
  if (hours > 0) return `${hours}小时后过期`
  return '即将过期'
}

// ========== 统一表单对话框方法 ==========

// 打开创建对话框
function openCreateDialog() {
  editingKeyData.value = null
  showKeyFormDialog.value = true
}

// 关闭表单对话框
function closeKeyFormDialog() {
  showKeyFormDialog.value = false
  editingKeyData.value = null
}

// 统一处理表单提交
async function handleKeyFormSubmit(data: StandaloneKeyFormData) {
  keyFormDialogRef.value?.setSaving(true)
  try {
    if (data.id) {
      // 更新
      const updateData: Partial<CreateStandaloneApiKeyRequest> = {
        name: data.name || undefined,
        rate_limit: data.rate_limit,
        expire_days: data.never_expire ? null : (data.expire_days || null),
        auto_delete_on_expiry: data.auto_delete_on_expiry,
        allowed_providers: data.allowed_providers.length > 0 ? data.allowed_providers : undefined,
        allowed_api_formats: data.allowed_api_formats.length > 0 ? data.allowed_api_formats : undefined,
        allowed_models: data.allowed_models.length > 0 ? data.allowed_models : undefined
      }
      await adminApi.updateApiKey(data.id, updateData)
      success('API Key 更新成功')
    } else {
      // 创建
      if (!data.initial_balance_usd || data.initial_balance_usd <= 0) {
        error('初始余额必须大于 0')
        return
      }
      const createData: CreateStandaloneApiKeyRequest = {
        name: data.name || undefined,
        initial_balance_usd: data.initial_balance_usd,
        rate_limit: data.rate_limit,
        expire_days: data.never_expire ? null : (data.expire_days || null),
        auto_delete_on_expiry: data.auto_delete_on_expiry,
        allowed_providers: data.allowed_providers.length > 0 ? data.allowed_providers : undefined,
        allowed_api_formats: data.allowed_api_formats.length > 0 ? data.allowed_api_formats : undefined,
        allowed_models: data.allowed_models.length > 0 ? data.allowed_models : undefined
      }
      const response = await adminApi.createStandaloneApiKey(createData)
      newKeyValue.value = response.key
      showNewKeyDialog.value = true
      success('独立 Key 创建成功')
    }
    closeKeyFormDialog()
    await loadApiKeys()
  } catch (err: any) {
    log.error('保存独立Key失败:', err)
    error(err.response?.data?.detail || '保存失败')
  } finally {
    keyFormDialogRef.value?.setSaving(false)
  }
}
</script>
