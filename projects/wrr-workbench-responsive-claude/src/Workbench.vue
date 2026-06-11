<template>
  <div class="workbench">
    <!-- 统计卡片：el-row/el-col 栅格适配各屏幕 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <h3>课程数量</h3>
          <span class="value">{{ stats.courseCount }}</span>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <h3>学生人数</h3>
          <span class="value">{{ stats.studentCount }}</span>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <h3>作业数量</h3>
          <span class="value">{{ stats.homeworkCount }}</span>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <div class="stat-card">
          <h3>AI 使用次数</h3>
          <span class="value">{{ stats.aiUsageCount }}</span>
        </div>
      </el-col>
    </el-row>

    <!-- 快捷菜单：el-row/el-col 栅格适配 -->
    <el-row :gutter="16" class="shortcuts">
      <el-col :xs="8" :sm="4" v-for="item in shortcuts" :key="item.name">
        <div class="shortcut-item">
          <el-icon :size="40"><component :is="item.icon" /></el-icon>
          <p>{{ item.name }}</p>
        </div>
      </el-col>
    </el-row>

    <!-- 课程列表：el-row/el-col 栅格适配 -->
    <div class="course-list">
      <h3>最近课程</h3>
      <el-row :gutter="16">
        <el-col :xs="24" :sm="12" :md="8" v-for="course in recentCourses" :key="course.id">
          <el-card>
            <h4>{{ course.name }}</h4>
            <p>{{ course.description }}</p>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

const stats = ref({
  courseCount: 0,
  studentCount: 0,
  homeworkCount: 0,
  aiUsageCount: 0
})

const shortcuts = ref([
  { name: '课程管理', icon: 'Reading' },
  { name: '学生管理', icon: 'User' },
  { name: '作业批改', icon: 'Edit' },
  { name: 'AI 对话', icon: 'ChatDotRound' },
  { name: 'AI 绘画', icon: 'Picture' },
  { name: '数据统计', icon: 'DataLine' }
])

const recentCourses = ref<any[]>([])

onMounted(async () => {
  const { data } = await axios.get('/api/edu/workbench/summary')
  stats.value = data.data.stats
  recentCourses.value = data.data.recentCourses
})
</script>

<style scoped>
.workbench {
  padding: 20px;
  overflow-x: hidden;
}

.stat-card {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 20px;
  min-height: 120px;
  box-sizing: border-box;
  margin-bottom: 20px;
}

.stat-card .value {
  font-size: 36px;
  font-weight: bold;
  color: #409eff;
}

.shortcuts {
  margin-top: 4px;
}

.shortcut-item {
  text-align: center;
  padding: 12px 0;
  cursor: pointer;
}

.shortcut-item p {
  margin: 8px 0 0;
  font-size: 14px;
}

.course-list {
  margin-top: 20px;
}

.course-list .el-card {
  margin-bottom: 16px;
}

@media (max-width: 768px) {
  .stat-card .value {
    font-size: 28px;
  }

  .shortcut-item :deep(.el-icon) {
    font-size: 32px !important;
  }
}
</style>
