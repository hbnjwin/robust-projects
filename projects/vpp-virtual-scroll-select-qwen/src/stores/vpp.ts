import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useVppStore = defineStore('vpp', () => {
  const resources = ref<any[]>([])
  const loading = ref(false)

  return { resources, loading }
})
