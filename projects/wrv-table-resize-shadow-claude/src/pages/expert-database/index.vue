<template>
  <div class="expert-database">
    <t-table ref="tableRef" :data="tableData" :columns="columns"
      :loading="loading" :max-height="tableHeight" bordered>
    </t-table>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { debounce } from 'lodash'

const tableRef = ref(null)
const tableData = ref([])
const loading = ref(false)
const tableHeight = ref(600)
const columns = [
  { colKey: 'name', title: '文档名称', width: 200 },
  { colKey: 'type', title: '类型', width: 120 },
  { colKey: 'status', title: 'OCR状态', width: 120 },
  { colKey: 'createdAt', title: '上传时间', width: 180 },
  { colKey: 'operation', title: '操作', fixed: 'right', width: 150 },
]

const handleResize = debounce(() => {
  tableHeight.value = window.innerHeight - 200
}, 500)

onMounted(() => { window.addEventListener('resize', handleResize) })
onUnmounted(() => { window.removeEventListener('resize', handleResize) })
</script>
