/**
 * 文件预览模块类型定义
 */

/** 支持的预览类型 */
export type PreviewType = 'html' | 'docx' | 'markdown' | 'svg';

/** 预览组件通用 Props */
export interface FilePreviewProps {
  /** 文件对象（与 content 二选一） */
  file?: File;
  /** 原始内容字符串（与 file 二选一） */
  content?: string;
  /** 文件 MIME 类型（可选，用于辅助类型检测） */
  mimeType?: string;
}

/** 文件预览状态 */
export interface FilePreviewState {
  /** 消毒后的安全 HTML 内容 */
  sanitizedContent: string;
  /** 是否正在加载 */
  loading: boolean;
  /** 错误信息 */
  error: string | null;
  /** 检测到的预览类型 */
  previewType: PreviewType | null;
}

/** 文件大小限制（字节） */
export const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

/** 文件扩展名到预览类型的映射 */
export const EXTENSION_TYPE_MAP: Record<string, PreviewType> = {
  '.html': 'html',
  '.htm': 'html',
  '.docx': 'docx',
  '.md': 'markdown',
  '.markdown': 'markdown',
  '.svg': 'svg',
};

/** MIME 类型到预览类型的映射 */
export const MIME_TYPE_MAP: Record<string, PreviewType> = {
  'text/html': 'html',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
  'text/markdown': 'markdown',
  'image/svg+xml': 'svg',
};
