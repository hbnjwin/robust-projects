/**
 * PDF 预览相关类型定义
 *
 * 覆盖批注、高亮、渲染配置及页面视图等核心数据结构。
 */

/** 批注类型枚举 */
export enum AnnotationType {
  HIGHLIGHT = 'highlight',
  UNDERLINE = 'underline',
  STRIKETHROUGH = 'strikethrough',
  NOTE = 'note',
  RECTANGLE = 'rectangle',
}

/** PDF 批注数据 */
export interface PdfAnnotation {
  /** 批注唯一标识 */
  id: string;
  /** 批注类型 */
  type: AnnotationType;
  /** 所在页码（从 1 开始） */
  page: number;
  /** PDF 坐标系下的矩形区域 [x1, y1, x2, y2] */
  rect: [number, number, number, number];
  /** 高亮颜色（CSS 色值） */
  color: string;
  /** 批注内容文本 */
  content: string;
  /** 创建时间 */
  createdAt?: string;
  /** 批注作者 */
  author?: string;
}

/** 高亮标记 */
export interface PdfHighlight {
  id: string;
  page: number;
  /** PDF 坐标系下的矩形区域 */
  rect: [number, number, number, number];
  color: string;
  /** 关联的批注 ID */
  annotationId?: string;
}

/** CJK 字体修正选项 */
export interface CjkCorrectionOptions {
  /** 是否启用 CJK 字体偏移修正，默认 true */
  enabled: boolean;
  /** 垂直偏移修正系数（相对于字号），默认 0.15 */
  verticalOffsetFactor: number;
  /** 仅修正包含 CJK 字符的文本元素，默认 true */
  cjkOnly: boolean;
}

/** 文本层修正选项 */
export interface TextLayerOptions {
  /** 缩放比例变化时是否自动重新修正，默认 true */
  autoCorrectOnZoom: boolean;
  /** 最小修正阈值（px），小于此值跳过修正，默认 0.5 */
  minCorrectionThreshold: number;
}

/** GB18030 / 编码兼容选项 */
export interface EncodingCompatOptions {
  /** 是否启用 GB18030 编码兼容，默认 true */
  enabled: boolean;
  /** CMap 资源 URL（pdfjs-dist 的 cmaps 目录） */
  cMapUrl: string;
  /** 是否以打包格式加载 CMap，默认 true */
  isEvalSupported: boolean;
  /** 标准字体目录 URL */
  standardFontDataUrl: string;
}

/** PDF 渲染完整配置 */
export interface PdfRenderOptions {
  cjkCorrection: CjkCorrectionOptions;
  textLayer: TextLayerOptions;
  encoding: EncodingCompatOptions;
}

/** 页面视图信息 */
export interface PageView {
  pageNumber: number;
  viewport: {
    width: number;
    height: number;
    scale: number;
  };
}

/** 渲染完成事件携带的数据 */
export interface RenderCompleteEvent {
  page: number;
  scale: number;
  canvas: HTMLCanvasElement;
}

/** 文本层修正结果 */
export interface TextLayerCorrectionResult {
  /** 修正的文本元素数量 */
  correctedCount: number;
  /** 应用的平均偏移量（px） */
  averageOffset: number;
  /** 是否包含 CJK 字体 */
  hasCjkFonts: boolean;
}

/** 批注层修正结果 */
export interface AnnotationLayerCorrectionResult {
  /** 修正的批注元素数量 */
  correctedCount: number;
  /** 修正的偏移量映射 */
  offsets: Map<string, number>;
}
