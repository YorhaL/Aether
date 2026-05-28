import { describe, expect, it } from 'vitest'

import { getDefaultEndpointPath } from '../endpoint-default-paths'

const apiFormats = [
  { value: 'openai:chat', default_path: '/v1/chat/completions' },
  { value: 'gemini:generate_content', default_path: '/v1beta/models/{model}:{action}' },
  { value: 'gemini:embedding', default_path: '/v1beta/models/{model}:{action}' },
  { value: 'openai:responses', default_path: '/v1/responses' },
  { value: 'openai:embedding', default_path: '/v1/embeddings' },
  { value: 'claude:messages', default_path: '/v1/messages' },
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

  it('uses Gemini CLI v1internal paths for fixed Gemini CLI endpoints', () => {
    expect(getDefaultEndpointPath({
      apiFormat: 'gemini:generate_content',
      providerType: 'gemini_cli',
      apiFormats,
    })).toBe('/v1internal:{action}')
  })

  it('keeps Codex Responses root path without duplicating /v1', () => {
    expect(getDefaultEndpointPath({
      apiFormat: 'openai:responses',
      providerType: 'codex',
      apiFormats,
    })).toBe('/responses')
  })

  it('drops /v1 from OpenAI-compatible defaults when base URL includes a path', () => {
    expect(getDefaultEndpointPath({
      apiFormat: 'openai:chat',
      providerType: 'custom',
      baseUrl: 'https://proxy.example.com/api',
      apiFormats,
    })).toBe('/chat/completions')

    expect(getDefaultEndpointPath({
      apiFormat: 'openai:embedding',
      providerType: 'custom',
      baseUrl: 'https://proxy.example.com/api?tenant=demo',
      apiFormats,
    })).toBe('/embeddings')

    expect(getDefaultEndpointPath({
      apiFormat: 'openai:chat',
      providerType: 'custom',
      baseUrl: 'https://proxy.example.com/openai',
      apiFormats,
    })).toBe('/chat/completions')

    expect(getDefaultEndpointPath({
      apiFormat: 'openai:chat',
      providerType: 'custom',
      baseUrl: 'https://proxy.example.com',
      apiFormats,
    })).toBe('/v1/chat/completions')
  })

  it('drops /v1 from OpenAI-compatible defaults when base URL already includes a known API root', () => {
    expect(getDefaultEndpointPath({
      apiFormat: 'openai:chat',
      providerType: 'custom',
      baseUrl: 'https://open.bigmodel.cn/api/coding/paas/v4',
      apiFormats,
    })).toBe('/chat/completions')

    expect(getDefaultEndpointPath({
      apiFormat: 'openai:responses',
      providerType: 'custom',
      baseUrl: 'https://api.openai.example/v1',
      apiFormats,
    })).toBe('/responses')
  })

  it('keeps /v1 for Claude Messages defaults unless base URL already ends with v1', () => {
    expect(getDefaultEndpointPath({
      apiFormat: 'claude:messages',
      providerType: 'custom',
      baseUrl: 'https://api.anthropic.example/v1',
      apiFormats,
    })).toBe('/messages')

    expect(getDefaultEndpointPath({
      apiFormat: 'claude:messages',
      providerType: 'custom',
      baseUrl: 'https://proxy.example.com/api',
      apiFormats,
    })).toBe('/v1/messages')

    expect(getDefaultEndpointPath({
      apiFormat: 'claude:messages',
      providerType: 'custom',
      baseUrl: 'https://proxy.example.com/anthropic',
      apiFormats,
    })).toBe('/v1/messages')
  })
})
