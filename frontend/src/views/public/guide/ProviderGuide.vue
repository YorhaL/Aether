<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { ArrowRight, Server, Plus, Settings, Check, AlertTriangle, Info } from 'lucide-vue-next'
import { apiFormats, panelClasses } from './guide-config'

const props = withDefaults(
  defineProps<{
    baseUrl?: string
  }>(),
  {
    baseUrl: typeof window !== 'undefined' ? window.location.origin : 'https://your-aether.com'
  }
)

// 端点配置字段说明
const endpointFields = [
  { name: '名称', description: '端点的显示名称，用于区分不同的端点', required: true },
  { name: 'URL', description: 'API 的基础 URL，如 https://api.openai.com', required: true },
  { name: 'API Key', description: '调用该 API 需要的密钥', required: true },
  { name: 'API 格式', description: '该端点支持的 API 格式（OpenAI/Claude/Gemini 等）', required: true },
  { name: '优先级', description: '数字越大优先级越高，用于负载均衡', required: false },
  { name: '权重', description: '加权负载均衡时使用的权重值', required: false },
  { name: '代理', description: '如需通过代理访问，填写代理地址', required: false },
  { name: '超时', description: '请求超时时间（秒）', required: false }
]

// 常见供应商配置示例
const providerExamples = [
  {
    name: 'OpenAI',
    url: 'https://api.openai.com',
    format: 'OpenAI Chat',
    note: '官方 API，需要国际信用卡或通过代理访问'
  },
  {
    name: 'Anthropic',
    url: 'https://api.anthropic.com',
    format: 'Claude Chat',
    note: '官方 Claude API'
  },
  {
    name: 'Google AI',
    url: 'https://generativelanguage.googleapis.com',
    format: 'Gemini Chat',
    note: '官方 Gemini API'
  },
  {
    name: 'Azure OpenAI',
    url: 'https://{resource}.openai.azure.com',
    format: 'OpenAI Chat',
    note: '需要替换 {resource} 为你的资源名'
  },
  {
    name: 'OpenRouter',
    url: 'https://openrouter.ai/api',
    format: 'OpenAI Chat',
    note: '聚合多家供应商的 API 代理'
  },
  {
    name: '自托管 / 其他',
    url: 'https://your-api.com',
    format: 'OpenAI Chat',
    note: '大多数 OpenAI 兼容服务选择 OpenAI Chat 格式'
  }
]
</script>

