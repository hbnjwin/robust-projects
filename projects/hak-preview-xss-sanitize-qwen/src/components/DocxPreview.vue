<template>
  <div class="file-preview docx-preview">
    <!-- 加载状态 -->
    <div v-if="loading" class="preview-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>正在加载文档预览...</span>
    </div>

    <!-- 错误状态 -->
    <el-alert
      v-else-if="error"
      type="error"
      :title="error"
      show-icon
      :closable="false"
    />

    <!-- 消毒后的文档内容 -->
    <div
      v-else
      class="preview-content docx-content"
      v-html="sanitizedContent"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * DOCX 文件预览组件
 *
 * 安全特性：
 * - 假设 DOCX 已经由后端 mammoth.js 转换为 HTML
 * - DOMPurify allowlist 模式：只允许文档相关的标签和属性
 * - 封禁 onerror、onload 等所有事件处理属性
 * - 拦截 javascript: 协议超链接
 * - 保留表格结构（colspan/rowspan/边框）、列表、标题层级
 * - 保留内联 CSS 样式和 <style> 标签
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
    await previewFile(props.file, 'docx');
  } else if (props.content) {
    previewContent(props.content, 'docx');
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
/* 非 scoped 样式：DOCX 文档排版 */
.docx-content {
  font-family: 'SimSun', 'Times New Roman', serif;
  line-height: 1.8;
  color: #303133;
}

.docx-content table {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
}

.docx-content table th,
.docx-content table td {
  border: 1px solid #909399;
  padding: 6px 10px;
  text-align: left;
  vertical-align: top;
}

.docx-content table th {
  background-color: #ebeef5;
  font-weight: bold;
}

.docx-content ul,
.docx-content ol {
  padding-left: 24px;
  margin: 8px 0;
}

.docx-content li {
  margin: 4px 0;
}

.docx-content h1 {
  font-size: 22px;
  margin: 20px 0 12px;
  text-align: center;
}

.docx-content h2 {
  font-size: 18px;
  margin: 16px 0 10px;
}

.docx-content h3 {
  font-size: 16px;
  margin: 14px 0 8px;
}

.docx-content h4, .docx-content h5, .docx-content h6 {
  font-size: 14px;
  margin: 12px 0 6px;
}

.docx-content img {
  max-width: 100%;
  height: auto;
}

.docx-content blockquote {
  margin: 12px 0;
  padding: 8px 16px;
  border-left: 4px solid #c0c4cc;
  color: #606266;
  background: #f5f7fa;
}

.docx-content p {
  margin: 8px 0;
  text-indent: 0;
}
</style>
