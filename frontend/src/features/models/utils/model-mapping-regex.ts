export const MAX_MAPPINGS_PER_MODEL = 50
export const MAX_MAPPING_LENGTH = 200
export const MAX_MODEL_NAME_LENGTH = 200

export interface ValidationResult {
  valid: boolean
  error?: string
}

// 危险的正则模式（可能导致 ReDoS）
// 注意：后端使用 regex 库的 timeout 做强制保护；前端无法中断 JS 正则执行，只能做启发式拦截。
const DANGEROUS_REGEX_PATTERNS: RegExp[] = [
  /\([^)]*[+*]\)[+*]/, // (x+)+, (x*)*, (x+)*, (x*)+
  /\([^)]*\)\{[0-9]+,\}/, // (x){n,} 无上限
  /\(\.\*\)\{[0-9]+,\}/, // (.*){n,} 贪婪量词 + 高重复
  /\(\.\+\)\{[0-9]+,\}/, // (.+){n,} 贪婪量词 + 高重复
  /\([^)]*\|[^)]*\)[+*]/, // (a|b)+ 选择分支 + 量词
  /\(\.\*\)\+/, // (.*)+
  /\(\.\+\)\+/, // (.+)+
  /\([^)]*\*\)[+*]/, // 嵌套量词: (a*)+
  /\(\\w\+\)\+/, // (\w+)+ - 检测字面量 \w
  /\(\.\*\)\*/, // (.*)*
  /\(.*\+.*\)\+/, // (a+b)+ 更通用的嵌套量词检测
  /\[.*\]\{[0-9]+,\}\{/, // [x]{n,}{m,} 嵌套量词
  /\.{2,}\*/, // ..* 连续通配
  /\([^)]*\|[^)]*\)\*/, // (a|a)* 选择分支 + 星号
  /\{[0-9]{2,},\}/, // {10,} 高重复次数无上限
  /\(\[.*\]\+\)\+/, // ([x]+)+ 字符类嵌套量词
  // 补充的危险模式
  /\([^)]*[+*]\)\{[0-9]+,/, // (a+){n,} 量词后跟大括号量词
  /\(\([^)]*[+*]\)[+*]\)/, // ((a+)+) 三层嵌套量词
  /\(\?:[^)]*[+*]\)[+*]/, // (?:a+)+ 非捕获组嵌套量词
]

function isPotentiallyDangerousRegex(pattern: string): boolean {
  return DANGEROUS_REGEX_PATTERNS.some(re => re.test(pattern))
}

export interface LRURegexCache {
  get: (key: string) => RegExp | null | undefined
  set: (key: string, value: RegExp | null) => void
  clear: () => void
}

export function createLRURegexCache(maxSize: number): LRURegexCache {
  const cache = new Map<string, RegExp | null>()

  return {
    get: (key: string) => {
      if (!cache.has(key)) return undefined
      const value = cache.get(key)!
      cache.delete(key)
      cache.set(key, value)
      return value
    },
    set: (key: string, value: RegExp | null) => {
      if (cache.has(key)) {
        cache.delete(key)
      } else if (cache.size >= maxSize) {
        const firstKey = cache.keys().next().value as string | undefined
        if (firstKey !== undefined) {
          cache.delete(firstKey)
        }
      }
      cache.set(key, value)
    },
    clear: () => {
      cache.clear()
    },
  }
}

export function validateModelMappingPattern(pattern: string): ValidationResult {
  if (!pattern || !pattern.trim()) {
    return { valid: false, error: '规则不能为空' }
  }

  if (pattern.length > MAX_MAPPING_LENGTH) {
    return { valid: false, error: `规则过长 (最大 ${MAX_MAPPING_LENGTH} 字符)` }
  }

  if (isPotentiallyDangerousRegex(pattern)) {
    return { valid: false, error: '规则包含潜在危险的正则构造' }
  }

  try {
    new RegExp(`^${pattern}$`, 'i')
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e)
    return { valid: false, error: `正则表达式语法错误: ${message}` }
  }

  return { valid: true }
}

export function getCompiledModelMappingRegex(
  pattern: string,
  cache: LRURegexCache,
): RegExp | null {
  const normalized = pattern.trim()
  if (!normalized) return null

  if (normalized.length > MAX_MAPPING_LENGTH) {
    return null
  }

  if (isPotentiallyDangerousRegex(normalized)) {
    return null
  }

  let regex = cache.get(normalized)
  if (regex === undefined) {
    try {
      regex = new RegExp(`^${normalized}$`, 'i')
      cache.set(normalized, regex)
    } catch {
      cache.set(normalized, null)
      return null
    }
  }

  return regex
}

export function safeTestModelMappingPattern(
  pattern: string,
  modelName: string,
  cache: LRURegexCache,
): boolean {
  if (!pattern) return false

  if (pattern.toLowerCase() === modelName.toLowerCase()) {
    return true
  }

  if (pattern.length > MAX_MAPPING_LENGTH || modelName.length > MAX_MODEL_NAME_LENGTH) {
    return false
  }

  const regex = getCompiledModelMappingRegex(pattern, cache)
  if (regex === null) {
    return false
  }

  try {
    return regex.test(modelName)
  } catch {
    return false
  }
}
