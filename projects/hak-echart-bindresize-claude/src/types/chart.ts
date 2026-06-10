import type { ECharts, EChartsOption } from 'echarts'
import type { Ref } from 'vue'

export interface UseEChartsOptions {
  /** 初始ECharts配置 */
  option?: EChartsOption
  /** resize防抖延迟（毫秒），默认200 */
  resizeDelay?: number
  /** 是否自动绑定resize，默认true */
  autoResize?: boolean
}

export interface UseEChartsReturn {
  /** ECharts实例引用 */
  chartInstance: Ref<ECharts | null>
  /** 更新图表配置 */
  setOption: (option: EChartsOption, notMerge?: boolean) => void
  /** 手动触发resize */
  resize: () => void
  /** 手动销毁实例 */
  dispose: () => void
}
