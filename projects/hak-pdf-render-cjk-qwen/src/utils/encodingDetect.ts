/**
 * GB18030 / GBK 编码兼容工具
 *
 * 解决 2018 年之前的老报告使用 GB18030 编码时，PDF 预览中
 * 中文显示为方块乱码（tofu）的问题。
 *
 * 根因分析：
 * 1. PDF.js 默认的 CMap 配置未完整覆盖 GB18030 编码映射
 * 2. 老报告中的 CIDFont 可能缺少完整的 ToUnicode 映射表
 * 3. 嵌入字体子集可能不包含所有需要的字形
 *
 * 解决方案：
 * 1. 正确配置 CMap 资源路径，确保 GBK-EUC-H/GBK2K-EUC-H 等映射可用
 * 2. 启用 standardFontData 以支持未嵌入字体的回退
 * 3. 提供文档级别的编码检测，用于 UI 提示
 */

/**
 * 检测 PDF 文档是否使用 GB18030/GBK 编码
 *
 * 通过扫描所有页面的文本项，检测字体名称和内容特征来判断。
 *
 * @param pdfDocument - PDF.js 文档对象
 * @returns 是否疑似使用 GB18030/GBK 编码
 */
export async function detectGb18030Usage(
  pdfDocument: {
    numPages: number;
    getPage: (n: number) => Promise<{
      getTextContent: () => Promise<{
        items: Array<{ str: string; fontName?: string }>;
      }>;
    }>;
  },
): Promise<{
  usesGb18030: boolean;
  gbFonts: string[];
  sampleText: string;
}> {
  const gbFontPatterns = [
    'gbk', 'gb18030', 'gb2312', 'gbt',
    'cjk', 'chinese', 'simsun', 'simhei',
    'fangsong', 'kaiti', 'nsimsun',
    'adobesongstd', 'adobeheitistd',
    'adobekaitistd', 'adobefangsongstd',
  ];

  const gbFonts: string[] = [];
  let hasHighByteContent = false;
  let sampleText = '';

  // 扫描前 3 页（避免全量扫描的性能开销）
  const scanPages = Math.min(3, pdfDocument.numPages);

  for (let i = 1; i <= scanPages; i++) {
    const page = await pdfDocument.getPage(i);
    const textContent = await page.getTextContent();

    for (const item of textContent.items) {
      // 检测字体名称
      if (item.fontName) {
        const fontLower = item.fontName.toLowerCase();
        if (gbFontPatterns.some((p) => fontLower.includes(p))) {
          if (!gbFonts.includes(item.fontName)) {
            gbFonts.push(item.fontName);
          }
        }
      }

      // 检测是否包含 CJK 字符
      if (item.str && /[\u4E00-\u9FFF]/.test(item.str)) {
        hasHighByteContent = true;
        if (!sampleText) {
          sampleText = item.str.substring(0, 50);
        }
      }
    }
  }

  return {
    usesGb18030: gbFonts.length > 0 || hasHighByteContent,
    gbFonts,
    sampleText,
  };
}

/**
 * 构建 PDF.js 的 CMap 和标准字体配置
 *
 * 确保 GB18030 编码的 PDF 能正确解码中文字符。
 *
 * @param cMapUrl           - CMap 资源目录 URL
 * @param standardFontDataUrl - 标准字体数据目录 URL
 * @returns PDF.js getDocument 所需的配置项
 */
export function buildCMapConfig(
  cMapUrl: string,
  standardFontDataUrl: string,
): {
  cMapUrl: string;
  cMapPacked: boolean;
  standardFontDataUrl: string;
  isEvalSupported: boolean;
} {
  return {
    cMapUrl,
    cMapPacked: true,
    standardFontDataUrl,
    isEvalSupported: false,
  };
}

/**
 * 检测文本内容是否为乱码（方块字符或未解码的占位符）
 *
 * 用于在 UI 层提示用户当前页面可能存在编码问题。
 */
export function isGarbledText(text: string): boolean {
  if (!text) return false;

  // 方块字符 U+25A0-U+25FF
  const replacementCount = (text.match(/[\u25A0-\u25FF]/g) || []).length;
  // 替换字符 U+FFFD
  const fffdCount = (text.match(/\uFFFD/g) || []).length;
  // 私有区字符 U+E000-U+F8FF
  const puaCount = (text.match(/[\uE000-\uF8FF]/g) || []).length;

  const totalSuspicious = replacementCount + fffdCount + puaCount;
  const totalChars = text.replace(/\s/g, '').length;

  if (totalChars === 0) return false;

  // 超过 30% 的字符为可疑字符，判定为乱码
  return totalSuspicious / totalChars > 0.3;
}

/**
 * 获取 pdfjs-dist 包自带的 CMap 资源路径
 *
 * 优先使用本地打包的 CMap，避免网络依赖。
 * 回退到 CDN 路径。
 */
export function getDefaultCMapUrl(): string {
  try {
    return new URL('pdfjs-dist/cmaps/', import.meta.url).href;
  } catch {
    return 'https://cdn.jsdelivr.net/npm/pdfjs-dist@4.4.168/cmaps/';
  }
}

/**
 * 获取 pdfjs-dist 包自带的标准字体数据路径
 */
export function getDefaultStandardFontDataUrl(): string {
  try {
    return new URL('pdfjs-dist/standard_fonts/', import.meta.url).href;
  } catch {
    return 'https://cdn.jsdelivr.net/npm/pdfjs-dist@4.4.168/standard_fonts/';
  }
}
