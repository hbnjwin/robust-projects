<template>
  <!--
    Bug 2 修复配合层：
    beforeEnter 守卫已确保进入此组件时 store 有数据。
    这里做防御性条件渲染：loading/error 时不渲染 <RouterView>，
    避免子组件（如审核页）在数据未就绪时访问 store.currentReport。
  -->
  <div class="report-detail-layout">
    <div class="report-detail-layout__nav">
      <button class="back-btn" @click="goBack">返回列表</button>
      <template v-if="reportStore.currentReport">
        <RouterLink
          :to="{ name: 'report-detail', params: { id: reportStore.currentReport.id } }"
          class="nav-link"
          :class="{ active: route.name === 'report-detail' }"
        >
          详情
        </RouterLink>
        <RouterLink
          :to="{ name: 'report-review', params: { id: reportStore.currentReport.id } }"
          class="nav-link"
          :class="{ active: route.name === 'report-review' }"
        >
          审核
        </RouterLink>
      </template>
    </div>

    <AppLoading v-if="reportStore.loading" />
    <AppError
      v-else-if="reportStore.error"
      :message="reportStore.error"
      @retry="retry"
    />
    <template v-else-if="reportStore.currentReport">
      <ReportSummary :report="reportStore.currentReport" />
      <RouterView />
    </template>
  </div>
</template>

<script setup lang="ts">
import { useRouter, useRoute, RouterLink, RouterView } from 'vue-router'
import { useReportStore } from '@/stores/report'
import AppLoading from '@/components/AppLoading.vue'
import AppError from '@/components/AppError.vue'
import ReportSummary from '@/components/ReportSummary.vue'

const router = useRouter()
const route = useRoute()
const reportStore = useReportStore()

function goBack() {
  router.back()
}

function retry() {
  const id = route.params.id as string
  reportStore.fetchReport(id)
}
</script>

<style scoped>
.report-detail-layout {
  max-width: 1080px;
  margin: 0 auto;
  padding: 24px;
}

.report-detail-layout__nav {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;
}

.back-btn {
  padding: 6px 12px;
  background: #f3f4f6;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: #374151;
  margin-right: 8px;
}

.back-btn:hover {
  background: #e5e7eb;
}

.nav-link {
  padding: 6px 16px;
  text-decoration: none;
  color: #6b7280;
  font-size: 14px;
  border-radius: 6px;
}

.nav-link:hover {
  background: #f3f4f6;
}

.nav-link.active {
  color: #3b82f6;
  background: #eff6ff;
  font-weight: 500;
}
</style>
