<template>
  <t-dialog v-model:visible="visible" header="任务详情" width="800px">
    <div class="stats-bar">
      <t-tag theme="success">通过: {{ stats.pass }}</t-tag>
      <t-tag theme="warning">警告: {{ stats.warn }}</t-tag>
      <t-tag theme="danger">失败: {{ stats.fail }}</t-tag>
    </div>
    <t-table :data="checkResults" :columns="columns">
      <template #opinion="{ row }">
        <div v-html="sanitize(row.opinion)"></div>
      </template>
      <template #status="{ row }">
        <t-tag :theme="getStatusTheme(row.status)">{{ row.status }}</t-tag>
      </template>
    </t-table>
  </t-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { getTaskDetail } from '@/api/modules/ai-report-review'
import DOMPurify from 'dompurify'

const props = defineProps({ taskId: String })
const visible = ref(false)
const checkResults = ref([])
const columns = [
  { colKey: 'name', title: '检查项' },
  { colKey: 'opinion', title: '审查意见', cell: 'opinion' },
  { colKey: 'status', title: '状态', cell: 'status' },
]

const sanitize = (html) => DOMPurify.sanitize(html ?? '')

const stats = computed(() => {
  const counts = { pass: 0, warn: 0, fail: 0 }
  checkResults.value.forEach(item => {
    if (item.status in counts) {
      counts[item.status]++
    }
  })
  return counts
})

const getStatusTheme = (s) => ({ pass: 'success', warn: 'warning', fail: 'danger' }[s])

watch(() => props.taskId, async (id) => {
  if (!id) return
  const res = await getTaskDetail(id)
  checkResults.value = (res.items || []).map(item => {
    const cleaned = {}
    for (const key in item) {
      cleaned[key] = item[key] ?? ''
    }
    return cleaned
  })
})
</script>
