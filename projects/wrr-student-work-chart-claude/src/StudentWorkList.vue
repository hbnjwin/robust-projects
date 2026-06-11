<template>
  <div class="student-work">
    <el-card>
      <template #header>
        <div class="header">
          <span>学生作品管理</span>
          <!-- BUG (feature gap): 缺少统计面板切换按钮 -->
          <!-- <el-radio-group v-model="viewMode">
            <el-radio-button value="list">列表</el-radio-button>
            <el-radio-button value="chart">统计</el-radio-button>
          </el-radio-group> -->
        </div>
      </template>

      <!-- 只有列表视图，缺少统计面板 -->
      <el-table :data="works" v-loading="loading">
        <el-table-column prop="studentName" label="学生" />
        <el-table-column prop="type" label="作品类型">
          <template #default="{ row }">
            {{ typeMap[row.type] || row.type }}
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" />
        <el-table-column prop="createTime" label="创建时间" />
        <el-table-column label="操作">
          <template #default="{ row }">
            <el-button text @click="viewWork(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pageNo"
        :page-size="pageSize"
        :total="total"
        @current-change="loadWorks"
      />
    </el-card>

    <!-- BUG (feature gap): 缺少 ECharts 统计面板 -->
    <!-- 需要展示：
      1. 柱状图：每个学生的 AI 对话次数、绘画作品数、音乐生成数对比
      2. 折线图：全班使用趋势（按周统计）
    -->
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

const typeMap: Record<string, string> = {
  chat: 'AI 对话',
  painting: 'AI 绘画',
  music: 'AI 音乐'
}

const works = ref<any[]>([])
const loading = ref(false)
const pageNo = ref(1)
const pageSize = ref(20)
const total = ref(0)

const loadWorks = async () => {
  loading.value = true
  try {
    const { data } = await axios.get('/api/edu/student-work/page', {
      params: { pageNo: pageNo.value, pageSize: pageSize.value }
    })
    works.value = data.data.list
    total.value = data.data.total
  } finally {
    loading.value = false
  }
}

const viewWork = (work: any) => {
  // 查看作品详情
}

onMounted(loadWorks)
</script>
