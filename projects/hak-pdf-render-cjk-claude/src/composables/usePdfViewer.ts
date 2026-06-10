import { ref, computed, watch, type Ref } from 'vue'
import { RenderState, type PdfLoadOptions } from '@/types/pdf'
import { configurePdfWorker, buildPdfSource } from '@/utils/pdf-config'

export interface UsePdfViewerOptions {
  /** 初始 PDF 源 */
  source?: string | Uint8Array | PdfLoadOptions
  /** 初始缩放 */
  initialScale?: number
  /** 初始页码 */
  initialPage?: number
}

export function usePdfViewer(options: UsePdfViewerOptions = {}) {
  // 确保 Worker 已配置
  configurePdfWorker()

  const renderState = ref<RenderState>(RenderState.Idle)
  const error = ref<Error | null>(null)
  const currentPage = ref(options.initialPage ?? 1)
  const totalPages = ref(0)
  const scale = ref(options.initialScale ?? 1)

  // 内部 key，缩放或源变化时递增以强制 vue-pdf-embed 完全重新渲染
  // 避免 CSS transform 缩放导致的 text layer 偏移
  const renderKey = ref(0)

  const pdfSource: Ref<Record<string, unknown> | null> = ref(
    options.source ? buildPdfSource(options.source) : null,
  )

  /**
   * 加载 PDF 文档
   * 自动注入 CMap 配置以支持 GB18030 等 CJK 编码
   */
  function loadPdf(source: string | Uint8Array | PdfLoadOptions): void {
    renderState.value = RenderState.Loading
    error.value = null
    currentPage.value = 1
    totalPages.value = 0
    pdfSource.value = buildPdfSource(source)
  }

  /**
   * 设置缩放比例
   * 通过改变 scale 值触发 vue-pdf-embed 重新渲染（新 viewport），
   * 而非 CSS transform，确保 text layer / annotation layer / canvas 三层对齐
   */
  function setScale(value: number): void {
    const clamped = Math.max(0.25, Math.min(5, value))
    if (clamped === scale.value) return
    scale.value = clamped
  }

  // 缩放变化时强制重新渲染
  watch(scale, () => {
    renderKey.value++
    renderState.value = RenderState.Rendering
  })

  function goToPage(page: number): void {
    const target = Math.max(1, Math.min(totalPages.value || 1, page))
    currentPage.value = target
  }

  function nextPage(): void {
    goToPage(currentPage.value + 1)
  }

  function prevPage(): void {
    goToPage(currentPage.value - 1)
  }

  function onLoaded(pages: number): void {
    totalPages.value = pages
    renderState.value = RenderState.Rendering
  }

  function onRendered(): void {
    renderState.value = RenderState.Ready
  }

  function onError(err: Error): void {
    error.value = err
    renderState.value = RenderState.Error
  }

  const isLoading = computed(
    () =>
      renderState.value === RenderState.Loading ||
      renderState.value === RenderState.Rendering,
  )

  const hasError = computed(() => renderState.value === RenderState.Error)

  return {
    // 状态
    pdfSource,
    currentPage,
    totalPages,
    scale,
    renderState,
    renderKey,
    error,
    isLoading,
    hasError,

    // 方法
    loadPdf,
    setScale,
    goToPage,
    nextPage,
    prevPage,

    // 事件处理
    onLoaded,
    onRendered,
    onError,
  }
}
