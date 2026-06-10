import { defineAsyncComponent, type Component } from 'vue'
import AppLoading from '@/components/AppLoading.vue'
import AppError from '@/components/AppError.vue'

/**
 * Bug 3 核心修复：lazyView — defineAsyncComponent 包装器
 *
 * 解决"动态路由组件首次访问时闪白"的问题：
 * - delay: 0 表示立即显示 loadingComponent（骨架屏），不等待默认的200ms
 * - 在chunk下载期间，用户看到的是骨架屏而非空白页面
 * - timeout: 15000 超时后显示错误组件
 */
export function lazyView(loader: () => Promise<{ default: Component }>) {
  return defineAsyncComponent({
    loader,
    loadingComponent: AppLoading,
    errorComponent: AppError,
    delay: 0,
    timeout: 15000
  })
}
