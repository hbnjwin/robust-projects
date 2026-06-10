<template>
  <div class="docx-preview">
    <div v-if="securityWarning" class="security-warning">
      <el-alert
        type="warning"
        :title="securityWarning"
        :closable="true"
        show-icon
      />
    </div>
    <div class="preview-content docx-content" v-html="safeHtml"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { sanitizeDocxHtml, detectXssVectors } from '@/utils/sanitizer'

const props = defineProps<{
  /** DOCX转换后的HTML内容（不可信） */
  content: string
}>()

/** 消毒后的安全HTML */
const safeHtml = computed(() => sanitizeDocxHtml(props.content))

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
  return warnings.length > 0 ? warnings.join('；') : null
})
</script>

<style scoped>
.docx-preview {
  padding: 16px;
}

.security-warning {
  margin-bottom: 12px;
}

.docx-content {
  line-height: 1.8;
  font-family: 'SimSun', 'Times New Roman', serif;
}

/* DOCX表格样式保留 */
.docx-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 16px 0;
}

.docx-content :deep(th),
.docx-content :deep(td) {
  border: 1px solid #000;
  padding: 6px 10px;
}

/* DOCX列表样式 */
.docx-content :deep(ul),
.docx-content :deep(ol) {
  padding-left: 2em;
  margin: 8px 0;
}

.docx-content :deep(li) {
  margin: 4px 0;
}

/* 保留DOCX内联样式 - 不覆盖 */
.docx-content :deep(p) {
  margin: 8px 0;
}

.docx-content :deep(img) {
  max-width: 100%;
  height: auto;
}
</style>
