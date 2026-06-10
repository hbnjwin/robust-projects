<template>
  <div class="report-detail">
    <div class="header">
      <button @click="goBack" class="back-btn">
        ← 返回列表
      </button>
      <h1>{{ report?.title || '加载中...' }}</h1>
    </div>

    <div v-if="report" class="content">
      <div class="info">
        <p><strong>ID:</strong> {{ report.id }}</p>
        <p><strong>状态:</strong> {{ report.status }}</p>
        <p><strong>创建时间:</strong> {{ report.createdAt }}</p>
      </div>

      <div class="actions">
        <router-link :to="`/reports/${report.id}/review`" class="btn">
          进入审核
        </router-link>
      </div>
    </div>

    <div v-else class="loading">
      <p>正在加载报告详情...</p>
    </div>

    <!-- 子路由出口 -->
    <router-view v-if="report"></router-view>
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useReportStore } from '@/store/report'

const props = defineProps({
  id: { type: String, required: true }
})

const router = useRouter()
const route = useRoute()
const store = useReportStore()

const report = computed(() => store.currentReport)

// Bug 1 修复：返回时保留之前的 query 参数
// 使用 router.back() 而不是 router.push()，这样浏览器会自动恢复之前的历史状态
// 包括所有的 query 参数
function goBack() {
  router.back()
}

async function loadReport() {
  try {
    await store.loadReportById(props.id)
  } catch (error) {
    console.error('加载报告失败:', error)
    router.push('/reports')
  }
}

onMounted(loadReport)

// 监听 id 变化（路由参数变化时重新加载）
watch(() => props.id, loadReport)
</script>

<style scoped>
.report-detail {
  padding: 20px;
}

.header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 20px;
}

.back-btn {
  padding: 8px 16px;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  background: white;
}

.back-btn:hover {
  background: #f5f5f5;
}

.info {
  background: #f9f9f9;
  padding: 20px;
  border-radius: 4px;
  margin-bottom: 20px;
}

.actions {
  margin-top: 20px;
}

.btn {
  display: inline-block;
  padding: 10px 20px;
  background: #007bff;
  color: white;
  text-decoration: none;
  border-radius: 4px;
}

.btn:hover {
  background: #0056b3;
}

.loading {
  text-align: center;
  padding: 40px;
  color: #999;
}
</style>
