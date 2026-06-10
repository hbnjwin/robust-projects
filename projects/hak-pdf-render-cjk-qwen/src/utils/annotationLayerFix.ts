/**
 * 批注层对齐修正
 *
 * 解决批注层（annotation layer）高亮标记与文本层对不齐的问题。
 *
 * 问题描述：
 * 批注高亮的位置基于 PDF 坐标系计算，与文本层使用相同的定位逻辑。
 * 当文本层因 CJK 字体偏移被修正后，批注层也需要同步修正，
 * 否则高亮标记仍指向原始（偏移的）位置，覆盖错误行的内容。
 *
 * 修正策略：
 * 1. 直接修正法：遍历批注层 DOM 元素，应用与文本层相同的偏移量
 * 2. 重映射法：根据批注的 PDF 坐标重新计算屏幕位置
 *
 * 本模块同时支持两种策略，优先使用直接修正法（性能更好）。
 */

import {
  isCjkFont,
  hasCjkContent,
  calculateVerticalCorrection,
} from './cjkFont';
import type { AnnotationLayerCorrectionResult } from '@/types/pdf';

/**
 * 修正批注层元素的垂直定位，使其与文本层对齐
 *
 * @param annotationLayerElement - 批注层容器 DOM 元素
 * @param textContent            - PDF.js 页面的文本内容
 * @param scale                  - 当前缩放比例
 * @param viewportHeight         - 当前视口高度（PDF 坐标系）
 */
export function correctAnnotationLayer(
  annotationLayerElement: HTMLElement,
  textContent: {
    items: Array<{
      str: string;
      fontName?: string;
      transform?: number[];
      height?: number;
    }>;
  },
  scale: number,
  viewportHeight?: number,
): AnnotationLayerCorrectionResult {
  const annotationElements = annotationLayerElement.querySelectorAll<HTMLElement>(
    '.annotationLayer .highlightAnnotation, ' +
    '.annotationLayer .underlineAnnotation, ' +
    '.annotationLayer .squigglyAnnotation, ' +
    '.annotationLayer .strikeoutAnnotation, ' +
    '.annotationLayer .popupAnnotation, ' +
    '[data-annotation-id]',
  );

  const offsets = new Map<string, number>();
  let correctedCount = 0;

  annotationElements.forEach((el) => {
    const annotationId =
      el.getAttribute('data-annotation-id') ||
      el.id ||
      `anon-${correctedCount}`;

    // 计算此批注位置处的文本偏移
    const correction = calculateCorrectionForAnnotation(
      el,
      textContent,
      scale,
      viewportHeight,
    );

    if (Math.abs(correction) < 0.5) return;

    // 应用修正
    applyAnnotationCorrection(el, correction);
    offsets.set(annotationId, correction);
    correctedCount++;
  });

  return { correctedCount, offsets };
}

/**
 * 使用 viewport 和 PDF 坐标重新定位批注元素
 *
 * 更精确的修正方式，直接从 PDF 坐标重新计算屏幕位置。
 *
 * @param annotationLayerElement - 批注层容器
 * @param annotations            - 批注数据数组（PDF 坐标）
 * @param viewport               - PDF.js viewport 对象
 */
export function remapAnnotationPositions(
  annotationLayerElement: HTMLElement,
  annotations: Array<{
    id: string;
    rect: [number, number, number, number];
  }>,
  viewport: {
    convertToViewportPoint: (x: number, y: number) => [number, number];
    height: number;
    scale: number;
  },
): void {
  annotations.forEach((annotation) => {
    const el = annotationLayerElement.querySelector<HTMLElement>(
      `[data-annotation-id="${annotation.id}"]`,
    );
    if (!el) return;

    // 转换 PDF 坐标到屏幕坐标
    const [x1, y1] = viewport.convertToViewportPoint(
      annotation.rect[0],
      annotation.rect[1],
    );
    const [x2, y2] = viewport.convertToViewportPoint(
      annotation.rect[2],
      annotation.rect[3],
    );

    const left = Math.min(x1, x2);
    const top = Math.min(y1, y2);
    const width = Math.abs(x2 - x1);
    const height = Math.abs(y2 - y1);

    el.style.left = `${left}px`;
    el.style.top = `${top}px`;
    el.style.width = `${width}px`;
    el.style.height = `${height}px`;
  });
}

