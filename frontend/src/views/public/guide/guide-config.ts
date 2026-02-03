import type { Component } from 'vue'
import {
  BookOpen,
  Server,
  Layers,
  Users,
  Settings,
  HelpCircle
} from 'lucide-vue-next'

// 导航配置
export interface GuideNavItem {
  id: string
  name: string
  path: string
  icon: Component
  description?: string
}

export const guideNavItems: GuideNavItem[] = [
  {
    id: 'overview',
    name: '概览',
    path: '/guide',
    icon: BookOpen,
    description: '系统架构与核心概念'
  },
  {
    id: 'provider',
    name: '供应商管理',
    path: '/guide/provider',
    icon: Server,
    description: '添加供应商与端点配置'
  },
  {
    id: 'model',
    name: '模型管理',
    path: '/guide/model',
    icon: Layers,
    description: '模型映射与负载均衡'
  },
  {
    id: 'user-key',
    name: '用户与密钥',
    path: '/guide/user-key',
    icon: Users,
    description: 'API Key 与权限管理'
  },
  {
    id: 'advanced',
    name: '高级功能',
    path: '/guide/advanced',
    icon: Settings,
    description: '格式转换、请求头规则等'
  },
  {
    id: 'faq',
    name: '常见问题',
    path: '/guide/faq',
    icon: HelpCircle,
    description: '使用中的常见问题'
  }
]

// 样式类常量
export const panelClasses = {
  card: 'bg-white/70 dark:bg-[#262624]/80 backdrop-blur-sm rounded-2xl border border-[#e5e4df] dark:border-[rgba(227,224,211,0.16)]',
  cardHover: 'hover:border-[#cc785c]/30 dark:hover:border-[#d4a27f]/30 transition-colors',
  section: 'bg-white/50 dark:bg-[#262624]/60 backdrop-blur-sm rounded-xl border border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)]',
  commandPanel: 'rounded-xl border border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)] bg-white/50 dark:bg-[#1f1d1a]/50',
  configPanel: 'rounded-xl border border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)] overflow-hidden',
  panelHeader: 'px-4 py-2 border-b border-[#e5e4df] dark:border-[rgba(227,224,211,0.08)] bg-[#fafaf7]/50 dark:bg-[#1f1d1a]/50',
  codeBody: 'p-0',
  badge: 'inline-flex items-center gap-1.5 rounded-full bg-[#cc785c]/10 dark:bg-[#cc785c]/20 border border-[#cc785c]/20 dark:border-[#cc785c]/40 px-3 py-1.5 text-xs font-medium text-[#cc785c] dark:text-[#d4a27f]',
  badgeBlue: 'inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 dark:bg-blue-500/20 border border-blue-500/20 dark:border-blue-500/40 px-2 py-0.5 text-xs font-medium text-blue-600 dark:text-blue-400',
  badgeGreen: 'inline-flex items-center gap-1.5 rounded-full bg-green-500/10 dark:bg-green-500/20 border border-green-500/20 dark:border-green-500/40 px-2 py-0.5 text-xs font-medium text-green-600 dark:text-green-400',
  badgeYellow: 'inline-flex items-center gap-1.5 rounded-full bg-yellow-500/10 dark:bg-yellow-500/20 border border-yellow-500/20 dark:border-yellow-500/40 px-2 py-0.5 text-xs font-medium text-yellow-600 dark:text-yellow-400',
  iconButtonSmall: [
    'flex items-center justify-center rounded-lg border h-7 w-7',
    'border-[#e5e4df] dark:border-[rgba(227,224,211,0.12)]',
    'bg-transparent',
    'text-[#666663] dark:text-[#f1ead8]',
    'transition hover:bg-[#f0f0eb] dark:hover:bg-[#3a3731]'
  ].join(' ')
} as const

// 核心概念数据
export const coreConcepts = [
  {
    name: '供应商 (Provider)',
    description: '代表一个 AI 服务提供商，如 OpenAI、Anthropic、Google 等',
    color: 'blue'
  },
  {
    name: '端点 (Endpoint)',
    description: '供应商下的具体 API 端点，包含 URL、密钥、API 格式等配置',
    color: 'green'
  },
  {
    name: '模型 (Model)',
    description: '可供用户使用的模型，可关联多个端点实现负载均衡',
    color: 'purple'
  },
  {
    name: 'API Key',
    description: '用户访问系统的凭证，可设置权限、配额、允许的模型等',
    color: 'orange'
  }
]

// API 格式说明
export const apiFormats = [
  {
    name: 'OpenAI Chat',
    endpoint: '/v1/chat/completions',
    auth: 'Authorization: Bearer xxx',
    clients: ['OpenAI SDK', 'Cursor', 'LangChain', '大部分开源工具']
  },
  {
    name: 'OpenAI CLI',
    endpoint: '/v1/responses',
    auth: 'Authorization: Bearer xxx',
    clients: ['Codex CLI']
  },
  {
    name: 'Claude Chat',
    endpoint: '/v1/messages',
    auth: 'x-api-key: xxx',
    clients: ['Anthropic SDK']
  },
  {
    name: 'Claude CLI',
    endpoint: '/v1/messages',
    auth: 'Authorization: Bearer xxx',
    clients: ['Claude Code']
  },
  {
    name: 'Gemini Chat',
    endpoint: '/v1beta/models/{model}:generateContent',
    auth: 'x-goog-api-key: xxx',
    clients: ['Gemini SDK', 'Gemini CLI']
  }
]

