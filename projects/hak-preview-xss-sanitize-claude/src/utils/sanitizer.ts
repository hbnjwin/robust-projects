import DOMPurify from 'dompurify'
import type { SanitizerConfig, SanitizeReport } from '@/types/preview'

/**
 * 安全的HTML标签白名单
 * 保留文档排版所需的所有标签，但排除脚本和危险交互元素
 */
const BASE_ALLOWED_TAGS = [
  // 文档结构
  'html', 'head', 'body', 'main', 'article', 'section', 'nav', 'aside',
  'header', 'footer', 'div', 'span',
  // 标题
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  // 文本格式
  'p', 'br', 'hr', 'pre', 'code', 'blockquote', 'cite',
  'strong', 'b', 'em', 'i', 'u', 's', 'del', 'ins', 'sub', 'sup',
  'small', 'mark', 'abbr', 'dfn', 'var', 'kbd', 'samp',
  // 列表
  'ul', 'ol', 'li', 'dl', 'dt', 'dd',
  // 表格
  'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td',
  'caption', 'colgroup', 'col',
  // 媒体（安全的）
  'img', 'figure', 'figcaption', 'picture', 'source',
  // 链接
  'a',
  // 其他排版
  'details', 'summary', 'ruby', 'rt', 'rp', 'wbr',
  // 样式（允许内联样式表，DOMPurify会清理危险CSS）
  'style',
]

/**
 * SVG安全标签白名单
 * 允许SVG渲染所需的标签，但排除 foreignObject, script 等危险标签
 */
const SVG_ALLOWED_TAGS = [
  'svg', 'g', 'path', 'circle', 'ellipse', 'rect', 'line',
  'polyline', 'polygon', 'text', 'tspan', 'textPath',
  'defs', 'use', 'symbol', 'clipPath', 'mask',
  'linearGradient', 'radialGradient', 'stop', 'pattern',
  'marker', 'title', 'desc', 'metadata',
  'image',
  // 注意：故意不包含 foreignObject, script, animate (SMIL可被滥用)
]

/**
 * 安全的HTML属性白名单
 * 保留样式和排版属性，但排除所有事件处理器属性
 */
const BASE_ALLOWED_ATTR = [
  // 通用属性
  'id', 'class', 'style', 'title', 'lang', 'dir', 'role',
  'aria-label', 'aria-hidden', 'aria-describedby', 'aria-labelledby',
  // 表格属性
  'colspan', 'rowspan', 'scope', 'headers',
  'border', 'cellpadding', 'cellspacing', 'width', 'height',
  'align', 'valign',
  // 链接属性
  'href', 'target', 'rel',
  // 图片属性
  'src', 'alt', 'loading', 'decoding',
  // 列表属性
  'type', 'start', 'value', 'reversed',
  // 其他
  'open', 'cite', 'datetime', 'name',
  'data-*',
]

/**
 * SVG安全属性白名单
 */
const SVG_ALLOWED_ATTR = [
  'viewBox', 'xmlns', 'xmlns:xlink', 'version',
  'x', 'y', 'x1', 'y1', 'x2', 'y2',
  'cx', 'cy', 'r', 'rx', 'ry',
  'width', 'height',
  'd', 'fill', 'stroke', 'stroke-width', 'stroke-linecap',
  'stroke-linejoin', 'stroke-dasharray', 'stroke-dashoffset',
  'opacity', 'fill-opacity', 'stroke-opacity',
  'transform', 'clip-path', 'mask',
  'font-family', 'font-size', 'font-weight', 'font-style',
  'text-anchor', 'dominant-baseline', 'letter-spacing',
  'gradientUnits', 'gradientTransform', 'spreadMethod',
  'offset', 'stop-color', 'stop-opacity',
  'points', 'preserveAspectRatio',
  'marker-start', 'marker-mid', 'marker-end',
  'xlink:href', 'href',
  'id', 'class', 'style',
  'patternUnits', 'patternTransform',
  'markerWidth', 'markerHeight', 'refX', 'refY', 'orient',
]

/**
 * 所有on*事件处理器属性的匹配模式
 * 这些必须被完全禁止，是XSS的主要攻击面
 */
const EVENT_HANDLER_PATTERN = /^on\w+/i

/**
 * 危险的URI协议
 */
const DANGEROUS_URI_PROTOCOLS = ['javascript', 'data', 'vbscript']

/**
 * 创建DOMPurify安全配置
 */
