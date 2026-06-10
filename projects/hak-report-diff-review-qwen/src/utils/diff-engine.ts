/**
 * 字符级Diff引擎
 *
 * Bug Fix #1: 中文字词级别diff标注不准确
 * 修复方案：使用LCS（最长公共子序列）算法对中文字符逐个对比，
 *          而非按词/空格分词。"风机叶片桨距角" vs "风机叶片浆距角"
 *          只会标出 "桨→浆" 一个字的差异。
 */

import type { DiffSegment, DiffType } from '@/types/diff'

/**
 * 智能分词：中文拆为单字，英文/数字保持为词
 * 例："风机叶片桨距角" → ["风","机","叶","片","桨","距","角"]
 *     "model A100" → ["model", "A100"]
 *     "温度32.5℃" → ["温","度","32.5","℃"]
 */
function smartTokenize(text: string): string[] {
  const tokens: string[] = []
  // 正则：连续英文字母数字为一个token，其他字符（含中文）各为一个token
  const regex = /[a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)*|./gs
  let match: RegExpExecArray | null
  while ((match = regex.exec(text)) !== null) {
    tokens.push(match[0])
  }
  return tokens
}

/**
 * 计算LCS（最长公共子序列）DP表
 */
function computeLCS(oldTokens: string[], newTokens: string[]): number[][] {
  const m = oldTokens.length
  const n = newTokens.length
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldTokens[i - 1] === newTokens[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
      }
    }
  }
  return dp
}

/**
 * 从LCS DP表回溯，生成diff片段
 */
function backtrackDiff(
  dp: number[][],
  oldTokens: string[],
  newTokens: string[],
): DiffSegment[] {
  const segments: DiffSegment[] = []
  let i = oldTokens.length
  let j = newTokens.length

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldTokens[i - 1] === newTokens[j - 1]) {
      segments.push({ type: 'equal', value: oldTokens[i - 1] })
      i--
      j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      segments.push({ type: 'added', value: newTokens[j - 1] })
      j--
    } else {
      segments.push({ type: 'removed', value: oldTokens[i - 1] })
      i--
    }
  }

  return segments.reverse()
}

/**
 * 合并相邻同类型片段，减少渲染节点数
 */
function mergeAdjacentSegments(segments: DiffSegment[]): DiffSegment[] {
  if (segments.length === 0) return []
  const merged: DiffSegment[] = [segments[0]]
  for (let i = 1; i < segments.length; i++) {
    const last = merged[merged.length - 1]
    const curr = segments[i]
    if (last.type === curr.type) {
      last.value += curr.value
    } else {
      merged.push(curr)
    }
  }
  return merged
}

/**
 * 核心diff函数：对两段文本进行字符级diff
 *
 * 对于中文文本，每个汉字是独立的比较单元，
 * 因此"风机叶片桨距角" vs "风机叶片浆距角"只会产生：
 *   equal("风机叶片"), removed("桨"), added("浆"), equal("距角")
 */
export function diffText(oldText: string, newText: string): DiffSegment[] {
  if (oldText === newText) {
    return oldText ? [{ type: 'equal', value: oldText }] : []
  }
  if (!oldText) {
    return [{ type: 'added', value: newText }]
  }
  if (!newText) {
    return [{ type: 'removed', value: oldText }]
  }

  const oldTokens = smartTokenize(oldText)
  const newTokens = smartTokenize(newText)
  const dp = computeLCS(oldTokens, newTokens)
  const segments = backtrackDiff(dp, oldTokens, newTokens)
  return mergeAdjacentSegments(segments)
}

/**
 * 检测diff片段中是否包含实际差异
 */
export function hasDiff(segments: DiffSegment[]): boolean {
  return segments.some(s => s.type !== 'equal')
}

/**
 * 将removed+added配对标记为modified（用于UI显示"接受/拒绝"按钮）
 * 将连续的 removed...added... 归为一组modified
 */
export function groupModifiedSegments(segments: DiffSegment[]): DiffSegment[] {
  const result: DiffSegment[] = []
  let i = 0
  while (i < segments.length) {
    if (segments[i].type === 'removed') {
      // 收集连续的removed
      const removedParts: string[] = []
      while (i < segments.length && segments[i].type === 'removed') {
        removedParts.push(segments[i].value)
        i++
      }
      // 收集紧随其后的added
      const addedParts: string[] = []
      while (i < segments.length && segments[i].type === 'added') {
        addedParts.push(segments[i].value)
        i++
      }
      if (addedParts.length > 0) {
        result.push({ type: 'modified', value: removedParts.join('') })
        result.push({ type: 'added', value: addedParts.join('') })
      } else {
        result.push({ type: 'removed', value: removedParts.join('') })
      }
    } else {
      result.push(segments[i])
      i++
    }
  }
  return result
}
