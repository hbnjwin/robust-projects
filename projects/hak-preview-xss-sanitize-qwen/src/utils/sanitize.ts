/**
 * DOMPurify 消毒工具 — 文件预览模块 XSS 安全加固
 *
 * 设计理念：
 * 1. DOMPurify 是 DOM 感知消毒器（非文本转义），保留正常文档结构
 * 2. 分层配置：基础禁令 → 类型专用规则 → 自定义钩子
 * 3. 保留 CSS 样式、表格结构、列表排版，阻断 script/iframe/on*事件/javascript: URI
 */
import DOMPurify from 'dompurify';
import type { PreviewType } from '@/types/preview';

// ============================================================
// 1. 通用危险属性列表（所有预览类型共用）
// ============================================================

/** 所有 on* 事件处理属性 — 全面封禁 */
const DANGEROUS_EVENT_ATTRS = [
  'onabort', 'onafterprint', 'onanimationend', 'onanimationiteration',
  'onanimationstart', 'onbeforeprint', 'onbeforeunload', 'onblur',
  'oncanplay', 'oncanplaythrough', 'onchange', 'onclick', 'oncontextmenu',
  'oncopy', 'oncut', 'ondblclick', 'ondrag', 'ondragend', 'ondragenter',
  'ondragleave', 'ondragover', 'ondragstart', 'ondrop', 'ondurationchange',
  'onemptied', 'onended', 'onerror', 'onfocus', 'onfocusin', 'onfocusout',
  'onfullscreenchange', 'onfullscreenerror', 'ongotpointercapture',
  'onhashchange', 'oninput', 'oninvalid', 'onkeydown', 'onkeypress',
  'onkeyup', 'onlanguagechange', 'onload', 'onloadeddata',
  'onloadedmetadata', 'onloadstart', 'onlostpointercapture',
  'onmessage', 'onmousedown', 'onmouseenter', 'onmouseleave',
  'onmousemove', 'onmouseout', 'onmouseover', 'onmouseup',
  'onmousewheel', 'onoffline', 'ononline', 'onopen', 'onpagehide',
  'onpageshow', 'onpaste', 'onpause', 'onplay', 'onplaying',
  'onpointercancel', 'onpointerdown', 'onpointerenter',
  'onpointerleave', 'onpointerlockchange', 'onpointerlockerror',
  'onpointermove', 'onpointerout', 'onpointerover', 'onpointerup',
  'onpopstate', 'onprogress', 'onratechange', 'onreadystatechange',
  'onrejectionhandled', 'onreset', 'onresize', 'onscroll',
  'onsearch', 'onseeked', 'onseeking', 'onselect', 'onselectionchange',
  'onselectstart', 'onshow', 'onstalled', 'onstorage', 'onsubmit',
  'onsuspend', 'ontimeupdate', 'ontoggle', 'ontouchcancel',
  'ontouchend', 'ontouchmove', 'ontouchstart', 'ontransitioncancel',
  'ontransitionend', 'ontransitionrun', 'ontransitionstart',
  'onunhandledrejection', 'onunload', 'onvolumechange', 'onwaiting',
  'onwheel',
];

/** 危险的 URI 协议 */
const DANGEROUS_URI_PROTOCOLS = [
  'javascript:',
  'vbscript:',
  'data:text/html',
  'data:text/javascript',
  'data:application/javascript',
  'data:application/x-javascript',
];

