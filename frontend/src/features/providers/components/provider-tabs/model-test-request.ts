import { normalizeApiFormatAlias } from '@/api/endpoints/types/api-format'
import type { ProviderModelMapping } from '@/api/endpoints/types'
import type { TestModelRequest } from '@/api/endpoints/providers'
import {
  modelSupportsImageGeneration,
  normalizeModelTestStringList,
  type ModelTestImageSource,
} from './model-test-capabilities'

export {
  formatModelTestDiagnostic,
  getOpenAiImageModelTestCapability,
  getOpenAiImageModelTestMaxGenerationCount,
  isModelTestableApiFormat,
  isModelTestableEndpoint,
  modelTestKeySupportsEndpoint,
  selectPreferredModelTestEndpoint,
} from './model-test-capabilities'
export type {
  ModelTestEndpointSource,
  ModelTestImageSource,
  ModelTestKeySource,
} from './model-test-capabilities'
export {
  extractModelTestImagePreviews,
  extractModelTestResponsePreview,
} from './model-test-preview'
export type { ModelTestImagePreview } from './model-test-preview'

const DEFAULT_MODEL_TEST_MESSAGE = 'Hello! This is a test message.'

type ModelTestMappingSource = {
  provider_model_name: string
  provider_model_mappings?: ProviderModelMapping[] | null
}

type ModelTestMappingEndpoint = {
  id: string
  api_format: string
}

export type ModelTestMappedModelOption = {
  name: string
  priority: number
}

function mappingApiFormatMatches(mapping: ProviderModelMapping, endpoint: ModelTestMappingEndpoint): boolean {
  const apiFormats = normalizeModelTestStringList(mapping.api_formats)
  if (apiFormats.length === 0) return true
  const endpointFormat = normalizeApiFormatAlias(endpoint.api_format)
  return apiFormats.some(format => normalizeApiFormatAlias(format) === endpointFormat)
}

function mappingEndpointMatches(mapping: ProviderModelMapping, endpoint: ModelTestMappingEndpoint): boolean {
  const endpointIds = normalizeModelTestStringList(mapping.endpoint_ids)
  if (endpointIds.length === 0) return true
  return endpointIds.includes(endpoint.id)
}

export function listModelTestMappedModelOptions(
  model: ModelTestMappingSource | null | undefined,
  endpoint: ModelTestMappingEndpoint | null | undefined,
): ModelTestMappedModelOption[] {
  if (!model || !endpoint || !Array.isArray(model.provider_model_mappings)) return []

  const matchedMappings = model.provider_model_mappings
    .filter(mapping => mapping.name.trim())
    .filter(mapping => mappingApiFormatMatches(mapping, endpoint))
    .filter(mapping => mappingEndpointMatches(mapping, endpoint))
    .sort((left, right) => {
      const leftPriority = Number.isFinite(left.priority) ? left.priority : 1
      const rightPriority = Number.isFinite(right.priority) ? right.priority : 1
      return leftPriority - rightPriority || left.name.localeCompare(right.name)
    })
  const seen = new Set<string>()
  return matchedMappings.flatMap((mapping) => {
    const name = mapping.name.trim()
    const dedupeKey = name.toLowerCase()
    if (seen.has(dedupeKey)) return []
    seen.add(dedupeKey)
    return [{
      name,
      priority: Number.isFinite(mapping.priority) ? mapping.priority : 1,
    }]
  })
}

export function normalizeModelTestMappedModelSelection(
  options: ModelTestMappedModelOption[],
  preferredName: string | null | undefined,
): string | null {
  const preferred = preferredName?.trim()
  if (!preferred) return null
  return options.find(option => option.name === preferred)?.name ?? null
}

export function setModelTestRequestBodyModel(draft: string, modelName: string): string {
  const parsed = parseModelTestRequestBodyDraft(draft)
  if (!parsed.value || parsed.error) return draft

  return JSON.stringify({
    ...parsed.value,
    model: modelName,
  }, null, 2)
}