// 负载均衡模式
export const loadBalanceModes = [
  {
    mode: 'priority',
    name: '优先级',
    description: '按端点优先级顺序调用，高优先级的先用，失败后降级到低优先级'
  },
  {
    mode: 'random',
    name: '随机',
    description: '随机选择一个可用端点，适合多个同质端点'
  },
  {
    mode: 'round_robin',
    name: '轮询',
    description: '依次轮流使用各个端点，分摊负载'
  },
  {
    mode: 'weighted',
    name: '加权',
    description: '按权重比例分配请求，权重高的端点处理更多请求'
  },
  {
    mode: 'latency',
    name: '最低延迟',
    description: '优先使用历史延迟最低的端点'
  }
]

// FAQ 数据
export const faqItems = [
  {
    id: 'concept-provider-endpoint',
    category: '概念理解',
    question: '供应商和端点有什么区别？',
    answer: '供应商是逻辑分组，用于组织管理多个端点。一个供应商可以有多个端点（比如不同区域、不同账号的 API）。端点才是实际调用 API 的配置单元，包含 URL、密钥等信息。'
  },
  {
    id: 'concept-model-mapping',
    category: '概念理解',
    question: '模型映射是什么意思？',
    answer: '模型映射让你可以用自定义的模型名（如 gpt-4）来访问实际的模型（如某端点的 gpt-4-turbo）。一个模型可以映射到多个端点，实现负载均衡和故障转移。'
  },
  {
    id: 'config-format',
    category: '配置问题',
    question: '端点的 API 格式怎么选择？',
    answer: '根据实际服务商的 API 格式选择。比如 OpenAI 官方选 OpenAI，Anthropic 官方选 Claude。如果用的是 OpenAI 兼容的第三方服务，通常选 OpenAI 格式。'
  },
  {
    id: 'config-priority',
    category: '配置问题',
    question: '端点优先级有什么用？',
    answer: '当模型关联多个端点且使用优先级负载均衡模式时，系统会先调用高优先级端点。如果失败（超时、错误等），会自动降级到低优先级端点。适合主备切换场景。'
  },
  {
    id: 'config-quota',
    category: '配置问题',
    question: '如何限制用户的使用量？',
    answer: '在 API Key 配置中设置配额：可以限制每日/每月的请求次数或 Token 用量。也可以在用户层面设置默认配额，新建的 Key 会继承用户配额。'
  },
  {
    id: 'advanced-conversion',
    category: '高级功能',
    question: '什么是格式转换？',
    answer: '格式转换允许用 OpenAI SDK 调用 Claude 模型，或用 Anthropic SDK 调用 OpenAI 模型。系统会自动转换请求和响应格式。需要在系统设置开启，并在端点配置中启用。'
  },
  {
    id: 'advanced-header-rules',
    category: '高级功能',
    question: '请求头规则有什么用？',
    answer: '可以在转发请求时添加、修改或删除 HTTP 头。常用于：添加认证信息、设置特定的 API 版本、添加跟踪标记等。'
  },
  {
    id: 'error-401',
    category: '常见错误',
    question: '返回 401 Unauthorized 错误？',
    answer: '检查：1) API Key 是否正确；2) Key 是否已过期或被禁用；3) 请求头格式是否正确（OpenAI 用 Bearer，Claude 用 x-api-key）。'
  },
  {
    id: 'error-404',
    category: '常见错误',
    question: '返回 404 Not Found 错误？',
    answer: '检查：1) 模型名称是否正确；2) 该模型是否已在系统中配置；3) API Key 是否有权限访问该模型；4) 端点 URL 是否正确。'
  },
  {
    id: 'error-502',
    category: '常见错误',
    question: '返回 502/503 错误？',
    answer: '表示上游服务不可用。检查：1) 端点健康状态；2) 供应商 API 是否正常；3) 网络连接是否正常。可以在健康监控页面查看端点状态。'
  }
]

// 配置流程步骤
export const configSteps = [
  {
    step: 1,
    title: '添加供应商',
    description: '创建一个供应商来组织你的 API 端点',
    path: '/admin/providers'
  },
  {
    step: 2,
    title: '配置端点',
    description: '在供应商下添加 API 端点，填写 URL、密钥等',
    path: '/admin/providers'
  },
  {
    step: 3,
    title: '创建模型',
    description: '创建用户可用的模型，关联到端点',
    path: '/admin/models'
  },
  {
    step: 4,
    title: '发放密钥',
    description: '为用户创建 API Key，设置权限和配额',
    path: '/admin/keys'
  }
]
