<template>
  <div class="html-preview">
    <div v-if="securityWarning" class="security-warning">
      <el-alert
        type="warning"
        :title="securityWarning"
        :closable="true"
        show-icon
      />
    </div>
    <div class="preview-content" v-html="safeHtml"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { sanitizeHtml, detectXssVectors } from '@/utils/sanitizer'

const props = defineProps<{
  /** 原始HTML内容（不可信） */
  content: string
}>()

/** 消毒后的安全HTML */
const safeHtml = computed(() => sanitizeHtml(props.content))

/** 安全警告信息 */
const securityWarning = computed(() => {
  const report = detectXssVectors(props.content)
  const warnings: string[] = []
  if (report.removedTags.length > 0) {
    warnings.push(`已过滤危险标签: ${report.removedTags.join(', ')}`)
  }
  if (report.removedAttributes.length > 0) {
    warnings.push(`已过滤危险属性: ${report.removedAttributes.join(', ')}`)
  }
  if (report.blockedUris > 0) {
    warnings.push(`已阻止 ${report.blockedUris} 个危险链接`)
  }
  return warnings.length > 0 ? warnings.join('；') : null
})
</script>

<style scoped>
.html-preview {
  padding: 16px;
}

.security-warning {
  margin-bottom: 12px;
}

.preview-content {
  line-height: 1.6;
  word-wrap: break-word;
  overflow-wrap: break-word;
}

/* 保留表格样式 */
.preview-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
}

.preview-content :deep(th),
.preview-content :deep(td) {
  border: 1px solid #dcdfe6;
  padding: 8px 12px;
  text-align: left;
}

.preview-content :deep(th) {
  background-color: #f5f7fa;
  font-weight: 600;
}

/* 保留列表样式 */
.preview-content :deep(ul),
.preview-content :deep(ol) {
  padding-left: 2em;
  margin: 8px 0;
}

.preview-content :deep(li) {
  margin: 4px 0;
}

/* 保留代码块样式 */
.preview-content :deep(pre) {
  background-color: #f5f7fa;
  border-radius: 4px;
  padding: 12px;
  overflow-x: auto;
}

.preview-content :deep(code) {
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.9em;
}

/* 保留图片样式 */
.preview-content :deep(img) {
  max-width: 100%;
  height: auto;
}
</style>
