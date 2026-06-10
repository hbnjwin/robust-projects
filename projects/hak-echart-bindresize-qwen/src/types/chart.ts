import type { EChartsOption, ECharts } from 'echarts'
import type { Ref } from 'vue'

/**
 * ECharts 实例配置
 */
export interface EChartsConfig {
  /** ECharts 配置项 */
  option: EChartsOption
  /** 是否启用自动 resize，默认 true */
  autoResize?: boolean
  /** resize 防抖延迟（毫秒），默认 150 */
  resizeDebounce?: number
}

/**
 * useECharts composable 返回值
 */
export interface UseEChartsReturn {
  /** ECharts 实例引用 */
  chartInstance: ECharts | null
  /** 图表 DOM 容器引用 */
  chartRef: Ref<HTMLElement | null>
  /** 手动触发 resize */
  resize: () => void
  /** 更新图表配置 */
  updateOption: (option: EChartsOption, notMerge?: boolean) => void
  /** 销毁图表实例 */
  dispose: () => void
}
