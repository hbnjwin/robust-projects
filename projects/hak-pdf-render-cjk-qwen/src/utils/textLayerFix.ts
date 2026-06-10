/**
 * 文本层垂直偏移修正
 *
 * 解决 PDF.js 文本层（text layer）中 CJK 字体渲染位置向下偏移的问题。
 *
 * 问题描述：
 * PDF.js 的文本层通过 CSS transform: matrix() 定位每个文本块。
 * matrix 中的 e（translateX）和 f（translateY）基于 PDF 坐标系计算。
 * 对于 CJK 字体，PDF 内嵌的 ascent 值（通常 0.80-0.85）小于浏览器
 * 实际渲染时使用的 ascent 值（约 0.88），导致文本视觉上向下偏移。
 *
 * 修正方式：
 * 遍历文本层 DOM 元素，从 PDF.js 的 textContent 获取每个文本项的
 * 字体度量，计算偏移差值，修正 transform matrix 的 translateY 分量。
 */

import {
  isCjkFont,
  hasCjkContent,
  calculateVerticalCorrection,
} from './cjkFont';
import type { TextLayerCorrectionResult } from '@/types/pdf';

/**
 * 修正文本层中 CJK 字体的垂直偏移
 *
 * @param textLayerElement - 文本层容器 DOM 元素
 * @param textContent      - PDF.js 页面的文本内容
 * @param scale            - 当前缩放比例
 * @param cjkOnly          - 是否仅修正 CJK 文本（默认 true）
 * @returns 修正结果统计
 */
export function correctTextLayerOffset(
  textLayerElement: HTMLElement,
  textContent: {
    items: Array<{
      str: string;
      fontName?: string;
      transform?: number[];
      height?: number;
      width?: number;
    }>;
  },
  scale: number = 1,
  cjkOnly: boolean = true,
): TextLayerCorrectionResult {
  const textDivs = textLayerElement.querySelectorAll<HTMLElement>(
    '.textLayer span, [role="presentation"] > span',
  );

  let correctedCount = 0;
  let totalOffset = 0;
  let hasCjkFonts = false;

  textDivs.forEach((div, index) => {
    const item = textContent.items[index];
    if (!item || !item.str) return;

    // 判断是否需要修正
    const fontName = item.fontName || '';
    const isCjk = isCjkFont(fontName) || hasCjkContent(item.str);

    if (cjkOnly && !isCjk) return;

    if (isCjk) hasCjkFonts = true;

    // 获取字号：优先从 transform 矩阵提取，否则使用 height
    const fontSize = extractFontSize(item, scale);
    if (fontSize <= 0) return;

    // 获取 PDF 内嵌的 ascent 值
    const pdfAscent = extractFontAscent(item);

    // 计算垂直修正量（正数 = 向上移动）
    const correction = calculateVerticalCorrection(
      pdfAscent,
      fontName,
      fontSize,
    );

    if (Math.abs(correction) < 0.5) return; // 阈值以下跳过

    // 应用修正到 transform matrix
    const currentTransform = div.style.transform;
    const newTransform = applyTransformCorrection(currentTransform, correction);

    if (newTransform !== currentTransform) {
      div.style.transform = newTransform;
      correctedCount++;
      totalOffset += Math.abs(correction);
    }
  });

  return {
    correctedCount,
    averageOffset: correctedCount > 0 ? totalOffset / correctedCount : 0,
    hasCjkFonts,
  };
}

/**
 * 重新修正文本层（缩放变化后调用）
 *
 * 先移除旧修正、再重新计算并应用新修正。
 */
export function reCorrectTextLayer(
  textLayerElement: HTMLElement,
  textContent: {
    items: Array<{
      str: string;
      fontName?: string;
      transform?: number[];
      height?: number;
      width?: number;
    }>;
  },
  scale: number,
): TextLayerCorrectionResult {
  // 先还原到原始位置
  resetTextLayerTransforms(textLayerElement);

  // 重新计算并应用修正
  return correctTextLayerOffset(textLayerElement, textContent, scale, true);
}

/**
 * 重置文本层所有元素的 transform 到未修正状态
 */
export function resetTextLayerTransforms(textLayerElement: HTMLElement): void {
  const textDivs = textLayerElement.querySelectorAll<HTMLElement>(
    '.textLayer span, [role="presentation"] > span',
  );

  textDivs.forEach((div) => {
    // 移除我们添加的修正标记
    div.removeAttribute('data-cjk-corrected');
    // transform 保持不变（因为每次都是重新计算的）
  });
}

/**
 * 从文本项的 transform 矩阵或 height 中提取字号
 */
function extractFontSize(
  item: {
    transform?: number[];
    height?: number;
  },
  scale: number,
): number {
  if (item.transform && item.transform.length >= 4) {
    // transform 格式: [a, b, c, d, e, f]
    // |a| 和 |d| 分别代表 X/Y 方向的缩放因子
    // 字号 = max(|a|, |d|) * scale
    const scaleX = Math.abs(item.transform[0]);
    const scaleY = Math.abs(item.transform[3]);
    return Math.max(scaleX, scaleY) * scale;
  }

  if (item.height) {
    return item.height * scale;
  }

  return 0;
}

/**
 * 从文本项中提取 PDF 内嵌的 ascent 值
 *
 * PDF.js 的 TextItem 不直接暴露 ascent，但可以通过
 * transform 矩阵推算：
 *   文本块高度 = |d| * ascent
 *   其中 |d| 是 Y 方向缩放因子（约等于字号）
 */
function extractFontAscent(
  item: {
    transform?: number[];
    height?: number;
  },
): number {
  if (item.transform && item.transform.length >= 4 && item.height) {
    const scaleY = Math.abs(item.transform[3]);
    if (scaleY > 0) {
      const ascent = item.height / scaleY;
      // 合理范围校验
      if (ascent > 0.5 && ascent < 1.5) {
        return ascent;
      }
    }
  }

  // CJK 字体的典型 PDF ascent 值（通常偏低）
  return 0.82;
}

/**
 * 在 CSS transform matrix 字符串上应用垂直修正
 *
 * 输入格式: matrix(a, b, c, d, e, f)
 * 修正 f 分量（Y 轴平移）减去 correction 像素
 */
function applyTransformCorrection(
  transformStr: string,
  correction: number,
): string {
  // 匹配 matrix(a, b, c, d, e, f)
  const match = transformStr.match(
    /matrix\(([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^)]+)\)/,
  );

  if (match) {
    const values = match.slice(1, 7).map(Number);
    // f 分量（Y 平移）减去修正量（向上移动 = 减小 translateY）
    values[5] -= correction;
    return `matrix(${values.join(', ')})`;
  }

  // 回退：尝试 translate 格式
  const translateMatch = transformStr.match(
    /translate\(([^,]+)px,\s*([^)]+)px\)/,
  );
  if (translateMatch) {
    const x = parseFloat(translateMatch[1]);
    const y = parseFloat(translateMatch[2]) - correction;
    return `translate(${x}px, ${y}px)`;
  }

  // 无法解析时，追加 translate
  if (transformStr) {
    return `${transformStr} translateY(${-correction}px)`;
  }
  return `translateY(${-correction}px)`;
}
