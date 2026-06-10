import {
  DiffType,
  DiffSegment,
  DiffChange,
  BlockType,
  TextDiffBlock,
  TableDiffBlock,
  TableCellDiff,
  DiffBlock,
  DiffResult,
  ReportData,
  ReportNode,
  NodeType,
  TableCell,
} from '@/types/diff'

// ─── 字符级别 Myers Diff ─────────────────────────────────

interface EditOp {
  type: DiffType
  oldStart: number
  oldEnd: number
  newStart: number
  newEnd: number
}

/**
 * Myers diff 算法，计算两个字符串之间的最短编辑路径。
 * 返回编辑操作序列，确保字符级别精确标注。
 * 例如 "风机叶片桨距角" vs "风机叶片浆距角" → 只标出"桨→浆"
 */
function myersEditOps(oldStr: string, newStr: string): EditOp[] {
  const n = oldStr.length
  const m = newStr.length

  if (n === 0 && m === 0) return []
  if (n === 0) {
    return [{ type: DiffType.Added, oldStart: 0, oldEnd: 0, newStart: 0, newEnd: m }]
  }
  if (m === 0) {
    return [{ type: DiffType.Removed, oldStart: 0, oldEnd: n, newStart: 0, newEnd: 0 }]
  }

  const max = n + m
  const vSize = 2 * max + 1
  const v = new Int32Array(vSize)
  const trace: Int32Array[] = []

  // Forward pass
  let found = false
  for (let d = 0; d <= max && !found; d++) {
    trace.push(new Int32Array(v))
    for (let k = -d; k <= d; k += 2) {
      const kIdx = k + max
      let x: number
      if (k === -d || (k !== d && v[kIdx - 1] < v[kIdx + 1])) {
        x = v[kIdx + 1] // insert (move down)
      } else {
        x = v[kIdx - 1] + 1 // delete (move right)
      }
      let y = x - k
      // Follow diagonal (equal characters)
      while (x < n && y < m && oldStr[x] === newStr[y]) {
        x++
        y++
      }
      v[kIdx] = x
      if (x >= n && y >= m) {
        found = true
        break
      }
    }
  }

  // Backtrack to extract edit operations
  let x = n
  let y = m
  const ops: EditOp[] = []

  for (let d = trace.length - 1; d >= 0; d--) {
    const vPrev = trace[d]
    const k = x - y
    const kIdx = k + max
    let prevK: number
    if (k === -d || (k !== d && vPrev[kIdx - 1] < vPrev[kIdx + 1])) {
      prevK = k + 1 // came from insert
    } else {
      prevK = k - 1 // came from delete
    }

    const prevX = vPrev[prevK + max]
    const prevY = prevX - prevK

    // Diagonal (equal characters) - walk back
    while (x > prevX && y > prevY) {
      x--
      y--
      ops.push({ type: DiffType.Equal, oldStart: x, oldEnd: x + 1, newStart: y, newEnd: y + 1 })
    }

    if (d > 0) {
      if (x === prevX) {
        // Insert
        y--
        ops.push({ type: DiffType.Added, oldStart: x, oldEnd: x, newStart: y, newEnd: y + 1 })
      } else {
        // Delete
        x--
        ops.push({ type: DiffType.Removed, oldStart: x, oldEnd: x + 1, newStart: y, newEnd: y })
      }
    }
  }

  ops.reverse()
  return ops
}

/**
 * 合并相邻的相同类型操作，生成紧凑的 DiffSegment 数组。
 */
function mergeOpsToSegments(ops: EditOp[], oldStr: string, newStr: string): { oldSegs: DiffSegment[]; newSegs: DiffSegment[] } {
  const oldSegs: DiffSegment[] = []
  const newSegs: DiffSegment[] = []

  for (const op of ops) {
    switch (op.type) {
      case DiffType.Equal: {
        const text = oldStr.slice(op.oldStart, op.oldEnd)
        appendSegment(oldSegs, text, DiffType.Equal)
        appendSegment(newSegs, text, DiffType.Equal)
        break
      }
      case DiffType.Removed: {
        const text = oldStr.slice(op.oldStart, op.oldEnd)
        appendSegment(oldSegs, text, DiffType.Removed)
        break
      }
      case DiffType.Added: {
        const text = newStr.slice(op.newStart, op.newEnd)
        appendSegment(newSegs, text, DiffType.Added)
        break
      }
    }
  }

  return { oldSegs, newSegs }
}

function appendSegment(segs: DiffSegment[], text: string, type: DiffType) {
  if (text.length === 0) return
  const last = segs[segs.length - 1]
  if (last && last.type === type) {
    last.text += text
  } else {
    segs.push({ text, type })
  }
}

/**
 * 对两个字符串做字符级别diff。
 * 确保中文文本如 "桨" → "浆" 只标注单个字的差异。
 */
export function computeCharDiff(
  oldStr: string,
  newStr: string,
): { oldSegs: DiffSegment[]; newSegs: DiffSegment[] } {
  if (oldStr === newStr) {
    const seg: DiffSegment = { text: oldStr, type: DiffType.Equal }
    return { oldSegs: [seg], newSegs: [{ ...seg }] }
  }
  const ops = myersEditOps(oldStr, newStr)
  return mergeOpsToSegments(ops, oldStr, newStr)
}

// ─── 报告级别 Diff ──────────────────────────────────────

let changeIdCounter = 0

function nextChangeId(): string {
  return `change-${++changeIdCounter}`
}