export function syncModelTestRequestBodyDraft(
  draft: string,
  resetValue: string,
  nextResetValue: string,
  modelName?: string | null,
): { draft: string; resetValue: string } {
  const nextReset = modelName?.trim()
    ? setModelTestRequestBodyModel(nextResetValue, modelName.trim())
    : nextResetValue
  const draftIsUntouched = !draft || draft === resetValue

  if (draftIsUntouched) {
    return {
      draft: nextReset,
      resetValue: nextReset,
    }
  }

  return {
    draft: modelName?.trim()
      ? setModelTestRequestBodyModel(draft, modelName.trim())
      : draft,
    resetValue: nextReset,
  }
}

export function buildExactModelMappingTestRequest(
  providerId: string,
  modelName: string,
  apiFormat: string | null | undefined,
): TestModelRequest {
  return {
    provider_id: providerId,
    model_name: modelName,
    mode: 'direct',
    apply_model_mapping: false,
    api_format: apiFormat || undefined,
  }
}

export function buildDefaultModelTestRequestBody(
  modelName: string,
  apiFormat?: string | null,
  model?: ModelTestImageSource | null,
): string {
  if (apiFormat?.trim().toLowerCase().endsWith(':embedding')) {
    return JSON.stringify({
      model: modelName,
      input: 'This is a test embedding input.',
    }, null, 2)
  }

  if (apiFormat?.trim().toLowerCase().endsWith(':rerank')) {
    return JSON.stringify({
      model: modelName,
      query: 'Apple',
      documents: [
        'apple',
        'banana',
        'fruit',
        'vegetable',
      ],
      return_documents: true,
      top_n: 4,
    }, null, 2)
  }

  if (normalizeApiFormatAlias(apiFormat ?? '') === 'openai:image') {
    return JSON.stringify({
      model: modelName,
      prompt: DEFAULT_MODEL_TEST_MESSAGE,
      n: 1,
      size: '1024x1024',
      stream: true,
    }, null, 2)
  }

  if (normalizeApiFormatAlias(apiFormat ?? '') === 'openai:responses' && modelSupportsImageGeneration(model)) {
    return JSON.stringify({
      model: modelName,
      input: DEFAULT_MODEL_TEST_MESSAGE,
      tools: [
        {
          type: 'image_generation',
          size: '1024x1024',
          output_format: 'png',
        },
      ],
      tool_choice: {
        type: 'image_generation',
      },
      stream: true,
    }, null, 2)
  }

  return JSON.stringify({
    model: modelName,
    messages: [
      {
        role: 'user',
        content: DEFAULT_MODEL_TEST_MESSAGE,
      },
    ],
    max_tokens: 30,
    temperature: 0.7,
    stream: true,
  }, null, 2)
}

export function buildDefaultModelTestRequestHeaders(): string {
  return JSON.stringify({}, null, 2)
}

function parseModelTestJsonObjectDraft(
  draft: string,
  options: {
    emptyValue: Record<string, unknown> | null
    emptyError: string | null
    invalidTypeError: string
  },
): { value: Record<string, unknown> | null; error: string | null } {
  const normalized = draft.trim()
  if (!normalized) {
    return {
      value: options.emptyValue,
      error: options.emptyError,
    }
  }

  try {
    const parsed = JSON.parse(normalized)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return {
        value: null,
        error: options.invalidTypeError,
      }
    }
    return {
      value: parsed as Record<string, unknown>,
      error: null,
    }
  } catch (error) {
    return {
      value: null,
      error: error instanceof Error ? error.message : '无效的 JSON',
    }
  }
}

export function parseModelTestRequestBodyDraft(
  draft: string,
): { value: Record<string, unknown> | null; error: string | null } {
  return parseModelTestJsonObjectDraft(draft, {
    emptyValue: null,
    emptyError: '测试请求体不能为空',
    invalidTypeError: '测试请求体必须是 JSON 对象',
  })
}

export function parseModelTestRequestHeadersDraft(
  draft: string,
): { value: Record<string, unknown> | null; error: string | null } {
  return parseModelTestJsonObjectDraft(draft, {
    emptyValue: {},
    emptyError: null,
    invalidTypeError: '测试请求头必须是 JSON 对象',
  })
}
