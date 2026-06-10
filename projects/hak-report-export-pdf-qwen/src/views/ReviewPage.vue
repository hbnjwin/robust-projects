<template>
  <div class="review-page">
    <h2>报告审核</h2>

    <div v-if="report" class="review-content">
      <div class="report-info">
        <h3>{{ report.title }}</h3>
        <p>当前状态: <strong>{{ report.status }}</strong></p>
      </div>

      <div class="review-actions">
        <button @click="approve" class="btn approve">
          ✓ 通过
        </button>
        <button @click="reject" class="btn reject">
          ✗ 拒绝
        </button>
      </div>

      <div class="comments">
        <h4>审核意见</h4>
        <textarea
          v-model="comments"
          placeholder="请输入审核意见..."
          rows="5"
        ></textarea>
      </div>
    </div>

    <div v-else class="loading">
      <p>加载中...</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useReportStore } from '@/store/report'

const props = defineProps({
  id: { type: String, required: true }
})

const router = useRouter()
const store = useReportStore()

const comments = ref('')

const report = computed(() => store.currentReport)

async function approve() {
  try {
    // 模拟 API 调用
    await fetch(`/api/reports/${props.id}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ comments: comments.value })
    })

    // 更新 store 中的状态
    if (report.value) {
      report.value.status = 'approved'
    }

    alert('审核通过！')
    router.push('/reports')
  } catch (error) {
    console.error('审核失败:', error)
    alert('审核失败，请重试')
  }
}

async function reject() {
  if (!comments.value.trim()) {
    alert('拒绝时请填写审核意见')
    return
  }

  try {
    await fetch(`/api/reports/${props.id}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ comments: comments.value })
    })

    if (report.value) {
      report.value.status = 'rejected'
    }

    alert('已拒绝！')
    router.push('/reports')
  } catch (error) {
    console.error('审核失败:', error)
    alert('审核失败，请重试')
  }
}

onMounted(() => {
  // 如果 store 中没有当前报告，尝试加载
  if (!report.value) {
    store.loadReportById(props.id)
  }
})
</script>

<style scoped>
.review-page {
  padding: 20px;
  background: white;
  border-radius: 4px;
  margin-top: 20px;
}

.report-info {
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid #eee;
}

.review-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

.btn.approve {
  background: #28a745;
  color: white;
}

.btn.approve:hover {
  background: #218838;
}

.btn.reject {
  background: #dc3545;
  color: white;
}

.btn.reject:hover {
  background: #c82333;
}

.comments {
  margin-top: 20px;
}

.comments h4 {
  margin-bottom: 10px;
}

.comments textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  resize: vertical;
}

.loading {
  text-align: center;
  padding: 40px;
  color: #999;
}
</style>
