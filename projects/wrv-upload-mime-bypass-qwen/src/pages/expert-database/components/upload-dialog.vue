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

// 扩展名白名单及对应合法 MIME 类型
const ALLOWED_EXTENSIONS = ['pdf', 'docx', 'xlsx', 'doc']
const EXT_MIME_MAP = {
  pdf: 'application/pdf',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  doc: 'application/msword',
}
// 同一会话内已上传文件的 SHA-256 哈希集合，用于去重
const uploadedHashes = ref(new Set())
// 暂存待确认文件哈希：beforeUpload 写入，onSuccess/onFail 消费
const fileHashMap = new Map()

/**
 * 使用 Web Crypto API 计算文件的 SHA-256 哈希值
 */
const computeHash = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = async () => {
      try {
        const hashBuffer = await crypto.subtle.digest('SHA-256', reader.result)
        const hashArray = Array.from(new Uint8Array(hashBuffer))
        resolve(hashArray.map((b) => b.toString(16).padStart(2, '0')).join(''))
      } catch (err) {
        reject(err)
      }
    }
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsArrayBuffer(file)
  })

const beforeUpload = async (file) => {
  // 1. 校验文件扩展名
  const ext = file.name.split('.').pop().toLowerCase()
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    MessagePlugin.error('不支持的文件格式')
    return false
  }

  // 2. 校验 MIME 类型，防止伪造扩展名（如 .exe 改名为 .docx）
  const expectedMime = EXT_MIME_MAP[ext]
  if (expectedMime && file.type && file.type !== expectedMime) {
    MessagePlugin.error('文件类型与扩展名不匹配，请确认文件真实格式')
    return false
  }

  // 3. 计算文件哈希，防止重复上传
  let fileHash
  try {
    fileHash = await computeHash(file)
  } catch {
    MessagePlugin.error('文件读取失败，请重试')
    return false
  }
  if (uploadedHashes.value.has(fileHash)) {
    MessagePlugin.warning('该文件已上传，请勿重复上传')
    return false
  }

  // 将哈希暂存到 Map，供 onSuccess/onFail 回调消费
  fileHashMap.set(file, fileHash)
  return true
}

const onSuccess = (ctx) => {
  const { file, response } = ctx || {}
  // 从 Map 中取出哈希（优先 raw File，回退到直接 File 引用）
  const hash = fileHashMap.get(file?.raw || file)
  fileHashMap.delete(file?.raw || file)

  // 解析服务端业务响应：HTTP 200 但业务层返回错误码时，需展示具体错误信息
  const data = response && typeof response === 'object' ? response : {}
  if (data.code && data.code !== 0 && data.code !== 200) {
    if (hash) uploadedHashes.value.delete(hash)
    MessagePlugin.error(data.message || data.msg || '文件处理失败，请确认文件格式是否正确')
    return
  }

  if (hash) uploadedHashes.value.add(hash)
  MessagePlugin.success('上传成功')
}

const onFail = (ctx) => {
  const { file } = ctx || {}
  const hash = fileHashMap.get(file?.raw || file)
  fileHashMap.delete(file?.raw || file)
  if (hash) uploadedHashes.value.delete(hash)
  MessagePlugin.error('上传失败，请检查网络连接或文件格式后重试')
}

const handleClose = () => { visible.value = false }

defineExpose({ visible })
</script>
