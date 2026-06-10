<template>
  <t-dialog v-model:visible="visible" header="任务详情" width="800px">
    <div class="stats-bar">
      <t-tag theme="success">通过: {{ stats.pass }}</t-tag>
      <t-tag theme="warning">警告: {{ stats.warn }}</t-tag>
      <t-tag theme="danger">失败: {{ stats.fail }}</t-tag>
    </div>
    <t-table :data="checkResults" :columns="columns">
      <template #opinion="{ row }">
        <div v-html="row.opinion"></div>
      </template>
      <template #status="{ row }">
        <t-tag :theme="getStatusTheme(row.status)">{{ row.status }}</t-tag>
      </template>
    </t-table>
  </t-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { getTaskDetail } from '@/api/modules/ai-report-review'

const props = defineProps({ taskId: String })
const visible = ref(false)
const stats = ref({ pass: 0, warn: 0, fail: 0 })
const checkResults = ref([])
const columns = [
  { colKey: 'name', title: '检查项' },
  { colKey: 'opinion', title: '审查意见', cell: 'opinion' },
  { colKey: 'status', title: '状态', cell: 'status' },
]

const getStatusTheme = (s) => ({ pass: 'success', warn: 'warning', fail: 'danger' }[s])

watch(() => props.taskId, async (id) => {
  if (!id) return
  const res = await getTaskDetail(id)
  stats.value = res.stats
  checkResults.value = res.items
})
</script>
