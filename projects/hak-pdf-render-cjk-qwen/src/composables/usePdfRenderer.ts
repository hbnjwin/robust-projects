/**
 * PDF 渲染管理组合式函数
 *
 * 封装 PDF 文档加载与层修正的完整生命周期。
 * 渲染由 vue-pdf-embed 负责，本 composable 专注于：
 * - 文档加载与 GB18030 编码检测
 * - 页面文本内容提取（供偏移修正使用）
 * - CJK 字体偏移修正
 * - 批注层对齐修正
 */

import { ref, shallowRef, onBeforeUnmount } from 'vue';
import * as pdfjsLib from 'pdfjs-dist';
import { correctTextLayerOffset, reCorrectTextLayer } from '@/utils/textLayerFix';
import { correctAnnotationLayer } from '@/utils/annotationLayerFix';
import {
  detectGb18030Usage,
  buildCMapConfig,
  getDefaultCMapUrl,
  getDefaultStandardFontDataUrl,
} from '@/utils/encodingDetect';
import type {
  PdfAnnotation,
  TextLayerCorrectionResult,
  AnnotationLayerCorrectionResult,
} from '@/types/pdf';

/** usePdfRenderer 配置选项 */
export interface UsePdfRendererOptions {
  /** PDF.js worker 脚本路径 */
  workerSrc?: string;
  /** CMap 资源路径 */
  cMapUrl?: string;
  /** 标准字体数据路径 */
  standardFontDataUrl?: string;
  /** 页码变化时的回调 */
  onPageChange?: (page: number) => void;
  /** 批注点击时的回调 */
  onAnnotationClick?: (annotation: PdfAnnotation) => void;
  /** 渲染完成的回调 */
  onRendered?: (page: number, scale: number) => void;
}

/**
 * PDF 渲染管理 composable
 *
 * @example
 * ```vue
 * <script setup>
 * const { loadDocument, loadPageText, applyTextLayerCorrection } = usePdfRenderer({
 *   cMapUrl: '/cmaps/',
 * });
 *
 * await loadDocument('/reports/wind-turbine-2024.pdf');
 * // vue-pdf-embed 渲染完成后：
 * await loadPageText(1, 1.5);
 * applyTextLayerCorrection(textLayerEl);
 * </script>
 * ```
 */
