<template>
  <div class="review-panel">
    <h2>审核操作</h2>
    <div class="review-panel__form">
      <div class="review-panel__field">
        <label>审核意见</label>
        <textarea
          v-model="comment"
          placeholder="请输入审核意见..."
          rows="4"
        ></textarea>
      </div>
      <div class="review-panel__actions">
        <button
          class="btn btn--approve"
          :disabled="submitting"
          @click="handleSubmit('approve')"
        >
          通过
        </button>
        <button
          class="btn btn--reject"
          :disabled="submitting"
          @click="handleSubmit('reject')"
        >
          驳回
        </button>
      </div>
      <p v-if="error" class="review-panel__error">{{ error }}</p>
    </div>

    <div v-if="report.annotations.length > 0" class="review-panel__annotations">
      <h3>批注记录</h3>
      <div
        v-for="anno in report.annotations"
        :key="anno.id"
        class="annotation-item"
      >
        <div class="annotation-item__header">
          <span class="annotation-item__author">{{ anno.author }}</span>
          <span class="annotation-item__date">{{ formatDate(anno.createdAt) }}</span>
        </div>
        <p class="annotation-item__content">{{ anno.content }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { Report, ReviewPayload } from '@/types/report'

const props = defineProps<{
  report: Report
}>()

const emit = defineEmits<{
  submit: [payload: ReviewPayload]
}>()

const comment = ref('')
const submitting = ref(false)
const error = ref<string | null>(null)

async function handleSubmit(action: 'approve' | 'reject') {
  if (!comment.value.trim()) {
    error.value = '请输入审核意见'
    return
  }
  submitting.value = true
  error.value = null
  try {
    emit('submit', { action, comment: comment.value })
  } finally {
    submitting.value = false
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.review-panel {
  padding: 20px 24px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.review-panel h2 {
  font-size: 16px;
  margin: 0 0 16px;
  color: #111827;
}

.review-panel__field {
  margin-bottom: 16px;
}

.review-panel__field label {
  display: block;
  font-size: 13px;
  color: #374151;
  margin-bottom: 6px;
  font-weight: 500;
}

.review-panel__field textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  resize: vertical;
  box-sizing: border-box;
}

.review-panel__actions {
  display: flex;
  gap: 12px;
}

.btn {
  padding: 8px 24px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  font-weight: 500;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn--approve {
  background: #10b981;
  color: white;
}

.btn--approve:hover:not(:disabled) {
  background: #059669;
}

.btn--reject {
  background: #ef4444;
  color: white;
}

.btn--reject:hover:not(:disabled) {
  background: #dc2626;
}

.review-panel__error {
  color: #dc2626;
  font-size: 13px;
  margin-top: 12px;
}

.review-panel__annotations {
  margin-top: 24px;
  border-top: 1px solid #e5e7eb;
  padding-top: 20px;
}

.review-panel__annotations h3 {
  font-size: 14px;
  margin: 0 0 12px;
  color: #374151;
}

.annotation-item {
  padding: 12px;
  background: #f9fafb;
  border-radius: 6px;
  margin-bottom: 8px;
}

.annotation-item__header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.annotation-item__author {
  font-size: 13px;
  font-weight: 500;
  color: #111827;
}

.annotation-item__date {
  font-size: 12px;
  color: #9ca3af;
}

.annotation-item__content {
  font-size: 13px;
  color: #4b5563;
  margin: 0;
}
</style>
