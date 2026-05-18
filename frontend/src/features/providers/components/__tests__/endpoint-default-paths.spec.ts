import { describe, expect, it } from 'vitest'

import { getDefaultEndpointPath } from '../endpoint-default-paths'

const apiFormats = [
  { value: 'gemini:generate_content', default_path: '/v1beta/models/{model}:{action}' },
  { value: 'gemini:embedding', default_path: '/v1beta/models/{model}:{action}' },
  { value: 'openai:responses', default_path: '/v1/responses' },
]

describe('endpoint default paths', () => {
  it('uses Gemini Developer API paths for custom Gemini endpoints', () => {
    expect(getDefaultEndpointPath({
      apiFormat: 'gemini:generate_content',
      providerType: 'custom',
      apiFormats,
    })).toBe('/v1beta/models/{model}:{action}')

    expect(getDefaultEndpointPath({
      apiFormat: 'gemini:embedding',
      providerType: 'custom',
      apiFormats,
    })).toBe('/v1beta/models/{model}:{action}')
  })

  it('uses Vertex AI project/location paths for Vertex provider Gemini endpoints', () => {
    expect(getDefaultEndpointPath({
      apiFormat: 'gemini:generate_content',
      providerType: 'vertex_ai',
      apiFormats,
    })).toBe('/v1/projects/{project_id}/locations/{region}/publishers/google/models/{model}:{action}')

    expect(getDefaultEndpointPath({
      apiFormat: 'gemini:embedding',
      providerType: 'vertex_ai',
      apiFormats,
    })).toBe('/v1/projects/{project_id}/locations/{region}/publishers/google/models/{model}:predict')
  })

  it('keeps Codex Responses root path without duplicating /v1', () => {
    expect(getDefaultEndpointPath({
      apiFormat: 'openai:responses',
      providerType: 'codex',
      apiFormats,
    })).toBe('/responses')
  })
})
