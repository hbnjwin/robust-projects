<template>
  <div class="report-detail-view">
    <div v-if="report" class="sections">
      <div
        v-for="section in report.sections"
        :key="section.id"
        class="section-card"
      >
        <h3>{{ section.order }}. {{ section.title }}</h3>
        <p>{{ section.content }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useReportStore } from '@/stores/report'

const reportStore = useReportStore()

// 可以安全访问 currentReport：
// beforeEnter 守卫已保证进入此组件时 store 有数据
// ReportDetailLayout 仅在 currentReport 不为 null 时渲染 <RouterView>
const report = computed(() => reportStore.currentReport)
</script>

<style scoped>
.report-detail-view {
  margin-top: 4px;
}

.sections {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-card {
  padding: 20px 24px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.section-card h3 {
  font-size: 16px;
  color: #111827;
  margin: 0 0 12px;
}

.section-card p {
  font-size: 14px;
  color: #4b5563;
  line-height: 1.6;
  margin: 0;
}
</style>
