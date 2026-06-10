import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'

/**
 * Bug 1 核心修复：useRouteQuery composable
 *
 * 设计原则：筛选状态完全由 route.query 派生（computed），绝不存在组件本地ref中。
 * 更新筛选时使用 router.push()（非 replace），确保浏览器历史栈中保留带query的记录。
 *
 * 这解决了"浏览器返回时query参数丢失"的问题：
 * - 组件卸载再挂载时，从route.query读取当前URL参数，自动恢复筛选状态
 * - router.push() 创建新历史记录，浏览器返回时恢复到之前的URL（含query参数）
 */
export function useRouteQuery<T extends Record<string, string>>(defaults: T) {
  const router = useRouter()
  const route = useRoute()

  // 读取：将route.query合并到默认值上，route.query优先
  const filters = computed<T>(() => {
    const result = { ...defaults } as Record<string, string>
    for (const key of Object.keys(defaults)) {
      const val = route.query[key]
      if (val !== undefined && val !== null) {
        result[key] = String(val)
      }
    }
    return result as T
  })

  // 写入：通过 router.push 更新URL query参数
  // 关键：必须用 push 而非 replace，push 创建新历史条目，replace 会覆盖当前条目
  function updateFilters(patch: Partial<T>) {
    router.push({
      path: route.path,
      query: {
        ...route.query,
        ...patch
      }
    })
  }

  // 重置所有筛选为默认值
  function resetFilters() {
    router.push({
      path: route.path,
      query: {}
    })
  }

  return { filters, updateFilters, resetFilters }
}
