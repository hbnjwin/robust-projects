/**
 * 验证工具方法
 */

/**
 * 验证端口号是否合法（1-65535 的整数）
 *
 * 注意：此处正则不能带 g（global）标志。
 * 带 g 标志的 RegExp 对象在调用 test() 时会维护内部 lastIndex 状态，
 * 导致连续调用结果交替变化（第一次成功 lastIndex 移到末尾，
 * 第二次从 lastIndex 开始匹配失败并重置为 0，第三次又成功……），
 * 在表单校验场景中表现为同一个合法端口号随机显示"格式错误"。
 *
 * @param {string|number} value - 待验证的端口号
 * @returns {boolean} 是否为合法端口号
 */
export function port(value) {
  const str = String(value).trim()
  // 修复：去掉原正则 /^(\d)+$/g 中的 g 标志，避免 lastIndex 状态导致交替匹配失败
  const portRegex = /^(\d+)$/
  if (!portRegex.test(str)) {
    return false
  }
  const num = Number(str)
  return num >= 1 && num <= 65535
}

export default {
  port
}