/**
 * 计算某个批注位置处需要的垂直修正量
 *
 * 通过找到与批注元素垂直位置最接近的文本项，
 * 使用该文本项的字体度量来计算修正量。
 */
function calculateCorrectionForAnnotation(
  annotationEl: HTMLElement,
  textContent: {
    items: Array<{
      str: string;
      fontName?: string;
      transform?: number[];
      height?: number;
    }>;
  },
  scale: number,
  _viewportHeight?: number,
): number {
  // 获取批注元素在页面上的垂直位置
  const annotationTop = getAnnotationVerticalPosition(annotationEl);

  // 找到与该位置最接近的 CJK 文本项
  let closestCorrection = 0;
  let minDistance = Infinity;

  for (const item of textContent.items) {
    if (!item.str || !item.fontName) continue;

    const isCjk = isCjkFont(item.fontName) || hasCjkContent(item.str);
    if (!isCjk) continue;

    // 计算文本项的垂直位置
    const textY = getItemVerticalPosition(item, scale);
    const distance = Math.abs(textY - annotationTop);

    if (distance < minDistance) {
      minDistance = distance;
      const fontSize = extractFontSize(item, scale);
      if (fontSize > 0) {
        closestCorrection = calculateVerticalCorrection(
          extractFontAscent(item),
          item.fontName,
          fontSize,
        );
      }
    }
  }

  return closestCorrection;
}

/**
 * 获取批注元素的垂直位置（相对于批注层容器）
 */
function getAnnotationVerticalPosition(el: HTMLElement): number {
  // 尝试从 CSS top 值解析
  const topStyle = el.style.top;
  if (topStyle) {
    const match = topStyle.match(/^([\d.]+)/);
    if (match) return parseFloat(match[1]);
  }

  // 尝试从 transform 解析
  const transform = el.style.transform;
  if (transform) {
    // matrix 格式: matrix(a, b, c, d, e, f)
    const matrixMatch = transform.match(
      /matrix\([^,]+,[^,]+,[^,]+,[^,]+,[^,]+,\s*([^)]+)\)/,
    );
    if (matrixMatch) return parseFloat(matrixMatch[1]);

    // translateY 格式
    const translateYMatch = transform.match(/translateY\(([^)]+)\)/);
    if (translateYMatch) return parseFloat(translateYMatch[1]);
  }

  return el.offsetTop;
}

/**
 * 获取文本项的垂直位置
 */
function getItemVerticalPosition(
  item: { transform?: number[] },
  _scale: number,
): number {
  if (item.transform && item.transform.length >= 6) {
    return item.transform[5]; // f 分量 = Y 平移
  }
  return 0;
}

/**
 * 从文本项中提取字号
 */
function extractFontSize(
  item: { transform?: number[]; height?: number },
  scale: number,
): number {
  if (item.transform && item.transform.length >= 4) {
    return Math.max(
      Math.abs(item.transform[0]),
      Math.abs(item.transform[3]),
    ) * scale;
  }
  return (item.height || 0) * scale;
}

/**
 * 从文本项中提取 ascent 值
 */
function extractFontAscent(
  item: { transform?: number[]; height?: number },
): number {
  if (item.transform && item.transform.length >= 4 && item.height) {
    const scaleY = Math.abs(item.transform[3]);
    if (scaleY > 0) {
      const ascent = item.height / scaleY;
      if (ascent > 0.5 && ascent < 1.5) return ascent;
    }
  }
  return 0.82;
}

/**
 * 对批注元素应用垂直修正
 */
function applyAnnotationCorrection(
  el: HTMLElement,
  correction: number,
): void {
  // 方式 1：修正 top 定位
  const currentTop = el.style.top;
  if (currentTop) {
    const match = currentTop.match(/^([\d.]+)(.*)/);
    if (match) {
      const value = parseFloat(match[1]);
      const unit = match[2] || 'px';
      el.style.top = `${value - correction}${unit}`;
      return;
    }
  }

  // 方式 2：修正 transform
  const transform = el.style.transform;
  if (transform) {
    const matrixMatch = transform.match(
      /matrix\(([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^)]+)\)/,
    );
    if (matrixMatch) {
      const values = matrixMatch.slice(1, 7).map(Number);
      values[5] -= correction;
      el.style.transform = `matrix(${values.join(', ')})`;
      return;
    }
  }

  // 方式 3：追加 translateY
  el.style.transform = `${transform || ''} translateY(${-correction}px)`.trim();
}