export function usePdfRenderer(options: UsePdfRendererOptions = {}) {
  // ---- 响应式状态 ----
  const pdfDocument = shallowRef<pdfjsLib.PDFDocumentProxy | null>(null);
  const totalPages = ref(0);
  const isLoading = ref(false);
  const hasEncodingIssue = ref(false);
  const encodingInfo = ref<{ usesGb18030: boolean; gbFonts: string[] }>({
    usesGb18030: false,
    gbFonts: [],
  });
  const lastCorrection = ref<{
    text: TextLayerCorrectionResult | null;
    annotation: AnnotationLayerCorrectionResult | null;
  }>({ text: null, annotation: null });

  // ---- 非响应式缓存 ----
  let currentTextContent: Awaited<
    ReturnType<pdfjsLib.PDFPageProxy['getTextContent']>
  > | null = null;
  let currentViewport: pdfjsLib.PageViewport | null = null;
  let cachedPageNum: number = -1;
  let cachedScale: number = -1;

  // ---- Worker 配置 ----
  function initWorker(): void {
    if (pdfjsLib.GlobalWorkerOptions.workerSrc) return;

    pdfjsLib.GlobalWorkerOptions.workerSrc =
      options.workerSrc ||
      `https://cdn.jsdelivr.net/npm/pdfjs-dist@4.4.168/build/pdf.worker.mjs`;
  }

  // ---- 文档加载 ----

  /**
   * 加载 PDF 文档
   *
   * 配置 CMap 和标准字体以支持 GB18030 编码，
   * 并自动检测文档是否使用 GB18030/GBK 编码。
   */
  async function loadDocument(
    source: string | Uint8Array | ArrayBuffer,
  ): Promise<pdfjsLib.PDFDocumentProxy> {
    initWorker();
    isLoading.value = true;
    hasEncodingIssue.value = false;

    try {
      const cMapUrl = options.cMapUrl || getDefaultCMapUrl();
      const standardFontDataUrl =
        options.standardFontDataUrl || getDefaultStandardFontDataUrl();
      const cMapConfig = buildCMapConfig(cMapUrl, standardFontDataUrl);

      const loadingTask = pdfjsLib.getDocument({
        url: typeof source === 'string' ? source : undefined,
        data:
          typeof source !== 'string'
            ? source instanceof ArrayBuffer
              ? new Uint8Array(source)
              : source
            : undefined,
        ...cMapConfig,
        useSystemFonts: true,
        disableAutoFetch: false,
        enableXfa: true,
      } as pdfjsLib.DocumentInitParameters);

      const doc = await loadingTask.promise;
      pdfDocument.value = doc;
      totalPages.value = doc.numPages;

      // 检测 GB18030 编码使用情况
      const encoding = await detectGb18030Usage(doc);
      encodingInfo.value = {
        usesGb18030: encoding.usesGb18030,
        gbFonts: encoding.gbFonts,
      };
      hasEncodingIssue.value = encoding.usesGb18030;

      // 清除旧缓存
      cachedPageNum = -1;
      cachedScale = -1;
      currentTextContent = null;
      currentViewport = null;

      return doc;
    } finally {
      isLoading.value = false;
    }
  }

  // ---- 页面文本加载 ----

  /**
   * 加载指定页面的文本内容和视口信息
   *
   * 在 vue-pdf-embed 渲染完成后调用，
   * 提取字体名称和度量信息供偏移修正使用。
   *
   * @param pageNum - 页码（从 1 开始）
   * @param scale   - 当前缩放比例
   */
  async function loadPageText(
    pageNum: number,
    scale: number,
  ): Promise<void> {
    const doc = pdfDocument.value;
    if (!doc) return;

    // 缓存命中：同一页同一缩放不重复加载
    if (pageNum === cachedPageNum && scale === cachedScale && currentTextContent) {
      return;
    }

    try {
      const page = await doc.getPage(pageNum);
      currentTextContent = await page.getTextContent();
      currentViewport = page.getViewport({ scale });
      cachedPageNum = pageNum;
      cachedScale = scale;
    } catch (err) {
      console.error('Failed to load page text content:', err);
      currentTextContent = null;
    }
  }

  // ---- 层修正 ----

  /**
   * 修正文本层 CJK 字体垂直偏移
   *
   * @param textLayerElement - 文本层容器 DOM 元素
   * @param zoomScale        - 当前缩放比例（传入时表示缩放变化，会先重置再重算）
   */
  function applyTextLayerCorrection(
    textLayerElement: HTMLElement,
    zoomScale?: number,
  ): TextLayerCorrectionResult | null {
    if (!currentTextContent) return null;

    const effectiveScale = zoomScale || cachedScale || 1.0;
    let result: TextLayerCorrectionResult;

    if (zoomScale !== undefined) {
      // 缩放变化时先重置再重新计算
      result = reCorrectTextLayer(
        textLayerElement,
        currentTextContent,
        effectiveScale,
      );
    } else {
      result = correctTextLayerOffset(
        textLayerElement,
        currentTextContent,
        effectiveScale,
        true,
      );
    }

    lastCorrection.value = {
      ...lastCorrection.value,
      text: result,
    };

    return result;
  }

  /**
   * 修正批注层定位，与文本层对齐
   *
   * @param annotationLayerElement - 批注层容器 DOM 元素
   * @param zoomScale              - 当前缩放比例
   */
  function applyAnnotationCorrection(
    annotationLayerElement: HTMLElement,
    zoomScale?: number,
  ): AnnotationLayerCorrectionResult | null {
    if (!currentTextContent) return null;

    const effectiveScale = zoomScale || cachedScale || 1.0;
    const viewportHeight = currentViewport?.height;

    const result = correctAnnotationLayer(
      annotationLayerElement,
      currentTextContent,
      effectiveScale,
      viewportHeight,
    );

    lastCorrection.value = {
      ...lastCorrection.value,
      annotation: result,
    };

    return result;
  }

  // ---- 清理 ----
  onBeforeUnmount(() => {
    pdfDocument.value?.destroy();
  });

  return {
    // 状态
    pdfDocument,
    totalPages,
    isLoading,
    hasEncodingIssue,
    encodingInfo,
    lastCorrection,
    // 方法
    loadDocument,
    loadPageText,
    applyTextLayerCorrection,
    applyAnnotationCorrection,
  };
}
