<template>
  <div class="file-preview">
    <!-- 加载状态 -->
    <div v-if="loading" class="preview-loading">
      <el-skeleton :rows="5" animated />
    </div>

    <!-- 错误状态 -->
    <el-alert
      v-else-if="error"
      type="error"
      :title="error"
      show-icon
      :closable="false"
    />

    <!-- 预览内容 -->
    <template v-else-if="fileContent">
      <HtmlPreview
        v-if="currentFileType === 'html'"
        :content="fileContent"
      />
      <DocxPreview
        v-else-if="currentFileType === 'docx'"
        :content="fileContent"
      />
      <MarkdownPreview
        v-else-if="currentFileType === 'markdown'"
        :content="fileContent"
      />
      <SvgPreview
        v-else-if="currentFileType === 'svg'"
        :content="fileContent"
      />
    </template>

    <!-- 空状态 -->
    <el-empty v-else description="暂无预览内容" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { PreviewFileType } from '@/types/preview'
import HtmlPreview from './HtmlPreview.vue'
import DocxPreview from './DocxPreview.vue'
import MarkdownPreview from './MarkdownPreview.vue'
import SvgPreview from './SvgPreview.vue'

const props = defineProps<{
  /** 文件名（用于推断文件类型） */
  fileName?: string
  /** 显式指定文件类型（优先于文件名推断） */
  fileType?: PreviewFileType
  /** 文件内容（字符串） */
  content?: string
}>()

const loading = ref(false)
const error = ref<string | null>(null)

/** 当前文件类型 */
const currentFileType = computed<PreviewFileType | null>(() => {
  if (props.fileType) return props.fileType
  if (props.fileName) return inferFileType(props.fileName)
  return null
})

/** 文件内容 */
const fileContent = computed(() => props.content ?? null)

/** 从文件名推断类型 */
function inferFileType(filename: string): PreviewFileType {
  const ext = filename.split('.').pop()?.toLowerCase()
  switch (ext) {
    case 'html':
    case 'htm':
      return 'html'
    case 'docx':
      return 'docx'
    case 'md':
    case 'markdown':
      return 'markdown'
    case 'svg':
      return 'svg'
    default:
      return 'html'
  }
}

watch(() => props.content, (newContent) => {
  if (newContent && !currentFileType.value) {
    error.value = '无法识别文件类型，请指定 fileType 属性'
  } else {
    error.value = null
  }
})
</script>

<style scoped>
.file-preview {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #fff;
  min-height: 200px;
  overflow: auto;
}

.preview-loading {
  padding: 24px;
}
</style>
