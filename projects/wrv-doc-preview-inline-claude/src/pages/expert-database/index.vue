<template>
  <div class="expert-database">
    <t-table :data="tableData" :columns="columns">
      <template #name="{ row }">
        <a href="javascript:void(0)" @click="handleDownload(row)">{{ row.name }}</a>
      </template>
    </t-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { EXPERT_DATABASE } from '@/api'

const tableData = ref([])
const columns = [
  { colKey: 'name', title: '文档名称', cell: 'name' },
  { colKey: 'type', title: '类型' },
  { colKey: 'status', title: '状态' },
]

const handleDownload = (row) => {
  window.open(`/api/documents/download/${row.id}`)
}

onMounted(async () => {
  const res = await EXPERT_DATABASE.getDocumentList({})
  tableData.value = res.list
})
</script>
