<template>
  <t-dialog v-model:visible="visible" header="上传文档" :before-close="handleBeforeClose" :on-close="handleBeforeClose">
    <t-upload-dragger v-if="!uploading && !progress" @change="onFileSelect">
      <div class="drag-area">
        <span>点击或拖拽文件到此区域上传</span>
      </div>
    </t-upload-dragger>
    <div v-if="selectedFile" class="file-info">
      <span>{{ selectedFile.name }} ({{ formatSize(selectedFile.size) }})</span>
    </div>
    <t-progress v-if="uploading || progress > 0" :percentage="progress" :status="progressStatus" />
    <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>
    <template #footer>
      <t-button v-if="selectedFile && !uploading" theme="primary" @click="startUpload">开始上传</t-button>
      <t-button v-if="uploading" theme="danger" @click="handleCancel">取消上传</t-button>
    </template>
  </t-dialog>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'
import { MessagePlugin } from 'tdesign-vue-next'
import { getOauth } from '@/utils/oauth2'

const visible = ref(false)
const uploading = ref(false)
const progress = ref(0)
const progressStatus = ref('active')
const selectedFile = ref(null)
const errorMsg = ref('')
let currentController = null
let formData = null

const onFileSelect = (files) => {
  if (files && files.length > 0) {
    selectedFile.value = files[0]
    formData = null
    progress.value = 0
    progressStatus.value = 'active'
    errorMsg.value = ''
  }
}

const startUpload = async () => {
  if (!selectedFile.value) return
  uploading.value = true
  progress.value = 0
  progressStatus.value = 'active'
  errorMsg.value = ''
  formData = new FormData()
  formData.append('file', selectedFile.value)
  currentController = new AbortController()
  try {
    await axios.post('/api/documents/uploadFile', formData, {
      headers: { Authorization: `Bearer ${getOauth()}` },
      signal: currentController.signal,
      onUploadProgress: (e) => {
        progress.value = e.total ? Math.round((e.loaded * 100) / e.total) : 0
      }
    })
    MessagePlugin.success('上传成功')
    uploading.value = false
    progress.value = 0
    selectedFile.value = null
    formData = null
  } catch (err) {
    if (axios.isCancel(err)) {
      progressStatus.value = 'warning'
    } else {
      errorMsg.value = err.response?.data?.message || '上传失败'
      progressStatus.value = 'error'
    }
    uploading.value = false
  } finally {
    currentController = null
  }
}

const formatSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

const handleCancel = () => {
  if (currentController) {
    currentController.abort()
  }
  uploading.value = false
}

const resetState = () => {
  if (currentController) {
    currentController.abort()
    currentController = null
  }
  formData = null
  selectedFile.value = null
  uploading.value = false
  progress.value = 0
  progressStatus.value = 'active'
  errorMsg.value = ''
}

const handleBeforeClose = () => {
  resetState()
  return true
}

defineExpose({ visible })
</script>

<style scoped>
.drag-area {
  padding: 40px 0;
  text-align: center;
  color: #999;
}
.file-info {
  margin: 8px 0;
  font-size: 13px;
  color: #333;
}
.error-msg {
  margin-top: 8px;
  color: #e34d59;
  font-size: 13px;
}
</style>
