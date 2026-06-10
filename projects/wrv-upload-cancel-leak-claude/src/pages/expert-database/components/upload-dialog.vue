<template>
  <t-dialog v-model:visible="visible" header="上传文档" :before-close="handleBeforeClose">
    <t-upload ref="uploadRef" :action="uploadUrl" :headers="headers"
      :on-progress="onProgress" :on-success="onSuccess">
      <t-button>选择文件</t-button>
    </t-upload>
    <t-progress v-if="uploading" :percentage="progress" />
    <t-button v-if="uploading" @click="handleCancel">取消上传</t-button>
  </t-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { getOauth } from '@/utils/oauth2'

const visible = ref(false)
const uploading = ref(false)
const progress = ref(0)
const uploadUrl = '/api/documents/uploadFile'
const headers = { Authorization: `Bearer ${getOauth()}` }

const onProgress = (val) => { uploading.value = true; progress.value = val.percent }
const onSuccess = () => { uploading.value = false; progress.value = 0 }
const handleCancel = () => { uploading.value = false }
const handleBeforeClose = () => { visible.value = false }

defineExpose({ visible })
</script>
