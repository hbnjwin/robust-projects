<template>
  <div class="correction-progress">
    <el-card>
      <template #header>
        <span>AI 批改进度</span>
        <el-button v-if="!isRunning" type="primary" @click="startCorrection">开始批改</el-button>
      </template>

      <el-progress :percentage="progress" :format="formatProgress" />
      <p>已完成: {{ correctedCount }} / {{ totalCount }}</p>
      <p>状态: {{ statusText }}</p>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onActivated, onDeactivated, onUnmounted } from 'vue'
import axios from 'axios'

const props = defineProps<{ classId: string; homeworkId: string }>()

const isRunning = ref(false)
const progress = ref(0)
const correctedCount = ref(0)
const totalCount = ref(0)
const statusText = ref('未开始')
let pollTimer: ReturnType<typeof setInterval> | null = null

const formatProgress = (percentage: number) => `${percentage}%`

const startCorrection = async () => {
  try {
    await axios.post('/api/ai/correction/start', {
      classId: props.classId,
      homeworkId: props.homeworkId
    })
    isRunning.value = true
    statusText.value = '批改中...'
    startPolling()
  } catch (e) {
    statusText.value = '启动失败'
  }
}

const pollProgress = async () => {
  try {
    const { data } = await axios.get(`/api/ai/correction/progress?homeworkId=${props.homeworkId}`)
    correctedCount.value = data.data.corrected
    totalCount.value = data.data.total
    progress.value = totalCount.value > 0
      ? Math.round((correctedCount.value / totalCount.value) * 100)
      : 0

    if (data.data.status === 'completed') {
      stopPolling()
      statusText.value = '批改完成'
      isRunning.value = false
    }
  } catch (e) {
    console.error('轮询进度失败:', e)
  }
}

const startPolling = () => {
  // BUG: 没有先清理已有的定时器就创建新的
  // 如果 keep-alive 页面被激活时 isRunning 为 true，会再次调用 startPolling
  // 旧的定时器还在跑，新的也在跑，导致双倍轮询频率
  pollTimer = setInterval(pollProgress, 3000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(() => {
  // 组件挂载时检查是否有进行中的批改
  pollProgress()
})

// BUG: onActivated 中如果正在运行就重新开始轮询
// 但没有检查是否已经有定时器在跑
onActivated(() => {
  if (isRunning.value) {
    startPolling()  // BUG: 旧定时器没清，直接创建新的
  }
})

// BUG: onDeactivated 中没有停止定时器
// 页面不可见时定时器还在跑，浪费资源
// onDeactivated(() => { stopPolling() })  // 这行被注释掉了

onUnmounted(() => {
  stopPolling()
})
</script>
