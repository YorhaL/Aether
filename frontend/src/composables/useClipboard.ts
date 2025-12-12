import { useToast } from './useToast'
import { log } from '@/utils/logger'

export function useClipboard() {
  const { success, error: showError } = useToast()

  async function copyToClipboard(text: string): Promise<boolean> {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text)
        success('已复制到剪贴板')
        return true
      }

      // Fallback for non-secure contexts
      const textArea = document.createElement('textarea')
      textArea.value = text
      textArea.style.position = 'fixed'
      textArea.style.left = '-999999px'
      textArea.style.top = '-999999px'
      document.body.appendChild(textArea)
      textArea.focus()
      textArea.select()

      try {
        const successful = document.execCommand('copy')
        if (successful) {
          success('已复制到剪贴板')
          return true
        }
        showError('复制失败，请手动复制')
        return false
      } finally {
        document.body.removeChild(textArea)
      }
    } catch (err) {
      log.error('复制失败:', err)
      showError('复制失败，请手动选择文本进行复制')
      return false
    }
  }

  return { copyToClipboard }
}
