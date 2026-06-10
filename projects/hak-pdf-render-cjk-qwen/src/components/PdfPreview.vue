<template>
  <div class="pdf-preview-container" ref="containerRef" :data-zoom-high="localZoom > 1.5">
    <!-- 工具栏 -->
    <div class="pdf-toolbar">
      <div class="pdf-toolbar-left">
        <el-button size="small" :disabled="localPage <= 1" @click="goToPage(localPage - 1)">
          上一页
        </el-button>
        <span class="pdf-page-info">{{ localPage }} / {{ totalPages }}</span>
        <el-button
          size="small"
          :disabled="localPage >= totalPages"
          @click="goToPage(localPage + 1)"
        >
          下一页
        </el-button>
      </div>
      <div class="pdf-toolbar-center">
        <el-button size="small" @click="zoomOut" :disabled="localZoom <= 0.25">
          -
        </el-button>
        <span class="pdf-zoom-info">{{ Math.round(localZoom * 100) }}%</span>
        <el-button size="small" @click="zoomIn" :disabled="localZoom >= 5.0">
          +
        </el-button>
        <el-button size="small" @click="resetZoom">重置</el-button>
      </div>
      <div class="pdf-toolbar-right">
        <el-tag v-if="hasEncodingIssue" type="warning" size="small">
          GB18030
        </el-tag>
      </div>
    </div>

    <!-- 编码警告 -->
    <div v-if="hasEncodingIssue" class="pdf-encoding-warning">
      <span>
        该报告使用了 GB18030 编码（常见于 2018 年前的老报告），已启用兼容模式。
        如仍有乱码请检查 CMap 资源配置。
      </span>
    </div>

    <!-- PDF 渲染区 -->
    <div class="pdf-preview-wrapper">
      <div v-if="isLoading" class="pdf-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在加载 PDF...</span>
      </div>

      <div class="pdf-page-wrapper" v-show="!isLoading">
        <vue-pdf-embed
          ref="pdfEmbedRef"
          :src="src"
          :page="localPage"
          :scale="localZoom"
          :text-layer="showTextLayer"
          :annotation-layer="showAnnotationLayer"
          @rendered="onPdfRendered"
          @rendering-failed="onPdfError"
        />

        <!-- 自定义批注覆盖层 -->
        <div class="pdf-annotation-overlay">
          <div
            v-for="annotation in currentPageAnnotations"
            :key="annotation.id"
            class="pdf-highlight-mark"
            :class="{ 'is-active': annotation.id === activeAnnotationId }"
            :style="getAnnotationStyle(annotation)"
            @click="onAnnotationClick(annotation)"
            :title="annotation.content"
          />
        </div>

        <!-- 自定义高亮层 -->
        <div class="pdf-annotation-overlay" v-if="currentPageHighlights.length">
          <div
            v-for="highlight in currentPageHighlights"
            :key="highlight.id"
            class="pdf-highlight-mark"
            :style="getHighlightStyle(highlight)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import {
  defineComponent,
  ref,
  watch,
  nextTick,
  onMounted,
  onBeforeUnmount,
  computed,
  type PropType,
} from 'vue';
import { Loading } from '@element-plus/icons-vue';
import VuePdfEmbed from 'vue-pdf-embed';
import { usePdfRenderer } from '@/composables/usePdfRenderer';
import type { PdfAnnotation, PdfHighlight } from '@/types/pdf';

