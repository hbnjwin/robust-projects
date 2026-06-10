/**
 * Diff查看器状态管理
 *
 * Bug Fix #3: 滚动定位不准确，差异项被固定header遮挡
 * 修复方案：scrollIntoView + 额外偏移量（headerHeight），确保差异项可见
 *
 * Bug Fix #4: "接受修改"后高亮未消失
 * 修复方案：accept/reject操作立即更新block.status，UI响应式移除高亮class
 */

import { ref, computed, nextTick } from 'vue'
import type { DiffBlock, DiffStatus } from '@/types/diff'
import { diffHtml, resetBlockIdCounter } from '@/utils/html-diff'

export function useDiffViewer(oldContent: string, newContent: string, headerHeight = 64) {
  // 重置计数器后执行diff
  resetBlockIdCounter()
  const blocks = ref<DiffBlock[]>(diffHtml(oldContent, newContent))

  // 当前聚焦的差异索引
  const currentDiffIndex = ref(-1)

  // 有差异的block列表
  const diffBlocks = computed(() => blocks.value.filter(b => b.hasChanges))

  // 差异总数
  const totalDiffs = computed(() => diffBlocks.value.length)

  // 待处理差异数
  const pendingDiffs = computed(() =>
    diffBlocks.value.filter(b => b.status === 'pending').length
  )

  /**
   * 导航到下一个差异
   * Bug Fix #3: 使用scrollIntoView并补偿fixed header偏移
   */
  function goToNextDiff() {
    if (totalDiffs.value === 0) return

    currentDiffIndex.value = (currentDiffIndex.value + 1) % totalDiffs.value
    scrollToCurrentDiff()
  }

  /**
   * 导航到上一个差异
   */
  function goToPrevDiff() {
    if (totalDiffs.value === 0) return

    currentDiffIndex.value =
      currentDiffIndex.value <= 0
        ? totalDiffs.value - 1
        : currentDiffIndex.value - 1
    scrollToCurrentDiff()
  }

  /**
   * Bug Fix #3: 滚动到当前差异位置
   * 关键：考虑固定header高度的偏移，确保差异元素不被遮挡
   */
  function scrollToCurrentDiff() {
    if (currentDiffIndex.value < 0 || currentDiffIndex.value >= totalDiffs.value) return

    const block = diffBlocks.value[currentDiffIndex.value]
    if (!block) return

    nextTick(() => {
      const el = document.getElementById(block.id)
      if (!el) return

      // 计算目标滚动位置：元素顶部位置 - header高度 - 额外padding
      const scrollTop = window.scrollY || document.documentElement.scrollTop
      const elementTop = el.getBoundingClientRect().top + scrollTop
      const targetScroll = elementTop - headerHeight - 20 // 20px额外间距

      window.scrollTo({
        top: Math.max(0, targetScroll),
        behavior: 'smooth',
      })
    })
  }

  /**
   * Bug Fix #4: 接受修改
   * 更新状态为accepted，UI立即移除高亮（响应式更新）
   */
  function acceptChange(blockId: string) {
    const block = blocks.value.find(b => b.id === blockId)
    if (!block || block.status !== 'pending') return

    block.status = 'accepted'

    // 表格类型：同时更新所有单元格状态
    if (block.tableDiff) {
      block.tableDiff.rows.forEach(row => {
        row.cells.forEach(cell => {
          if (cell.status === 'pending') {
            cell.status = 'accepted'
          }
        })
      })
    }
  }

  /**
   * Bug Fix #4: 拒绝修改
   * 更新状态为rejected，UI立即移除高亮
   */
  function rejectChange(blockId: string) {
    const block = blocks.value.find(b => b.id === blockId)
    if (!block || block.status !== 'pending') return

    block.status = 'rejected'

    if (block.tableDiff) {
      block.tableDiff.rows.forEach(row => {
        row.cells.forEach(cell => {
          if (cell.status === 'pending') {
            cell.status = 'rejected'
          }
        })
      })
    }
  }

  /**
   * 接受表格中单个单元格的修改
   */
  function acceptTableCell(blockId: string, rowIdx: number, colIdx: number) {
    const block = blocks.value.find(b => b.id === blockId)
    if (!block?.tableDiff) return

    const cell = block.tableDiff.rows[rowIdx]?.cells[colIdx]
    if (cell && cell.status === 'pending') {
      cell.status = 'accepted'
    }
  }

  /**
   * 拒绝表格中单个单元格的修改
   */
  function rejectTableCell(blockId: string, rowIdx: number, colIdx: number) {
    const block = blocks.value.find(b => b.id === blockId)
    if (!block?.tableDiff) return

    const cell = block.tableDiff.rows[rowIdx]?.cells[colIdx]
    if (cell && cell.status === 'pending') {
      cell.status = 'rejected'
    }
  }

  /**
   * 获取当前差异的显示信息 "X / Y"
   */
  const currentDiffLabel = computed(() => {
    if (totalDiffs.value === 0) return '0 / 0'
    return `${currentDiffIndex.value + 1} / ${totalDiffs.value}`
  })

  return {
    blocks,
    diffBlocks,
    currentDiffIndex,
    totalDiffs,
    pendingDiffs,
    currentDiffLabel,
    goToNextDiff,
    goToPrevDiff,
    acceptChange,
    rejectChange,
    acceptTableCell,
    rejectTableCell,
  }
}
