/**
 * PDF报告下载工具模块
 *
 * 修复三个核心问题:
 * 1. 文件名中文乱码 - 正确解析RFC 5987 UTF-8编码的Content-Disposition header
 * 2. 大文件内存溢出 - 使用流式写入磁盘替代Blob全量加载内存
 * 3. 网络中断无提示 - 完整的错误处理、超时检测与用户反馈机制
 */

// ============ 配置常量 ============

const DEFAULT_CHUNK_TIMEOUT_MS = 30000; // 30秒无数据视为网络中断
const DEFAULT_RETRY_COUNT = 0; // 默认不重试(大文件不适合自动重试)
const DEFAULT_MIME_TYPE = 'application/pdf';

// ============ Bug 1 修复: RFC 5987 UTF-8 文件名解析 ============

/**
 * 从Content-Disposition header中解析文件名
 *
 * 支持两种格式:
 *   - filename*=UTF-8''%E5%93%88... (RFC 5987, 优先使用)
 *   - filename="..." (普通格式, 回退使用)
 *
 * @param {string|null} contentDisposition - Content-Disposition header值
 * @param {string} fallbackName - 解析失败时的默认文件名
 * @returns {string} 解码后的文件名
 */
export function parseContentDispositionFilename(contentDisposition, fallbackName = 'download.pdf') {
  if (!contentDisposition) {
    return fallbackName;
  }

  // 优先匹配 filename*=UTF-8''... (RFC 5987编码格式)
  const utf8Match = contentDisposition.match(
    /filename\*\s*=\s*(?:UTF-8|utf-8)''(.+?)(?:;|$)/i
  );
  if (utf8Match) {
    try {
      return decodeURIComponent(utf8Match[1].trim());
    } catch {
      // percent-decode失败, 回退到下面的普通格式
    }
  }

  // 回退: filename="..." 或 filename=... (无引号)
  const normalMatch = contentDisposition.match(
    /filename\s*=\s*(?:"([^"]+)"|([^;\s]+))/i
  );
  if (normalMatch) {
    return (normalMatch[1] || normalMatch[2]).trim();
  }

  return fallbackName;
}

// ============ Bug 2 修复: 流式下载避免内存溢出 ============

/**
 * 通过File System Access API将数据流直接写入磁盘
 * 内存占用仅为一个chunk大小(~64KB), 而非整个文件
 *
 * @param {Response} response - fetch Response对象(body为ReadableStream)
 * @param {string} filename - 保存的文件名
 * @param {Function} onProgress - 进度回调(percent, loaded, total)
 * @param {AbortSignal} signal - 中断信号
 * @param {number} total - 预期文件总大小
 * @returns {Promise<void>}
 */
async function streamToDisk(response, filename, onProgress, signal, total) {
  const writableHandle = await window.showSaveFilePicker({
    suggestedName: filename,
    types: [{
      description: 'PDF文件',
      accept: { 'application/pdf': ['.pdf'] },
    }],
  });

  const writable = await writableHandle.createWritable();

  try {
    const reader = response.body.getReader();
    let receivedLength = 0;

    while (true) {
      const { done, value } = await Promise.race([
        reader.read(),
        new Promise((_, reject) => {
          if (signal.aborted) {
            reject(new DOMException('下载已取消', 'AbortError'));
          }
          signal.addEventListener('abort', () => {
            reject(new DOMException('下载已取消', 'AbortError'));
          }, { once: true });
        }),
      ]);
      if (done) break;

      await writable.write(value);
      receivedLength += value.byteLength;

      if (onProgress && total > 0) {
        onProgress(Math.round((receivedLength / total) * 100), receivedLength, total);
      }
    }
  } finally {
    await writable.close();
  }
}

