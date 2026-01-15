<template>
  <Dialog
    v-model="isOpen"
    size="lg"
  >
    <div class="space-y-6">
      <!-- Logo 和标题 -->
      <div class="flex flex-col items-center text-center">
        <div class="mb-4 rounded-3xl border border-primary/30 dark:border-[#cc785c]/30 bg-primary/5 dark:bg-transparent p-4 shadow-inner shadow-white/40 dark:shadow-[#cc785c]/10">
          <img
            src="/aether_adaptive.svg"
            alt="Logo"
            class="h-16 w-16"
          >
        </div>
        <h2 class="text-2xl font-semibold text-slate-900 dark:text-white">
          欢迎回来
        </h2>
      </div>

      <!-- Demo 模式提示 -->
      <div
        v-if="isDemo"
        class="rounded-lg border border-primary/20 dark:border-primary/30 bg-primary/5 dark:bg-primary/10 p-4"
      >
        <div class="flex items-start gap-3">
          <div class="flex-shrink-0 text-primary dark:text-primary/90">
            <svg
              class="h-5 w-5"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fill-rule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
                clip-rule="evenodd"
              />
            </svg>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-foreground">
              演示模式
            </p>
            <p class="mt-1 text-xs text-muted-foreground">
              当前处于演示模式，所有数据均为模拟数据。
            </p>
            <div class="mt-3 space-y-2">
              <button
                type="button"
                class="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors group"
                @click="fillDemoAccount('admin')"
              >
                <span class="inline-flex items-center justify-center w-5 h-5 rounded bg-primary/20 dark:bg-primary/30 text-primary text-[10px] font-bold group-hover:bg-primary/30 dark:group-hover:bg-primary/40 transition-colors">A</span>
                <span>管理员：admin@demo.aether.io / demo123</span>
              </button>
              <button
                type="button"
                class="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors group"
                @click="fillDemoAccount('user')"
              >
                <span class="inline-flex items-center justify-center w-5 h-5 rounded bg-muted text-muted-foreground text-[10px] font-bold group-hover:bg-muted/80 transition-colors">U</span>
                <span>普通用户：user@demo.aether.io / demo123</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 认证方式切换 -->
      <div
        v-if="showAuthTypeTabs"
        class="auth-type-tabs"
      >
        <button
          type="button"
          class="auth-tab"
          :class="[authType === 'local' && 'active']"
          @click="authType = 'local'"
        >
          本地登录
        </button>
        <button
          type="button"
          class="auth-tab"
          :class="[authType === 'ldap' && 'active']"
          @click="authType = 'ldap'"
        >
          LDAP 登录
        </button>
      </div>


      <!-- 登录表单 -->
      <form
        class="space-y-4"
        @submit.prevent="handleLogin"
      >
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <Label for="login-email">{{ emailLabel }}</Label>
            <button
              v-if="ldapExclusive && authType === 'ldap'"
              type="button"
              class="text-xs text-muted-foreground/60 hover:text-muted-foreground transition-colors"
              @click="authType = 'local'"
            >
              管理员本地登录
            </button>
            <button
              v-if="ldapExclusive && authType === 'local'"
              type="button"
              class="text-xs text-muted-foreground/60 hover:text-muted-foreground transition-colors"
              @click="authType = 'ldap'"
            >
              返回 LDAP 登录
            </button>
          </div>
          <Input
            id="login-email"
            v-model="form.email"
            type="text"
            required
            placeholder="username 或 email"
            autocomplete="off"
          />
        </div>

        <div class="space-y-2">
          <Label for="login-password">密码</Label>
          <Input
            id="login-password"
            v-model="form.password"
            type="password"
            required
            placeholder="********"
            autocomplete="off"
            @keyup.enter="handleLogin"
          />
        </div>

        <!-- 提示信息 -->
        <p
          v-if="!isDemo && !allowRegistration"
          class="text-xs text-slate-400 dark:text-muted-foreground/80"
        >
          如需开通账户，请联系管理员配置访问权限
        </p>
      </form>

      <!-- 注册链接 -->
      <div
        v-if="allowRegistration"
        class="mt-4 text-center text-sm"
      >
        还没有账户？
        <Button
          variant="link"
          class="h-auto p-0"
          @click="handleSwitchToRegister"
        >
          立即注册
        </Button>
      </div>
    </div>

    <template #footer>
      <Button
        type="button"
        variant="outline"
        class="w-full sm:w-auto border-slate-200 dark:border-slate-600 text-slate-500 dark:text-slate-400 hover:text-primary hover:border-primary/50 hover:bg-primary/5 dark:hover:text-primary dark:hover:border-primary/50 dark:hover:bg-primary/10"
        @click="isOpen = false"
      >
        取消
      </Button>
      <Button
        :disabled="authStore.loading"
        class="w-full sm:w-auto bg-primary hover:bg-primary/90 text-white border-0"
        @click="handleLogin"
      >
        {{ authStore.loading ? '登录中...' : '登录' }}
      </Button>
    </template>
  </Dialog>

  <!-- Register Dialog -->
  <RegisterDialog
    v-model:open="showRegisterDialog"
    :require-email-verification="requireEmailVerification"
    @success="handleRegisterSuccess"
    @switch-to-login="handleSwitchToLogin"
  />
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog } from '@/components/ui'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Label from '@/components/ui/label.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { isDemoMode, DEMO_ACCOUNTS } from '@/config/demo'
import RegisterDialog from './RegisterDialog.vue'
import { authApi } from '@/api/auth'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const router = useRouter()
const authStore = useAuthStore()
const { success: showSuccess, warning: showWarning, error: showError } = useToast()

