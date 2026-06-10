<template>
  <div class="dashboard">
    <h3 class="section-title">{{ $t('dashboard.title') }}</h3>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6" v-for="stat in statCards" :key="stat.key">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">{{ $t(stat.labelKey) }}</div>
          <div class="stat-value">{{ stat.value }}</div>
          <div class="stat-footer">
            <span>{{ $t('dashboard.comparedToYesterday') }}</span>
            <span :class="stat.trend > 0 ? 'trend-up' : 'trend-down'">
              {{ stat.trend > 0 ? $t('dashboard.increase') : $t('dashboard.decrease') }}
              {{ Math.abs(stat.trend) }}%
            </span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 趋势图占位 -->
    <el-card shadow="hover" class="chart-card">
      <template #header>
        <div class="card-header">
          <span>{{ $t('dashboard.trendChart') }}</span>
          <el-radio-group v-model="chartPeriod" size="small">
            <el-radio-button value="week">{{ $t('dashboard.week') }}</el-radio-button>
            <el-radio-button value="month">{{ $t('dashboard.month') }}</el-radio-button>
            <el-radio-button value="year">{{ $t('dashboard.year') }}</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <div class="chart-placeholder">
        {{ $t('dashboard.trendChart') }} ({{ $t('dashboard.' + chartPeriod) }})
      </div>
    </el-card>

    <!-- 最近动态 -->
    <el-card shadow="hover" class="activity-card">
      <template #header>
        <span>{{ $t('dashboard.recentActivities') }}</span>
      </template>
      <el-timeline>
        <el-timeline-item
          v-for="(item, idx) in activities"
          :key="idx"
          :timestamp="item.time"
          placement="top"
        >
          {{ item.content }}
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'

const chartPeriod = ref('week')

const statCards = reactive([
  { key: 'visits', labelKey: 'dashboard.todayVisits', value: '12,846', trend: 12.5 },
  { key: 'users', labelKey: 'dashboard.totalUsers', value: '58,392', trend: 3.2 },
  { key: 'active', labelKey: 'dashboard.activeUsers', value: '8,127', trend: -2.1 },
  { key: 'orders', labelKey: 'dashboard.orderCount', value: '3,456', trend: 8.7 }
])

const activities = reactive([
  { content: 'admin 执行了用户管理操作', time: '2026-06-10 14:32' },
  { content: 'operator 导出了报表数据', time: '2026-06-10 13:15' },
  { content: 'admin 修改了系统设置', time: '2026-06-10 11:48' },
  { content: 'viewer 提交了反馈工单', time: '2026-06-10 09:22' }
])
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.section-title {
  margin: 0 0 4px;
  font-size: 18px;
  color: #303133;
}
.stat-card {
  text-align: center;
}
.stat-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
}
.stat-footer {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
  display: flex;
  justify-content: center;
  gap: 6px;
}
.trend-up { color: #67c23a; }
.trend-down { color: #f56c6c; }
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.chart-placeholder {
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  border-radius: 6px;
  color: #909399;
  font-size: 14px;
}
</style>
