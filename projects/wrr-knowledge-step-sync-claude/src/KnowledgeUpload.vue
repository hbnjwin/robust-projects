<template>
  <div class="knowledge-upload">
    <el-steps :active="activeStep" finish-status="success">
      <el-step title="上传文件" />
      <el-step title="自动分片" />
      <el-step title="向量处理" />
    </el-steps>

    <div v-if="activeStep === 0" class="upload-area">
      <el-upload :action="uploadUrl" :on-success="handleUploadSuccess" :on-error="handleUploadError">
        <el-button type="primary">选择文档</el-button>
      </el-upload>
    </div>
    <div v-else class="progress-area">
      <el-progress :percentage="progress" :status="progressStatus" />
      <p>{{ statusText }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import axios from 'axios'

const props = defineProps<{ knowledgeId: string }>()

const activeStep = ref(0)
const progress = ref(0)
const statusText = ref('')
const uploadUrl = `/api/ai/knowledge/doc/upload?knowledgeId=${props.knowledgeId}`

const progressStatus = computed(() => {
  if (progress.value === 100) return 'success'
  return ''
})

const handleUploadSuccess = async (response: any) => {
  const docId = response.data.id
  statusText.value = '文件上传成功，开始分片...'
  // BUG: 上传成功后直接调用分片接口，但没有等分片完成就设置 activeStep
  // activeStep 应该在分片 API 返回成功后才更新

  startChunking(docId)
}

const handleUploadError = () => {
  statusText.value = '上传失败，请重试'
}

const startChunking = async (docId: string) => {
  try {
    // BUG: 这里调用了分片接口，但 activeStep 还没更新
    // API 是异步的，但 activeStep 在调用前就应该设为 1 吗？
    const res = await axios.post(`/api/ai/knowledge/doc/chunk`, { docId })
    // BUG: API 返回成功后才设置 activeStep = 1
    // 但实际上后端可能已经完成了分片并推进到向量处理阶段
    // 如果后端处理很快，这里 set activeStep=1 时后端已经在 step 2 了
    activeStep.value = 1
    progress.value = 50
    statusText.value = '分片完成，开始向量处理...'

    // BUG: 直接同步调用下一步，没有用定时轮询检查后端实际状态
    startVectorProcessing(docId)
  } catch (e) {
    statusText.value = '分片失败'
  }
}

const startVectorProcessing = async (docId: string) => {
  try {
    await axios.post(`/api/ai/knowledge/doc/vectorize`, { docId })
    // BUG: 这个接口可能只是触发异步任务，返回成功不代表向量处理完成
    // 应该轮询状态接口检查实际进度
    activeStep.value = 2
    progress.value = 100
    statusText.value = '处理完成！'
  } catch (e) {
    statusText.value = '向量处理失败'
  }
}
</script>
