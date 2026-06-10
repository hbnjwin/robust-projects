<template>
  <div class="report-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>报告列表</span>
        </div>
      </template>

      <el-table :data="reportList" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="报告标题" />
        <el-table-column prop="author" label="作者" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="date" label="提交日期" width="120" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const reportList = ref([
  { id: 1, title: '2024年第一季度风电场运行报告', author: '张三', status: '待审核', date: '2024-03-15' },
  { id: 2, title: '风机故障分析报告', author: '李四', status: '已通过', date: '2024-03-10' },
  { id: 3, title: '月度发电量统计报告', author: '王五', status: '初审中', date: '2024-03-08' },
  { id: 4, title: '设备维护记录', author: '赵六', status: '已驳回', date: '2024-03-05' },
  { id: 5, title: '安全巡检报告', author: '孙七', status: '复审中', date: '2024-03-01' }
])

const getStatusType = (status: string) => {
  const typeMap: Record<string, string> = {
    '待审核': 'warning',
    '初审中': '',
    '复审中': 'info',
    '已通过': 'success',
    '已驳回': 'danger'
  }
  return typeMap[status] || ''
}
</script>

<style scoped>
.report-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
