import { describe, it, expect } from 'vitest'
import {
  MAX_MAPPING_LENGTH,
  MAX_MODEL_NAME_LENGTH,
  createLRURegexCache,
  safeTestModelMappingPattern,
  validateModelMappingPattern,
} from '@/features/models/utils/model-mapping-regex'

describe('model-mapping-regex', () => {
  it('validateModelMappingPattern: rejects empty', () => {
    expect(validateModelMappingPattern('').valid).toBe(false)
    expect(validateModelMappingPattern('   ').valid).toBe(false)
  })

  it('validateModelMappingPattern: rejects too long', () => {
    const tooLong = 'a'.repeat(MAX_MAPPING_LENGTH + 1)
    const result = validateModelMappingPattern(tooLong)
    expect(result.valid).toBe(false)
  })

  it('validateModelMappingPattern: rejects potentially dangerous patterns', () => {
    const result = validateModelMappingPattern('(a+)+')
    expect(result.valid).toBe(false)
  })

  it('validateModelMappingPattern: accepts basic patterns', () => {
    expect(validateModelMappingPattern('claude-haiku-.*').valid).toBe(true)
    expect(validateModelMappingPattern('gpt-4o').valid).toBe(true)
  })

  it('safeTestModelMappingPattern: matches case-insensitively and anchors', () => {
    const cache = createLRURegexCache(10)
    expect(safeTestModelMappingPattern('gpt-4o', 'GPT-4O', cache)).toBe(true)
    expect(safeTestModelMappingPattern('gpt-4o', 'gpt-4o-mini', cache)).toBe(false)
  })

  it('safeTestModelMappingPattern: rejects overly long model names', () => {
    const cache = createLRURegexCache(10)
    const longName = 'a'.repeat(MAX_MODEL_NAME_LENGTH + 1)
    expect(safeTestModelMappingPattern('a.*', longName, cache)).toBe(false)
  })
})

