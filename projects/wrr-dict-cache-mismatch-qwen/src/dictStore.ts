import { defineStore } from 'pinia'

export interface DictData {
  label: string
  value: string | number
  colorType?: string
}

interface DictState {
  dictDataMap: Map<string, DictData[]>
  isSetDict: boolean
}

export const useDictStore = defineStore('dict', {
  state: (): DictState => ({
    dictDataMap: new Map<string, DictData[]>(),
    isSetDict: false
  }),

  getters: {
    getDictByType: (state) => {
      return (type: string): DictData[] | undefined => {
        // BUG: dictDataMap 是 Map 类型，但这里用中括号语法访问
        // Map 的 [] 访问不会调用 get()，而是访问对象属性，永远返回 undefined
        return state.dictDataMap[type]
      }
    }
  },

  actions: {
    async loadDictData(type: string) {
      const cacheKey = `dict_${type}`
      const cached = sessionStorage.getItem(cacheKey)

      if (cached) {
        const { data, timestamp } = JSON.parse(cached)
        // BUG: 缓存过期时间只有 60 秒，太短了，导致频繁重新加载
        if (Date.now() - timestamp < 60 * 1000) {
          // BUG: 从 sessionStorage 恢复时也用了 [] 语法设置
          this.dictDataMap[type] = data
          return data
        }
      }

      try {
        const res = await fetch(`/api/system/dict-data/type?type=${type}`)
        const { data } = await res.json()
        // BUG: 这里也是用 [] 语法设置 Map，应该用 .set()
        this.dictDataMap[type] = data

        sessionStorage.setItem(cacheKey, JSON.stringify({
          data,
          timestamp: Date.now()
        }))

        return data
      } catch (e) {
        console.error(`加载字典 ${type} 失败:`, e)
        return []
      }
    },

    setDictMap(dictMap: Record<string, DictData[]>) {
      Object.entries(dictMap).forEach(([key, value]) => {
        // BUG: 同样的问题，应该用 this.dictDataMap.set(key, value)
        this.dictDataMap[key] = value
      })
      this.isSetDict = true
    }
  }
})
