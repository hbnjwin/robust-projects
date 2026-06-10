<template>
  <div class="svg-preview">
    <div v-if="securityWarning" class="security-warning">
      <el-alert
        type="warning"
        :title="securityWarning"
        :closable="true"
        show-icon
      />
    </div>
    <div class="preview-content svg-container" v-html="safeSvg"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { sanitizeSvg, detectXssVectors } from '@/utils/sanitizer'

const props = defineProps<{
  /** 原始SVG内容（不可信） */
  content: string
}>()

/** 消毒后的安全SVG */
const safeSvg = computed(() => sanitizeSvg(props.content))

/** 安全警告 */
const securityWarning = computed(() => {
  const report = detectXssVectors(props.content)
  const warnings: string[] = []
  if (report.removedTags.length > 0) {
    warnings.push(`已过滤危险标签: ${report.removedTags.join(', ')}`)
  }
  if (report.blockedUris > 0) {
    warnings.push(`已阻止 ${report.blockedUris} 个危险链接`)
  }
  return warnings.length > 0 ? warnings.join('；') : null
})
</script>

<style scoped>
.svg-preview {
  padding: 16px;
}

.security-warning {
  margin-bottom: 12px;
}

.svg-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
}

.svg-container :deep(svg) {
  max-width: 100%;
  max-height: 80vh;
  height: auto;
}
</style>
