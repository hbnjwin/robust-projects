<template>
  <div class="custom-header">
    <t-button variant="text" @click="drawerVisible = true">自定义列</t-button>
    <t-drawer v-model:visible="drawerVisible" header="自定义列配置">
      <div ref="sortableRef" class="column-list">
        <div v-for="col in columnConfig" :key="col.colKey" class="column-item">
          <t-checkbox v-model="col.visible">{{ col.title }}</t-checkbox>
        </div>
      </div>
      <t-button @click="handleSave">保存</t-button>
      <t-button variant="text" @click="handleReset">恢复默认</t-button>
    </t-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import Sortable from 'sortablejs'
import { useTableStore } from '@/store'

const props = defineProps({ storageKey: String, defaultColumns: Array })
const emit = defineEmits(['change'])
const tableStore = useTableStore()
const drawerVisible = ref(false)
const columnConfig = ref([])
const sortableRef = ref(null)

const mergeColumns = (cached, defaults) => {
  const defaultKeySet = new Set(defaults.map(c => c.colKey))
  const cachedKeySet = new Set(cached.map(c => c.colKey))
  const defaultMap = Object.fromEntries(defaults.map(c => [c.colKey, c]))

  // keep cached order, remove deleted columns, update title from defaults
  const merged = cached
    .filter(c => defaultKeySet.has(c.colKey))
    .map(c => ({ ...c, title: defaultMap[c.colKey].title }))

  // append new columns to the end
  defaults.forEach(c => {
    if (!cachedKeySet.has(c.colKey)) {
      merged.push({ ...c, visible: true })
    }
  })

  return merged
}

onMounted(() => {
  const cached = tableStore.tableStoreColumns[props.storageKey]
  if (cached) {
    columnConfig.value = mergeColumns(cached, props.defaultColumns)
  } else {
    columnConfig.value = props.defaultColumns.map(c => ({ ...c, visible: true }))
  }
  if (sortableRef.value) {
    Sortable.create(sortableRef.value, { onEnd: () => {} })
  }
})

const handleSave = () => {
  tableStore.tableStoreColumns[props.storageKey] = columnConfig.value
  emit('change', columnConfig.value.filter(c => c.visible))
  drawerVisible.value = false
}
const handleReset = () => {
  columnConfig.value = props.defaultColumns.map(c => ({ ...c, visible: true }))
}
</script>
