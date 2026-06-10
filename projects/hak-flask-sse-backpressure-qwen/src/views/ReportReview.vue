<template>
  <div class="report-review-page">
    <header class="page-header">
      <h2>报告审核</h2>
      <div class="report-meta">
        <span>报告编号: {{ reportId }}</span>
        <span class="divider">|</span>
        <span>状态: {{ reportStatus }}</span>
      </div>
    </header>

    <!-- Report content display section -->
    <section class="report-content">
      <h3>报告内容</h3>
      <div v-html="reportData.content" class="content-preview"></div>
    </section>

    <!-- Review opinion editor section -->
    <section class="review-section">
      <h3>审核意见</h3>

      <RichTextEditor
        v-model="reviewOpinion"
        :editor-height="'300px'"
        :image-upload-url="'/api/reports/upload'"
        :upload-headers="uploadHeaders"
        @on-created="onEditorCreated"
        @on-change="onEditorChange"
      />

      <div class="review-actions">
        <button class="btn btn-reject" @click="submitReview('rejected')">
          驳回
        </button>
        <button class="btn btn-approve" @click="submitReview('approved')">
          通过
        </button>
        <button class="btn btn-save" @click="saveDraft">
          暂存
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
/**
 * ReportReview.vue
 *
 * 报告审核页面 — 使用 RichTextEditor 编写审核意见。
 *
 * 此页面通过 Vue Router 的 keep-alive 缓存。
 * RichTextEditor 组件内部已处理 activated/deactivated 生命周期，
 * 确保编辑器实例和事件监听器正确清理，不会内存泄漏。
 */

import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import RichTextEditor from '@/components/RichTextEditor.vue'

// ─── Router ─────────────────────────────────────────────────────────────────

const route = useRoute()
const router = useRouter()

// ─── State ──────────────────────────────────────────────────────────────────

const reportId = computed(() => route.params.id)
const reportStatus = ref('待审核')
const reviewOpinion = ref('')
const reportData = ref({
  content: '',
})

const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${getToken()}`,
  'X-Report-Id': reportId.value,
}))

// ─── Editor callbacks ───────────────────────────────────────────────────────

function onEditorCreated(editor) {
  console.log('[ReportReview] editor created, id:', reportId.value)
}

function onEditorChange(editor) {
  // Optional: auto-save draft on change
}

// ─── Actions ────────────────────────────────────────────────────────────────

async function submitReview(decision) {
  if (!reviewOpinion.value || reviewOpinion.value === '<p><br></p>') {
    alert('请填写审核意见')
    return
  }

  try {
    const response = await fetch(`/api/reports/${reportId.value}/review`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${getToken()}`,
      },
      body: JSON.stringify({
        decision,
        opinion: reviewOpinion.value,
      }),
    })

    if (!response.ok) {
      throw new Error(`提交审核失败: ${response.status}`)
    }

    reportStatus.value = decision === 'approved' ? '已通过' : '已驳回'
    alert(`审核${decision === 'approved' ? '通过' : '驳回'}成功`)

    // Navigate back to report list
    router.push('/reports')
  } catch (err) {
    console.error('[ReportReview] submit error:', err)
    alert('提交失败，请重试')
  }
}

async function saveDraft() {
  try {
    await fetch(`/api/reports/${reportId.value}/draft`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${getToken()}`,
      },
      body: JSON.stringify({ opinion: reviewOpinion.value }),
    })
    alert('暂存成功')
  } catch (err) {
    console.error('[ReportReview] save draft error:', err)
  }
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function getToken() {
  return localStorage.getItem('auth_token') || ''
}

// ─── Lifecycle ──────────────────────────────────────────────────────────────

onMounted(async () => {
  // Load report data
  try {
    const res = await fetch(`/api/reports/${reportId.value}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    if (res.ok) {
      reportData.value = await res.json()
    }
  } catch (err) {
    console.error('[ReportReview] failed to load report:', err)
  }
})
</script>

<style scoped>
.report-review-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0 0 8px;
}

.report-meta {
  color: #666;
  font-size: 14px;
}

.report-meta .divider {
  margin: 0 12px;
}

.report-content {
  margin-bottom: 32px;
  padding: 16px;
  background: #f9f9f9;
  border-radius: 4px;
}

.content-preview {
  margin-top: 12px;
  line-height: 1.6;
}

.review-section h3 {
  margin-bottom: 12px;
}

.review-actions {
  margin-top: 16px;
  display: flex;
  gap: 12px;
}

.btn {
  padding: 8px 24px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-approve {
  background: #52c41a;
  color: white;
}

.btn-reject {
  background: #ff4d4f;
  color: white;
}

.btn-save {
  background: #1890ff;
  color: white;
}
</style>
