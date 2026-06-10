export const enum RenderState {
  Idle = 'idle',
  Loading = 'loading',
  Rendering = 'rendering',
  Ready = 'ready',
  Error = 'error',
}

export interface PdfLoadOptions {
  /** PDF文件URL或二进制数据 */
  url?: string
  data?: Uint8Array
  /** 解密密码 */
  password?: string
  /** CMap配置 - 用于CJK编码支持 */
  cMapUrl?: string
  cMapPacked?: boolean
  /** 标准字体数据路径 */
  standardFontDataUrl?: string
  /** 是否禁用字体Face加载 */
  disableFontFace?: boolean
  /** 是否使用系统字体作为回退 */
  useSystemFonts?: boolean
}

export interface PdfViewerProps {
  /** PDF源: URL字符串、Uint8Array或加载配置对象 */
  source: string | Uint8Array | PdfLoadOptions
  /** 当前页码 (从1开始) */
  page?: number
  /** 缩放比例 (1 = 100%) */
  scale?: number
  /** 是否启用文本选择层 */
  textLayer?: boolean
  /** 是否启用批注层 */
  annotationLayer?: boolean
}

export interface PdfViewerEmits {
  (e: 'loaded', totalPages: number): void
  (e: 'rendered'): void
  (e: 'error', error: Error): void
  (e: 'page-changed', page: number): void
  (e: 'scale-changed', scale: number): void
}