<template>
  <div class="space-y-8">
    <!-- 标题 -->
    <div class="space-y-4">
      <h1 class="text-3xl font-bold text-[#262624] dark:text-[#f1ead8]">
        供应商管理
      </h1>
      <p class="text-lg text-[#666663] dark:text-[#a3a094]">
        供应商和端点是 Aether 的基础配置，决定了系统可以调用哪些 AI 服务。
      </p>
    </div>

    <!-- 概念说明 -->
    <section class="space-y-4">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        供应商 vs 端点
      </h2>

      <div class="grid gap-4 md:grid-cols-2">
        <div :class="[panelClasses.section, 'p-5']">
          <div class="flex items-center gap-3 mb-3">
            <div class="p-2 rounded-lg bg-blue-500/10">
              <Server class="h-5 w-5 text-blue-500" />
            </div>
            <h3 class="font-semibold text-[#262624] dark:text-[#f1ead8]">供应商 (Provider)</h3>
          </div>
          <ul class="space-y-2 text-sm text-[#666663] dark:text-[#a3a094]">
            <li class="flex items-start gap-2">
              <Check class="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
              <span>逻辑分组，用于组织管理多个端点</span>
            </li>
            <li class="flex items-start gap-2">
              <Check class="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
              <span>一个供应商可以有多个端点</span>
            </li>
            <li class="flex items-start gap-2">
              <Check class="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
              <span>例如：OpenAI 供应商下可以有官方端点和多个代理端点</span>
            </li>
          </ul>
        </div>

        <div :class="[panelClasses.section, 'p-5']">
          <div class="flex items-center gap-3 mb-3">
            <div class="p-2 rounded-lg bg-green-500/10">
              <Settings class="h-5 w-5 text-green-500" />
            </div>
            <h3 class="font-semibold text-[#262624] dark:text-[#f1ead8]">端点 (Endpoint)</h3>
          </div>
          <ul class="space-y-2 text-sm text-[#666663] dark:text-[#a3a094]">
            <li class="flex items-start gap-2">
              <Check class="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
              <span>实际的 API 配置单元</span>
            </li>
            <li class="flex items-start gap-2">
              <Check class="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
              <span>包含 URL、密钥、API 格式等信息</span>
            </li>
            <li class="flex items-start gap-2">
              <Check class="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
              <span>系统实际调用的是端点，而非供应商</span>
            </li>
          </ul>
        </div>
      </div>
    </section>

    <!-- 添加供应商步骤 -->
    <section class="space-y-4">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        添加供应商
      </h2>

      <div :class="[panelClasses.section, 'p-5 space-y-4']">
        <div class="flex items-start gap-4">
          <div class="w-8 h-8 rounded-full bg-[#cc785c] flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
            1
          </div>
          <div>
            <h3 class="font-semibold text-[#262624] dark:text-[#f1ead8]">进入供应商管理页面</h3>
            <p class="text-sm text-[#666663] dark:text-[#a3a094] mt-1">
              登录管理后台，在左侧菜单点击「供应商管理」
            </p>
          </div>
        </div>

        <div class="flex items-start gap-4">
          <div class="w-8 h-8 rounded-full bg-[#cc785c] flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
            2
          </div>
          <div>
            <h3 class="font-semibold text-[#262624] dark:text-[#f1ead8]">创建供应商</h3>
            <p class="text-sm text-[#666663] dark:text-[#a3a094] mt-1">
              点击「添加供应商」按钮，填写供应商名称（如 OpenAI、Anthropic）
            </p>
          </div>
        </div>

        <div class="flex items-start gap-4">
          <div class="w-8 h-8 rounded-full bg-[#cc785c] flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
            3
          </div>
          <div>
            <h3 class="font-semibold text-[#262624] dark:text-[#f1ead8]">添加端点</h3>
            <p class="text-sm text-[#666663] dark:text-[#a3a094] mt-1">
              在供应商下点击「添加端点」，填写 API URL、密钥等配置
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- 端点配置字段 -->
    <section class="space-y-4">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        端点配置字段
      </h2>

      <div :class="[panelClasses.section, 'overflow-hidden']">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)] bg-[#fafaf7]/50 dark:bg-[#1f1d1a]/50">
                <th class="px-4 py-3 text-left font-medium text-[#666663] dark:text-[#a3a094]">字段</th>
                <th class="px-4 py-3 text-left font-medium text-[#666663] dark:text-[#a3a094]">说明</th>
                <th class="px-4 py-3 text-center font-medium text-[#666663] dark:text-[#a3a094]">必填</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="field in endpointFields"
                :key="field.name"
                class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)] last:border-0"
              >
                <td class="px-4 py-3 font-medium text-[#262624] dark:text-[#f1ead8]">
                  {{ field.name }}
                </td>
                <td class="px-4 py-3 text-[#666663] dark:text-[#a3a094]">
                  {{ field.description }}
                </td>
                <td class="px-4 py-3 text-center">
                  <span v-if="field.required" :class="panelClasses.badgeGreen">必填</span>
                  <span v-else class="text-[#999]">可选</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- API 格式选择 -->
    <section class="space-y-4">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        API 格式选择
      </h2>

      <div :class="[panelClasses.section, 'p-4']">
        <div class="flex items-start gap-3">
          <Info class="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
          <div class="text-sm text-[#666663] dark:text-[#a3a094]">
            <p class="font-medium text-[#262624] dark:text-[#f1ead8]">如何选择正确的 API 格式？</p>
            <p class="mt-1">
              根据目标 API 服务的实际格式选择。大多数第三方 API 代理（如 OpenRouter）都兼容 OpenAI 格式。
              如果不确定，可以先尝试 OpenAI 格式。
            </p>
          </div>
        </div>
      </div>

      <div :class="[panelClasses.section, 'overflow-hidden']">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)] bg-[#fafaf7]/50 dark:bg-[#1f1d1a]/50">
                <th class="px-4 py-3 text-left font-medium text-[#666663] dark:text-[#a3a094]">格式</th>
                <th class="px-4 py-3 text-left font-medium text-[#666663] dark:text-[#a3a094]">端点路径</th>
                <th class="px-4 py-3 text-left font-medium text-[#666663] dark:text-[#a3a094]">认证方式</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="format in apiFormats"
                :key="format.name"
                class="border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)] last:border-0"
              >
                <td class="px-4 py-3 font-medium text-[#262624] dark:text-[#f1ead8]">
                  {{ format.name }}
                </td>
                <td class="px-4 py-3 font-mono text-xs text-[#666663] dark:text-[#a3a094]">
                  {{ format.endpoint }}
                </td>
                <td class="px-4 py-3 font-mono text-xs text-[#666663] dark:text-[#a3a094]">
                  {{ format.auth }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- 常见供应商示例 -->
    <section class="space-y-4">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        常见供应商配置
      </h2>

      <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="example in providerExamples"
          :key="example.name"
          :class="[panelClasses.section, 'p-4']"
        >
          <h3 class="font-semibold text-[#262624] dark:text-[#f1ead8]">
            {{ example.name }}
          </h3>
          <div class="mt-2 space-y-1 text-sm">
            <div>
              <span class="text-[#666663] dark:text-[#a3a094]">URL: </span>
              <code class="text-xs bg-[#f5f5f0] dark:bg-[#1f1d1a] px-1.5 py-0.5 rounded">{{ example.url }}</code>
            </div>
            <div>
              <span class="text-[#666663] dark:text-[#a3a094]">格式: </span>
              <span :class="panelClasses.badgeBlue">{{ example.format }}</span>
            </div>
          </div>
          <p class="mt-2 text-xs text-[#999]">{{ example.note }}</p>
        </div>
      </div>
    </section>

    <!-- 注意事项 -->
    <section class="space-y-4">
      <h2 class="text-xl font-semibold text-[#262624] dark:text-[#f1ead8]">
        注意事项
      </h2>

      <div :class="[panelClasses.section, 'p-4 space-y-3']">
        <div class="flex items-start gap-3">
          <AlertTriangle class="h-5 w-5 text-yellow-500 flex-shrink-0 mt-0.5" />
          <div class="text-sm">
            <p class="font-medium text-[#262624] dark:text-[#f1ead8]">API Key 安全</p>
            <p class="text-[#666663] dark:text-[#a3a094] mt-1">
              端点的 API Key 会被加密存储，但仍建议使用子账号或限定范围的 Key，而非主账号 Key。
            </p>
          </div>
        </div>

        <div class="flex items-start gap-3">
          <AlertTriangle class="h-5 w-5 text-yellow-500 flex-shrink-0 mt-0.5" />
          <div class="text-sm">
            <p class="font-medium text-[#262624] dark:text-[#f1ead8]">测试端点</p>
            <p class="text-[#666663] dark:text-[#a3a094] mt-1">
              添加端点后，可以在健康监控页面测试连通性。如果显示不健康，请检查 URL 和 Key 是否正确。
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- 下一步 -->
    <section class="pt-4">
      <RouterLink
        to="/guide/model"
        :class="[panelClasses.section, panelClasses.cardHover, 'p-4 flex items-center gap-3 group']"
      >
        <div class="flex-1">
          <div class="font-medium text-[#262624] dark:text-[#f1ead8]">下一步：模型管理</div>
          <div class="text-sm text-[#666663] dark:text-[#a3a094]">配置模型映射和负载均衡</div>
        </div>
        <ArrowRight class="h-5 w-5 text-[#999] group-hover:text-[#cc785c] transition-colors" />
      </RouterLink>
    </section>
  </div>
</template>
