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
import SparkMD5 from 'spark-md5'
import axios from 'axios'

const CHUNK_SIZE = 5 * 1024 * 1024 // 5MB per chunk

const uploading = ref(false)
const uploadProgress = ref(0)
const statusText = ref('')

const handleFileChange = async (uploadFile: any) => {
  const file: File = uploadFile.raw
  if (!file) return

  uploading.value = true
  uploadProgress.value = 0

  const fileHash = await calculateHash(file, (percent) => {
    statusText.value = `计算文件哈希... ${percent}%`
    uploadProgress.value = Math.round(percent * 0.3) // 哈希阶段占 30%
  })
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

  // 分片上传（进度条从 30% 到 100%）
  await uploadChunks(file, fileHash, checkResult.data.uploadedChunks || [])
}

const HASH_CHUNK_SIZE = 2 * 1024 * 1024 // 2MB per hash chunk

const calculateHash = (file: File, onProgress?: (percent: number) => void): Promise<string> => {
  return new Promise((resolve) => {
    const spark = new SparkMD5.ArrayBuffer()
    const totalChunks = Math.ceil(file.size / HASH_CHUNK_SIZE)
    let currentChunk = 0

    const processNextChunk = () => {
      const start = currentChunk * HASH_CHUNK_SIZE
      const end = Math.min(start + HASH_CHUNK_SIZE, file.size)
      const blob = file.slice(start, end)

      const reader = new FileReader()
      reader.onload = (e) => {
        spark.append(e.target!.result as ArrayBuffer)
        currentChunk++
        onProgress?.(Math.round((currentChunk / totalChunks) * 100))

        if (currentChunk < totalChunks) {
          // 让出主线程，避免阻塞 UI 渲染
          setTimeout(processNextChunk, 0)
        } else {
          resolve(spark.end())
        }
      }
      reader.readAsArrayBuffer(blob)
    }

    processNextChunk()
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
    statusText.value = `上传中... ${Math.round((uploaded / totalChunks) * 100)}%`
    uploadProgress.value = 30 + Math.round((uploaded / totalChunks) * 70)
  }

  await axios.post('/api/infra/file/merge', { hash, fileName: file.name, totalChunks })
  statusText.value = '上传完成！'
}
</script>
