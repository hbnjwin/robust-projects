<template>
  <div class="workbench">
    <!-- BUG: 使用固定像素布局，不响应屏幕尺寸变化 -->
    <!-- 在 iPad 竖屏和 13 寸笔记本上会严重错乱 -->
    <div class="stat-cards" style="display: flex; gap: 20px;">
      <div class="stat-card" style="width: 280px; height: 120px;">
        <h3>课程数量</h3>
        <span class="value">{{ stats.courseCount }}</span>
      </div>
      <div class="stat-card" style="width: 280px; height: 120px;">
        <h3>学生人数</h3>
        <span class="value">{{ stats.studentCount }}</span>
      </div>
      <div class="stat-card" style="width: 280px; height: 120px;">
        <h3>作业数量</h3>
        <span class="value">{{ stats.homeworkCount }}</span>
      </div>
      <div class="stat-card" style="width: 280px; height: 120px;">
        <h3>AI 使用次数</h3>
        <span class="value">{{ stats.aiUsageCount }}</span>
      </div>
    </div>

    <!-- BUG: 快捷菜单也是固定宽度 -->
    <div class="shortcuts" style="display: flex; gap: 16px; margin-top: 20px;">
      <div v-for="item in shortcuts" :key="item.name"
           class="shortcut-item" style="width: 100px; text-align: center;">
        <el-icon :size="40"><component :is="item.icon" /></el-icon>
        <p>{{ item.name }}</p>
      </div>
    </div>

    <!-- BUG: 课程列表没有做响应式，宽度可能超出容器 -->
    <div class="course-list" style="margin-top: 20px;">
      <h3>最近课程</h3>
      <div style="display: flex; gap: 16px; flex-wrap: nowrap;">
        <el-card v-for="course in recentCourses" :key="course.id"
                 style="width: 320px; flex-shrink: 0;">
          <h4>{{ course.name }}</h4>
          <p>{{ course.description }}</p>
        </el-card>
      </div>
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
/* BUG: 没有响应式样式 */
/* 应该使用 CSS Grid 或 Element Plus 的 Row/Col 栅格系统 */
/* 应该添加 @media 查询适配不同屏幕尺寸 */
.stat-card {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 20px;
}
.stat-card .value {
  font-size: 36px;
  font-weight: bold;
  color: #409eff;
}
</style>
