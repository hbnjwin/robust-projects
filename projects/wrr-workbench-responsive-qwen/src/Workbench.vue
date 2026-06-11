<template>
  <div class="workbench">
    <!-- 统计卡片：使用 el-row/el-col 响应式栅格 -->
    <el-row :gutter="20">
      <el-col :xs="12" :sm="12" :md="6" v-for="(item, index) in statList" :key="index">
        <div class="stat-card">
          <h3>{{ item.label }}</h3>
          <span class="value">{{ item.value }}</span>
        </div>
      </el-col>
    </el-row>

    <!-- 快捷菜单：使用 CSS Grid auto-fit 自适应 -->
    <div class="shortcuts">
      <div v-for="item in shortcuts" :key="item.name"
           class="shortcut-item">
        <el-icon :size="iconSize"><component :is="item.icon" /></el-icon>
        <p>{{ item.name }}</p>
      </div>
    </div>

    <!-- 课程列表：使用 el-row/el-col 响应式栅格 -->
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'

const stats = ref({
  courseCount: 0,
  studentCount: 0,
  homeworkCount: 0,
  aiUsageCount: 0
})

const statList = computed(() => [
  { label: '课程数量', value: stats.value.courseCount },
  { label: '学生人数', value: stats.value.studentCount },
  { label: '作业数量', value: stats.value.homeworkCount },
  { label: 'AI 使用次数', value: stats.value.aiUsageCount }
])

const shortcuts = ref([
  { name: '课程管理', icon: 'Reading' },
  { name: '学生管理', icon: 'User' },
  { name: '作业批改', icon: 'Edit' },
  { name: 'AI 对话', icon: 'ChatDotRound' },
  { name: 'AI 绘画', icon: 'Picture' },
  { name: '数据统计', icon: 'DataLine' }
])

const recentCourses = ref<any[]>([])

// 响应式图标尺寸
const windowWidth = ref(window.innerWidth)
const iconSize = computed(() => (windowWidth.value < 768 ? 32 : 40))

const onResize = () => {
  windowWidth.value = window.innerWidth
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  const { data } = await axios.get('/api/edu/workbench/summary')
  stats.value = data.data.stats
  recentCourses.value = data.data.recentCourses
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
})
</script>

<style scoped>
.workbench {
  box-sizing: border-box;
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.stat-card {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 20px;
  min-height: 120px;
  margin-bottom: 12px;
}
.stat-card .value {
  font-size: 36px;
  font-weight: bold;
  color: #409eff;
}

/* 快捷菜单：CSS Grid auto-fit 自适应 */
.shortcuts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
  gap: 16px;
  margin-top: 20px;
}
.shortcut-item {
  text-align: center;
  padding: 12px 4px;
}
.shortcut-item p {
  margin: 8px 0 0;
  font-size: 14px;
  word-break: keep-all;
  white-space: nowrap;
}

/* 课程列表 */
.course-list {
  margin-top: 20px;
}
.course-list .el-card {
  margin-bottom: 12px;
}

/* iPad 竖屏及以下 (< 768px) */
@media (max-width: 768px) {
  .workbench {
    padding: 12px;
  }
  .stat-card {
    padding: 14px;
    min-height: 100px;
  }
  .stat-card .value {
    font-size: 28px;
  }
  .shortcuts {
    grid-template-columns: repeat(auto-fit, minmax(72px, 1fr));
    gap: 12px;
  }
  .shortcut-item p {
    font-size: 12px;
  }
}

/* 13 寸笔记本及中等屏幕 (768px ~ 1199px) */
@media (min-width: 769px) and (max-width: 1199px) {
  .stat-card {
    padding: 16px;
  }
  .stat-card .value {
    font-size: 32px;
  }
}
</style>