/** 危险的 CSS 属性/值模式 */
const DANGEROUS_CSS_PATTERNS = [
  /expression\s*\(/i,
  /behavior\s*:/i,
  /-moz-binding\s*:/i,
  /url\s*\(\s*['"]?\s*javascript:/i,
  /url\s*\(\s*['"]?\s*vbscript:/i,
  /url\s*\(\s*['"]?\s*data\s*:\s*text\/html/i,
  /@import/i,
  /-o-link\s*:/i,
  /-o-link-source\s*:/i,
];

/** URI 类属性列表 — 需要协议校验 */
const URI_ATTRS = new Set([
  'href', 'src', 'action', 'formaction', 'poster', 'cite',
  'background', 'longdesc', 'usemap', 'xlink:href',
]);

// ============================================================
// 2. 自定义钩子 — CSS 清洗 + URI 协议校验
// ============================================================

/**
 * 安装 DOMPurify 自定义钩子（只需安装一次）
 */
function installHooks(): void {
  // 清除旧钩子防止重复注册
  DOMPurify.removeHook('beforeSanitizeAttributes');
  DOMPurify.removeHook('afterSanitizeAttributes');

  /**
   * 钩子1：消毒属性之前 — 清洗 style 属性中的危险 CSS
   */
  DOMPurify.addHook('beforeSanitizeAttributes', (node: Element) => {
    if (node instanceof HTMLElement && node.hasAttribute('style')) {
      const style = node.getAttribute('style') || '';
      const cleaned = cleanCssValue(style);
      if (cleaned !== style) {
        if (cleaned.trim()) {
          node.setAttribute('style', cleaned);
        } else {
          node.removeAttribute('style');
        }
      }
    }
  });

  /**
   * 钩子2：消毒属性之后 — 校验 URI 协议
   * DOMPurify 默认会处理 javascript: 但这里做双重保险
   */
  DOMPurify.addHook('afterSanitizeAttributes', (node: Element) => {
    for (const attr of URI_ATTRS) {
      const value = node.getAttribute(attr);
      if (value && isDangerousUri(value)) {
        node.removeAttribute(attr);
      }
    }

    // SVG <use> 标签：仅允许本地 #fragment 引用
    if (node.tagName.toLowerCase() === 'use') {
      const href = node.getAttribute('xlink:href') || node.getAttribute('href');
      if (href && !href.startsWith('#')) {
        node.removeAttribute('xlink:href');
        node.removeAttribute('href');
      }
    }

    // SVG <a> 标签：清洗 xlink:href
    if (node.tagName.toLowerCase() === 'a') {
      const xlinkHref = node.getAttribute('xlink:href');
      if (xlinkHref && isDangerousUri(xlinkHref)) {
        node.removeAttribute('xlink:href');
      }
    }
  });
}

/**
 * 清洗 CSS 值 — 移除危险属性/值
 */
function cleanCssValue(css: string): string {
  let cleaned = css;
  for (const pattern of DANGEROUS_CSS_PATTERNS) {
    // 移除匹配的规则片段（属性:值对）
    cleaned = cleaned.replace(
      new RegExp(`[^;]*${pattern.source}[^;]*;?`, 'gi'),
      '',
    );
  }
  return cleaned;
}

/**
 * 检测 URI 是否包含危险协议
 */
function isDangerousUri(uri: string): boolean {
  const normalized = uri.trim().toLowerCase().replace(/[\s\x00-\x1f]/g, '');
  return DANGEROUS_URI_PROTOCOLS.some(
    (protocol) => normalized.startsWith(protocol),
  );
}

// 安装钩子（模块加载时自动执行）
installHooks();

// ============================================================
// 3. 类型专用消毒配置
// ============================================================

/**
 * HTML 报告消毒 — 宽允许列表（报告需要丰富排版）
 *
 * 使用 FORBID_TAGS 模式（denylist），允许大多数标签，只禁止危险标签。
 * 这样可以保留报告中的所有排版元素（表格、列表、样式等）。
 */
export function sanitizeHtml(dirty: string): string {
  return DOMPurify.sanitize(dirty, {
    // 禁止的危险标签
    FORBID_TAGS: [
      'script', 'iframe', 'object', 'embed', 'applet',
      'form', 'input', 'button', 'textarea', 'select',
      'base', 'meta', 'link', 'noscript',
    ],
    // 额外允许的属性（DOMPurify 默认可能不包含）
    ADD_ATTR: [
      'colspan', 'rowspan', 'border', 'cellpadding', 'cellspacing',
      'width', 'height', 'valign', 'align', 'bgcolor', 'scope',
      'summary', 'frame', 'rules', 'start', 'type', 'reversed',
      'target', 'rel', 'download', 'tabindex', 'title',
      'data-language', 'data-line',
    ],
    // 允许 <style> 标签（CSS 样式保留）
    ADD_TAGS: ['style'],
    // 禁止 data-* 属性防止数据泄露
    ALLOW_DATA_ATTR: false,
    // 保留 aria 属性（无障碍）
    ALLOW_ARIA_ATTR: true,
    // 允许未知协议？不允许
    ALLOW_UNKNOWN_PROTOCOLS: false,
    // 允许的 URI 协议
    ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
    // 事件属性全面禁止
    FORBID_ATTR: DANGEROUS_EVENT_ATTRS,
    // 保留注释（某些报告用注释做标记）
    // 默认已移除注释，这里保持默认
  });
}

/**
 * DOCX 转 HTML 消毒 — 基于文档输出标签的 allowlist
 *
 * DOCX 转换工具（如 mammoth.js）输出可预测的标签集合，
 * 使用 allowlist 模式更精确地控制允许的内容。
 */
export function sanitizeDocx(dirty: string): string {
  return DOMPurify.sanitize(dirty, {
    // DOCX 转换产出的安全标签集合
    ALLOWED_TAGS: [
      // 文档结构
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'p', 'br', 'hr', 'div', 'span',
      // 列表
      'ul', 'ol', 'li', 'dl', 'dt', 'dd',
      // 表格
      'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td',
      'colgroup', 'col', 'caption',
      // 行内格式
      'strong', 'b', 'em', 'i', 'u', 's', 'del', 'ins',
      'sub', 'sup', 'small', 'mark', 'abbr',
      // 代码
      'pre', 'code',
      // 链接和图片
      'a', 'img',
      // 其他
      'blockquote', 'figure', 'figcaption',
      // 样式标签（DOCX 转换可能带内嵌样式）
      'style',
    ],
    // DOCX 转换产出的安全属性集合
    ALLOWED_ATTR: [
      // 通用
      'class', 'style', 'id', 'title', 'lang', 'dir',
      // 表格
      'colspan', 'rowspan', 'border', 'cellpadding', 'cellspacing',
      'width', 'height', 'valign', 'align', 'bgcolor', 'scope',
      'frame', 'rules',
      // 链接
      'href', 'target', 'rel',
      // 图片
      'src', 'alt',
      // 列表
      'start', 'type', 'reversed', 'value',
    ],
    // 禁止所有 on* 事件
    FORBID_ATTR: DANGEROUS_EVENT_ATTRS,
    // 禁止 data 属性
    ALLOW_DATA_ATTR: false,
    // 不允许未知协议
    ALLOW_UNKNOWN_PROTOCOLS: false,
    ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
  });
}

/**
 * Markdown 渲染 HTML 消毒 — 中等允许列表
 *
 * marked 库输出的 HTML + 可能的内联 HTML（Markdown 规范允许）。
 * 禁止 iframe 防止代码块中的嵌入式攻击。
 */
export function sanitizeMarkdown(dirty: string): string {
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: [
      // Markdown 标准输出
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'p', 'br', 'hr',
      // 行内
      'strong', 'em', 'del', 'code', 'a', 'img',
      // 代码块
      'pre',
      // 列表
      'ul', 'ol', 'li',
      // 表格（GFM 扩展）
      'table', 'thead', 'tbody', 'tr', 'th', 'td',
      // 引用
      'blockquote',
      // 行内容器
      'span', 'div', 'sup', 'sub',
      // 定义列表
      'dl', 'dt', 'dd',
      // 格式
      'b', 'i', 'u', 's', 'mark', 'abbr',
      // 其他
      'figure', 'figcaption', 'details', 'summary',
    ],
    ALLOWED_ATTR: [
      // 通用
      'class', 'style', 'id', 'title', 'lang', 'dir',
      // 表格
      'colspan', 'rowspan', 'align', 'width', 'height',
      // 链接
      'href', 'target', 'rel',
      // 图片
      'src', 'alt', 'width', 'height',
      // 代码高亮
      'data-language',
      // details
      'open',
    ],
    // 禁止的危险标签（特别是 iframe）
    FORBID_TAGS: [
      'script', 'iframe', 'object', 'embed', 'form',
      'input', 'button', 'textarea', 'select',
      'base', 'meta', 'link', 'style',
    ],
    FORBID_ATTR: DANGEROUS_EVENT_ATTRS,
    ALLOW_DATA_ATTR: false,
    ALLOW_UNKNOWN_PROTOCOLS: false,
    ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp|data:image):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
  });
}

/**
 * SVG 消毒 — SVG 专用配置
 *
 * SVG 是重大 XSS 向量：
 * - <script> 在 SVG 上下文中可执行
 * - <foreignObject> 可嵌入任意 HTML（含 script）
 * - <use xlink:href> 可引用外部资源
 * - on* 事件处理在所有 SVG 元素上有效
 *
 * 策略：使用 DOMPurify SVG profile + 封杀 foreignObject + URI 校验
 */
export function sanitizeSvg(dirty: string): string {
  return DOMPurify.sanitize(dirty, {
    // 使用 DOMPurify 的 SVG profile
    USE_PROFILES: { svg: true, svgFilters: true },
    // 封杀 foreignObject — 它可以嵌入任意 HTML 和脚本
    FORBID_TAGS: [
      'foreignObject',
      'script',
    ],
    // 封杀所有 on* 事件属性
    FORBID_ATTR: DANGEROUS_EVENT_ATTRS,
    // 额外允许的安全 SVG 属性
    ADD_ATTR: [
      'viewBox', 'preserveAspectRatio', 'xmlns', 'xmlns:xlink',
      'fill', 'stroke', 'stroke-width', 'stroke-dasharray',
      'stroke-linecap', 'stroke-linejoin', 'stroke-opacity',
      'fill-opacity', 'fill-rule', 'clip-rule',
      'opacity', 'transform', 'd', 'cx', 'cy', 'r', 'rx', 'ry',
      'x', 'y', 'x1', 'y1', 'x2', 'y2',
      'width', 'height', 'points', 'offset',
      'stop-color', 'stop-opacity',
      'gradientUnits', 'gradientTransform',
      'patternUnits', 'patternTransform',
      'spreadMethod', 'markerWidth', 'markerHeight',
      'markerUnits', 'orient', 'refX', 'refY',
      'text-anchor', 'dominant-baseline', 'font-family',
      'font-size', 'font-weight', 'font-style',
      'letter-spacing', 'word-spacing',
      'class', 'style', 'id', 'clip-path', 'mask',
      'filter', 'color-interpolation-filters',
      'stdDeviation', 'in', 'in2', 'result', 'mode',
      'type', 'values', 'baseFrequency', 'numOctaves',
      'seed', 'stitchTiles', 'operator',
    ],
    // 不允许 data 属性
    ALLOW_DATA_ATTR: false,
    // 不允许未知协议
    ALLOW_UNKNOWN_PROTOCOLS: false,
  });
}

// ============================================================
// 4. 统一消毒入口
// ============================================================

/** 消毒函数映射表 */
const SANITIZERS: Record<PreviewType, (dirty: string) => string> = {
  html: sanitizeHtml,
  docx: sanitizeDocx,
  markdown: sanitizeMarkdown,
  svg: sanitizeSvg,
};

/**
 * 根据预览类型自动选择消毒策略
 * @param dirty 原始 HTML 内容
 * @param type 预览类型
 * @returns 消毒后的安全 HTML
 */
export function sanitize(dirty: string, type: PreviewType): string {
  const sanitizer = SANITIZERS[type];
  if (!sanitizer) {
    // 未知类型：最严格消毒（只保留纯文本）
    return DOMPurify.sanitize(dirty, { ALLOWED_TAGS: [] });
  }
  return sanitizer(dirty);
}
