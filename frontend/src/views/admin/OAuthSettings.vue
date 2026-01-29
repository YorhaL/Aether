<template>
  <PageContainer>
    <PageHeader
      title="OAuth 配置"
      description="配置 OAuth Providers（登录/绑定）"
    >
      <template #actions>
        <Button
          variant="outline"
          :disabled="loading"
          @click="loadAll"
        >
          刷新
        </Button>
      </template>
    </PageHeader>

    <div class="mt-6">
      <!-- Provider 选择 Tab -->
      <div class="flex flex-wrap gap-2 mb-6">
        <button
          v-for="t in supportedTypes"
          :key="t.provider_type"
          class="flex items-center gap-3 px-4 py-2 rounded-lg text-sm font-medium transition-colors border"
          :class="selectedType === t.provider_type
            ? 'border-primary text-primary'
            : 'border-border text-muted-foreground hover:border-primary/50 hover:text-foreground'"
          @click="handleTabClick(t.provider_type)"
        >
          <div class="flex flex-col items-center leading-none">
            <span>{{ t.display_name }}</span>
            <span class="text-[10px] text-muted-foreground">
              {{ configs[t.provider_type]
                ? (configs[t.provider_type]?.is_enabled ? '点击禁用' : '点击启用')
                : '未配置' }}
            </span>
          </div>
          <span
            class="w-2 h-2 rounded-full"
            :class="configs[t.provider_type]?.is_enabled ? 'bg-green-500' : 'bg-gray-300'"
          />
        </button>
      </div>

      <!-- 无 Provider 提示 -->
      <div
        v-if="supportedTypes.length === 0 && !loading"
        class="text-center py-12 text-muted-foreground"
      >
        未发现可用的 OAuth Provider
      </div>

      <!-- 配置表单 -->
      <CardSection
        v-if="selectedType"
        :title="selectedTypeMeta?.display_name || selectedType"
        :description="configs[selectedType]?.is_enabled ? '已启用' : '未配置'"
      >
        <template #actions>
          <div class="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              :disabled="saving || testing"
              @click="handleTest"
            >
              {{ testing ? '测试中...' : '测试' }}
            </Button>
            <Button
              size="sm"
              :disabled="saving"
              @click="handleSave"
            >
              {{ saving ? '保存中...' : '保存' }}
            </Button>
          </div>
        </template>

        <div class="space-y-6">
          <!-- 凭证配置 -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label class="block text-sm font-medium">Client ID</Label>
              <Input
                v-model="form.client_id"
                class="mt-1"
                placeholder="client_id"
                autocomplete="off"
              />
            </div>
            <div>
              <Label class="block text-sm font-medium">Client Secret</Label>
              <Input
                v-model="form.client_secret"
                masked
                class="mt-1"
                :placeholder="hasSecret ? '已设置（留空保持不变）' : '请输入 secret'"
              />
            </div>
          </div>

          <!-- 回调地址 -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label class="block text-sm font-medium">Redirect URI（后端回调）</Label>
              <Input
                v-model="form.redirect_uri"
                class="mt-1"
                placeholder="http://localhost:8084/api/oauth/xxx/callback"
                autocomplete="off"
              />
            </div>
            <div>
              <Label class="block text-sm font-medium">前端回调页</Label>
              <Input
                v-model="form.frontend_callback_url"
                class="mt-1"
                placeholder="http://localhost:5173/auth/callback"
                autocomplete="off"
              />
            </div>
          </div>

          <!-- 高级选项（折叠） -->
          <details class="group">
            <summary class="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
              高级选项
            </summary>
            <div class="mt-4 space-y-4 pl-4 border-l-2 border-border">
              <div>
                <Label class="block text-sm font-medium">Scopes</Label>
                <Input
                  v-model="form.scopes_input"
                  class="mt-1"
                  :placeholder="selectedTypeMeta?.default_scopes?.join(' ') || '留空使用默认值'"
                  autocomplete="off"
                />
                <p class="mt-1 text-xs text-muted-foreground">
                  空格/逗号分隔；留空使用默认值
                </p>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label class="block text-sm font-medium">Authorization URL</Label>
                  <Input
                    v-model="form.authorization_url_override"
                    class="mt-1"
                    :placeholder="selectedTypeMeta?.default_authorization_url || '默认'"
                    autocomplete="off"
                  />
                </div>
                <div>
                  <Label class="block text-sm font-medium">Token URL</Label>
                  <Input
                    v-model="form.token_url_override"
                    class="mt-1"
                    :placeholder="selectedTypeMeta?.default_token_url || '默认'"
                    autocomplete="off"
                  />
                </div>
                <div>
                  <Label class="block text-sm font-medium">Userinfo URL</Label>
                  <Input
                    v-model="form.userinfo_url_override"
                    class="mt-1"
                    :placeholder="selectedTypeMeta?.default_userinfo_url || '默认'"
                    autocomplete="off"
                  />
                </div>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label class="block text-sm font-medium">Attribute Mapping</Label>
                  <Textarea
                    v-model="form.attribute_mapping_json"
                    class="mt-1 font-mono text-xs"
                    rows="3"
                    placeholder="{&quot;id&quot;: &quot;user_id&quot;, &quot;username&quot;: &quot;login&quot;}"
                  />
                </div>
                <div>
                  <Label class="block text-sm font-medium">Extra Config</Label>
                  <Textarea
                    v-model="form.extra_config_json"
                    class="mt-1 font-mono text-xs"
                    rows="3"
                    placeholder="{&quot;min_trust_level&quot;: 1}"
                  />
                </div>
              </div>
            </div>
          </details>
        </div>

        <!-- 测试结果 -->
        <div
          v-if="lastTestResult"
          class="mt-6 rounded-lg border border-border p-4 text-sm"
        >
          <div class="font-medium mb-2">
            测试结果
          </div>
          <div class="flex flex-wrap gap-4 text-xs">
            <div class="flex items-center gap-2">
              <span
                class="w-2 h-2 rounded-full"
                :class="lastTestResult.authorization_url_reachable ? 'bg-green-500' : 'bg-red-500'"
              />
              <span class="text-muted-foreground">Authorization URL</span>
            </div>
            <div class="flex items-center gap-2">
              <span
                class="w-2 h-2 rounded-full"
                :class="lastTestResult.token_url_reachable ? 'bg-green-500' : 'bg-red-500'"
              />
              <span class="text-muted-foreground">Token URL</span>
            </div>
            <div class="flex items-center gap-2">
              <span
                class="w-2 h-2 rounded-full"
                :class="lastTestResult.secret_status === 'likely_valid' ? 'bg-green-500' : lastTestResult.secret_status === 'invalid' ? 'bg-red-500' : 'bg-yellow-500'"
              />
              <span class="text-muted-foreground">Secret: {{ lastTestResult.secret_status }}</span>
            </div>
            <span
              v-if="lastTestResult.details"
              class="text-muted-foreground"
            >
              {{ lastTestResult.details }}
            </span>
          </div>
        </div>
      </CardSection>
    </div>
  </PageContainer>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { oauthApi, type OAuthProviderAdminConfig, type OAuthProviderTestResponse, type SupportedOAuthType } from '@/api/oauth'
