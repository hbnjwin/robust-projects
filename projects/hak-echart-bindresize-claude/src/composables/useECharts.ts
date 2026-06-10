import { ref, shallowRef, onMounted, onBeforeUnmount, onActivated, onDeactivated } from 'vue'
import type { Ref } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import type { UseEChartsOptions, UseEChartsReturn } from '@/types/chart'
import { debounce } from '@/utils/debounce'

/**
 * ECharts 组合式函数
 *
 * 解决的问题：
 * 1. resize事件监听器泄漏 —— 使用同一引用绑定/解绑，确保无残留
 * 2. keep-alive生命周期 —— activated重新绑定，deactivated解绑，避免重复叠加
 * 3. 侧边栏展开/收起 —— 使用ResizeObserver监听容器大小变化
 * 4. 浏览器窗口resize —— 监听window resize事件
 *
 * @param containerRef 图表容器DOM元素的模板引用
 * @param options 配置选项
 */
export function useECharts(
  containerRef: Ref<HTMLElement | null>,
  options: UseEChartsOptions = {}
): UseEChartsReturn {
  const { resizeDelay = 200, autoResize = true } = options

  // 使用shallowRef避免Vue对ECharts实例进行深度响应式代理（性能优化）
  const chartInstance = shallowRef<echarts.ECharts | null>(null)

  // 追踪resize事件是否已绑定，防止重复绑定
  let isBound = false

  // ResizeObserver实例（监听容器元素大小变化，处理侧边栏展开/收起场景）
  let resizeObserver: ResizeObserver | null = null

  /** 执行图表resize */
  function resizeChart(): void {
    if (chartInstance.value && !chartInstance.value.isDisposed()) {
      chartInstance.value.resize({ animation: { duration: 300 } })
    }
  }

  /** 防抖后的resize处理函数 —— 始终使用同一个引用，确保remove时能匹配 */
  const debouncedResize = debounce(resizeChart, resizeDelay)

  /** 绑定resize监听 */
  function bindResize(): void {
    if (isBound || !autoResize) return

    // 绑定window resize事件
    window.addEventListener('resize', debouncedResize)

    // 绑定ResizeObserver监听容器大小变化（处理侧边栏等布局变化）
    if (containerRef.value) {
      resizeObserver = new ResizeObserver(debouncedResize)
      resizeObserver.observe(containerRef.value)
    }

    isBound = true
  }

  /** 解绑resize监听 */
  function unbindResize(): void {
    if (!isBound) return

    window.removeEventListener('resize', debouncedResize)
    debouncedResize.cancel()

    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }

    isBound = false
  }

  /** 初始化ECharts实例 */
  function initChart(): void {
    if (!containerRef.value) return

    // 防止重复初始化：如果已有实例先销毁
    if (chartInstance.value && !chartInstance.value.isDisposed()) {
      chartInstance.value.dispose()
    }

    chartInstance.value = echarts.init(containerRef.value)

    if (options.option) {
      chartInstance.value.setOption(options.option)
    }
  }

  /** 更新图表配置 */
  function setOption(option: EChartsOption, notMerge = false): void {
    if (chartInstance.value && !chartInstance.value.isDisposed()) {
      chartInstance.value.setOption(option, notMerge)
    }
  }

  /** 销毁ECharts实例及所有相关资源 */
  function dispose(): void {
    unbindResize()
    if (chartInstance.value && !chartInstance.value.isDisposed()) {
      chartInstance.value.dispose()
      chartInstance.value = null
    }
  }

  // ── 生命周期管理 ──

  onMounted(() => {
    initChart()
    bindResize()
  })

  // keep-alive: 组件重新激活时重新绑定resize并立即调整大小
  onActivated(() => {
    // 只在从deactivated恢复时重新绑定（首次mounted已绑定，此时isBound=true会跳过）
    bindResize()
    // 立即resize一次，因为在deactivated期间容器尺寸可能已变化
    resizeChart()
  })

  // keep-alive: 组件失活时解绑resize（但保留ECharts实例供再次激活使用）
  onDeactivated(() => {
    unbindResize()
  })

  // 组件最终销毁时完全清理
  onBeforeUnmount(() => {
    dispose()
  })

  return {
    chartInstance,
    setOption,
    resize: resizeChart,
    dispose
  }
}
