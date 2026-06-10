/**
 * CJK 字体渲染偏移修正工具
 *
 * 问题根因：pdf.js 的 text layer 使用字体度量信息定位 <span>，
 * CJK 字体的 ascent/descent 与拉丁字体存在差异（CJK ~0.88em vs Latin ~0.76em），
 * 导致中文字符在 text layer 中的垂直位置偏移约半行。
 * 缩放时偏移按比例放大，150% 以上尤为明显。
 */

/** CJK 字符 Unicode 范围（含扩展区） */
const CJK_RANGES =
  /[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u2e80-\u2eff\u3000-\u303f\u31c0-\u31ef\ufe30-\ufe4f\uff00-\uffef]/

/**
 * CJK 字体 ascent 修正系数
 * 拉丁字体典型 ascent ≈ 0.76em，CJK 字体 ≈ 0.88em
 * 差值 0.12 即为偏移来源
 */
const CJK_ASCENT_DELTA = 0.12

/**
 * 检测文本是否包含 CJK 字符
 */
export function containsCjk(text: string): boolean {
  return CJK_RANGES.test(text)
}

/**
 * 从 CSS transform matrix 中解析平移分量
 * matrix(a, b, c, d, tx, ty) → { tx, ty }
 */
function parseTransformMatrix(transform: string): { tx: number; ty: number } | null {
  const match = transform.match(
    /matrix\(\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,)]+)\)/,
  )
  if (!match) return null
  return { tx: parseFloat(match[5]), ty: parseFloat(match[6]) }
}

/**
 * 创建字体度量测量器，通过 DOM 实测 CJK 与拉丁字符的基线差异
 * 比硬编码修正值更准确，能适配不同浏览器和系统字体
 */
function measureBaselineDelta(
  fontFamily: string,
  fontSize: number,
): number {
  const container = document.createElement('div')
  container.style.cssText =
    'position:absolute;visibility:hidden;top:-9999px;left:-9999px;'
  document.body.appendChild(container)

  const createSpan = (char: string): HTMLSpanElement => {
    const span = document.createElement('span')
    span.style.fontFamily = fontFamily
    span.style.fontSize = `${fontSize}px`
    span.style.lineHeight = '1'
    span.textContent = char
    container.appendChild(span)
    return span
  }

  const latinSpan = createSpan('Hg')
  const cjkSpan = createSpan('\u4e2d') // "中"

  const latinRect = latinSpan.getBoundingClientRect()
  const cjkRect = cjkSpan.getBoundingClientRect()

  // 高度差反映 ascent 差异
  const delta = cjkRect.height - latinRect.height

  document.body.removeChild(container)
  return delta
}

/**
 * 修正 text layer 中 CJK 文字的垂直偏移
 *
 * 在 vue-pdf-embed 的 @rendered 事件回调中调用此函数：
 * - 遍历 text layer 中所有 <span>
 * - 对包含 CJK 字符的 span 修正垂直位置
 * - 同时修正 annotation layer 的对齐基准
 *
 * @param container - PDF 渲染容器 DOM 元素
 * @param scale - 当前缩放比例，用于保持修正量与缩放同步
 */
export function patchCjkTextLayerOffsets(
  container: HTMLElement,
  scale: number = 1,
): void {
  const textLayer = container.querySelector<HTMLElement>('.textLayer')
  if (!textLayer) return

  const spans = textLayer.querySelectorAll<HTMLSpanElement>('span')
  if (spans.length === 0) return

  // 用第一个 CJK span 的字体做基线测量
  let measuredDelta: number | null = null
  let measuredFontKey = ''

  spans.forEach((span) => {
    const text = span.textContent || ''
    if (!containsCjk(text)) return

    const computed = getComputedStyle(span)
    const fontSize = parseFloat(computed.fontSize)
    if (fontSize <= 0 || isNaN(fontSize)) return

    const fontFamily = computed.fontFamily
    const fontKey = `${fontFamily}:${Math.round(fontSize)}`

    // 同一字体大小组合只测量一次
    if (fontKey !== measuredFontKey) {
      measuredDelta = measureBaselineDelta(fontFamily, fontSize)
      measuredFontKey = fontKey
    }

    // 优先使用实测值，回退到启发式系数
    const correction =
      measuredDelta !== null && Math.abs(measuredDelta) > 0.5
        ? measuredDelta * 0.5
        : fontSize * CJK_ASCENT_DELTA

    // 修正方式1: 有 transform matrix 的 span
    const inlineTransform = span.style.transform
    if (inlineTransform) {
      const matrix = parseTransformMatrix(getComputedStyle(span).transform)
      if (matrix) {
        // 保持原始 scaleX，只修正 translateY
        const scaleXMatch = inlineTransform.match(/scaleX\(([^)]+)\)/)
        const scaleX = scaleXMatch ? scaleXMatch[1] : '1'
        span.style.transform =
          `scaleX(${scaleX}) translateY(${-correction}px)`
        return
      }
    }

    // 修正方式2: 使用 top 定位的 span
    const currentTop = parseFloat(span.style.top) || 0
    span.style.top = `${currentTop - correction}px`
  })
}

/**
 * 同步 annotation layer 位置到修正后的 text layer
 * 确保批注标记（高亮、链接等）与修正后的文字位置对齐
 */
export function syncAnnotationLayerPosition(container: HTMLElement): void {
  const textLayer = container.querySelector<HTMLElement>('.textLayer')
  const annotationLayer = container.querySelector<HTMLElement>('.annotationLayer')
  if (!textLayer || !annotationLayer) return

  // 确保两个层使用相同的定位基准
  const textRect = textLayer.getBoundingClientRect()
  const annotRect = annotationLayer.getBoundingClientRect()

  const offsetY = textRect.top - annotRect.top
  if (Math.abs(offsetY) > 0.5) {
    const currentTop = parseFloat(annotationLayer.style.top) || 0
    annotationLayer.style.top = `${currentTop + offsetY}px`
  }
}
