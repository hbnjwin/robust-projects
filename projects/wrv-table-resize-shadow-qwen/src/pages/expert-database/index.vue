<template>
  <div class="expert-database">
    <t-table ref="tableRef" :key="tableKey" :data="tableData" :columns="columns"
      :loading="loading" :max-height="tableHeight" bordered
      table-layout="auto">
    </t-table>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { debounce } from 'lodash'

const tableRef = ref(null)
const tableData = ref([])
const loading = ref(false)
const tableHeight = ref(600)
// [fix] 递增 key 强制 t-table 重新挂载，触发列宽重算与固定列阴影重绘
const tableKey = ref(0)

const columns = [
  { colKey: 'name', title: '文档名称', width: 200 },
  { colKey: 'type', title: '类型', width: 120 },
  { colKey: 'status', title: 'OCR状态', width: 120 },
  { colKey: 'createdAt', title: '上传时间', width: 180 },
  { colKey: 'operation', title: '操作', fixed: 'right', width: 150 },
]

// [fix] debounce 从 500ms 降至 100ms，减少窗口拖拽缩放时的布局跳动
// [fix] 更新 tableHeight 并递增 tableKey，同时解决列宽溢出和阴影消失问题
const handleResize = debounce(() => {
  tableHeight.value = window.innerHeight - 200
  tableKey.value++
}, 100)

onMounted(() => {
  tableHeight.value = window.innerHeight - 200
  window.addEventListener('resize', handleResize)
})
onUnmounted(() => { window.removeEventListener('resize', handleResize) })

// [fix] 数据刷新后通过 nextTick + key 变更强制 t-table 重新挂载，恢复固定列阴影
async function fetchData() {
  loading.value = true
  try {
    // ...fetch logic
  } finally {
    loading.value = false
    await nextTick()
    tableKey.value++
  }
}
</script>
