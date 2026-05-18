import { describe, expect, it } from 'vitest'

import {
  buildProviderModelCreatePayload,
  buildProviderModelUpdatePayload,
  modelSupportsEmbedding,
} from '../provider-model-form-helpers'

const pricing = {
  tiers: [{ up_to: null, input_price_per_1m: 0.02, output_price_per_1m: 0 }],
}

describe('provider model form embedding helpers', () => {
  it.each([
    { supported_capabilities: ['embedding'], config: {} },
    { supported_capabilities: null, config: { embedding: true } },
    { supported_capabilities: null, config: { model_type: 'embedding' } },
    { supported_capabilities: null, config: { api_formats: ['doubao:embedding'] } },
    { supports_embedding: true, effective_supports_embedding: null, config: {} },
    { supports_embedding: null, effective_supports_embedding: true, config: {} },
  ])('detects embedding metadata from %o', (model) => {
    expect(modelSupportsEmbedding(model)).toBe(true)
  })

  it('keeps provider create payload inherited from the selected embedding global model', () => {
    const payload = buildProviderModelCreatePayload({
      globalModelId: 'gm-embedding',
      providerModelName: 'text-embedding-3-small',
      finalTieredPricing: pricing,
      tieredPricingModified: false,
      pricePerRequest: undefined,
      cleanConfig: {
        embedding: true,
        model_type: 'embedding',
        api_formats: ['openai:embedding'],
      },
      configTouched: false,
      supportsStreaming: false,
      isActive: true,
    })

    expect(payload).toMatchObject({
      global_model_id: 'gm-embedding',
      provider_model_name: 'text-embedding-3-small',
      tiered_pricing: undefined,
      config: undefined,
      supports_streaming: false,
    })
    expect('supports_embedding' in payload).toBe(false)
  })

  it('uses supplied provider model name in create payload', () => {
    const payload = buildProviderModelCreatePayload({
      globalModelId: 'gm-local-manual',
      providerModelName: 'intranet-chat-model-v1',
      finalTieredPricing: pricing,
      tieredPricingModified: false,
      pricePerRequest: undefined,
      cleanConfig: undefined,
      configTouched: false,
      isActive: true,
    })

    expect(payload).toMatchObject({
      global_model_id: 'gm-local-manual',
      provider_model_name: 'intranet-chat-model-v1',
      tiered_pricing: undefined,
      price_per_request: undefined,
      config: undefined,
      is_active: true,
    })
  })

  it('preserves edited provider embedding config without posting unsupported embedding controls', () => {
    const payload = buildProviderModelUpdatePayload({
      finalTieredPricing: pricing,
      pricePerRequest: undefined,
      cleanConfig: {
        streaming: false,
        embedding: true,
        model_type: 'embedding',
        api_formats: ['gemini:embedding'],
      },
      supportsStreaming: false,
      isActive: true,
    })

    expect(payload.config).toEqual({
      streaming: false,
      embedding: true,
      model_type: 'embedding',
      api_formats: ['gemini:embedding'],
    })
    expect(payload.supports_streaming).toBe(false)
    expect('supports_embedding' in payload).toBe(false)
  })
})
