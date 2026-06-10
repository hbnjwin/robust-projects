<template>
  <div class="report-review-view">
    <!--
      Bug 2 修复效果验证点：
      此组件在 /reports/:id/review（第三层路由）。
      F5刷新时，beforeEnter守卫在父路由先执行，
      await fetchReport(id) 完成后才挂载此组件，
      因此 report 一定有值，不会出现白屏。
    -->
    <div v-if="report" class="review-content">
      <div class="review-sections">
        <div
          v-for="section in report.sections"
          :key="section.id"
          class="section-card"
        >
          <h3>{{ section.order }}. {{ section.title }}</h3>
          <p>{{ section.content }}</p>
        </div>
      </div>
      <aside class="review-sidebar">
        <ReviewPanel :report="report" @submit="handleReview" />
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useReportStore } from '@/stores/report'
import ReviewPanel from '@/components/ReviewPanel.vue'
import type { ReviewPayload } from '@/types/report'

const router = useRouter()
const reportStore = useReportStore()

const report = computed(() => reportStore.currentReport)

async function handleReview(payload: ReviewPayload) {
  if (!report.value) return
  try {
    await reportStore.review(report.value.id, payload)
    router.push({ name: 'report-detail', params: { id: report.value.id } })
  } catch {
    // 错误已在 store 中处理
  }
}
</script>

<style scoped>
.report-review-view {
  margin-top: 4px;
}

.review-content {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 20px;
  align-items: start;
}

.review-sections {
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

.review-sidebar {
  position: sticky;
  top: 24px;
}
</style>
