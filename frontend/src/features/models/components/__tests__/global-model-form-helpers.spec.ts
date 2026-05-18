import { describe, expect, it } from 'vitest'

import {
  EMBEDDING_API_FORMATS,
  buildGlobalModelCreatePayload,
  buildGlobalModelUpdatePayload,
  getModelDirectoryEmptyText,
} from '../global-model-form-helpers'

const embeddingPricing = {
  tiers: [{ up_to: null, input_price_per_1m: 0.02, output_price_per_1m: 0 }],
}

describe('global model form embedding payload helpers', () => {
  it('preserves embedding metadata in create payloads', () => {
    const payload = buildGlobalModelCreatePayload({
      name: 'text-embedding-3-small',
      display_name: 'text-embedding-3-small',
      supported_capabilities: ['embedding'],
      config: {
        streaming: false,
        embedding: true,
        model_type: 'embedding',
        api_formats: [...EMBEDDING_API_FORMATS],
      },
      is_active: true,
    }, embeddingPricing)

    expect(payload).toMatchObject({
      name: 'text-embedding-3-small',
      supported_capabilities: ['embedding'],
      config: {
        streaming: false,
        embedding: true,
        model_type: 'embedding',
        api_formats: ['openai:embedding', 'gemini:embedding', 'jina:embedding', 'doubao:embedding'],
      },
    })
  })

  it('preserves embedding metadata in update payloads', () => {
    const payload = buildGlobalModelUpdatePayload({
      name: 'unused-on-update',
      display_name: 'Jina Embeddings v3',
      supported_capabilities: ['embedding'],
      config: {
        streaming: false,
        embedding: true,
        model_type: 'embedding',
        api_formats: ['jina:embedding'],
      },
      is_active: true,
    }, embeddingPricing)

    expect(payload.supported_capabilities).toEqual(['embedding'])
    expect(payload.config).toEqual({
      streaming: false,
      embedding: true,
      model_type: 'embedding',
      api_formats: ['jina:embedding'],
    })
  })

  it('surfaces manual-add guidance when the online model directory is unavailable', () => {
    expect(getModelDirectoryEmptyText({
      searchQuery: '',
      manualModelMode: false,
      modelListLoadFailed: true,
    })).toBe('模型目录加载失败，请使用手动添加继续创建')

    expect(getModelDirectoryEmptyText({
      searchQuery: '',
      manualModelMode: true,
      modelListLoadFailed: false,
    })).toBe('已切换到手动添加，可在右侧填写模型信息')
  })

  it('keeps search empty state ahead of manual/offline guidance', () => {
    expect(getModelDirectoryEmptyText({
      searchQuery: 'local-model',
      manualModelMode: true,
      modelListLoadFailed: true,
    })).toBe('未找到模型')
  })
})
