/** 差异类型 */
export enum DiffType {
  /** 无变化 */
  Equal = 'equal',
  /** 新增 */
  Added = 'added',
  /** 删除 */
  Removed = 'removed',
}

/** 字符级别的差异片段 */
export interface DiffSegment {
  text: string
  type: DiffType
}

/** 一个可操作的差异项（用于导航和接受/拒绝） */
export interface DiffChange {
  /** 唯一ID */
  id: string
  /** 差异在左侧(旧版)的片段 */
  oldSegments: DiffSegment[]
  /** 差异在右侧(新版)的片段 */
  newSegments: DiffSegment[]
  /** 是否已被接受 */
  accepted: boolean
  /** 是否已被拒绝 */
  rejected: boolean
}

/** 内容块类型 */
export enum BlockType {
  Text = 'text',
  Table = 'table',
}

/** 文本diff块 */
export interface TextDiffBlock {
  type: BlockType.Text
  /** 每行包含多个diff片段 */
  lines: {
    oldLine: DiffSegment[]
    newLine: DiffSegment[]
    changeId?: string
  }[]
}

/** 表格单元格diff */
export interface TableCellDiff {
  oldSegments: DiffSegment[]
  newSegments: DiffSegment[]
  changeId?: string
  colspan?: number
  rowspan?: number
}

/** 表格diff块 */
export interface TableDiffBlock {
  type: BlockType.Table
  headers: TableCellDiff[]
  rows: TableCellDiff[][]
}

/** diff内容块（文本或表格） */
export type DiffBlock = TextDiffBlock | TableDiffBlock

/** 完整的diff结果 */
export interface DiffResult {
  blocks: DiffBlock[]
  changes: DiffChange[]
}

/** 报告内容节点类型 */
export enum NodeType {
  Text = 'text',
  Table = 'table',
}

/** 报告文本节点 */
export interface TextNode {
  type: NodeType.Text
  content: string
}

/** 表格单元格 */
export interface TableCell {
  content: string
  colspan?: number
  rowspan?: number
}

/** 报告表格节点 */
export interface TableNode {
  type: NodeType.Table
  headers: TableCell[]
  rows: TableCell[][]
}

/** 报告内容节点 */
export type ReportNode = TextNode | TableNode

/** 报告数据 */
export interface ReportData {
  title: string
  nodes: ReportNode[]
}
