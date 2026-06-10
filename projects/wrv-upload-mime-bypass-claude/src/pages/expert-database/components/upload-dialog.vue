<template>
  <t-dialog v-model:visible="visible" header="上传文档" @close="handleClose">
    <t-upload
      :action="uploadUrl"
      :headers="uploadHeaders"
      :before-upload="beforeUpload"
      :on-success="onSuccess"
      :on-fail="onFail"
      accept=".pdf,.docx,.xlsx,.doc"
      :size-limit="{ size: 100, unit: 'MB' }"
    >
      <t-button>选择文件</t-button>
    </t-upload>
  </t-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { getOauth } from '@/utils/oauth2'

const visible = ref(false)
const uploadUrl = '/api/documents/uploadFile'
const uploadHeaders = { Authorization: `Bearer ${getOauth()}` }

const beforeUpload = (file) => {
  const ext = file.name.split('.').pop().toLowerCase()
  const allowedExts = ['pdf', 'docx', 'xlsx', 'doc']
  if (!allowedExts.includes(ext)) {
    MessagePlugin.error('不支持的文件格式')
    return false
  }
  return true
}

const onSuccess = () => { MessagePlugin.success('上传成功') }
const onFail = () => { MessagePlugin.error('上传失败') }
const handleClose = () => { visible.value = false }

defineExpose({ visible })
</script>
