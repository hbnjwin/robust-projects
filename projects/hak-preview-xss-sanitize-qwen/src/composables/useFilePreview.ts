/**
 * 文件预览组合式函数
 *
 * 提供文件读取、类型检测、内容消毒的完整预览流程。
 */
import { ref, watch, type Ref } from 'vue';
import { marked } from 'marked';
import {
  type PreviewType,
  MAX_FILE_SIZE,
  EXTENSION_TYPE_MAP,
  MIME_TYPE_MAP,
} from '@/types/preview';
import { sanitize } from '@/utils/sanitize';

// ============================================================
// 配置 marked
// ============================================================

marked.setOptions({
  gfm: true,       // GitHub Flavored Markdown（表格、任务列表等）
  breaks: false,    // 不把换行变成 <br>
});

// ============================================================
// 工具函数
// ============================================================

/**
 * 根据文件名扩展名和 MIME 类型推断预览类型
 */
export function detectPreviewType(file: File): PreviewType | null {
  // 1. 先按 MIME 匹配
  const mimeMatch = MIME_TYPE_MAP[file.type];
  if (mimeMatch) return mimeMatch;

  // 2. 按扩展名匹配
  const ext = '.' + file.name.split('.').pop()?.toLowerCase();
  const extMatch = EXTENSION_TYPE_MAP[ext];
  if (extMatch) return extMatch;

  return null;
}

/**
 * 使用 FileReader 读取文件为文本
 */
function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        resolve(reader.result);
      } else {
        reject(new Error('文件读取失败：内容不是文本'));
      }
    };
    reader.onerror = () => reject(new Error('文件读取失败'));
    reader.readAsText(file);
  });
}

/**
 * 预处理文件内容（按类型做初步转换）
 * @param rawContent 原始文件文本内容
 * @param type 预览类型
 * @returns 转换后的 HTML 字符串（尚未消毒）
 */
function preprocessContent(rawContent: string, type: PreviewType): string {
  switch (type) {
    case 'html':
      // HTML 文件直接使用
      return rawContent;

    case 'docx':
      // DOCX 文件通常由后端 mammoth 转换后传入 HTML 字符串
      // 如果传入的是原始 DOCX 二进制（base64），这里提示需要后端预处理
      // 目前假定 content 已是 mammoth 输出的 HTML
      return rawContent;

    case 'markdown':
      // Markdown → HTML（使用 marked 库）
      // 注意：marked 默认允许内联 HTML，后续由 sanitize 消毒
      // 使用 { async: false } 强制同步解析，避免返回 Promise
      return marked.parse(rawContent, { async: false }) as string;

    case 'svg':
      // SVG 文件直接使用（SVG 也是 XML，DOMPurify 可处理）
      return rawContent;

    default:
      return rawContent;
  }
}

// ============================================================
// 组合式函数
// ============================================================

/**
 * 文件预览组合式函数
 *
 * @example
 * ```vue
 * <template>
 *   <div v-if="loading">加载中...</div>
 *   <div v-else-if="error">{{ error }}</div>
 *   <div v-else v-html="sanitizedContent"></div>
 * </template>
 *
 * <script setup>
 * const { sanitizedContent, loading, error, previewFile } = useFilePreview();
 * previewFile(file);
 * </script>
 * ```
 */
export function useFilePreview() {
  const sanitizedContent: Ref<string> = ref('');
  const loading: Ref<boolean> = ref(false);
  const error: Ref<string | null> = ref(null);
  const previewType: Ref<PreviewType | null> = ref(null);

  /**
   * 预览文件 — 主入口
   * @param file 要预览的文件对象
   * @param forceType 强制指定预览类型（跳过自动检测）
   */
  async function previewFile(file: File, forceType?: PreviewType): Promise<void> {
    loading.value = true;
    error.value = null;
    sanitizedContent.value = '';

    try {
      // 1. 文件大小校验
      if (file.size > MAX_FILE_SIZE) {
        throw new Error(`文件大小超过限制（最大 ${Math.round(MAX_FILE_SIZE / 1024 / 1024)}MB）`);
      }

      if (file.size === 0) {
        throw new Error('文件内容为空');
      }

      // 2. 类型检测
      const type = forceType || detectPreviewType(file);
      if (!type) {
        throw new Error(`不支持的文件类型: ${file.name}`);
      }
      previewType.value = type;

      // 3. 读取文件内容
      const rawContent = await readFileAsText(file);

      // 4. 预处理（Markdown → HTML 等）
      const htmlContent = preprocessContent(rawContent, type);

      // 5. DOMPurify 消毒
      sanitizedContent.value = sanitize(htmlContent, type);
    } catch (err) {
      const message = err instanceof Error ? err.message : '未知错误';
      error.value = message;
    } finally {
      loading.value = false;
    }
  }

  /**
   * 预览内容字符串（非文件对象）
   * @param content 内容字符串
   * @param type 预览类型
   */
  function previewContent(content: string, type: PreviewType): void {
    loading.value = false;
    error.value = null;
    previewType.value = type;

    try {
      const htmlContent = preprocessContent(content, type);
      sanitizedContent.value = sanitize(htmlContent, type);
    } catch (err) {
      const message = err instanceof Error ? err.message : '消毒处理失败';
      error.value = message;
    }
  }

  /**
   * 重置预览状态
   */
  function reset(): void {
    sanitizedContent.value = '';
    loading.value = false;
    error.value = null;
    previewType.value = null;
  }

  return {
    sanitizedContent,
    loading,
    error,
    previewType,
    previewFile,
    previewContent,
    reset,
  };
}
