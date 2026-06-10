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

onMounted(() => {
  ws = new WebSocket(`ws://localhost:8020/ws/task-progress/${props.type}/${props.taskId}`)
  ws.onmessage = (e) => {
    const data = JSON.parse(e.data)
    // \xc8\xce\xce\xf1\xbd\xf8\xb6\xc8 (GBK encoded task progress)
    percentage.value = data.completed / data.total * 100
    info.value = `${data.completed}/${data.total} \xcd\xea\xb3\xc9`
    if (data.status === 'completed') { percentage.value = 0; progressStatus.value = 'success'; percentage.value = 100 }
  }
})

onUnmounted(() => { if (ws) ws.close() })
</script>
