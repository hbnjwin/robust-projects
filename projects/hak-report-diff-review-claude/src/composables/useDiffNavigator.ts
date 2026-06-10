import { ref, computed, nextTick } from 'vue'
import type { DiffChange } from '@/types/diff'

/** 固定header的高度(px)，滚动定位时需要减去这个偏移 */
const HEADER_OFFSET = 64

/**
 * 差异导航组合式函数。
 * 提供上一个/下一个差异跳转，滚动时考虑固定header偏移量，
 * 确保差异项不会被遮挡。
 */
export function useDiffNavigator(changes: () => DiffChange[]) {
  const currentIndex = ref(-1)

  /** 未处理的差异项（未接受且未拒绝） */
  const pendingChanges = computed(() =>
    changes().filter((c) => !c.accepted && !c.rejected),
  )

  const totalChanges = computed(() => changes().length)
  const pendingCount = computed(() => pendingChanges.value.length)

  const currentChangeId = computed(() => {
    const all = changes()
    if (currentIndex.value < 0 || currentIndex.value >= all.length) return null
    return all[currentIndex.value].id
  })

  /** 滚动到指定差异项，减去header偏移量 */
  async function scrollToChange(changeId: string) {
    await nextTick()
    const el = document.querySelector(`[data-change-id="${changeId}"]`)
    if (!el) return

    const rect = el.getBoundingClientRect()
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop
    const targetY = rect.top + scrollTop - HEADER_OFFSET - 20 // 额外20px留白

    window.scrollTo({
      top: Math.max(0, targetY),
      behavior: 'smooth',
    })

    // 添加视觉聚焦效果
    el.classList.add('diff-focus')
    setTimeout(() => el.classList.remove('diff-focus'), 1500)
  }

  /** 跳转到下一个差异 */
  function goToNext() {
    const all = changes()
    if (all.length === 0) return
    currentIndex.value = (currentIndex.value + 1) % all.length
    scrollToChange(all[currentIndex.value].id)
  }

  /** 跳转到上一个差异 */
  function goToPrev() {
    const all = changes()
    if (all.length === 0) return
    currentIndex.value =
      currentIndex.value <= 0 ? all.length - 1 : currentIndex.value - 1
    scrollToChange(all[currentIndex.value].id)
  }

  /** 跳转到指定差异 */
  function goToChange(changeId: string) {
    const idx = changes().findIndex((c) => c.id === changeId)
    if (idx >= 0) {
      currentIndex.value = idx
      scrollToChange(changeId)
    }
  }

  return {
    currentIndex,
    currentChangeId,
    totalChanges,
    pendingCount,
    goToNext,
    goToPrev,
    goToChange,
    scrollToChange,
  }
}
