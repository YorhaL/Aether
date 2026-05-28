interface ApiFormatPathDefinition {
  value: string
  default_path: string
}

export function normalizeEndpointApiFormat(apiFormat: string): string {
  switch (apiFormat.trim().toLowerCase()) {
    default:
      return apiFormat.trim().toLowerCase()
  }
}

function isCodexUrl(baseUrl: string): boolean {
  const url = baseUrl.replace(/\/+$/, '')
  return url.includes('/backend-api/codex') || url.endsWith('/codex')
}

function parseBaseUrlParts(baseUrl?: string | null): { host: string; path: string } | null {
  const raw = (baseUrl || '').trim()
  if (!raw) return null
  try {
    const parsed = new URL(raw)
    return {
      host: parsed.hostname.toLowerCase(),
      path: parsed.pathname.replace(/\/+$/, '').toLowerCase(),
    }
  } catch {
    const pathStart = raw.indexOf('/')
    return {
      host: '',
      path: pathStart >= 0 ? raw.slice(pathStart).split('?')[0].replace(/\/+$/, '').toLowerCase() : '',
    }
  }
}

function baseUrlHasPathApiRoot(baseUrl?: string | null): boolean {
  const path = parseBaseUrlParts(baseUrl)?.path
  return !!path && path !== '/'
}

function baseUrlEndsWithV1Root(baseUrl?: string | null): boolean {
  return parseBaseUrlParts(baseUrl)?.path.endsWith('/v1') ?? false
}

function isBigModelCodingApiRoot(baseUrl?: string | null): boolean {
  const parts = parseBaseUrlParts(baseUrl)
  return parts?.host === 'open.bigmodel.cn' && parts.path === '/api/coding/paas/v4'
}

function isGoogleOpenAiCompatApiRoot(baseUrl?: string | null): boolean {
  const parts = parseBaseUrlParts(baseUrl)
  return parts?.host === 'generativelanguage.googleapis.com'
    && (parts.path === '/v1beta/openai' || parts.path === '/v1/openai')
}

function isVertexOpenAiCompatApiRoot(baseUrl?: string | null): boolean {
  const parts = parseBaseUrlParts(baseUrl)
  return !!parts
    && (parts.host === 'aiplatform.googleapis.com' || parts.host.endsWith('.aiplatform.googleapis.com') || parts.host.endsWith('-aiplatform.googleapis.com'))
    && parts.path.endsWith('/endpoints/openapi')
}

function openAiCompatibleBaseIncludesApiRoot(baseUrl?: string | null): boolean {
  return baseUrlEndsWithV1Root(baseUrl)
    || baseUrlHasPathApiRoot(baseUrl)
    || isBigModelCodingApiRoot(baseUrl)
    || isGoogleOpenAiCompatApiRoot(baseUrl)
    || isVertexOpenAiCompatApiRoot(baseUrl)
}

function v1CompatibleBaseIncludesApiRoot(baseUrl?: string | null): boolean {
  return baseUrlEndsWithV1Root(baseUrl)
}

function stripV1PrefixForApiRoot(path: string): string {
  return path.replace(/^\/v1(?=\/)/i, '')
}

function isOpenAiCompatibleFormat(apiFormat: string): boolean {
  return apiFormat.startsWith('openai:') || apiFormat.startsWith('jina:')
}

function isClaudeCompatibleFormat(apiFormat: string): boolean {
  return apiFormat === 'claude:messages'
}

export function getDefaultEndpointPath(params: {
  apiFormat: string
  providerType?: string | null
  baseUrl?: string
  apiFormats: ApiFormatPathDefinition[]
}): string {
  const providerType = (params.providerType || '').toLowerCase()
  const normalizedApiFormat = normalizeEndpointApiFormat(params.apiFormat)
  if (providerType === 'gemini_cli') {
    if (normalizedApiFormat === 'gemini:generate_content') {
      return '/v1internal:{action}'
    }
  }
  if (providerType === 'vertex_ai') {
    if (normalizedApiFormat === 'gemini:generate_content') {
      return '/v1/projects/{project_id}/locations/{region}/publishers/google/models/{model}:{action}'
    }
    if (normalizedApiFormat === 'gemini:embedding') {
      return '/v1/projects/{project_id}/locations/{region}/publishers/google/models/{model}:predict'
    }
    if (normalizedApiFormat === 'claude:messages') {
      return '/v1/projects/{project_id}/locations/{region}/publishers/anthropic/models/{model}:{action}'
    }
  }

  const format = params.apiFormats.find(f => f.value === normalizedApiFormat)
  const defaultPath = format?.default_path || ''
  const isCodex = providerType
    ? providerType === 'codex'
    : (!!params.baseUrl && isCodexUrl(params.baseUrl))
  if (normalizedApiFormat === 'openai:responses' && isCodex) {
    return '/responses'
  }
  if (openAiCompatibleBaseIncludesApiRoot(params.baseUrl) && isOpenAiCompatibleFormat(normalizedApiFormat)) {
    return stripV1PrefixForApiRoot(defaultPath)
  }
  if (v1CompatibleBaseIncludesApiRoot(params.baseUrl) && isClaudeCompatibleFormat(normalizedApiFormat)) {
    return stripV1PrefixForApiRoot(defaultPath)
  }
  return defaultPath
}