/** 重置ID计数器（用于测试） */
export function resetChangeIdCounter() {
  changeIdCounter = 0
}

function hasActualDiff(segs: DiffSegment[]): boolean {
  return segs.some((s) => s.type !== DiffType.Equal)
}

/**
 * 对两个文本节点做行级+字符级diff。
 * 先按行分割，然后对每行做字符级别diff。
 */
function diffTextNodes(
  oldText: string,
  newText: string,
  changes: DiffChange[],
): TextDiffBlock {
  const oldLines = oldText.split('\n')
  const newLines = newText.split('\n')
  const maxLines = Math.max(oldLines.length, newLines.length)
  const lines: TextDiffBlock['lines'] = []

  for (let i = 0; i < maxLines; i++) {
    const ol = oldLines[i] ?? ''
    const nl = newLines[i] ?? ''

    if (ol === nl) {
      lines.push({
        oldLine: [{ text: ol, type: DiffType.Equal }],
        newLine: [{ text: nl, type: DiffType.Equal }],
      })
    } else {
      const { oldSegs, newSegs } = computeCharDiff(ol, nl)
      const changeId = nextChangeId()
      changes.push({
        id: changeId,
        oldSegments: oldSegs,
        newSegments: newSegs,
        accepted: false,
        rejected: false,
      })
      lines.push({ oldLine: oldSegs, newLine: newSegs, changeId })
    }
  }

  return { type: BlockType.Text, lines }
}

/**
 * 对两个表格节点做单元格级别diff。
 * 保持表格结构完整，在每个单元格内做字符级diff。
 */
function diffTableNodes(
  oldHeaders: TableCell[],
  newHeaders: TableCell[],
  oldRows: TableCell[][],
  newRows: TableCell[][],
  changes: DiffChange[],
): TableDiffBlock {
  const headers = diffCellRow(oldHeaders, newHeaders, changes)
  const maxRows = Math.max(oldRows.length, newRows.length)
  const rows: TableCellDiff[][] = []

  for (let r = 0; r < maxRows; r++) {
    const oldRow = oldRows[r] ?? []
    const newRow = newRows[r] ?? []
    rows.push(diffCellRow(oldRow, newRow, changes))
  }

  return { type: BlockType.Table, headers, rows }
}

function diffCellRow(
  oldCells: TableCell[],
  newCells: TableCell[],
  changes: DiffChange[],
): TableCellDiff[] {
  const maxCols = Math.max(oldCells.length, newCells.length)
  const result: TableCellDiff[] = []

  for (let c = 0; c < maxCols; c++) {
    const oc = oldCells[c]
    const nc = newCells[c]
    const oldContent = oc?.content ?? ''
    const newContent = nc?.content ?? ''

    const { oldSegs, newSegs } = computeCharDiff(oldContent, newContent)
    const hasDiff = hasActualDiff(oldSegs) || hasActualDiff(newSegs)
    let changeId: string | undefined

    if (hasDiff) {
      changeId = nextChangeId()
      changes.push({
        id: changeId,
        oldSegments: oldSegs,
        newSegments: newSegs,
        accepted: false,
        rejected: false,
      })
    }

    result.push({
      oldSegments: oldSegs,
      newSegments: newSegs,
      changeId,
      colspan: nc?.colspan ?? oc?.colspan,
      rowspan: nc?.rowspan ?? oc?.rowspan,
    })
  }

  return result
}

/**
 * 对两份报告做节点级别对齐和diff。
 * 同类型节点逐个对比，不同类型节点标记为完全替换。
 */
export function diffReports(oldReport: ReportData, newReport: ReportData): DiffResult {
  changeIdCounter = 0
  const changes: DiffChange[] = []
  const blocks: DiffBlock[] = []

  const maxNodes = Math.max(oldReport.nodes.length, newReport.nodes.length)

  for (let i = 0; i < maxNodes; i++) {
    const oldNode = oldReport.nodes[i]
    const newNode = newReport.nodes[i]

    if (!oldNode && newNode) {
      // 新增节点
      if (newNode.type === NodeType.Text) {
        blocks.push(diffTextNodes('', newNode.content, changes))
      } else {
        blocks.push(diffTableNodes([], newNode.headers, [], newNode.rows, changes))
      }
    } else if (oldNode && !newNode) {
      // 删除节点
      if (oldNode.type === NodeType.Text) {
        blocks.push(diffTextNodes(oldNode.content, '', changes))
      } else {
        blocks.push(diffTableNodes(oldNode.headers, [], oldNode.rows, [], changes))
      }
    } else if (oldNode && newNode) {
      if (oldNode.type === NodeType.Text && newNode.type === NodeType.Text) {
        blocks.push(diffTextNodes(oldNode.content, newNode.content, changes))
      } else if (oldNode.type === NodeType.Table && newNode.type === NodeType.Table) {
        blocks.push(diffTableNodes(oldNode.headers, newNode.headers, oldNode.rows, newNode.rows, changes))
      } else {
        // 类型不同，分别标记旧删新增
        if (oldNode.type === NodeType.Text) {
          blocks.push(diffTextNodes(oldNode.content, '', changes))
        } else {
          blocks.push(diffTableNodes(oldNode.headers, [], oldNode.rows, [], changes))
        }
        if (newNode.type === NodeType.Text) {
          blocks.push(diffTextNodes('', newNode.content, changes))
        } else {
          blocks.push(diffTableNodes([], newNode.headers, [], newNode.rows, changes))
        }
      }
    }
  }

  return { blocks, changes }
}