import { PageContainer, PageHeader, CardSection } from '@/components/layout'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Label from '@/components/ui/label.vue'
import Textarea from '@/components/ui/textarea.vue'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { log } from '@/utils/logger'
import { getErrorMessage, getErrorStatus, isApiError } from '@/types/api-error'

const { success, error: showError } = useToast()
const { confirmWarning } = useConfirm()

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)

const supportedTypes = ref<SupportedOAuthType[]>([])
const configs = ref<Record<string, OAuthProviderAdminConfig>>({})
const selectedType = ref<string>('')
const lastTestResult = ref<OAuthProviderTestResponse | null>(null)

const form = ref({
  client_id: '',
  client_secret: '',
  authorization_url_override: '',
  token_url_override: '',
  userinfo_url_override: '',
  scopes_input: '',
  redirect_uri: '',
  frontend_callback_url: '',
  attribute_mapping_json: '',
  extra_config_json: '',
})

const hasSecret = computed(() => !!configs.value[selectedType.value]?.has_secret)
const selectedTypeMeta = computed(() => supportedTypes.value.find((t) => t.provider_type === selectedType.value))

function defaultRedirectUri(providerType: string): string {
  return new URL(`/api/oauth/${providerType}/callback`, window.location.origin).toString()
}

function defaultFrontendCallbackUrl(): string {
  return new URL('/auth/callback', window.location.origin).toString()
}

function parseScopes(input: string): string[] | null {
  const raw = input.trim()
  if (!raw) return null
  const parts = raw.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean)
  return parts.length ? parts : null
}

function parseJsonOrNull(input: string): Record<string, any> | null {
  const raw = input.trim()
  if (!raw) return null
  return JSON.parse(raw)
}

function handleTabClick(providerType: string) {
  // 如果点击的是当前选中的 Provider，且已配置，则切换启用状态
  if (selectedType.value === providerType && configs.value[providerType]) {
    toggleProviderEnabled(providerType, !configs.value[providerType].is_enabled)
    return
  }
  // 否则切换到该 Provider
  selectedType.value = providerType
  syncFormFromSelected()
}

