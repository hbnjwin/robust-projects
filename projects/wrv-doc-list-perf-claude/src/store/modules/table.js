import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useTableStore = defineStore('table', () => {
  const tableStoreColumns = ref({})

  function setColumns(tableKey, columns) {
    tableStoreColumns.value[tableKey] = columns.map((col, index) => ({
      key: col.key ?? col.prop ?? col.field,
      visible: col.visible !== false,
      order: col.order ?? index,
    }))
  }

  function getColumns(tableKey) {
    return tableStoreColumns.value[tableKey] ?? []
  }

  function removeColumns(tableKey) {
    delete tableStoreColumns.value[tableKey]
  }

  return { tableStoreColumns, setColumns, getColumns, removeColumns }
}, {
  persist: {
    key: 'table-store',
    storage: localStorage,
    pick: ['tableStoreColumns'],
  }
})
