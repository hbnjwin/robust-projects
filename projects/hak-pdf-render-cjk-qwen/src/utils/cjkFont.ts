/**
 * CJK 字体检测与字体度量工具
 *
 * 解决中英文混排 PDF 中，CJK 字体在浏览器渲染时 ascent/descent 比例
 * 与 PDF 内嵌字体度量不一致，导致文本层垂直偏移约半行的问题。
 *
 * 原理：
 * PDF 文本定位使用字体内嵌的 ascent 值来确定基线位置，
 * 但浏览器渲染 CJK 字体时实际使用的 ascent 值往往不同。
 * 对于大多数 CJK 字体，PDF 中的 ascent 约为 0.80-0.88，
 * 而浏览器 CSS 渲染使用的 ascent 约为 0.88-0.92，
 * 导致 CJK 字符在视觉上向下偏移。
 */

/** CJK 字体的 ascent/descent 度量 */
export interface FontMetrics {
  /** 上升高度比例（从基线到顶部） */
  ascent: number;
  /** 下降深度比例（从基线到底部，正数） */
  descent: number;
  /** 行高比例 */
  lineGap: number;
}

/** 已知 CJK 字体名称关键词 → 正确度量的映射 */
const CJK_FONT_METRICS: Record<string, FontMetrics> = {
  SimSun: { ascent: 0.88, descent: 0.12, lineGap: 0 },
  'Noto Serif CJK': { ascent: 0.88, descent: 0.12, lineGap: 0 },
  'Noto Sans CJK': { ascent: 0.88, descent: 0.12, lineGap: 0 },
  'Source Han Sans': { ascent: 0.88, descent: 0.12, lineGap: 0 },
  'Source Han Serif': { ascent: 0.88, descent: 0.12, lineGap: 0 },
  'Microsoft YaHei': { ascent: 0.90, descent: 0.10, lineGap: 0 },
  STSong: { ascent: 0.86, descent: 0.14, lineGap: 0 },
  STHeiti: { ascent: 0.88, descent: 0.12, lineGap: 0 },
  FangSong: { ascent: 0.88, descent: 0.12, lineGap: 0 },
  KaiTi: { ascent: 0.88, descent: 0.12, lineGap: 0 },
  Hei: { ascent: 0.88, descent: 0.12, lineGap: 0 },
  Ming: { ascent: 0.88, descent: 0.12, lineGap: 0 },
  Song: { ascent: 0.88, descent: 0.12, lineGap: 0 },
  AdobeSongStd: { ascent: 0.88, descent: 0.12, lineGap: 0 },
  AdobeHeitiStd: { ascent: 0.88, descent: 0.12, lineGap: 0 },
  AdobeKaitiStd: { ascent: 0.88, descent: 0.12, lineGap: 0 },
  AdobeFangsongStd: { ascent: 0.88, descent: 0.12, lineGap: 0 },
  DengXian: { ascent: 0.88, descent: 0.12, lineGap: 0 },
  'WenQuanYi': { ascent: 0.88, descent: 0.12, lineGap: 0 },
  'PingFang': { ascent: 0.88, descent: 0.12, lineGap: 0 },
  'Hiragino Sans GB': { ascent: 0.88, descent: 0.12, lineGap: 0 },
};

/** 标准 CJK 字体的默认度量（当无法精确匹配时使用） */
const DEFAULT_CJK_METRICS: FontMetrics = {
  ascent: 0.88,
  descent: 0.12,
  lineGap: 0,
};

/**
 * 检测字体名称是否为 CJK 字体
 *
 * 匹配规则：
 * 1. 与已知 CJK 字体名称做子串匹配（不区分大小写）
 * 2. 检测 PDF 标准 CJK 字体前缀（MSung, MHei, STSong 等）
 */
export function isCjkFont(fontName: string): boolean {
  const normalized = fontName.toLowerCase().replace(/[#_+\-]/g, ' ');

  // 精确匹配已知字体
  for (const key of Object.keys(CJK_FONT_METRICS)) {
    if (normalized.includes(key.toLowerCase())) {
      return true;
    }
  }

  // PDF 中常见的 CJK CID 字体前缀
  const cjkPrefixes = [
    'msung', 'mhei', 'stsong', 'stheiti', 'stkaiti',
    'adobesong', 'adobehei', 'adobekai', 'adobefang',
    'dengxian', 'fangsong', 'kaiti', 'simhei',
    'simsun', 'nsimsun', 'youyuan', 'liushu',
  ];
  return cjkPrefixes.some((prefix) => normalized.includes(prefix));
}

/**
 * 检测文本内容是否包含 CJK 字符
 *
 * 覆盖 Unicode 范围：
 * - U+2E80-U+2EFF: CJK 部首补充
 * - U+3000-U+303F: CJK 符号和标点
 * - U+3400-U+4DBF: CJK 统一汉字扩展 A
 * - U+4E00-U+9FFF: CJK 统一汉字（基本区）
 * - U+F900-U+FAFF: CJK 兼容汉字
 * - U+20000-U+2A6DF: CJK 扩展 B
 */
export function hasCjkContent(text: string): boolean {
  return /[\u2E80-\u2EFF\u3000-\u303F\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]/.test(text);
}

/**
 * 获取 CJK 字体的预期度量值
 *
 * 根据字体名称匹配已知度量，未匹配时返回默认 CJK 度量。
 */
export function getCjkFontMetrics(fontName: string): FontMetrics {
  const normalized = fontName.toLowerCase().replace(/[#_+\-]/g, ' ');

  for (const [key, metrics] of Object.entries(CJK_FONT_METRICS)) {
    if (normalized.includes(key.toLowerCase())) {
      return metrics;
    }
  }

  return DEFAULT_CJK_METRICS;
}

/**
 * 计算 CJK 文本元素的垂直偏移修正量（像素）
 *
 * @param fontAscent - PDF 内嵌字体的 ascent 值
 * @param fontName   - 字体名称
 * @param fontSize   - 字号（px）
 * @returns 需要向上修正的像素值（正数表示向上移动）
 *
 * 计算原理：
 * PDF 使用 fontAscent * fontSize 确定基线到顶部的距离。
 * 浏览器渲染 CJK 字体时使用 correctAscent * fontSize。
 * 差值即为需要修正的偏移量。
 */
export function calculateVerticalCorrection(
  fontAscent: number,
  fontName: string,
  fontSize: number,
): number {
  const correctMetrics = getCjkFontMetrics(fontName);
  const correctAscent = correctMetrics.ascent;

  // 正数表示需要向上移动（PDF ascent < 实际 ascent → 文本偏下）
  const delta = correctAscent - fontAscent;
  return delta * fontSize;
}
