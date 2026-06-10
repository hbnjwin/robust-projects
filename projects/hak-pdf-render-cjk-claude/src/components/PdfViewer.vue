<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import VuePdfEmbed from 'vue-pdf-embed'
// vue-pdf-embed 的 text layer 和 annotation layer 必须导入对应 CSS
// 缺少这些样式会导致各层定位完全错乱
import 'vue-pdf-embed/dist/styles/textLayer.css'
import 'vue-pdf-embed/dist/styles/annotationLayer.css'
import { usePdfViewer } from '@/composables/usePdfViewer'
import { patchCjkTextLayerOffsets, syncAnnotationLayerPosition } from '@/utils/cjk-font-patch'
import type { PdfLoadOptions } from '@/types/pdf'

const props = withDefaults(
  defineProps<{
    /** PDF源: URL字符串、Uint8Array或加载配置对象 */
    source: string | Uint8Array | PdfLoadOptions
    /** 当前页码 */
    page?: number
    /** 缩放比例 (1 = 100%) */
    scale?: number
    /** 是否启用文本选择层 */
    textLayer?: boolean
    /** 是否启用批注层 */
    annotationLayer?: boolean
  }>(),
  {
    page: 1,
    scale: 1,
    textLayer: true,
    annotationLayer: true,
  },
)

const emit = defineEmits<{
  (e: 'loaded', totalPages: number): void
  (e: 'rendered'): void
  (e: 'error', error: Error): void
  (e: 'page-changed', page: number): void
  (e: 'scale-changed', scale: number): void
}>()

const containerRef = ref<HTMLElement>()

const {
  pdfSource,
  currentPage,
  totalPages,
  scale: viewerScale,
  renderKey,
  isLoading,
  hasError,
  error,
  loadPdf,
  setScale,
  goToPage,
  nextPage,
  prevPage,
  onLoaded: handleLoaded,
  onRendered: handleRendered,
  onError: handleError,
} = usePdfViewer({
  source: props.source,
  initialScale: props.scale,
  initialPage: props.page,
})

// 同步外部 props 变化
watch(
  () => props.source,
  (newSource) => loadPdf(newSource),
)

watch(
  () => props.scale,
  (newScale) => setScale(newScale),
)

watch(
  () => props.page,
  (newPage) => goToPage(newPage),
)

// PDF 加载完成
function onDocumentLoaded(doc: { numPages: number }) {
  handleLoaded(doc.numPages)
  emit('loaded', doc.numPages)
}

// 页面渲染完成 — 执行 CJK 偏移修正
async function onPageRendered() {
  handleRendered()

  // 等待 DOM 更新完成
  await nextTick()

  if (!containerRef.value) return

  // 核心修复: 修正 CJK 文字在 text layer 中的垂直偏移
  if (props.textLayer) {
    patchCjkTextLayerOffsets(containerRef.value, viewerScale.value)
  }

  // 核心修复: 同步 annotation layer 位置到修正后的 text layer
  if (props.annotationLayer) {
    syncAnnotationLayerPosition(containerRef.value)
  }

  emit('rendered')
}

function onRenderingFailed(err: Error) {
  handleError(err)
  emit('error', err)
}

watch(currentPage, (page) => emit('page-changed', page))
watch(viewerScale, (scale) => emit('scale-changed', scale))

// 初始加载
onMounted(() => {
  if (props.source) {
    loadPdf(props.source)
  }
})

defineExpose({
  currentPage,
  totalPages,
  scale: viewerScale,
  isLoading,
  hasError,
  error,
  loadPdf,
  setScale,
  goToPage,
  nextPage,
  prevPage,
})
</script>

<template>
  <div ref="containerRef" class="pdf-viewer">
    <div v-if="isLoading" class="pdf-viewer__loading">
      <slot name="loading">
        <span>加载中...</span>
      </slot>
    </div>

    <div v-if="hasError" class="pdf-viewer__error">
      <slot name="error" :error="error">
        <span>PDF 加载失败: {{ error?.message }}</span>
      </slot>
    </div>

    <vue-pdf-embed
      v-if="pdfSource"
      :key="renderKey"
      :source="pdfSource"
      :page="currentPage"
      :scale="viewerScale"
      :text-layer="textLayer"
      :annotation-layer="annotationLayer"
      @loaded="onDocumentLoaded"
      @rendered="onPageRendered"
      @rendering-failed="onRenderingFailed"
    />
  </div>
</template>

<style scoped>
.pdf-viewer {
  position: relative;
  width: 100%;
}

.pdf-viewer__loading,
.pdf-viewer__error {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: #666;
}

.pdf-viewer__error {
  color: #f56c6c;
}

/*
 * ===== CJK 渲染偏移修复 - 核心 CSS =====
 *
 * 修复1: text layer 与 canvas 层精确对齐
 * 修复2: CJK 字体垂直偏移的 CSS 级修正
 * 修复3: annotation layer 与 text layer 对齐
 */

/* text layer 容器：精确覆盖 canvas */
.pdf-viewer :deep(.textLayer) {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
  opacity: 0.25;
  line-height: 1.0;
  /* 禁止额外的容器级 transform，避免引入偏移源 */
}

/* text layer 中的文本 span：修正 CJK 垂直对齐 */
.pdf-viewer :deep(.textLayer span) {
  position: absolute;
  white-space: pre;
  color: transparent;
  transform-origin: 0% 0%;
  /*
   * CJK 字体的 line-height 默认比拉丁字体高，
   * 强制 line-height: 1 消除行高差异导致的偏移
   */
  line-height: 1.0;
}

/* 文本选中时的高亮样式 */
.pdf-viewer :deep(.textLayer span::selection) {
  background: rgba(0, 0, 255, 0.3);
}

/* annotation layer：与 text layer 使用相同定位基准 */
.pdf-viewer :deep(.annotationLayer) {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
  /* 确保 annotation 的 z-index 高于 text layer */
  z-index: 1;
}

/* annotation layer 中的各类标注元素 */
.pdf-viewer :deep(.annotationLayer section) {
  position: absolute;
  cursor: pointer;
}

/* 高亮标注：确保覆盖区域与文字精确对齐 */
.pdf-viewer :deep(.annotationLayer .highlightAnnotation) {
  transform-origin: 0% 0%;
}

/*
 * canvas 层（PDF 渲染层）
 * 修复 vue-pdf-embed scale prop 的已知问题：
 * CSS width/height 会覆盖 canvas 属性导致 scale 失效
 * 必须 unset CSS 尺寸，让 canvas attribute 控制实际渲染分辨率
 */
.pdf-viewer :deep(canvas) {
  display: block;
  width: unset !important;
  height: unset !important;
}

/*
 * vue-pdf-embed 的页面容器
 * 使用 relative 定位作为 text layer 和 annotation layer 的定位锚点
 */
.pdf-viewer :deep(.vue-pdf-embed > div) {
  position: relative;
}
</style>
