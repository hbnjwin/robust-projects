<template>
  <div class="report-item" :class="`status-${report.status}`">
    <!-- 报告标题（可能 1-2 行，高度不固定的主要原因） -->
    <div class="report-header">
      <h3 class="report-title">{{ report.title }}</h3>
      <StatusBadge :status="report.status" />
    </div>

    <!-- 报告摘要 -->
    <p class="report-summary">{{ report.summary }}</p>

    <!-- 标签列表（数量不定，0-N 个） -->
    <div v-if="report.tags && report.tags.length > 0" class="report-tags">
      <el-tag
        v-for="tag in report.tags"
        :key="tag"
        size="small"
        type="info"
      >
        {{ tag }}
      </el-tag>
    </div>

    <!-- 审核人信息（头像 + 姓名，人数不定） -->
    <div class="report-meta">
      <div class="reviewers">
        <el-avatar
          v-for="reviewer in report.reviewers"
          :key="reviewer.name"
          :size="24"
          :src="reviewer.avatar"
        >
          {{ reviewer.name.charAt(0) }}
        </el-avatar>
        <span v-if="report.reviewers.length > 0" class="reviewer-names">
          {{ report.reviewers.map((r) => r.name).join('、') }}
        </span>
      </div>

      <span class="created-at">{{ report.createdAt }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import StatusBadge from './StatusBadge.vue'

interface Report {
  id: string | number
  title: string
  status: 'pending' | 'approved' | 'rejected'
  tags: string[]
  reviewers: { name: string; avatar: string }[]
  createdAt: string
  summary: string
}

defineProps<{
  report: Report
}>()
</script>

<style scoped>
.report-item {
  padding: 16px;
  border-bottom: 1px solid #f0f0f0;
  background: #fff;
  transition: background-color 0.2s;
}

.report-item:hover {
  background: #f5f7fa;
}

.report-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 8px;
}

.report-title {
  flex: 1;
  margin: 0;
  font-size: 15px;
  font-weight: 500;
  line-height: 1.5;
  color: #303133;
  /* 允许标题自然换行（1-2 行），不强制截断 */
}

.report-summary {
  margin: 0 0 12px 0;
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
}

.report-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.report-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #909399;
}

.reviewers {
  display: flex;
  align-items: center;
  gap: 8px;
}

.reviewer-names {
  color: #606266;
}

.created-at {
  color: #c0c4cc;
}

/* 状态颜色标识 */
.status-pending {
  border-left: 3px solid #e6a23c;
}

.status-approved {
  border-left: 3px solid #67c23a;
}

.status-rejected {
  border-left: 3px solid #f56c6c;
}
</style>
