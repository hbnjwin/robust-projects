<template>
  <div class="file-preview svg-preview">
    <!-- 加载状态 -->
    <div v-if="loading" class="preview-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>正在加载 SVG 预览...</span>
    </div>

    <!-- 错误状态 -->
    <el-alert
      v-else-if="error"
      type="error"
      :title="error"
      show-icon
      :closable="false"
    />

    <!-- 消毒后的 SVG 内容 -->
    <div
      v-else
      class="preview-content svg-content"
      v-html="sanitizedContent"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * SVG 文件预览组件
 *
 * 安全特性：
 * - 使用 DOMPurify SVG profile 消毒
 * - 封杀 <foreignObject>（渗透报告漏洞4：嵌入脚本不受限）
 * - 封杀 <script> 标签
 * - 封杀所有 on* 事件处理属性
 * - <use xlink:href> 仅允许本地 #fragment 引用
 * - <a xlink:href> 清洗 javascript: 协议
 * - 清洗危险 CSS（expression、behavior 等）
 * - 保留 SVG 视觉属性（viewBox、fill、stroke、transform 等）
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
    await previewFile(props.file, 'svg');
  } else if (props.content) {
    previewContent(props.content, 'svg');
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
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>

<style>
/* 非 scoped 样式：SVG 显示 */
.svg-content svg {
  max-width: 100%;
  height: auto;
}
</style>