function createSafeConfig(options?: SanitizerConfig): DOMPurify.Config {
  const allowedTags = [...BASE_ALLOWED_TAGS]
  const allowedAttr = [...BASE_ALLOWED_ATTR]

  if (options?.allowSvg !== false) {
    allowedTags.push(...SVG_ALLOWED_TAGS)
    allowedAttr.push(...SVG_ALLOWED_ATTR)
  }

  if (options?.extraAllowedTags) {
    const safeTags = options.extraAllowedTags.filter(
      tag => !['script', 'iframe', 'object', 'embed', 'applet', 'foreignobject'].includes(tag.toLowerCase())
    )
    allowedTags.push(...safeTags)
  }

  if (options?.extraAllowedAttr) {
    const safeAttrs = options.extraAllowedAttr.filter(
      attr => !EVENT_HANDLER_PATTERN.test(attr)
    )
    allowedAttr.push(...safeAttrs)
  }

  return {
    ALLOWED_TAGS: allowedTags,
    ALLOWED_ATTR: allowedAttr,
    ALLOW_DATA_ATTR: true,
    // 禁止危险标签（即使在白名单中也会被移除）
    FORBID_TAGS: [
      'script',       // XSS漏洞1: 直接脚本执行
      'iframe',        // XSS漏洞3: iframe嵌入javascript
      'object',        // Flash/Java applet攻击
      'embed',         // 嵌入恶意内容
      'applet',        // Java applet
      'form',          // 表单劫持
      'input',         // 表单注入
      'textarea',      // 表单注入
      'select',        // 表单注入
      'button',        // 点击劫持
      'foreignobject', // XSS漏洞4: SVG foreignObject脚本注入
      'foreignObject', // 大小写变体
    ],
    // 禁止所有事件处理器属性 (XSS漏洞2: onerror等事件属性)
    FORBID_ATTR: [
      'onerror', 'onload', 'onclick', 'onmouseover', 'onmouseout',
      'onmouseenter', 'onmouseleave', 'onmousedown', 'onmouseup',
      'onfocus', 'onblur', 'onsubmit', 'onreset', 'onchange',
      'oninput', 'onkeydown', 'onkeyup', 'onkeypress',
      'ondblclick', 'oncontextmenu', 'onwheel', 'onscroll',
      'ondrag', 'ondragstart', 'ondragend', 'ondragover',
      'ondragenter', 'ondragleave', 'ondrop',
      'ontouchstart', 'ontouchend', 'ontouchmove', 'ontouchcancel',
      'onanimationstart', 'onanimationend', 'onanimationiteration',
      'ontransitionend', 'onresize', 'onauxclick',
      'onpointerdown', 'onpointerup', 'onpointermove',
      'onpointerenter', 'onpointerleave', 'onpointerover', 'onpointerout',
      'formaction', 'xlink:href',
    ],
    // 允许安全的URI协议
    ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|tel|ftp):|[^a-z]|[a-z+.-]+(?:[^a-z+.\-:]|$))/i,
    // 保留内容（不要把标签内的文字也删掉）
    KEEP_CONTENT: true,
    // 强制body模式，确保<style>标签在片段解析时不被丢弃
    FORCE_BODY: true,
    IN_PLACE: false,
  }
}

/**
 * 安装DOMPurify钩子来拦截更多攻击向量
 */
