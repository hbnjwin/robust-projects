/**
 * 创建防抖函数
 * @param fn 要防抖的函数
 * @param delay 延迟毫秒数
 * @returns 防抖后的函数（带cancel方法）
 */
export function debounce<T extends (...args: unknown[]) => void>(
  fn: T,
  delay: number
): T & { cancel: () => void } {
  let timer: ReturnType<typeof setTimeout> | null = null

  const debounced = function (this: unknown, ...args: unknown[]) {
    if (timer !== null) {
      clearTimeout(timer)
    }
    timer = setTimeout(() => {
      fn.apply(this, args)
      timer = null
    }, delay)
  } as T & { cancel: () => void }

  debounced.cancel = () => {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  return debounced
}