const isOpen = ref(props.modelValue)
const isDemo = computed(() => isDemoMode())
const showRegisterDialog = ref(false)
const requireEmailVerification = ref(false)
const allowRegistration = ref(false) // 由系统配置控制，默认关闭

// LDAP authentication settings
const PREFERRED_AUTH_TYPE_KEY = 'aether_preferred_auth_type'
function getStoredAuthType(): 'local' | 'ldap' {
  const stored = localStorage.getItem(PREFERRED_AUTH_TYPE_KEY)
  return (stored === 'ldap' || stored === 'local') ? stored : 'local'
}
const authType = ref<'local' | 'ldap'>(getStoredAuthType())
const localEnabled = ref(true)
const ldapEnabled = ref(false)
const ldapExclusive = ref(false)

// 保存用户的认证类型偏好
watch(authType, (newType) => {
  localStorage.setItem(PREFERRED_AUTH_TYPE_KEY, newType)
})

const showAuthTypeTabs = computed(() => {
  return localEnabled.value && ldapEnabled.value && !ldapExclusive.value
})

const emailLabel = computed(() => {
  return '用户名/邮箱'
})

watch(() => props.modelValue, (val) => {
  isOpen.value = val
  // 打开对话框时重置表单
  if (val) {
    form.value = {
      email: '',
      password: ''
    }
  }
})

watch(isOpen, (val) => {
  emit('update:modelValue', val)
})

const form = ref({
  email: '',
  password: ''
})

function fillDemoAccount(type: 'admin' | 'user') {
  const account = DEMO_ACCOUNTS[type]
  form.value.email = account.email
  form.value.password = account.password
}

async function handleLogin() {
  if (!form.value.email || !form.value.password) {
    showWarning('请输入邮箱和密码')
    return
  }

  const success = await authStore.login(form.value.email, form.value.password, authType.value)
  if (success) {
    showSuccess('登录成功，正在跳转...')

    // 关闭对话框
    isOpen.value = false

    // 延迟一下让用户看到成功消息
    setTimeout(() => {
      // 根据用户角色跳转到不同的仪表盘
      const targetPath = authStore.user?.role === 'admin' ? '/admin/dashboard' : '/dashboard'
      router.push(targetPath)
    }, 1000)
  } else {
    showError(authStore.error || '登录失败，请检查邮箱和密码')
  }
}

function handleSwitchToRegister() {
  isOpen.value = false
  showRegisterDialog.value = true
}

function handleRegisterSuccess() {
  showRegisterDialog.value = false
  showSuccess('注册成功！请登录')
  isOpen.value = true
}

function handleSwitchToLogin() {
  showRegisterDialog.value = false
  isOpen.value = true
}

// Load authentication and registration settings on mount
onMounted(async () => {
  try {
    // Load registration settings
    const regSettings = await authApi.getRegistrationSettings()
    allowRegistration.value = !!regSettings.enable_registration
    requireEmailVerification.value = !!regSettings.require_email_verification

    // Load authentication settings
    const authSettings = await authApi.getAuthSettings()
    localEnabled.value = authSettings.local_enabled
    ldapEnabled.value = authSettings.ldap_enabled
    ldapExclusive.value = authSettings.ldap_exclusive
    // 若仅允许 LDAP 登录，则禁用本地注册入口
    if (ldapExclusive.value) {
      allowRegistration.value = false
    }

    // Set default auth type based on settings
    if (authSettings.ldap_exclusive) {
      authType.value = 'ldap'
    } else if (!authSettings.local_enabled && authSettings.ldap_enabled) {
      authType.value = 'ldap'
    } else {
      authType.value = 'local'
    }
  } catch {
    // If获取失败，保持默认：关闭注册 & 关闭邮箱验证 & 使用本地认证
    allowRegistration.value = false
    requireEmailVerification.value = false
    localEnabled.value = true
    ldapEnabled.value = false
    ldapExclusive.value = false
    authType.value = 'local'
  }
})
</script>

<style scoped>
.auth-type-tabs {
  display: flex;
  border-bottom: 1px solid hsl(var(--border));
}

.auth-tab {
  flex: 1;
  padding: 0.625rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: hsl(var(--muted-foreground));
  background: transparent;
  border: none;
  cursor: pointer;
  transition: color 0.15s ease;
  position: relative;
}

.auth-tab::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 2px;
  background: transparent;
  transition: background 0.15s ease;
}

.auth-tab:hover:not(.active) {
  color: hsl(var(--foreground));
}

.auth-tab.active {
  color: var(--book-cloth);
  font-weight: 600;
}

.auth-tab.active::after {
  background: var(--book-cloth);
}
</style>
