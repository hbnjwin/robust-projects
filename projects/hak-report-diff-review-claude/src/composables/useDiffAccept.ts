import { computed } from 'vue'
import type { DiffChange } from '@/types/diff'

/**
 * 接受/拒绝修改组合式函数。
 * 点击"接受修改"后立即更新状态，高亮随之消失。
 * 通过响应式状态驱动视图更新，确保UI同步。
 */
export function useDiffAccept(changes: () => DiffChange[]) {
  const acceptedCount = computed(
    () => changes().filter((c) => c.accepted).length,
  )
  const rejectedCount = computed(
    () => changes().filter((c) => c.rejected).length,
  )
  const processedCount = computed(
    () => acceptedCount.value + rejectedCount.value,
  )
  const totalCount = computed(() => changes().length)
  const allProcessed = computed(
    () => totalCount.value > 0 && processedCount.value === totalCount.value,
  )

  /** 接受修改：采用新版内容，高亮消失 */
  function acceptChange(changeId: string) {
    const change = changes().find((c) => c.id === changeId)
    if (!change) return
    change.accepted = true
    change.rejected = false
  }

  /** 拒绝修改：保留旧版内容，高亮消失 */
  function rejectChange(changeId: string) {
    const change = changes().find((c) => c.id === changeId)
    if (!change) return
    change.rejected = true
    change.accepted = false
  }

  /** 撤销对某个差异的处理 */
  function resetChange(changeId: string) {
    const change = changes().find((c) => c.id === changeId)
    if (!change) return
    change.accepted = false
    change.rejected = false
  }

  /** 全部接受 */
  function acceptAll() {
    for (const change of changes()) {
      change.accepted = true
      change.rejected = false
    }
  }

  /** 全部拒绝 */
  function rejectAll() {
    for (const change of changes()) {
      change.rejected = true
      change.accepted = false
    }
  }

  return {
    acceptedCount,
    rejectedCount,
    processedCount,
    totalCount,
    allProcessed,
    acceptChange,
    rejectChange,
    resetChange,
    acceptAll,
    rejectAll,
  }
}