function syncFormFromSelected() {
  lastTestResult.value = null
  const cfg = configs.value[selectedType.value]

  form.value = {
    client_id: cfg?.client_id || '',
    client_secret: '',
    authorization_url_override: cfg?.authorization_url_override || '',
    token_url_override: cfg?.token_url_override || '',
    userinfo_url_override: cfg?.userinfo_url_override || '',
    scopes_input: (cfg?.scopes || []).join(' '),
    redirect_uri: cfg?.redirect_uri || defaultRedirectUri(selectedType.value),
    frontend_callback_url: cfg?.frontend_callback_url || defaultFrontendCallbackUrl(),
    attribute_mapping_json: cfg?.attribute_mapping ? JSON.stringify(cfg.attribute_mapping, null, 2) : '',
    extra_config_json: cfg?.extra_config ? JSON.stringify(cfg.extra_config, null, 2) : '',
  }
}

async function toggleProviderEnabled(providerType: string, enabled: boolean, force = false) {
  const cfg = configs.value[providerType]
  if (!cfg) {
    showError('请先保存配置后再启用')
    return
  }

  saving.value = true
  try {
    const payload = {
      display_name: cfg.display_name,
      client_id: cfg.client_id,
      redirect_uri: cfg.redirect_uri,
      frontend_callback_url: cfg.frontend_callback_url,
      is_enabled: enabled,
      force,
    }
    await oauthApi.admin.upsertProviderConfig(providerType, payload)
    success(enabled ? '已启用' : '已禁用')
    await loadAll()
  } catch (err: unknown) {
    // 检查是否是需要确认的冲突错误
    if (isApiError(err) && getErrorStatus(err) === 409) {
      const errorData = err.response?.data?.error
      if (errorData?.type === 'confirmation_required') {
        const affectedCount = errorData.details?.affected_count ?? 0
        const confirmed = await confirmWarning(
          `禁用该 Provider 会导致 ${affectedCount} 个用户无法登录，是否继续？`,
          '确认禁用'
        )
        if (confirmed) {
          await toggleProviderEnabled(providerType, enabled, true)
        }
        return
      }
    }
    showError(getErrorMessage(err, '操作失败'))
  } finally {
    saving.value = false
  }
}

async function loadAll() {
  loading.value = true
  try {
    const [types, list] = await Promise.all([
      oauthApi.admin.getSupportedTypes(),
      oauthApi.admin.listProviderConfigs(),
    ])
    supportedTypes.value = types
    configs.value = Object.fromEntries(list.map((c) => [c.provider_type, c]))

    if (!selectedType.value && supportedTypes.value.length > 0) {
      selectedType.value = supportedTypes.value[0].provider_type
    }

    if (selectedType.value) {
      syncFormFromSelected()
    }
  } catch (err: any) {
    log.error('加载 OAuth 配置失败:', err)
    showError(getErrorMessage(err, '加载失败'))
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!selectedType.value) return
  saving.value = true
  lastTestResult.value = null
  try {
    const typeMeta = supportedTypes.value.find((t) => t.provider_type === selectedType.value)
    const existingConfig = configs.value[selectedType.value]
    const payload = {
      display_name: typeMeta?.display_name || selectedType.value,
      client_id: form.value.client_id.trim(),
      client_secret: form.value.client_secret.trim() || undefined,
      authorization_url_override: form.value.authorization_url_override.trim() || null,
      token_url_override: form.value.token_url_override.trim() || null,
      userinfo_url_override: form.value.userinfo_url_override.trim() || null,
      scopes: parseScopes(form.value.scopes_input),
      redirect_uri: form.value.redirect_uri.trim(),
      frontend_callback_url: form.value.frontend_callback_url.trim(),
      attribute_mapping: parseJsonOrNull(form.value.attribute_mapping_json),
      extra_config: parseJsonOrNull(form.value.extra_config_json),
      is_enabled: existingConfig?.is_enabled || false,
    }

    await oauthApi.admin.upsertProviderConfig(selectedType.value, payload)
    success('保存成功')
    await loadAll()
  } catch (err: any) {
    showError(getErrorMessage(err, '保存失败'))
  } finally {
    saving.value = false
    form.value.client_secret = ''
  }
}

async function handleTest() {
  if (!selectedType.value) return
  testing.value = true
  try {
    const testPayload = {
      client_id: form.value.client_id.trim(),
      client_secret: form.value.client_secret.trim() || undefined,
      authorization_url_override: form.value.authorization_url_override.trim() || null,
      token_url_override: form.value.token_url_override.trim() || null,
      redirect_uri: form.value.redirect_uri.trim(),
    }
    lastTestResult.value = await oauthApi.admin.testProviderConfig(selectedType.value, testPayload)
    success('测试完成')
  } catch (err: any) {
    showError(getErrorMessage(err, '测试失败'))
  } finally {
    testing.value = false
  }
}

onMounted(async () => {
  await loadAll()
})
</script>
