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
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import Sortable from 'sortablejs'
import { useTableStore } from '@/store'

const props = defineProps({ storageKey: String, defaultColumns: Array })
const emit = defineEmits(['change'])
const tableStore = useTableStore()
const drawerVisible = ref(false)
const columnConfig = ref([])
const sortableRef = ref(null)
let sortableInstance = null

/**
 * 将缓存配置与后端最新列定义做 diff 同步：
 * 1. 后端新增的列 → 追加到末尾，默认 visible: true
 * 2. 后端已删除的列 → 从缓存中移除
 * 3. 两端都有的列 → 保留缓存中的 visible 状态和排列顺序
 */
const syncColumns = (cached, defaults) => {
  if (!cached || !cached.length) {
    return defaults.map(c => ({ ...c, visible: true }))
  }

  const defaultKeys = new Set(defaults.map(c => c.colKey))

  // 保留缓存中仍有效的列（维持用户排序和 visible 状态）
  const merged = cached
    .filter(c => defaultKeys.has(c.colKey))
    .map(c => {
      const def = defaults.find(d => d.colKey === c.colKey)
      return { ...def, visible: c.visible }
    })

  // 后端新增的列追加到末尾
  const mergedKeys = new Set(merged.map(c => c.colKey))
  for (const def of defaults) {
    if (!mergedKeys.has(def.colKey)) {
      merged.push({ ...def, visible: true })
    }
  }

  return merged
}

const initColumns = () => {
  const cached = tableStore.tableStoreColumns[props.storageKey]
  columnConfig.value = syncColumns(cached, props.defaultColumns)
}

const destroySortable = () => {
  if (sortableInstance) {
    sortableInstance.destroy()
    sortableInstance = null
  }
}

const initSortable = () => {
  destroySortable()
  if (sortableRef.value) {
    sortableInstance = Sortable.create(sortableRef.value, {
      onEnd: ({ oldIndex, newIndex }) => {
        if (oldIndex === newIndex) return
        const list = [...columnConfig.value]
        const [moved] = list.splice(oldIndex, 1)
        list.splice(newIndex, 0, moved)
        columnConfig.value = list
      },
    })
  }
}

onMounted(() => {
  initColumns()
  initSortable()
})

// 当后端列定义变化时（如切换页面），重新同步
watch(() => props.defaultColumns, () => {
  initColumns()
  initSortable()
}, { deep: true })

onBeforeUnmount(() => {
  destroySortable()
})

const handleSave = () => {
  tableStore.tableStoreColumns[props.storageKey] = columnConfig.value
  emit('change', columnConfig.value.filter(c => c.visible))
  drawerVisible.value = false
}
const handleReset = () => {
  columnConfig.value = props.defaultColumns.map(c => ({ ...c, visible: true }))
  // 重置后需要重建 Sortable，因为 DOM 会被 v-for 重渲染
  initSortable()
}
</script>
