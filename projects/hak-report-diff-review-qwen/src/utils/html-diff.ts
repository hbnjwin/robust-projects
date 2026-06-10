/**
 * HTML Diff处理器 - 表格结构保持
 *
 * Bug Fix #2: 报告里的表格经过diff后结构被打散
 * 修复方案：识别HTML中的<table>元素，对其单独处理——
 *          逐行逐单元格diff，但保持完整的表格HTML结构。
 */

import type { DiffBlock, DiffSegment, TableDiff, TableRowDiff, TableCellDiff, DiffStatus } from '@/types/diff'
import { diffText, hasDiff } from './diff-engine'

let blockIdCounter = 0
function nextBlockId(): string {
  return `diff-block-${++blockIdCounter}`
}

/**
 * 从HTML字符串中提取块级元素
 * 将HTML拆分为文本块和表格块，表格保持完整结构
 */
function parseBlocks(html: string): Array<{ type: 'text' | 'heading' | 'table' | 'list'; html: string; text: string }> {
  const blocks: Array<{ type: 'text' | 'heading' | 'table' | 'list'; html: string; text: string }> = []
  // 匹配表格或常见块级元素
  const blockRegex = /<table[^>]*>[\s\S]*?<\/table>|<(h[1-6]|p|div|li|ul|ol)[^>]*>[\s\S]*?<\/\1>/gi
  let match: RegExpExecArray | null

  while ((match = blockRegex.exec(html)) !== null) {
    const raw = match[0]
    const tag = raw.match(/^<(\w+)/)?.[1]?.toLowerCase() || 'div'
    const text = stripTags(raw)

    if (tag === 'table') {
      blocks.push({ type: 'table', html: raw, text })
    } else if (tag.match(/^h[1-6]$/)) {
      blocks.push({ type: 'heading', html: raw, text })
    } else if (tag === 'li' || tag === 'ul' || tag === 'ol') {
      blocks.push({ type: 'list', html: raw, text })
    } else {
      blocks.push({ type: 'text', html: raw, text })
    }
  }

  // 如果没有匹配到任何块级元素，把整个HTML当做一个文本块
  if (blocks.length === 0 && html.trim()) {
    blocks.push({ type: 'text', html: html, text: stripTags(html) })
  }

  return blocks
}

/**
 * 去除HTML标签，提取纯文本
 */
function stripTags(html: string): string {
  return html.replace(/<[^>]*>/g, '').trim()
}

/**
 * 提取表格的HTML属性字符串
 */
function extractTableAttrs(tableHtml: string): string {
  const match = tableHtml.match(/^<table([^>]*)>/i)
  return match ? match[1].trim() : ''
}

/**
 * 解析HTML表格为二维单元格文本数组
 */
function parseTable(tableHtml: string): string[][] {
  const rows: string[][] = []
  const rowRegex = /<tr[^>]*>([\s\S]*?)<\/tr>/gi
  let rowMatch: RegExpExecArray | null

  while ((rowMatch = rowRegex.exec(tableHtml)) !== null) {
    const cells: string[] = []
    const cellRegex = /<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi
    let cellMatch: RegExpExecArray | null

    while ((cellMatch = cellRegex.exec(rowMatch[1])) !== null) {
      cells.push(stripTags(cellMatch[1]))
    }
    if (cells.length > 0) {
      rows.push(cells)
    }
  }

  return rows
}

/**
 * 对比两个表格，生成单元格级别的diff
 * 保持表格完整结构，不做碎片化处理
 */
function diffTables(oldTableHtml: string, newTableHtml: string): TableDiff {
  const oldRows = parseTable(oldTableHtml)
  const newRows = parseTable(newTableHtml)
  const tableAttrs = extractTableAttrs(newTableHtml) || extractTableAttrs(oldTableHtml)

  const maxRows = Math.max(oldRows.length, newRows.length)
  const resultRows: TableRowDiff[] = []
  let tableHasChanges = false

  for (let r = 0; r < maxRows; r++) {
    const oldRow = oldRows[r] || []
    const newRow = newRows[r] || []
    const maxCols = Math.max(oldRow.length, newRow.length)
    const cells: TableCellDiff[] = []

    for (let c = 0; c < maxCols; c++) {
      const oldCell = oldRow[c] || ''
      const newCell = newRow[c] || ''
      const segments = diffText(oldCell, newCell)
      const cellChanged = hasDiff(segments)
      if (cellChanged) tableHasChanges = true

      cells.push({
        segments,
        status: 'pending',
      })
    }

    resultRows.push({ cells })
  }

  return { rows: resultRows, tableAttrs, hasChanges: tableHasChanges }
}

/**
 * 对两个HTML文档进行diff，返回DiffBlock列表
 * 表格元素会单独处理，保持结构完整
 */
export function diffHtml(oldHtml: string, newHtml: string): DiffBlock[] {
  const oldBlocks = parseBlocks(oldHtml)
  const newBlocks = parseBlocks(newHtml)
  const result: DiffBlock[] = []

  const maxLen = Math.max(oldBlocks.length, newBlocks.length)

  for (let i = 0; i < maxLen; i++) {
    const oldBlock = oldBlocks[i]
    const newBlock = newBlocks[i]

    if (!oldBlock && newBlock) {
      // 新增块
      const segments: DiffSegment[] = [{ type: 'added', value: newBlock.text }]
      result.push({
        id: nextBlockId(),
        type: newBlock.type,
        oldValue: '',
        newValue: newBlock.text,
        segments,
        status: 'pending',
        hasChanges: true,
      })
    } else if (oldBlock && !newBlock) {
      // 删除块
      const segments: DiffSegment[] = [{ type: 'removed', value: oldBlock.text }]
      result.push({
        id: nextBlockId(),
        type: oldBlock.type,
        oldValue: oldBlock.text,
        newValue: '',
        segments,
        status: 'pending',
        hasChanges: true,
      })
    } else if (oldBlock && newBlock) {
      if (oldBlock.type === 'table' && newBlock.type === 'table') {
        // 表格块：逐单元格diff，保持表格结构
        const tableDiff = diffTables(oldBlock.html, newBlock.html)
        result.push({
          id: nextBlockId(),
          type: 'table',
          oldValue: oldBlock.text,
          newValue: newBlock.text,
          segments: [],
          tableDiff,
          status: 'pending',
          hasChanges: tableDiff.hasChanges,
        })
      } else {
        // 文本块：字符级diff
        const segments = diffText(oldBlock.text, newBlock.text)
        const changed = hasDiff(segments)
        result.push({
          id: nextBlockId(),
          type: newBlock.type,
          oldValue: oldBlock.text,
          newValue: newBlock.text,
          segments,
          status: 'pending',
          hasChanges: changed,
        })
      }
    }
  }

  return result
}

/**
 * 重置block ID计数器（用于测试或重新diff）
 */
export function resetBlockIdCounter(): void {
  blockIdCounter = 0
}
