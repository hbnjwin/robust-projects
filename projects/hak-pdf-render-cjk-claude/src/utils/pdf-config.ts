import * as pdfjsLib from 'pdfjs-dist'
import type { PdfLoadOptions } from '@/types/pdf'

/**
 * CMap 和标准字体的基础路径
 * 构建时由 vite 插件从 node_modules/pdfjs-dist/ 复制到 public/
 */
const CMAP_URL = '/cmaps/'
const STANDARD_FONT_DATA_URL = '/standard_fonts/'

let workerConfigured = false

/**
 * 配置 pdf.js Worker 线程
 * 必须在任何 PDF 加载之前调用
 */
export function configurePdfWorker(): void {
  if (workerConfigured) return

  pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/build/pdf.worker.mjs',
    import.meta.url,
  ).toString()

  workerConfigured = true
}

/**
 * 构建带 CMap 配置的 DocumentInitParameters
 * CMap 是解决 GB2312/GBK/GB18030 编码 CJK 字体显示的关键
 */
export function buildPdfSource(
  source: string | Uint8Array | PdfLoadOptions,
): Record<string, unknown> {
  const cMapDefaults = {
    cMapUrl: CMAP_URL,
    cMapPacked: true,
    standardFontDataUrl: STANDARD_FONT_DATA_URL,
    disableFontFace: false,
    useSystemFonts: true,
  }

  if (typeof source === 'string') {
    return { url: source, ...cMapDefaults }
  }

  if (source instanceof Uint8Array) {
    return { data: source, ...cMapDefaults }
  }

  // PdfLoadOptions 对象：用户配置覆盖默认值
  return { ...cMapDefaults, ...source }
}
