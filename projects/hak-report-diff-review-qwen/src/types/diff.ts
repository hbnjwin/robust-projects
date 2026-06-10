/**
 * 报告Diff对比 - 类型定义
 */

/** 差异片段类型 */
export type DiffType = 'equal' | 'added' | 'removed' | 'modified'

/** 差异块状态 */
export type DiffStatus = 'pending' | 'accepted' | 'rejected'

/** 文本diff片段 */
export interface DiffSegment {
  type: DiffType
  value: string
}

/** 表格单元格diff */
export interface TableCellDiff {
  segments: DiffSegment[]
  status: DiffStatus
}

/** 表格行diff */
export interface TableRowDiff {
  cells: TableCellDiff[]
}

/** 表格diff（保持完整表格结构） */
export interface TableDiff {
  rows: TableRowDiff[]
  /** 原始table的HTML属性（class、style等） */
  tableAttrs: string
  /** 是否有差异 */
  hasChanges: boolean
}

/** 文档块diff */
export interface DiffBlock {
  id: string
  type: 'text' | 'heading' | 'table' | 'list'
  /** 左侧（旧版）文本内容 */
  oldValue: string
  /** 右侧（新版）文本内容 */
  newValue: string
  /** 文本级diff片段 */
  segments: DiffSegment[]
  /** 表格级diff（仅type='table'时使用） */
  tableDiff?: TableDiff
  /** 块状态 */
  status: DiffStatus
  /** 是否包含差异 */
  hasChanges: boolean
}

/** Diff导航项 */
export interface DiffNavItem {
  /** 对应DiffBlock的id */
  blockId: string
  /** 该差异的显示序号 */
  index: number
}

/** DiffViewer组件Props */
export interface DiffViewerProps {
  /** 旧版报告HTML内容 */
  oldContent: string
  /** 新版报告HTML内容 */
  newContent: string
  /** 旧版标题 */
  oldTitle?: string
  /** 新版标题 */
  newTitle?: string
  /** 固定header高度（px），用于滚动定位修正 */
  headerHeight?: number
}
