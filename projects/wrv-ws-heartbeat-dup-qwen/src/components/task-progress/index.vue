<template>
  <div class="task-progress">
    <t-progress :percentage="percentage" :status="status" />
    <span class="progress-text">{{ progressText }}</span>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { WebSocketManager } from '@/utils/websocket-manager'

const props = defineProps({ taskId: String, type: String })
const percentage = ref(0)
const progressText = ref('')
const status = ref('active')

let wsManager = null
let progressHandler = null

onMounted(() => {
  wsManager = new WebSocketManager(`ws://localhost:8020/ws/task-progress`)
  wsManager.connect()
  progressHandler = (data) => {
    if (data.taskId === props.taskId) {
      percentage.value = data.current / data.total * 100
      progressText.value = `${data.current}/${data.total}`
    }
  }
  wsManager.subscribe('progress', progressHandler)
})

onUnmounted(() => {
  if (wsManager) {
    if (progressHandler) {
      wsManager.unsubscribe('progress', progressHandler)
    }
    wsManager.close()
  }
})
</script>
