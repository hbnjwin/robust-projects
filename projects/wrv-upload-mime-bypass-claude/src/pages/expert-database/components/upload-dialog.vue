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

const uploadedFiles = new Set()

const ALLOWED_MIME_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/msword',
]

const MAGIC_SIGNATURES = [
  [0x25, 0x50, 0x44, 0x46], // %PDF
  [0x50, 0x4B, 0x03, 0x04], // PK (docx/xlsx are ZIP-based)
  [0xD0, 0xCF, 0x11, 0xE0], // OLE compound document (doc)
]

function readFileHeader(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => resolve(new Uint8Array(e.target.result))
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsArrayBuffer(file.slice(0, 4))
  })
}

const beforeUpload = async (file) => {
  const rawFile = file.raw || file

  // 1. 扩展名校验
  const ext = file.name.split('.').pop().toLowerCase()
  const allowedExts = ['pdf', 'docx', 'xlsx', 'doc']
  if (!allowedExts.includes(ext)) {
    MessagePlugin.error('不支持的文件格式，仅允许 PDF/DOCX/XLSX/DOC')
    return false
  }

  // 2. MIME 类型校验
  if (rawFile.type && !ALLOWED_MIME_TYPES.includes(rawFile.type)) {
    MessagePlugin.error('文件类型与扩展名不匹配，请确认文件真实格式')
    return false
  }

  // 3. 文件头 magic bytes 校验，防止改后缀绕过
  try {
    const header = await readFileHeader(rawFile)
    const valid = MAGIC_SIGNATURES.some((sig) =>
      sig.every((byte, i) => header[i] === byte)
    )
    if (!valid) {
      MessagePlugin.error('文件内容与扩展名不匹配，疑似伪造文件')
      return false
    }
  } catch {
    MessagePlugin.error('文件读取失败，请重试')
    return false
  }

  // 4. 重复上传去重
  const fileKey = `${file.name}_${rawFile.size}`
  if (uploadedFiles.has(fileKey)) {
    MessagePlugin.warning('该文件已上传，请勿重复提交')
    return false
  }

  return true
}

const onSuccess = (context) => {
  const res = context.response
  if (res && res.code !== 0 && res.code !== 200) {
    MessagePlugin.error(res.msg || res.message || '文件处理失败，请检查文件格式')
    return
  }
  const file = context.file
  const rawFile = file.raw || file
  uploadedFiles.add(`${file.name}_${rawFile.size}`)
  MessagePlugin.success('上传成功')
}

const onFail = (context) => {
  const res = context?.response
  MessagePlugin.error(res?.msg || res?.message || '上传失败，请稍后重试')
}

const handleClose = () => { visible.value = false }

defineExpose({ visible })
</script>