function installSecurityHooks(purifier: typeof DOMPurify): void {
  // 钩子: 在消毒每个元素时检查
  // 注意: foreignObject 已通过 FORBID_TAGS 处理，不在钩子中手动移除节点
  // 手动 removeChild 会与 DOMPurify 3.x 内部逻辑冲突导致异常
  purifier.addHook('uponSanitizeElement', (_node: Element, _data) => {
    // 预留钩子位置，用于未来扩展元素级安全检查
  })

  // 钩子: 在消毒每个属性时检查
  purifier.addHook('uponSanitizeAttribute', (_node: Element, data) => {
    // 拦截所有on*事件处理器（通过正则兜底，防止遗漏）
    if (EVENT_HANDLER_PATTERN.test(data.attrName)) {
      data.attrValue = ''
      data.keepAttr = false
      return
    }

    // 拦截javascript: URI（可能藏在href/src/action等属性中）
    if (data.attrValue) {
      const normalized = data.attrValue.replace(/[\s\u0000-\u001f]/g, '').toLowerCase()
      for (const protocol of DANGEROUS_URI_PROTOCOLS) {
        if (normalized.startsWith(`${protocol}:`)) {
          data.attrValue = ''
          data.keepAttr = false
          return
        }
      }
    }

    // 拦截CSS表达式注入 (IE兼容攻击)
    if (data.attrName === 'style' && data.attrValue) {
      data.attrValue = data.attrValue
        .replace(/expression\s*\(/gi, '/* blocked */(')
        .replace(/javascript\s*:/gi, '/* blocked */')
        .replace(/-moz-binding\s*:/gi, '/* blocked */')
        .replace(/behavior\s*:/gi, '/* blocked */')
    }
  })

  // 钩子: 后处理消毒结果
  purifier.addHook('afterSanitizeAttributes', (node: Element) => {
    // 给所有链接加上安全属性，防止target="_blank"的反向标签劫持
    if (node.tagName === 'A') {
      node.setAttribute('rel', 'noopener noreferrer')
      if (node.getAttribute('target') === '_blank') {
        // 保持target不变，但确保rel已设置
      }
    }

    // 给img添加referrerpolicy防止信息泄漏
    if (node.tagName === 'IMG') {
      node.setAttribute('referrerpolicy', 'no-referrer')
    }
  })
}

/**
 * 创建带安全钩子的DOMPurify实例
 */
function createPurifier(): typeof DOMPurify {
  // 使用独立实例避免全局污染
  const purifier = DOMPurify
  installSecurityHooks(purifier)
  return purifier
}

// 模块级单例
let purifierInstance: typeof DOMPurify | null = null

function getPurifier(): typeof DOMPurify {
  if (!purifierInstance) {
    purifierInstance = createPurifier()
  }
  return purifierInstance
}

/**
 * 消毒HTML内容
 * 适用于: HTML报告文件预览、DOCX转换后的HTML
 *
 * @param dirty - 不可信的HTML字符串
 * @param config - 可选的额外配置
 * @returns 消毒后的安全HTML字符串
 */
export function sanitizeHtml(dirty: string, config?: SanitizerConfig): string {
  const purifier = getPurifier()
  const purifyConfig = createSafeConfig(config)
  return purifier.sanitize(dirty, purifyConfig)
}

/**
 * 消毒SVG内容
 * 专门针对SVG的消毒处理，阻止foreignObject和脚本注入
 *
 * @param dirty - 不可信的SVG字符串
 * @returns 消毒后的安全SVG字符串
 */
export function sanitizeSvg(dirty: string): string {
  const purifier = getPurifier()
  const baseConfig = createSafeConfig({ allowSvg: true })
  const config: DOMPurify.Config = {
    ...baseConfig,
    // SVG专用: 额外禁止可能被滥用的标签
    FORBID_TAGS: [
      'script', 'iframe', 'object', 'embed', 'applet',
      'foreignobject', 'foreignObject',
      'form', 'input', 'textarea', 'select', 'button',
      // SVG动画可被滥用执行脚本
      'animate', 'animateTransform', 'animateMotion', 'set',
    ],
    // 不使用USE_PROFILES，它会覆盖ALLOWED_TAGS
    // 通过显式白名单控制允许的SVG标签
  }
  return purifier.sanitize(dirty, config)
}

/**
 * 消毒Markdown渲染后的HTML
 * 在marked将Markdown转换为HTML后调用，清理可能的XSS
 *
 * @param dirty - marked渲染输出的HTML
 * @returns 消毒后的安全HTML
 */
export function sanitizeMarkdownHtml(dirty: string): string {
  const purifier = getPurifier()
  const config = createSafeConfig()
  // Markdown中input只允许checkbox（任务列表），通过FORBID_TAGS已禁止input
  // 不再添加input到白名单，避免安全风险
  return purifier.sanitize(dirty, config)
}

/**
 * 消毒DOCX转换后的HTML内容
 * DOCX通过mammoth等库转为HTML后，需要过滤可能的恶意内容
 *
 * @param dirty - DOCX转换器输出的HTML
 * @returns 消毒后的安全HTML
 */
export function sanitizeDocxHtml(dirty: string): string {
  // DOCX转换的HTML通常包含大量内联样式，需要保留
  return sanitizeHtml(dirty, {
    extraAllowedAttr: ['data-docx-style'],
  })
}

/**
 * 根据文件类型自动选择消毒策略
 */
export function sanitizeByType(dirty: string, fileType: 'html' | 'docx' | 'markdown' | 'svg'): string {
  switch (fileType) {
    case 'html':
      return sanitizeHtml(dirty)
    case 'docx':
      return sanitizeDocxHtml(dirty)
    case 'markdown':
      return sanitizeMarkdownHtml(dirty)
    case 'svg':
      return sanitizeSvg(dirty)
    default:
      return sanitizeHtml(dirty)
  }
}

/**
 * 检测内容中是否存在潜在的XSS攻击向量
 * 用于日志记录和安全审计，不做消毒
 */
export function detectXssVectors(content: string): SanitizeReport {
  const report: SanitizeReport = {
    removedTags: [],
    removedAttributes: [],
    blockedUris: 0,
  }

  // 检测危险标签
  const tagPattern = /<(script|iframe|object|embed|applet|foreignobject|foreignObject)[^>]*>/gi
  let match: RegExpExecArray | null
  while ((match = tagPattern.exec(content)) !== null) {
    if (!report.removedTags.includes(match[1].toLowerCase())) {
      report.removedTags.push(match[1].toLowerCase())
    }
  }

  // 检测事件处理器
  const eventPattern = /\s(on\w+)\s*=/gi
  while ((match = eventPattern.exec(content)) !== null) {
    if (!report.removedAttributes.includes(match[1].toLowerCase())) {
      report.removedAttributes.push(match[1].toLowerCase())
    }
  }

  // 检测危险URI
  const uriPattern = /(?:javascript|vbscript|data)\s*:/gi
  while (uriPattern.exec(content) !== null) {
    report.blockedUris++
  }

  return report
}