export default defineComponent({
  name: 'PdfPreview',

  components: {
    VuePdfEmbed,
    Loading,
  },

  props: {
    /** PDF 文件路径或二进制数据 */
    src: {
      type: [String, Uint8Array] as PropType<string | Uint8Array>,
      required: true,
    },
    /** 当前页码 */
    page: {
      type: Number,
      default: 1,
    },
    /** 缩放比例 */
    initialZoom: {
      type: Number,
      default: 1.0,
    },
    /** 批注数据列表 */
    annotations: {
      type: Array as PropType<PdfAnnotation[]>,
      default: () => [],
    },
    /** 高亮数据列表 */
    highlights: {
      type: Array as PropType<PdfHighlight[]>,
      default: () => [],
    },
    /** CMap 资源 URL（GB18030 兼容） */
    cMapUrl: {
      type: String,
      default: '',
    },
    /** PDF.js worker 路径 */
    workerSrc: {
      type: String,
      default: '',
    },
    /** 是否显示文本层 */
    showTextLayer: {
      type: Boolean,
      default: true,
    },
    /** 是否显示批注层 */
    showAnnotationLayer: {
      type: Boolean,
      default: true,
    },
  },

  emits: [
    'annotation-click',
    'page-change',
    'rendered',
    'render-error',
    'encoding-warning',
  ],

  setup(props, { emit }) {
    // ---- 渲染管理 ----
    const {
      pdfDocument,
      totalPages,
      isLoading,
      hasEncodingIssue,
      encodingInfo,
      lastCorrection,
      loadDocument,
      loadPageText,
      applyTextLayerCorrection,
      applyAnnotationCorrection,
    } = usePdfRenderer({
      workerSrc: props.workerSrc || undefined,
      cMapUrl: props.cMapUrl || undefined,
    });

    // ---- DOM 引用 ----
    const containerRef = ref<HTMLElement | null>(null);
    const pdfEmbedRef = ref<InstanceType<typeof VuePdfEmbed> | null>(null);

    // ---- 本地状态 ----
    const localPage = ref(props.page);
    const localZoom = ref(props.initialZoom);
    const correctionApplied = ref(false);
    const activeAnnotationId = ref<string | null>(null);
    let correctionTimer: ReturnType<typeof setTimeout> | null = null;

    // ---- 计算属性 ----
    const currentPageAnnotations = computed(() =>
      props.annotations.filter((a) => a.page === localPage.value),
    );

    const currentPageHighlights = computed(() =>
      props.highlights.filter((h) => h.page === localPage.value),
    );

    // ---- 文档加载 ----
    async function initDocument(): Promise<void> {
      if (!props.src) return;

      try {
        await loadDocument(props.src);

        if (encodingInfo.value.usesGb18030) {
          emit('encoding-warning', {
            type: 'gb18030',
            fonts: encodingInfo.value.gbFonts,
          });
        }
      } catch (err) {
        emit('render-error', err);
      }
    }

    // ---- 层修正 ----

    /**
     * 调度层修正（防抖 150ms）
     *
     * 缩放拖拽时避免频繁修正，等待操作稳定后再计算。
     */
    function scheduleCorrection(isZoomChange: boolean = false): void {
      if (correctionTimer) clearTimeout(correctionTimer);

      correctionTimer = setTimeout(() => {
        nextTick(() => {
          performCorrection(isZoomChange);
        });
      }, 150);
    }

    /**
     * 执行文本层和批注层的偏移修正
     *
     * 先加载页面的文本内容（获取字体度量），再应用修正。
     */
    async function performCorrection(isZoomChange: boolean = false): Promise<void> {
      const container = containerRef.value;
      if (!container) return;

      // 先加载当前页的文本内容（含字体度量信息）
      await loadPageText(localPage.value, localZoom.value);

      // 修正文本层 CJK 偏移
      if (props.showTextLayer) {
        const textLayerEl = container.querySelector<HTMLElement>(
          '.textLayer, [class*="text-layer"]',
        );
        if (textLayerEl) {
          applyTextLayerCorrection(
            textLayerEl,
            isZoomChange ? localZoom.value : undefined,
          );
        }
      }

      // 修正批注层对齐
      if (props.showAnnotationLayer) {
        const annotationLayerEl = container.querySelector<HTMLElement>(
          '.annotationLayer, [class*="annotation-layer"]',
        );
        if (annotationLayerEl) {
          applyAnnotationCorrection(
            annotationLayerEl,
            isZoomChange ? localZoom.value : undefined,
          );
        }
      }

      correctionApplied.value = true;
    }

    // ---- 批注样式计算 ----

    /**
     * 将 PDF 坐标转换为 CSS 样式
     *
     * 批注的 rect 使用 PDF 坐标系（左下角原点），
     * 需要转换为 CSS 坐标系（左上角原点）。
     */
    function getAnnotationStyle(annotation: PdfAnnotation): Record<string, string> {
      const [x1, y1, x2, y2] = annotation.rect;
      const left = x1 * localZoom.value;
      const top = y1 * localZoom.value;
      const width = (x2 - x1) * localZoom.value;
      const height = (y2 - y1) * localZoom.value;

      return {
        left: `${left}px`,
        top: `${top}px`,
        width: `${width}px`,
        height: `${height}px`,
        backgroundColor: annotation.color || 'rgba(255, 255, 0, 0.3)',
      };
    }

    function getHighlightStyle(highlight: PdfHighlight): Record<string, string> {
      const [x1, y1, x2, y2] = highlight.rect;
      const left = x1 * localZoom.value;
      const top = y1 * localZoom.value;
      const width = (x2 - x1) * localZoom.value;
      const height = (y2 - y1) * localZoom.value;

      return {
        left: `${left}px`,
        top: `${top}px`,
        width: `${width}px`,
        height: `${height}px`,
        backgroundColor: highlight.color || 'rgba(255, 255, 0, 0.2)',
      };
    }

    // ---- 事件处理 ----

    function onPdfRendered(): void {
      emit('rendered', { page: localPage.value, scale: localZoom.value });
      emit('page-change', localPage.value);
      scheduleCorrection(false);
    }

    function onPdfError(err: Error): void {
      console.error('PDF render error:', err);
      emit('render-error', err);
    }

    function onAnnotationClick(annotation: PdfAnnotation): void {
      activeAnnotationId.value = annotation.id;
      emit('annotation-click', annotation);
    }

    // ---- 页码/缩放控制 ----

    function goToPage(page: number): void {
      if (page >= 1 && page <= totalPages.value) {
        localPage.value = page;
        correctionApplied.value = false;
        emit('page-change', page);
      }
    }

    function setZoom(zoom: number): void {
      localZoom.value = Math.max(0.25, Math.min(5.0, zoom));
    }

    function zoomIn(): void {
      setZoom(localZoom.value + 0.25);
    }

    function zoomOut(): void {
      setZoom(localZoom.value - 0.25);
    }

    function resetZoom(): void {
      setZoom(1.0);
    }

    // ---- 生命周期 ----

    onMounted(() => {
      initDocument();
    });

    onBeforeUnmount(() => {
      if (correctionTimer) clearTimeout(correctionTimer);
    });

    // 监听页码 prop 变化
    watch(
      () => props.page,
      (newPage) => {
        if (newPage !== localPage.value && newPage >= 1) {
          localPage.value = newPage;
          correctionApplied.value = false;
        }
      },
    );

    // 监听缩放变化 → 重新修正层偏移
    watch(localZoom, () => {
      scheduleCorrection(true);
    });

    // 监听 src 变化 → 重新加载文档
    watch(
      () => props.src,
      () => {
        correctionApplied.value = false;
        initDocument();
      },
    );

    return {
      // 状态
      pdfDocument,
      totalPages,
      localPage,
      localZoom,
      isLoading,
      hasEncodingIssue,
      correctionApplied,
      lastCorrection,
      currentPageAnnotations,
      currentPageHighlights,
      activeAnnotationId,
      // DOM
      containerRef,
      pdfEmbedRef,
      // 方法
      goToPage,
      setZoom,
      zoomIn,
      zoomOut,
      resetZoom,
      onPdfRendered,
      onPdfError,
      onAnnotationClick,
      getAnnotationStyle,
      getHighlightStyle,
      scheduleCorrection,
    };
  },
});
</script>

<style scoped src="@/styles/pdf-preview.css"></style>
