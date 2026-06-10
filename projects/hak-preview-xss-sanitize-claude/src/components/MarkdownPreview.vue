<template>
  <div class="markdown-preview">
    <div v-if="securityWarning" class="security-warning">
      <el-alert
        type="warning"
        :title="securityWarning"
        :closable="true"
        show-icon
      />
    </div>
    <div class="preview-content markdown-body" v-html="safeHtml"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import { sanitizeMarkdownHtml, detectXssVectors } from '@/utils/sanitizer'

const props = defineProps<{
  /** 原始Markdown内容 */
  content: string
}>()

/** marked渲染+DOMPurify消毒后的安全HTML */
const safeHtml = computed(() => {
  // 配置marked: 启用GFM（表格、任务列表等）
  marked.setOptions({
    breaks: true,
    gfm: true,
  })

  // 第一步: Markdown → HTML
  const rawHtml = marked.parse(props.content) as string
  // 第二步: DOMPurify消毒（清理代码块中的iframe等注入）
  return sanitizeMarkdownHtml(rawHtml)
})

/** 安全警告 */
const securityWarning = computed(() => {
  const rawHtml = marked.parse(props.content) as string
  const report = detectXssVectors(rawHtml)
  if (report.removedTags.length > 0 || report.removedAttributes.length > 0) {
    return `已过滤Markdown中的危险内容`
  }
  return null
})
</script>

<style scoped>
.markdown-preview {
  padding: 16px;
}

.security-warning {
  margin-bottom: 12px;
}

/* Markdown渲染样式 - 保留排版 */
.markdown-body {
  line-height: 1.6;
  word-wrap: break-word;
}

.markdown-body :deep(h1) { font-size: 2em; margin: 0.67em 0; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }
.markdown-body :deep(h2) { font-size: 1.5em; margin: 0.83em 0; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }
.markdown-body :deep(h3) { font-size: 1.17em; margin: 1em 0; }
.markdown-body :deep(h4) { font-size: 1em; margin: 1.33em 0; }

.markdown-body :deep(p) {
  margin: 8px 0;
}

/* 代码块 */
.markdown-body :deep(pre) {
  background-color: #f6f8fa;
  border-radius: 6px;
  padding: 16px;
  overflow-x: auto;
  line-height: 1.45;
}

.markdown-body :deep(code) {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 85%;
}

.markdown-body :deep(:not(pre) > code) {
  background-color: rgba(175, 184, 193, 0.2);
  border-radius: 3px;
  padding: 0.2em 0.4em;
}

/* 表格 */
.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 16px 0;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #d0d7de;
  padding: 6px 13px;
}

.markdown-body :deep(th) {
  background-color: #f6f8fa;
  font-weight: 600;
}

.markdown-body :deep(tr:nth-child(2n)) {
  background-color: #f6f8fa;
}

/* 列表 */
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 2em;
  margin: 8px 0;
}

.markdown-body :deep(li) {
  margin: 4px 0;
}

/* 引用块 */
.markdown-body :deep(blockquote) {
  margin: 8px 0;
  padding: 0 16px;
  color: #656d76;
  border-left: 4px solid #d0d7de;
}

/* 水平线 */
.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid #d0d7de;
  margin: 24px 0;
}

/* 图片 */
.markdown-body :deep(img) {
  max-width: 100%;
  height: auto;
}

/* 任务列表 */
.markdown-body :deep(input[type="checkbox"]) {
  margin-right: 4px;
}
</style>
