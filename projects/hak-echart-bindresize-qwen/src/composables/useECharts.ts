import { ref, onMounted, onUnmounted, onActivated, onDeactivated, type Ref, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption, ECharts } from 'echarts'
import type { EChartsConfig, UseEChartsReturn } from '@/types/chart'

/**
 * ECharts composable - 修复 resize 事件泄漏和 keep-alive 生命周期管理
 *
 * 核心修复点：
 * 1. 使用 ResizeObserver 监听容器尺寸变化（包括侧边栏展开/收起）
 * 2. 在 onDeactivated 时移除 resize 监听，避免 keep-alive 缓存组件重复绑定
 * 3. 在 onActivated 时重新绑定 resize 监听并触发 resize
 * 4. 在 onUnmounted 时完全销毁 ECharts 实例和所有监听器
 * 5. 使用防抖避免频繁 resize 导致性能问题
 */
export function useECharts(config: EChartsConfig): UseEChartsReturn {
  const chartRef = ref<HTMLElement | null>(null) as Ref<HTMLElement | null>
  let chartInstance: ECharts | null = null
  let resizeObserver: ResizeObserver | null = null
  let resizeTimer: ReturnType<typeof setTimeout> | null = null
  let isActivated = true // 标记组件是否处于激活状态

  const { autoResize = true, resizeDebounce = 150 } = config

  /**
   * 防抖 resize 处理
   */
  const debouncedResize = () => {
    if (!isActivated) return // keep-alive 非激活状态不执行 resize

    if (resizeTimer) {
      clearTimeout(resizeTimer)
    }

    resizeTimer = setTimeout(() => {
      if (chartInstance && !chartInstance.isDisposed() && isActivated) {
        chartInstance.resize()
      }
    }, resizeDebounce)
  }

  /**
   * 立即 resize（用于 activated 时）
   */
  const resize = () => {
    if (chartInstance && !chartInstance.isDisposed()) {
      nextTick(() => {
        chartInstance?.resize()
      })
    }
  }

  /**
   * 绑定 resize 监听
   */
  const bindResize = () => {
    if (!autoResize || !chartRef.value) return

    // 使用 ResizeObserver 监听容器尺寸变化
    // 这能捕获：窗口 resize、侧边栏展开/收起、布局变化等
    resizeObserver = new ResizeObserver(() => {
      debouncedResize()
    })
    resizeObserver.observe(chartRef.value)
  }

  /**
   * 解绑 resize 监听
   */
  const unbindResize = () => {
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }

    if (resizeTimer) {
      clearTimeout(resizeTimer)
      resizeTimer = null
    }
  }

  /**
   * 初始化图表
   */
  const initChart = () => {
    if (!chartRef.value) return

    // 如果实例已存在且未被销毁，直接返回
    if (chartInstance && !chartInstance.isDisposed()) {
      return
    }

    chartInstance = echarts.init(chartRef.value)
    chartInstance.setOption(config.option)

    // 绑定 resize 监听
    bindResize()
  }

  /**
   * 更新图表配置
   */
  const updateOption = (option: EChartsOption, notMerge = false) => {
    if (chartInstance && !chartInstance.isDisposed()) {
      chartInstance.setOption(option, notMerge)
    }
  }

  /**
   * 销毁图表实例
   */
  const dispose = () => {
    unbindResize()

    if (chartInstance && !chartInstance.isDisposed()) {
      chartInstance.dispose()
      chartInstance = null
    }
  }

  // 组件挂载时初始化
  onMounted(() => {
    initChart()
  })

  // keep-alive 激活时：重新绑定 resize 并触发 resize
  onActivated(() => {
    isActivated = true

    if (!chartInstance || chartInstance.isDisposed()) {
      initChart()
    } else {
      // 重新绑定 resize 监听
      bindResize()
      // 立即触发一次 resize，确保图表尺寸正确
      resize()
    }
  })

  // keep-alive 停用时：解绑 resize 监听（关键修复点）
  onDeactivated(() => {
    isActivated = false
    unbindResize()
  })

  // 组件卸载时完全清理
  onUnmounted(() => {
    isActivated = false
    dispose()
  })

  return {
    get chartInstance() {
      return chartInstance
    },
    chartRef,
    resize,
    updateOption,
    dispose
  }
}
