/** 支持的预览文件类型 */
export type PreviewFileType = 'html' | 'docx' | 'markdown' | 'svg'

/** 预览文件对象 */
export interface PreviewFile {
  /** 文件名 */
  name: string
  /** 文件类型 */
  type: PreviewFileType
  /** 原始内容(字符串或二进制) */
  content: string | ArrayBuffer
}

/** 消毒配置选项 */
export interface SanitizerConfig {
  /** 允许的HTML标签(追加到默认白名单) */
  extraAllowedTags?: string[]
  /** 允许的HTML属性(追加到默认白名单) */
  extraAllowedAttr?: string[]
  /** 是否允许SVG命名空间标签(默认true，但会过滤危险元素) */
  allowSvg?: boolean
}

/** 预览渲染结果 */
export interface PreviewResult {
  /** 消毒后的安全HTML */
  sanitizedHtml: string
  /** 原始文件类型 */
  fileType: PreviewFileType
  /** 是否有内容被过滤的警告 */
  hasFilteredContent: boolean
}

/** 消毒报告 - 记录被过滤的危险内容 */
export interface SanitizeReport {
  /** 被移除的标签列表 */
  removedTags: string[]
  /** 被移除的属性列表 */
  removedAttributes: string[]
  /** 被过滤的危险URI数量 */
  blockedUris: number
}