/**
 * 流式接收数据到内存, 最后组装为Blob触发下载
 * 比axios+Blob方式好在于: 逐chunk读取可以精确跟踪进度并检测网络中断
 * 注意: 仍然会将完整文件加载到内存, 仅在不支持File System Access API时使用
 *
 * @param {Response} response - fetch Response对象
 * @param {string} filename - 保存的文件名
 * @param {Function} onProgress - 进度回调
 * @param {AbortSignal} signal - 中断信号
 * @param {number} total - 预期文件总大小
 * @returns {Promise<void>}
 */
async function streamToBlob(response, filename, onProgress, signal, total) {
  const reader = response.body.getReader();
  const chunks = [];
  let receivedLength = 0;

  while (true) {
    // 将每次read与abort信号竞争, 防止网络中断时read()永远挂起
    const { done, value } = await Promise.race([
      reader.read(),
      new Promise((_, reject) => {
        if (signal.aborted) {
          reject(new DOMException('下载已取消', 'AbortError'));
        }
        signal.addEventListener('abort', () => {
          reject(new DOMException('下载已取消', 'AbortError'));
        }, { once: true });
      }),
    ]);
    if (done) break;

    chunks.push(value);
    receivedLength += value.byteLength;

    if (onProgress && total > 0) {
      onProgress(Math.round((receivedLength / total) * 100), receivedLength, total);
    }
  }

  const blob = new Blob(chunks, { type: DEFAULT_MIME_TYPE });
  const url = URL.createObjectURL(blob);
  triggerBrowserDownload(url, filename);
  // 延迟释放ObjectURL, 确保浏览器已开始下载
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

/**
 * 创建隐藏的<a>元素触发浏览器下载
 */
function triggerBrowserDownload(url, filename) {
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// ============ Bug 3 修复: 网络中断检测与错误处理 ============

/**
 * 创建带有chunk超时检测的AbortController
 *
 * 如果在指定时间内没有收到任何数据, 自动abort并标记为超时
 * 这解决了"网络断开但连接未关闭"导致的进度条卡死问题
 *
 * @param {number} timeoutMs - 超时毫秒数
 * @returns {{ controller: AbortController, onChunk: Function, cleanup: Function }}
 */
function createChunkTimeoutController(timeoutMs) {
  const controller = new AbortController();
  let timerId = null;
  let timedOut = false;

  function resetTimer() {
    if (timerId) clearTimeout(timerId);
    timerId = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
  }

  function onChunk() {
    resetTimer();
  }

  function cleanup() {
    if (timerId) {
      clearTimeout(timerId);
      timerId = null;
    }
  }

  // 启动初始计时器
  resetTimer();

  return { controller, onChunk, cleanup, isTimedOut: () => timedOut };
}

// ============ 主下载函数 ============

/**
 * 下载报告PDF文件
 *
 * @param {Object} options
 * @param {string} options.url - 下载接口URL
 * @param {string} [options.filename] - 默认文件名(当header中无法解析时使用)
 * @param {Object} [options.headers] - 额外请求头(如Authorization)
 * @param {Function} [options.onProgress] - 进度回调: (percent: number, loaded: number, total: number) => void
 * @param {Function} [options.onError] - 错误回调: (error: { code: string, message: string }) => void
 * @param {Function} [options.onComplete] - 完成回调: (filename: string) => void
 * @param {boolean} [options.useSaveAs] - 是否弹出"另存为"对话框(需File System Access API), 默认false
 * @param {number} [options.chunkTimeoutMs] - chunk间隔超时(毫秒), 默认30000
 * @param {AbortSignal} [options.externalSignal] - 外部取消信号
 * @returns {Promise<{ success: boolean, filename?: string, error?: Object }>}
 */
export async function downloadReport(options) {
  const {
    url,
    filename: fallbackFilename = 'report.pdf',
    headers = {},
    onProgress = null,
    onError = null,
    onComplete = null,
    useSaveAs = false,
    chunkTimeoutMs = DEFAULT_CHUNK_TIMEOUT_MS,
    externalSignal = null,
  } = options;

  if (!url) {
    const error = { code: 'INVALID_PARAMS', message: '下载链接不能为空' };
    onError?.(error);
    return { success: false, error };
  }

  // 创建内部AbortController用于超时, 并监听外部信号
  const timeoutCtrl = createChunkTimeoutController(chunkTimeoutMs);

  // 如果有外部信号(如用户点击"取消下载"), 联动到内部controller
  if (externalSignal) {
    if (externalSignal.aborted) {
      timeoutCtrl.controller.abort();
    } else {
      externalSignal.addEventListener('abort', () => {
        timeoutCtrl.controller.abort();
      }, { once: true });
    }
  }

  try {
    const response = await fetch(url, {
      headers: { ...headers },
      signal: timeoutCtrl.controller.signal,
    });

    if (!response.ok) {
      const error = {
        code: 'HTTP_ERROR',
        message: `服务器返回错误: ${response.status} ${response.statusText}`,
        status: response.status,
      };
      timeoutCtrl.cleanup();
      onError?.(error);
      return { success: false, error };
    }

    // 解析文件名: 优先从Content-Disposition的RFC 5987编码字段中提取
    const contentDisposition = response.headers.get('content-disposition');
    const filename = parseContentDispositionFilename(contentDisposition, fallbackFilename);

    // 获取文件总大小
    const contentLength = response.headers.get('content-length');
    const total = contentLength ? parseInt(contentLength, 10) : 0;

    // 检查response body是否支持流式读取
    if (!response.body) {
      // 回退: 一次性读取 (不支持流式的环境)
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      triggerBrowserDownload(blobUrl, filename);
      setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);
      timeoutCtrl.cleanup();
      onComplete?.(filename);
      return { success: true, filename };
    }

    // 包装reader以集成超时检测: 每次收到chunk重置计时器
    const originalReader = response.body.getReader();
    const wrappedReader = {
      read: async () => {
        const result = await originalReader.read();
        if (!result.done) {
          timeoutCtrl.onChunk();
        }
        return result;
      },
      cancel: () => originalReader.cancel(),
    };

    // 构造代理response body, 让下游函数使用wrappedReader
    const streamBody = new ReadableStream({
      async start(controller) {
        try {
          while (true) {
            const { done, value } = await wrappedReader.read();
            if (done) {
              controller.close();
              break;
            }
            controller.enqueue(value);
          }
        } catch (err) {
          controller.error(err);
        }
      },
    });

    // 构建代理Response用于流式读取
    const proxiedResponse = { body: streamBody };

    // 选择下载策略
    if (useSaveAs && window.showSaveFilePicker) {
      // 策略A: File System Access API - 流式写入磁盘, 内存占用极小
      await streamToDisk(proxiedResponse, filename, onProgress, timeoutCtrl.controller.signal, total);
    } else {
      // 策略B: 流式接收 + Blob组装 (回退方案)
      await streamToBlob(proxiedResponse, filename, onProgress, timeoutCtrl.controller.signal, total);
    }

    timeoutCtrl.cleanup();
    onComplete?.(filename);
    return { success: true, filename };

  } catch (err) {
    timeoutCtrl.cleanup();

    let error;
    if (err.name === 'AbortError') {
      if (timeoutCtrl.isTimedOut()) {
        error = {
          code: 'TIMEOUT',
          message: '下载超时: 长时间未收到数据, 请检查网络连接后重试',
        };
      } else {
        error = {
          code: 'CANCELLED',
          message: '下载已取消',
        };
      }
    } else if (err.name === 'TypeError' && err.message.includes('fetch')) {
      error = {
        code: 'NETWORK_ERROR',
        message: '网络连接失败, 请检查网络后重试',
      };
    } else {
      error = {
        code: 'UNKNOWN',
        message: `下载失败: ${err.message || '未知错误'}`,
      };
    }

    onError?.(error);
    return { success: false, error };
  }
}
