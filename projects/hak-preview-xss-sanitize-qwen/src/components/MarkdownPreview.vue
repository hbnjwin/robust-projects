<template>
  <div class="file-preview markdown-preview">
    <!-- 加载状态 -->
    <div v-if="loading" class="preview-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>正在加载 Markdown 预览...</span>
    </div>

    <!-- 错误状态 -->
    <el-alert
      v-else-if="error"
      type="error"
      :title="error"
      show-icon
      :closable="false"
    />

    <!-- 消毒后的 Markdown 渲染内容 -->
    <div
      v-else
      class="preview-content markdown-content"
      v-html="sanitizedContent"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * Markdown 文件预览组件
 *
 * 安全特性：
 * - 使用 marked 库解析 Markdown → HTML
 * - DOMPurify 消毒：移除 <script>、<iframe>、<object> 等
 * - 特别封禁代码块中的 <iframe>（渗透报告漏洞3）
 * - 拦截 javascript: 协议链接
 * - 拦截 Markdown 内联 HTML 中的 on* 事件属性
 * - 保留代码块 <pre><code>、表格、列表等 Markdown 标准输出
 *
 * 注意：Markdown 中的内联 HTML 会被保留但经过消毒。
 * <style> 标签被禁止（Markdown 不需要自定义样式）。
 */
import { onMounted, watch } from 'vue';
import { Loading } from '@element-plus/icons-vue';
import { useFilePreview } from '@/composables/useFilePreview';
import type { FilePreviewProps } from '@/types/preview';

const props = defineProps<FilePreviewProps>();

const { sanitizedContent, loading, error, previewFile, previewContent } =
  useFilePreview();

async function loadContent() {
  if (props.file) {
    await previewFile(props.file, 'markdown');
  } else if (props.content) {
    previewContent(props.content, 'markdown');
  }
}

onMounted(loadContent);
watch(() => [props.file, props.content], loadContent);
</script>

<style scoped>
.file-preview {
  width: 100%;
  min-height: 200px;
}

.preview-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px;
  color: #909399;
  font-size: 14px;
}

.preview-content {
  padding: 16px;
  overflow: auto;
  max-height: 80vh;
}
</style>

<style>
/* 非 scoped 样式：Markdown 排版 */
.markdown-content {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial,
    sans-serif;
  line-height: 1.6;
  color: #24292e;
  word-wrap: break-word;
}

.markdown-content h1, .markdown-content h2,
.markdown-content h3, .markdown-content h4,
.markdown-content h5, .markdown-content h6 {
  margin: 24px 0 16px;
  font-weight: 600;
  line-height: 1.25;
}

.markdown-content h1 { font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }
.markdown-content h2 { font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }
.markdown-content h3 { font-size: 1.25em; }
.markdown-content h4 { font-size: 1em; }

.markdown-content p {
  margin: 0 0 16px;
}

.markdown-content ul,
.markdown-content ol {
  padding-left: 2em;
  margin: 0 0 16px;
}

.markdown-content li {
  margin: 4px 0;
}

.markdown-content li + li {
  margin-top: 4px;
}

/* 表格 */
.markdown-content table {
  border-collapse: collapse;
  width: 100%;
  margin: 0 0 16px;
  overflow: auto;
}

.markdown-content table th,
.markdown-content table td {
  border: 1px solid #dfe2e5;
  padding: 6px 13px;
}

.markdown-content table th {
  font-weight: 600;
  background-color: #f6f8fa;
}

.markdown-content table tr:nth-child(2n) {
  background-color: #f6f8fa;
}

/* 代码块 */
.markdown-content code {
  padding: 0.2em 0.4em;
  margin: 0;
  font-size: 85%;
  background-color: rgba(27, 31, 35, 0.05);
  border-radius: 3px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}

.markdown-content pre {
  padding: 16px;
  overflow: auto;
  font-size: 85%;
  line-height: 1.45;
  background-color: #f6f8fa;
  border-radius: 3px;
  margin: 0 0 16px;
}

.markdown-content pre code {
  padding: 0;
  margin: 0;
  font-size: 100%;
  background-color: transparent;
  border: 0;
}

/* 引用 */
.markdown-content blockquote {
  margin: 0 0 16px;
  padding: 0 1em;
  color: #6a737d;
  border-left: 0.25em solid #dfe2e5;
}

/* 水平线 */
.markdown-content hr {
  height: 0.25em;
  padding: 0;
  margin: 24px 0;
  background-color: #e1e4e8;
  border: 0;
}

/* 链接 */
.markdown-content a {
  color: #0366d6;
  text-decoration: none;
}

.markdown-content a:hover {
  text-decoration: underline;
}

/* 图片 */
.markdown-content img {
  max-width: 100%;
  height: auto;
}

/* 删除线 */
.markdown-content del {
  text-decoration: line-through;
}
</style>
