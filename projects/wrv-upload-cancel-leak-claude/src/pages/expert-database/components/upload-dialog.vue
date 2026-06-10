<template>
  <t-dialog v-model:visible="visible" header="上传文档" :before-close="handleBeforeClose">
    <t-upload ref="uploadRef" :request-method="customUpload"
      :on-success="onSuccess">
      <t-button>选择文件</t-button>
    </t-upload>
    <t-progress v-if="uploading" :percentage="progress" />
    <t-button v-if="uploading" @click="handleCancel">取消上传</t-button>
  </t-dialog>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'
import { getOauth } from '@/utils/oauth2'

const visible = ref(false)
const uploading = ref(false)
const progress = ref(0)
const uploadRef = ref(null)
const uploadUrl = '/api/documents/uploadFile'

let abortController = null
let currentFormData = null

function cleanup() {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  currentFormData = null
  uploading.value = false
  progress.value = 0
}

async function customUpload(file) {
  cleanup()

  abortController = new AbortController()
  currentFormData = new FormData()
  currentFormData.append('file', file.raw)

  uploading.value = true
  try {
    const res = await axios.post(uploadUrl, currentFormData, {
      headers: { Authorization: `Bearer ${getOauth()}` },
      signal: abortController.signal,
      onUploadProgress(e) {
        if (e.total) {
          progress.value = Math.round((e.loaded / e.total) * 100)
        }
      }
    })
    return { status: 'success', response: res.data }
  } catch (err) {
    if (axios.isCancel(err)) {
      return { status: 'fail', error: '上传已取消' }
    }
    return { status: 'fail', error: err.message }
  } finally {
    abortController = null
    currentFormData = null
  }
}

const onSuccess = () => { cleanup() }

const handleCancel = () => { cleanup() }

const handleBeforeClose = () => {
  cleanup()
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
  visible.value = false
}

defineExpose({ visible })
</script>
