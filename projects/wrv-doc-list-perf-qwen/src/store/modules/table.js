import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * @typedef {Object} ColumnConfig
 * @property {string} colKey   - 列唯一标识
 * @property {boolean} visible - 是否显示
 * @property {number}  order   - 排序序号（越小越靠前）
 */

/**
 * 从任意输入中提取纯列配置信息，丢弃表格行数据等无关内容。
 * 兼容两种输入格式：数组 或 { columns: [...] } 对象。
 * @param {Array|Object} raw
 * @returns {ColumnConfig[]}
 */
function extractColumnConfig(raw) {
  const list = Array.isArray(raw) ? raw : raw?.columns
  if (!Array.isArray(list)) return []

  return list.map((col, index) => ({
    colKey: String(col.colKey ?? col.key ?? col.prop ?? `col_${index}`),
    visible: col.visible !== false,
    order: typeof col.order === 'number' ? col.order : index,
  }))
}

export const useTableStore = defineStore('table', () => {
  // 用 ref 替代 reactive，避免深层 Proxy 导致内存泄漏
  // 结构: { [tableKey]: { columns: ColumnConfig[] } }
  const tableStoreColumns = ref({})

  /**
   * 保存指定表格的列配置（仅显隐 + 排序，不存表格数据）
   * @param {string} tableKey - 表格唯一标识
   * @param {Array|Object} columns - 列配置数组或包含 columns 字段的对象
   */
  function setColumnConfig(tableKey, columns) {
    if (!tableKey) return
    tableStoreColumns.value[tableKey] = {
      columns: extractColumnConfig(columns),
    }
  }

  /**
   * 获取指定表格的列配置
   * @param {string} tableKey
   * @returns {ColumnConfig[]}
   */
  function getColumnConfig(tableKey) {
    return tableStoreColumns.value[tableKey]?.columns ?? []
  }

  /**
   * 删除指定表格的配置
   * @param {string} tableKey
   */
  function removeColumnConfig(tableKey) {
    delete tableStoreColumns.value[tableKey]
  }

  /**
   * 清理旧格式数据（之前误存的表格行数据等），只保留合法列配置。
   * 建议在应用启动时调用一次。
   */
  function sanitizeAll() {
    const store = tableStoreColumns.value
    for (const key of Object.keys(store)) {
      const entry = store[key]
      if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
        // 旧格式：直接存了数组或非法数据 → 尝试提取列配置，失败则删除
        const extracted = extractColumnConfig(entry)
        if (extracted.length > 0) {
          store[key] = { columns: extracted }
        } else {
          delete store[key]
        }
      } else {
        // 已有对象格式 → 确保只保留 columns 字段
        store[key] = { columns: extractColumnConfig(entry) }
      }
    }
  }

  return {
    tableStoreColumns,
    setColumnConfig,
    getColumnConfig,
    removeColumnConfig,
    sanitizeAll,
  }
}, {
  persist: {
    key: 'table-store',
    storage: localStorage,
    // 只持久化 tableStoreColumns，排除临时状态（如果以后扩展其他 state）
    paths: ['tableStoreColumns'],
  },
})
