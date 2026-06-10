<template>
  <div class="ai-report-review">
    <t-table :data="taskList" :columns="columns" :loading="loading">
      <template #status="{ row }">
        <t-tag :theme="statusThemeMap[row.status]">{{ row.status }}</t-tag>
      </template>
      <template #workflow="{ row }">
        <div v-for="step in row.workflowHistory" :key="step.id">
          <span>{{ step.timestamp }}</span>
          <t-tag :theme="statusThemeMap[step.status]">{{ step.stepName }}</t-tag>
          <t-button size="small" @click="showStepDetail(step)">查看详情</t-button>
        </div>
      </template>
    </t-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getTaskList } from '@/api/modules/ai-report-review'

const taskList = ref([])
const loading = ref(false)
const statusThemeMap = { queued: 'default', started: 'primary', completed: 'warning', failed: 'danger', warning: 'success' }
const columns = [
  { colKey: 'name', title: '任务名称' },
  { colKey: 'status', title: '状态', cell: 'status' },
  { colKey: 'workflow', title: '工作流', cell: 'workflow' },
]

const showStepDetail = (step) => { console.log(step) }
onMounted(async () => {
  loading.value = true
  const res = await getTaskList()
  taskList.value = res.list
  loading.value = false
})
</script>
