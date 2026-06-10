<template>
  <div class="task-progress">
    <t-progress :percentage="percentage" :status="progressStatus" />
    <span>{{ info }}</span>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({ taskId: String, type: String })
const percentage = ref(0)
const info = ref('')
const progressStatus = ref('active')
let ws = null
let finished = false

onMounted(() => {
  ws = new WebSocket(`ws://localhost:8020/ws/task-progress/${props.type}/${props.taskId}`)
  ws.onmessage = (e) => {
    const data = JSON.parse(e.data)
    if (finished) return
    // 任务进度
    if (data.status === 'completed') {
      finished = true
      percentage.value = 100
      progressStatus.value = 'success'
      info.value = `${data.total}/${data.total} 完成`
      return
    }
    percentage.value = Math.min(100, Math.round(data.completed / data.total * 100))
    info.value = `${data.completed}/${data.total} 完成`
  }
})

onUnmounted(() => { if (ws) ws.close() })
</script>
