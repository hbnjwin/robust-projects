import { defineStore } from 'pinia'
import { reactive } from 'vue'

export const useTableStore = defineStore('table', () => {
  const tableStoreColumns = reactive({})

  return { tableStoreColumns }
}, {
  persist: {
    key: 'table-store',
    storage: localStorage,
  }
})
