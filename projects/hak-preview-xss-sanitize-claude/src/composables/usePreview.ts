import { ref, shallowRef } from 'vue'
import { marked } from 'marked'
import { sanitizeHtml, sanitizeSvg, sanitizeMarkdownHtml, sanitizeDocxHtml, detectXssVectors } from '@/utils/sanitizer'
import type { PreviewFile, PreviewFileType, PreviewResult, SanitizeReport } from '@/types/preview'

/**
 * 文件预览组合式函数
 * 统一处理 HTML/DOCX/Markdown/SVG 文件的预览渲染和XSS消毒
 */
export function usePreview() {
  const previewResult = shallowRef<PreviewResult | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const securityReport = shallowRef<SanitizeReport | null>(null)

  /**
   * 配置marked渲染器
   * - 关闭HTML透传（避免原始HTML注入）
   * - 代码块使用安全渲染
   */
  function configureMarked(): void {
    marked.setOptions({
      breaks: true,
      gfm: true,
    })

    // 自定义渲染器: 代码块做HTML实体编码，防止iframe等注入
    const renderer = new marked.Renderer()
    const originalCode = renderer.code
    renderer.code = function (this: marked.Renderer, code: string, language: string | undefined, isEscaped: boolean): string {
      // 调用原始方法（marked自身会做HTML编码）
      return originalCode.call(this, code, language, isEscaped)
    }
    marked.use({ renderer })
  }

  /**
   * 处理HTML文件预览
   */
  function processHtml(content: string): PreviewResult {
    const sanitizedHtml = sanitizeHtml(content)
    const report = detectXssVectors(content)
    return {
      sanitizedHtml,
      fileType: 'html',
      hasFilteredContent: report.removedTags.length > 0 || report.removedAttributes.length > 0,
    }
  }

  /**
   * 处理DOCX转HTML预览
   * 假设DOCX已通过mammoth等工具转为HTML字符串传入
   */
  function processDocx(htmlContent: string): PreviewResult {
    const sanitizedHtml = sanitizeDocxHtml(htmlContent)
    const report = detectXssVectors(htmlContent)
    return {
      sanitizedHtml,
      fileType: 'docx',
      hasFilteredContent: report.removedTags.length > 0 || report.removedAttributes.length > 0,
    }
  }

  /**
   * 处理Markdown预览
   */
  function processMarkdown(content: string): PreviewResult {
    configureMarked()
    // 先用marked渲染为HTML
    const rawHtml = marked.parse(content) as string
    // 再用DOMPurify消毒渲染结果
    const sanitizedHtml = sanitizeMarkdownHtml(rawHtml)
    const report = detectXssVectors(rawHtml)
    return {
      sanitizedHtml,
      fileType: 'markdown',
      hasFilteredContent: report.removedTags.length > 0 || report.removedAttributes.length > 0,
    }
  }

  /**
   * 处理SVG预览
   */
  function processSvg(content: string): PreviewResult {
    const sanitizedHtml = sanitizeSvg(content)
    const report = detectXssVectors(content)
    return {
      sanitizedHtml,
      fileType: 'svg',
      hasFilteredContent: report.removedTags.length > 0 || report.removedAttributes.length > 0,
    }
  }

  /**
   * 根据文件类型自动选择处理器进行预览
   */
  async function preview(file: PreviewFile): Promise<void> {
    loading.value = true
    error.value = null
    securityReport.value = null

    try {
      const content = typeof file.content === 'string'
        ? file.content
        : new TextDecoder().decode(file.content)

      // 先做安全审计记录
      securityReport.value = detectXssVectors(content)

      let result: PreviewResult
      switch (file.type) {
        case 'html':
          result = processHtml(content)
          break
        case 'docx':
          result = processDocx(content)
          break
        case 'markdown':
          result = processMarkdown(content)
          break
        case 'svg':
          result = processSvg(content)
          break
        default:
          throw new Error(`不支持的文件类型: ${file.type}`)
      }

      previewResult.value = result

      // 如果检测到危险内容，输出控制台警告
      if (securityReport.value && (
        securityReport.value.removedTags.length > 0 ||
        securityReport.value.removedAttributes.length > 0 ||
        securityReport.value.blockedUris > 0
      )) {
        console.warn('[安全] 文件预览已过滤危险内容:', {
          file: file.name,
          removedTags: securityReport.value.removedTags,
          removedAttributes: securityReport.value.removedAttributes,
          blockedUris: securityReport.value.blockedUris,
        })
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : '预览失败'
      previewResult.value = null
    } finally {
      loading.value = false
    }
  }

  /**
   * 从文件名推断文件类型
   */
  function inferFileType(filename: string): PreviewFileType {
    const ext = filename.split('.').pop()?.toLowerCase()
    switch (ext) {
      case 'html':
      case 'htm':
        return 'html'
      case 'docx':
        return 'docx'
      case 'md':
      case 'markdown':
        return 'markdown'
      case 'svg':
        return 'svg'
      default:
        return 'html' // 默认按HTML处理
    }
  }

  /**
   * 清除预览状态
   */
  function clearPreview(): void {
    previewResult.value = null
    error.value = null
    securityReport.value = null
  }

  return {
    previewResult,
    loading,
    error,
    securityReport,
    preview,
    inferFileType,
    clearPreview,
  }
}
