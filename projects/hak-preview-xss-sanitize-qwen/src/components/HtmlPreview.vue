<template>
  <div class="file-preview html-preview">
    <!-- 加载状态 -->
    <div v-if="loading" class="preview-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>正在加载 HTML 预览...</span>
    </div>

    <!-- 错误状态 -->
    <el-alert
      v-else-if="error"
      type="error"
      :title="error"
      show-icon
      :closable="false"
    />

    <!-- 消毒后的 HTML 内容 -->
    <div
      v-else
      class="preview-content html-content"
      v-html="sanitizedContent"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * HTML 文件预览组件
 *
 * 安全特性：
 * - DOMPurify 消毒：移除 <script>、<iframe>、<object>、<embed> 等危险标签
 * - 封禁所有 on* 事件处理属性
 * - 拦截 javascript: 协议 URI
 * - 清洗危险 CSS（expression、behavior、-moz-binding）
 * - 保留表格结构、列表、CSS 样式等排版元素
 */
import { onMounted, watch } from 'vue';
import { Loading } from '@element-plus/icons-vue';
import { useFilePreview } from '@/composables/useFilePreview';
import type { FilePreviewProps } from '@/types/preview';

const props = defineProps<FilePreviewProps>();

const { sanitizedContent, loading, error, previewFile, previewContent } =
  useFilePreview();

/** 根据 props 加载内容 */
async function loadContent() {
  if (props.file) {
    await previewFile(props.file, 'html');
  } else if (props.content) {
    previewContent(props.content, 'html');
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

/* HTML 内容区域 — 不设 scoped，让内联样式和 <style> 生效 */
</style>

<style>
/* 非 scoped 样式：为 HTML 预览内容提供基础排版 */
.html-content table {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
}

.html-content table th,
.html-content table td {
  border: 1px solid #dcdfe6;
  padding: 8px 12px;
  text-align: left;
}

.html-content table th {
  background-color: #f5f7fa;
  font-weight: 600;
}

.html-content ul,
.html-content ol {
  padding-left: 24px;
  margin: 8px 0;
}

.html-content li {
  margin: 4px 0;
}

.html-content h1, .html-content h2, .html-content h3,
.html-content h4, .html-content h5, .html-content h6 {
  margin: 16px 0 8px;
  font-weight: 600;
}

.html-content img {
  max-width: 100%;
  height: auto;
}

.html-content blockquote {
  margin: 12px 0;
  padding: 8px 16px;
  border-left: 4px solid #dcdfe6;
  color: #606266;
  background: #f5f7fa;
}
</style>
