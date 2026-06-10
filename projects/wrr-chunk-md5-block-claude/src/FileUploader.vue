<template>
  <div class="file-uploader">
    <el-upload
      :auto-upload="false"
      :on-change="handleFileChange"
      :show-file-list="false"
    >
      <el-button type="primary">选择课件文件</el-button>
    </el-upload>
    <div v-if="uploading" class="progress">
      <el-progress :percentage="uploadProgress" />
      <p>{{ statusText }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'

const CHUNK_SIZE = 5 * 1024 * 1024 // 5MB per chunk

const uploading = ref(false)
const uploadProgress = ref(0)
const statusText = ref('')

const handleFileChange = async (uploadFile: any) => {
  const file: File = uploadFile.raw
  if (!file) return

  uploading.value = true
  statusText.value = '计算文件哈希...'

  // 使用 Web Worker 分片计算 MD5，不阻塞主线程
  const fileHash = await calculateHash(file)
  statusText.value = '检查秒传...'

  // 检查是否可以秒传
  const { data: checkResult } = await axios.post('/api/infra/file/check', {
    hash: fileHash,
    fileName: file.name
  })

  if (checkResult.data.uploaded) {
    statusText.value = '秒传成功！'
    uploadProgress.value = 100
    return
  }

  // 分片上传
  await uploadChunks(file, fileHash, checkResult.data.uploadedChunks || [])
}

const calculateHash = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL('./hashWorker.ts', import.meta.url), { type: 'module' })
    worker.onmessage = (e) => {
      const { type, hash, progress, error } = e.data
      if (type === 'progress') {
        statusText.value = `计算文件哈希... ${progress}%`
      } else if (type === 'done') {
        worker.terminate()
        resolve(hash)
      } else if (type === 'error') {
        worker.terminate()
        reject(new Error(error))
      }
    }
    worker.onerror = (err) => {
      worker.terminate()
      reject(err)
    }
    worker.postMessage({ file })
  })
}

const uploadChunks = async (file: File, hash: string, uploadedChunks: number[]) => {
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE)
  let uploaded = uploadedChunks.length

  for (let i = 0; i < totalChunks; i++) {
    if (uploadedChunks.includes(i)) continue

    const chunk = file.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE)
    const formData = new FormData()
    formData.append('file', chunk)
    formData.append('hash', hash)
    formData.append('chunkIndex', String(i))
    formData.append('totalChunks', String(totalChunks))

    await axios.post('/api/infra/file/upload-chunk', formData)
    uploaded++
    uploadProgress.value = Math.round((uploaded / totalChunks) * 100)
  }

  await axios.post('/api/infra/file/merge', { hash, fileName: file.name, totalChunks })
  statusText.value = '上传完成！'
}
</script>
